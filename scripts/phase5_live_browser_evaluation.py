from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import threading
import time

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("SATELL_E2E_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
USERNAME = os.environ["SATELL_E2E_USERNAME"]
PASSWORD = os.environ["SATELL_E2E_PASSWORD"]
DATASET = ROOT / "docs" / "phase4_evaluation_questions.json"
RESULT_PATH = ROOT / "docs" / "phase5" / "live_evaluation_results.json"
GPU_QUERY = r"C:\Windows\System32\nvidia-smi.exe"


def sample_resources(stop: threading.Event, samples: list[dict[str, object]]) -> None:
    while not stop.is_set():
        sample: dict[str, object] = {"timestamp_monotonic": round(time.monotonic(), 3)}
        if Path(GPU_QUERY).exists():
            try:
                output = subprocess.check_output(
                    [GPU_QUERY, "--query-gpu=utilization.gpu,memory.used,memory.total",
                     "--format=csv,noheader,nounits"], text=True, timeout=3,
                    stderr=subprocess.DEVNULL,
                ).strip().splitlines()
                if output:
                    values = [int(part.strip()) for part in output[0].split(",")]
                    sample["gpu_utilization_percent"] = values[0]
                    sample["gpu_memory_used_mib"] = values[1]
                    sample["gpu_memory_total_mib"] = values[2]
            except (OSError, subprocess.SubprocessError, ValueError):
                pass
        try:
            output = subprocess.check_output(
                ["docker", "stats", "--no-stream", "--format", "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}"],
                text=True, timeout=4, stderr=subprocess.DEVNULL,
            )
            sample["docker"] = [line.strip() for line in output.splitlines() if line.strip()]
        except (OSError, subprocess.SubprocessError):
            pass
        samples.append(sample)
        stop.wait(2)


def main() -> None:
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    queries = dataset["queries"][:20]
    results: dict[str, object] = {
        "dataset_id": dataset["dataset_id"],
        "query_count": len(queries),
        "evaluation_path": "browser -> Django -> authenticated FastAPI -> Qdrant/Ollama -> PostgreSQL",
        "responses_recorded": False,
        "queries": [],
        "resource_samples": [],
    }
    stop = threading.Event()
    sampler = threading.Thread(target=sample_resources, args=(stop, results["resource_samples"]), daemon=True)
    sampler.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True,
                                                args=["--disable-background-networking"])
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.set_default_timeout(20_000)
            page.goto(f"{BASE_URL}/accounts/login/", wait_until="domcontentloaded")
            page.get_by_label("Username").fill(USERNAME)
            page.get_by_label("Password").fill(PASSWORD)
            page.get_by_role("button", name="Sign in").click()
            expect(page.get_by_role("heading", name="What would you like to explore?")).to_be_visible()
            page.get_by_label("Conversation name").fill("Phase 5 20-query live evaluation")
            page.get_by_role("button", name="Start a chat").click()
            expect(page.get_by_label("Your message")).to_be_visible()
            for query in queries:
                page.get_by_label("Your message").fill(query["question"])
                start = time.perf_counter()
                with page.expect_navigation(wait_until="domcontentloaded", timeout=180_000):
                    page.get_by_role("button", name="Send").click()
                card = page.locator(".message-card.message-assistant").last
                expect(card).not_to_have_attribute("data-message-status", "pending", timeout=20_000)
                verification = card.locator(".verification-note").inner_text() if card.locator(".verification-note").count() else "not_reported"
                outcome = "verified" if "checked against" in verification.lower() else (
                    "partially_verified" if "partial evidence" in verification.lower() else (
                        "abstained" if "not enough authorized evidence" in verification.lower() else (
                            "failed" if "could not be verified" in verification.lower() else "not_reported")))
                citations = card.locator(".citation-card")
                results["queries"].append({
                    "query_id": query["query_id"],
                    "category": query["expected_sources"],
                    "expected_behavior": query["expected_behavior"],
                    "verification_outcome": outcome,
                    "citation_count": citations.count(),
                    "citation_outcome": "present" if citations.count() else "none",
                    "safe_abstention": outcome == "abstained",
                    "browser_elapsed_ms": round((time.perf_counter() - start) * 1000, 3),
                    "message_status": card.get_attribute("data-message-status"),
                    "persisted_in_rendered_history": card.is_visible(),
                })
                RESULT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            page.get_by_role("button", name="Sign out").click()
            browser.close()
    finally:
        stop.set()
        sampler.join(timeout=5)
    RESULT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "query_count": len(results["queries"]),
        "verification_outcomes": {status: sum(q["verification_outcome"] == status for q in results["queries"])
                                   for status in sorted({q["verification_outcome"] for q in results["queries"]})},
        "queries_with_citations": sum(q["citation_count"] > 0 for q in results["queries"]),
        "resource_sample_count": len(results["resource_samples"]),
        "result_file": str(RESULT_PATH),
    }, indent=2))


if __name__ == "__main__":
    main()
