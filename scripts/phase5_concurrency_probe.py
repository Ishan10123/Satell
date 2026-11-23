"""Measure bounded 2- and 3-request browser workloads through Django/real RAG."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time

from playwright.sync_api import expect, sync_playwright


BASE_URL = os.environ.get("SATELL_E2E_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
USERNAME = os.environ["SATELL_E2E_USERNAME"]
PASSWORD = os.environ["SATELL_E2E_PASSWORD"]


def main() -> int:
    results: dict[str, object] = {
        "evaluation_path": "browser -> Django -> authenticated FastAPI -> Qdrant/Ollama -> PostgreSQL",
        "gunicorn_workers": 1,
        "workloads": {},
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True,
                                             args=["--disable-background-networking"])
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(200_000)
        page.goto(f"{BASE_URL}/accounts/login/", wait_until="domcontentloaded")
        page.get_by_label("Username").fill(USERNAME)
        page.get_by_label("Password").fill(PASSWORD)
        page.get_by_role("button", name="Sign in").click()
        expect(page.get_by_role("heading", name="What would you like to explore?")).to_be_visible()

        for count in (2, 3):
            requests = []
            for index in range(count):
                page.get_by_label("Conversation name").fill(f"Temporary phase 5 concurrency {count}-{index + 1}")
                page.get_by_role("button", name="Start a chat").click()
                expect(page.get_by_label("Your message")).to_be_visible()
                requests.append(page.evaluate("""() => ({
                    url: document.querySelector('[data-message-form]').action,
                    csrf: document.querySelector('[data-message-form] input[name=csrfmiddlewaretoken]').value
                })"""))
                page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")

            prompts = [
                "State one concise fact: What is a dictionary in Python?",
                "State one concise fact: What is a path parameter in FastAPI?",
                "State one concise fact: What is a Docker Compose service?",
            ][:count]
            for request, prompt in zip(requests, prompts, strict=True):
                request["content"] = prompt
            started = time.perf_counter()
            outcomes = page.evaluate("""async (items) => Promise.all(items.map(async item => {
                const start = performance.now();
                const body = new URLSearchParams({
                    csrfmiddlewaretoken: item.csrf,
                    content: item.content
                });
                const response = await fetch(item.url, {
                    method: 'POST', credentials: 'same-origin',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body
                });
                const html = await response.text();
                return {
                    status: response.status,
                    elapsed_ms: Math.round(performance.now() - start),
                    completed: /message-card message-assistant[^>]*data-message-status="complete"/.test(html),
                    synthetic: html.includes('Synthetic test response; not a real RAG result.')
                };
            }))""", requests)
            wall_ms = round((time.perf_counter() - started) * 1000, 2)
            valid = len(outcomes) == count and all(item["status"] == 200 for item in outcomes)
            results["workloads"][str(count)] = {
                "request_count": count,
                "status_codes": [item["status"] for item in outcomes],
                "request_elapsed_ms": [item["elapsed_ms"] for item in outcomes],
                "wall_elapsed_ms": wall_ms,
                "assistant_messages_completed": [item["completed"] for item in outcomes],
                "synthetic_response_detected": any(item["synthetic"] for item in outcomes),
                "persisted_via_redirected_response": valid and all(item["completed"] for item in outcomes),
                "inference_concurrency": "serialized by one synchronous Gunicorn worker",
            }
            if not valid or not all(item["completed"] for item in outcomes) or any(item["synthetic"] for item in outcomes):
                raise RuntimeError("A controlled concurrency request did not complete successfully.")
            page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")

        context.close()
        browser.close()
    path = Path(__file__).resolve().parents[1] / "docs" / "phase5_closure" / "concurrency_probe_results.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
