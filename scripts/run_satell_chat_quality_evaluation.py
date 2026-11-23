"""Run the 30-question local RAG evaluation through the actual Django website."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("SATELL_E2E_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
USERNAME = os.environ["SATELL_E2E_USERNAME"]
PASSWORD = os.environ["SATELL_E2E_PASSWORD"]
DATASET = ROOT / "evaluation" / "satell_chat_quality_questions_20261119.jsonl"
RESULT = ROOT / "evaluation" / "results" / "satell_chat_quality_live_20261119.json"
RESULT = Path(os.environ.get("SATELL_EVAL_RESULT_PATH", str(RESULT)))


def outcome(card) -> str:
    if card.locator(".synthetic-notice").count():
        return "synthetic_rejected"
    if card.locator(".verification-partial").count():
        return "partially_verified"
    note = card.locator(".verification-note").inner_text().lower() if card.locator(".verification-note").count() else ""
    if "checked against" in note:
        return "verified"
    if "not enough authorized evidence" in note:
        return "abstained"
    if "could not be verified" in note:
        return "failed"
    return "verification_status_not_rendered"


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * fraction + 0.5)))
    return round(ordered[index], 2)


def main() -> None:
    queries = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    selected_ids = {item.strip() for item in os.environ.get("SATELL_EVAL_IDS", "").split(",") if item.strip()}
    if selected_ids:
        queries = [query for query in queries if query["question_id"] in selected_ids]
    if len(queries) < 30 and not selected_ids:
        raise RuntimeError(f"Evaluation dataset has only {len(queries)} questions.")
    results: dict[str, object] = {
        "dataset": DATASET.relative_to(ROOT).as_posix(),
        "dataset_expectation_quality": "heuristic expectations; none were represented as human-verified ground truth",
        "evaluation_path": "real Chrome browser -> Django session/CSRF/views -> authenticated FastAPI -> existing authorization and Qdrant/Ollama -> PostgreSQL persistence -> browser render",
        "mock_responses_allowed": False,
        "query_count": len(queries),
        "queries": [],
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True, args=["--disable-background-networking"])
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.set_default_timeout(20_000)
        page.goto(f"{BASE_URL}/accounts/login/", wait_until="domcontentloaded")
        page.get_by_label("Username").fill(USERNAME)
        page.locator("#id_password").fill(PASSWORD)
        page.get_by_role("button", name="Sign in").click()
        expect(page.get_by_role("heading", name="What would you like to explore?")).to_be_visible()
        for index, query in enumerate(queries, start=1):
            page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
            expect(page.get_by_role("heading", name="What would you like to explore?")).to_be_visible()
            page.get_by_role("button", name="New conversation").click()
            expect(page.get_by_label("Your message")).to_be_visible()
            page.get_by_label("Your message").fill(query["query"])
            started = time.perf_counter()
            with page.expect_navigation(wait_until="domcontentloaded", timeout=180_000):
                page.get_by_role("button", name="Send").click()
            elapsed = round((time.perf_counter() - started) * 1000, 2)
            card = page.locator(".message-card.message-assistant").last
            expect(card).to_be_visible()
            status = card.get_attribute("data-message-status") or "missing"
            if status == "pending":
                expect(card).not_to_have_attribute("data-message-status", "pending", timeout=30_000)
                status = card.get_attribute("data-message-status") or "missing"
            citations = card.locator(".citation-card")
            citation_labels = [" ".join(label.split()) for label in citations.locator("strong").all_inner_texts()]
            verification_outcome = outcome(card)
            if verification_outcome == "synthetic_rejected":
                raise AssertionError(f"Question {query['question_id']} received a synthetic response.")
            answer_node = card.locator("[data-markdown-content]") if card.locator("[data-markdown-content]").count() else card.locator(".message-content")
            answer_text = answer_node.inner_text()
            results["queries"].append({
                "question_id": query["question_id"],
                "expected_topic": query["expected_topic"],
                "expectation_basis": query["expectation_basis"],
                "expected_abstention": query["abstention_expected"],
                "answer_status": status,
                "verification_outcome": verification_outcome,
                "citation_count": citations.count(),
                "citation_labels": citation_labels,
                "citation_present": citations.count() > 0,
                "browser_end_to_end_ms": elapsed,
                "answer_character_count": len(answer_text),
                "question_answer_relevance": "requires human review; not inferred from fluency or citation presence",
                "evidence_support_assessment": "verifier outcome recorded; citation/evidence semantic audit requires human review",
                "format_assessment": "requires human review",
                "persisted_in_django_page": True,
                "synthetic": False,
            })
            RESULT.parent.mkdir(parents=True, exist_ok=True)
            RESULT.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"{index:02d}/{len(queries)} {query['question_id']} {verification_outcome} citations={citations.count()} latency_ms={elapsed}", flush=True)
        page.get_by_role("button", name="Sign out").click()
        browser.close()
    times = [row["browser_end_to_end_ms"] for row in results["queries"]]
    outcomes = {name: sum(row["verification_outcome"] == name for row in results["queries"])
                for name in sorted({row["verification_outcome"] for row in results["queries"]})}
    results["summary"] = {
        "outcomes": outcomes,
        "queries_with_citations": sum(row["citation_present"] for row in results["queries"]),
        "safe_abstentions_expected": sum(row["expected_abstention"] for row in results["queries"]),
        "safe_abstentions_observed": sum(row["verification_outcome"] == "abstained" for row in results["queries"]),
        "end_to_end_ms": {"min": round(min(times), 2), "p50": percentile(times, 0.5), "p95": percentile(times, 0.95), "max": round(max(times), 2)},
        "human_quality_judgments_completed": 0,
        "limitation": "Retrieval relevance, evidence-to-claim semantic support, answer completeness and format suitability were not automatically scored as correctness; expectations remain heuristic pending human review.",
    }
    RESULT.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result_file": str(RESULT), "summary": results["summary"]}, indent=2))


if __name__ == "__main__":
    main()
