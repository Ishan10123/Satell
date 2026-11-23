"""Verify Satell account recovery and conversation UX in a real browser."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import time

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("SATELL_E2E_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
USERNAME = os.environ["SATELL_E2E_USERNAME"]
PASSWORD = os.environ["SATELL_E2E_PASSWORD"]
RESULT = ROOT / "docs" / "academic_project" / "evidence" / "chat_experience_browser_results.json"


def main() -> None:
    result: dict[str, object] = {
        "browser": "Google Chrome controlled by Playwright",
        "base_url": BASE_URL,
        "scenarios": {},
        "live_rag": {},
        "limitations": ["SMTP delivery is not configured in this local deployment; backend email behavior is covered by Django email tests."],
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True, args=["--disable-background-networking"])
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        context.grant_permissions(["clipboard-read", "clipboard-write"], origin=BASE_URL)
        page = context.new_page()
        page.set_default_timeout(20_000)
        page_errors: list[str] = []
        share_requests: list[dict[str, object]] = []
        def record_share_request(request):
            if "/share" not in request.url:
                return
            share_requests.append({
                "method": request.method,
                "path": request.url.split(BASE_URL, 1)[-1].split("?", 1)[0],
                "origin_header_present": bool(request.headers.get("origin")),
                "referer_host": request.headers.get("referer", "").split("/", 3)[2] if request.headers.get("referer") else "",
                "cookie_names": sorted(part.strip().split("=", 1)[0] for part in request.headers.get("cookie", "").split(";") if "=" in part),
                "csrf_form_field_present": "csrfmiddlewaretoken=" in (request.post_data or ""),
            })

        def record_share_response(response):
            if share_requests and response.url.startswith(BASE_URL) and "/share" in response.url:
                share_requests[-1]["status"] = response.status

        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.on("dialog", lambda dialog: dialog.accept())
        page.on("request", record_share_request)
        page.on("response", record_share_response)

        page.goto(f"{BASE_URL}/accounts/login/", wait_until="domcontentloaded")
        expect(page).to_have_title(re.compile("satell", re.I))
        password = page.locator("#id_password")
        password.fill("temporary-browser-check")
        toggle = page.get_by_role("button", name="Show password")
        toggle.click()
        if password.get_attribute("type") != "text" or password.input_value() != "temporary-browser-check":
            raise AssertionError("Password visibility toggle did not reveal and preserve the entered value.")
        page.get_by_role("button", name="Hide password").click()
        if password.get_attribute("type") != "password" or password.input_value() != "temporary-browser-check":
            raise AssertionError("Password visibility toggle did not hide and preserve the entered value.")
        result["scenarios"]["password_visibility"] = "show/hide verified; value preserved"

        page.get_by_role("link", name="Forgot password?").click()
        expect(page.get_by_role("heading", name="Reset your password")).to_be_visible()
        page.get_by_label("Username or email").fill("unknown-browser-account@example.invalid")
        page.get_by_role("button", name="Send reset instructions").click()
        expect(page.get_by_text("If an active account matches that information and has a registered email address, reset instructions have been sent there.")).to_be_visible()
        result["scenarios"]["forgot_password_enumeration_safe_ui"] = "generic confirmation verified for unknown account"

        page.goto(f"{BASE_URL}/accounts/login/", wait_until="domcontentloaded")
        page.get_by_label("Username").fill(USERNAME)
        password = page.locator("#id_password")
        password.fill("definitely-not-the-correct-password")
        page.get_by_role("button", name="Sign in").click()
        expect(page.get_by_text("Please enter a correct username and password.")).to_be_visible()
        password.fill(PASSWORD)
        page.get_by_role("button", name="Sign in").click()
        expect(page.get_by_role("heading", name="What would you like to explore?")).to_be_visible()
        result["scenarios"]["invalid_and_valid_login"] = "invalid credentials rejected; temporary test account authenticated"
        result["scenarios"]["browser_secret_absent"] = all(secret not in page.content() for secret in ("RAG_API_TOKEN", "POSTGRES_PASSWORD"))

        first_question = "In FastAPI, what is a path parameter? Give one concise fact from its documentation."
        page.get_by_label("Conversation name").fill("")
        page.get_by_role("button", name=re.compile("Start a chat")).click()
        expect(page.get_by_label("Your message")).to_be_visible()
        page.get_by_label("Your message").fill(first_question)
        started = time.perf_counter()
        with page.expect_navigation(wait_until="domcontentloaded", timeout=180_000):
            page.get_by_role("button", name="Send").click()
        assistant = page.locator(".message-card.message-assistant").last
        expect(assistant).to_be_visible()
        expect(assistant).not_to_have_attribute("data-message-status", "pending")
        expect(assistant.locator("[data-markdown-content]")).to_be_visible()
        expect(page.locator(".message-card.message-user").last).to_be_visible()
        expect(assistant.locator(".message-meta strong")).to_have_text("Satell")
        expect(page.locator(".message-card.message-user .message-meta strong").last).to_have_text("You")
        if page.get_by_text("Synthetic test response; not a real RAG result.").count():
            raise AssertionError("Synthetic response appeared in the real application workflow.")
        citations = assistant.locator(".citation-card").count()
        verification = assistant.locator(".verification-note").inner_text() if assistant.locator(".verification-note").count() else "unreported"
        citation_labels = assistant.locator(".citation-card strong").all_inner_texts()
        if any(re.search(r"\{\s*#", label) for label in citation_labels):
            raise AssertionError(f"Citation heading anchor leaked into the browser label: {citation_labels}")
        if not citations and "not enough authorized evidence" not in verification.lower():
            raise AssertionError("Live query returned neither citations nor an explicit safe-abstention state.")
        title = page.locator(".chat-heading h1").inner_text()
        if title == "New conversation" or len(title) > 70:
            raise AssertionError(f"First question did not generate a reasonable title: {title!r}")
        if title != "FastAPI Path Parameter":
            raise AssertionError(f"Title summarizes too much of the user question: {title!r}")
        if assistant.locator(".message-content li").count():
            raise AssertionError("A single-fact question was rendered as a list after verified answer formatting.")
        result["live_rag"]["first_query"] = {
            "question": first_question,
            "browser_elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "citation_cards": citations,
            "verification_ui": verification,
            "answer_paragraph_count": assistant.locator(".message-content p").count(),
            "answer_list_item_count": assistant.locator(".message-content li").count(),
            "citation_labels": citation_labels,
            "automatic_title": title,
            "synthetic": False,
        }
        result["scenarios"]["user_right_satell_left"] = {
            "user_card_class": "message-user",
            "assistant_card_class": "message-assistant",
            "brand_label": "Satell",
        }
        copy_button = assistant.get_by_role("button", name="Copy Satell response")
        copy_button.click()
        expect(copy_button).to_have_text("Copied", timeout=3000)
        if not page.evaluate("() => navigator.clipboard.readText()"):
            raise AssertionError("Copy response did not write text to the clipboard.")
        result["scenarios"]["copy_response"] = "visible Satell answer copied"
        if citations:
            copy_citation = assistant.locator("[data-copy-citation]").first
            copy_citation.click()
            expect(copy_citation).to_have_text("Copied", timeout=3000)
            citation_clipboard = page.evaluate("() => navigator.clipboard.readText()")
            if "S" not in citation_clipboard or "internal-document" in citation_clipboard:
                raise AssertionError("Copied citation is missing its public reference or includes private identifiers.")
            result["scenarios"]["copy_citation"] = "citation label and safe source reference copied without internal IDs"

        page.get_by_label("Your message").fill("What does FastAPI response_model do?")
        with page.expect_navigation(wait_until="domcontentloaded", timeout=180_000):
            page.get_by_role("button", name="Send").click()
        expect(page.locator(".message-card.message-user")).to_have_count(2)
        expect(page.locator(".message-card.message-assistant")).to_have_count(2)
        expect(page.locator(".chat-heading h1")).to_have_text(title)
        result["scenarios"]["follow_up_and_title_stability"] = "second question/answer persisted; generated title remained stable"

        page.locator(".chat-heading .conversation-menu summary").click()
        page.locator(".chat-heading .conversation-menu").get_by_role("button", name="Rename").click()
        dialog = page.locator("[data-rename-dialog]")
        expect(dialog).to_be_visible()
        dialog.locator("#rename-title").fill("FastAPI path parameters")
        with page.expect_navigation(wait_until="domcontentloaded"):
            dialog.get_by_role("button", name="Save title").click()
        expect(page.locator(".chat-heading h1")).to_have_text("FastAPI path parameters")
        result["scenarios"]["rename"] = "saved and survived response refresh"

        menu = page.locator(".chat-heading .conversation-menu")
        menu.locator("summary").click()
        for fmt, suffix in (("md", ".md"), ("txt", ".txt"), ("json", ".json")):
            link = menu.get_by_role("link", name={"md": "Download Markdown", "txt": "Download text", "json": "Download JSON"}[fmt])
            download_url = link.get_attribute("href")
            response = context.request.get(BASE_URL + download_url)
            if not response.ok or not response.headers.get("content-disposition", "").endswith(suffix + '"'):
                raise AssertionError(f"{fmt} export did not return a downloadable file.")
            content = response.body().decode("utf-8")
            if "RAG_API_TOKEN" in content or "diagnostics" in content or "private-request" in content:
                raise AssertionError(f"{fmt} export exposed private metadata.")
            if fmt == "json":
                json.loads(content)
        result["scenarios"]["exports"] = "Markdown, plain text, JSON responses verified; JSON parses; private diagnostics absent"

        page.locator("#share-expiration").select_option("1")
        with page.expect_navigation(wait_until="domcontentloaded"):
            page.get_by_role("button", name="Create share link").click()
        share_input = page.locator("[data-share-link]")
        expect(share_input).to_be_visible()
        share_url = share_input.input_value()
        token = share_url.rstrip("/").rsplit("/", 1)[-1]
        if len(token) < 32:
            raise AssertionError("Share token is shorter than the expected random capability token.")
        # Open the capability link in a fresh browser context to prove it does not
        # depend on the owner's authenticated session cookie.
        recipient_context = browser.new_context(viewport={"width": 1280, "height": 900})
        shared_page = recipient_context.new_page()
        shared_page.goto(share_url, wait_until="domcontentloaded")
        expect(shared_page.get_by_text("SHARED READ-ONLY CONVERSATION")).to_be_visible()
        expect(shared_page.locator("[data-message-form]")).to_have_count(0)
        expect(shared_page.locator("meta[name=robots]")).to_have_attribute("content", "noindex,nofollow,noarchive")
        recipient_context.close()
        page.get_by_role("button", name="Revoke link").click()
        if page.locator("h1").count() and page.locator("h1").inner_text() == "Forbidden (403)":
            raise AssertionError(f"Share revocation failed CSRF checks; safe request metadata: {share_requests}")
        expect(page.get_by_text("Conversation share link revoked.")).to_be_visible()
        revoked = context.request.get(share_url)
        if revoked.status != 404:
            raise AssertionError(f"Revoked share URL returned {revoked.status}, expected 404.")
        if not any(request.get("path", "").endswith("/share/revoke/") and request.get("status") == 302
                   for request in share_requests):
            raise AssertionError(f"Share revocation did not complete normally; safe request metadata: {share_requests}")
        result["scenarios"]["share_and_revoke"] = "read-only link opened; noindex present; revoked link rejected"

        menu = page.locator(".chat-heading .conversation-menu")
        menu.locator("summary").click()
        menu.get_by_role("button", name="Lock").click()
        expect(page.get_by_text("This conversation is locked and read-only.")).to_be_visible()
        expect(page.locator("[data-message-form]")).to_have_count(0)
        page.get_by_role("button", name="Unlock conversation").click()
        expect(page.locator("[data-message-form]")).to_be_visible()
        result["scenarios"]["lock_unlock"] = "locked state removes composer; owner unlock restores it"

        page.locator(".sidebar .new-chat").click()
        expect(page.get_by_label("Your message")).to_be_visible()
        expect(page.locator(".chat-heading h1")).to_have_text("New conversation")
        delete_menu = page.locator(".chat-heading .conversation-menu")
        delete_menu.locator("summary").click()
        with page.expect_navigation(wait_until="domcontentloaded"):
            delete_menu.get_by_role("button", name="Delete").click()
        expect(page.get_by_role("heading", name="What would you like to explore?")).to_be_visible()
        result["scenarios"]["delete_confirmation"] = "new empty conversation deleted after confirmation"

        page.set_viewport_size({"width": 390, "height": 844})
        if page.evaluate("document.documentElement.scrollWidth > window.innerWidth"):
            raise AssertionError("Mobile viewport has horizontal overflow.")
        page.locator(".mobile-header [data-theme-toggle]").click()
        if page.locator("html").get_attribute("data-theme") not in {"light", "dark"}:
            raise AssertionError("Theme control did not leave the document in a supported theme.")
        result["scenarios"]["mobile_and_theme"] = "390px viewport has no horizontal overflow; theme control active"

        page.set_viewport_size({"width": 1440, "height": 1000})
        page.get_by_role("button", name="Sign out").click()
        expect(page.get_by_role("heading", name="Welcome back")).to_be_visible()
        page.goto(f"{BASE_URL}/accounts/login/", wait_until="domcontentloaded")
        page.get_by_label("Username").fill(USERNAME)
        page.locator("#id_password").fill(PASSWORD)
        page.get_by_role("button", name="Sign in").click()
        expect(page.locator(".history-main").filter(has_text="FastAPI path parameters")).to_be_visible()
        result["scenarios"]["logout_relogin_persistence"] = "conversation title remains in authenticated history"
        result["page_errors"] = page_errors
        if page_errors:
            raise AssertionError("Browser reported JavaScript page errors.")
        context.close()
        browser.close()

    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result_file": str(RESULT), "scenarios": result["scenarios"], "live_rag": result["live_rag"]}, indent=2))


if __name__ == "__main__":
    main()
