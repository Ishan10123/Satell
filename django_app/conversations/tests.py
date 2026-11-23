import re
from datetime import timedelta
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.test import RequestFactory, SimpleTestCase
from django.db import OperationalError
from django.utils import timezone
from django.core.management import call_command, CommandError
from django.urls import reverse
from pathlib import Path

from chat.views import message_create
from rag_client import MockRAGClient, RAGClientInputTooLarge
from rag_client import RAGClientTimeout

from .models import CitationSnapshot, Conversation, GenerationMetadata, Message


class DatabaseAvailabilityTests(SimpleTestCase):
    def test_operational_error_returns_generic_retryable_503_without_details(self):
        from config.middleware import DatabaseAvailabilityMiddleware

        response = DatabaseAvailabilityMiddleware(
            lambda _request: (_ for _ in ()).throw(OperationalError("private host and query detail"))
        )(RequestFactory().get("/"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "5")
        self.assertIn("temporarily unavailable", response.content.decode())
        self.assertNotIn("private host", response.content.decode())


class TrustedFounderMetadataTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="creator-questioner",
            password="Questioner-good-pass-981!")
        self.client.force_login(self.user)
        self.conversation = Conversation.objects.create(user=self.user)

    @patch("chat.views.get_rag_client")
    def test_creator_question_uses_trusted_metadata_without_calling_rag(self, get_client):
        response = self.client.post(reverse("conversations:message_create", args=(self.conversation.pk,)),
                                    {"content": "Who is the founder and creator of Satell?"})
        self.assertEqual(response.status_code, 302)
        get_client.assert_not_called()
        assistant = self.conversation.messages.get(role=Message.Role.ASSISTANT)
        self.assertEqual(assistant.status, Message.Status.COMPLETE)
        self.assertIn("Ishan Kaushik", assistant.content)
        self.assertIn("https://www.linkedin.com/in/ishankaushik/", assistant.content)
        self.assertEqual(assistant.citations.count(), 0)
        metadata = assistant.generation_metadata.get()
        self.assertEqual(metadata.verification_status, GenerationMetadata.VerificationStatus.TRUSTED_METADATA)
        self.assertEqual(metadata.retrieval_mode, "trusted_metadata")
        self.assertFalse(metadata.diagnostics["retrieval_performed"])

    @patch("chat.views.get_rag_client")
    def test_founder_links_question_returns_only_publicly_enabled_links(self, get_client):
        from accounts.models import CreatorProfile
        creator = CreatorProfile.objects.get(key="satell")
        creator.github_is_public = False
        creator.save(update_fields=("github_is_public", "updated_at"))
        self.client.post(reverse("conversations:message_create", args=(self.conversation.pk,)),
                         {"content": "Show the founder's LinkedIn profile"})
        get_client.assert_not_called()
        assistant = self.conversation.messages.get(role=Message.Role.ASSISTANT)
        self.assertIn("https://www.linkedin.com/in/ishankaushik/", assistant.content)
        self.assertNotIn("github.com", assistant.content)
        self.assertEqual(assistant.citations.count(), 0)

    @patch("chat.views.get_rag_client")
    def test_founder_background_uses_only_public_owner_supplied_fields(self, get_client):
        from accounts.models import CreatorProfile
        creator = CreatorProfile.objects.get(key="satell")
        creator.education_is_public = True
        creator.current_role_is_public = True
        creator.save(update_fields=("education_is_public", "current_role_is_public", "updated_at"))
        response = self.client.post(reverse("conversations:message_create", args=(self.conversation.pk,)),
                                    {"content": "What is the founder's education and current role?"})
        self.assertEqual(response.status_code, 302)
        get_client.assert_not_called()
        assistant = self.conversation.messages.get(role=Message.Role.ASSISTANT)
        self.assertIn("Rajasthan Technical University", assistant.content)
        self.assertIn("vTech Solution Inc.", assistant.content)
        self.assertIn("not been independently verified", assistant.content)
        self.assertEqual(assistant.citations.count(), 0)


class ConversationOwnershipTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="owner", password="good-password-981!")
        self.other = get_user_model().objects.create_user(username="other", password="good-password-982!")
        self.conversation = Conversation.objects.create(user=self.user, title="Private")

    def test_authentication_is_required(self):
        response = self.client.get(reverse("conversations:list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_login_authenticates_user(self):
        client = Client(enforce_csrf_checks=True)
        login_url = reverse("accounts:login")
        page = client.get(login_url)
        token_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode())
        self.assertIsNotNone(token_match)
        self.assertIn("csrftoken", client.cookies)
        response = client.post(login_url, {
            "username": "owner", "password": "good-password-981!",
            "csrfmiddlewaretoken": token_match.group(1),
        }, HTTP_ORIGIN="http://testserver")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(client.session.get("_auth_user_id"))

    def test_invalid_login_credentials_are_rejected(self):
        response = self.client.post(reverse("accounts:login"), {
            "username": "owner", "password": "incorrect-password",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.client.session.get("_auth_user_id"))
        self.assertContains(response, "Please enter a correct username and password")

    def test_logout_invalidates_session(self):
        self.client.force_login(self.user)
        self.assertTrue(self.client.session.get("_auth_user_id"))
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertIsNone(self.client.session.get("_auth_user_id"))
        protected = self.client.get(reverse("conversations:list"))
        self.assertEqual(protected.status_code, 302)
        self.assertIn(reverse("accounts:login"), protected.url)

    def test_login_page_renders_csrf_token_and_cookie(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.content.decode(), r'name="csrfmiddlewaretoken" value="[^"]+"')
        self.assertIn("csrftoken", client.cookies)
        self.assertTrue(client.cookies["csrftoken"]["httponly"])

    def test_login_rejects_untrusted_origin_even_with_valid_token(self):
        client = Client(enforce_csrf_checks=True)
        login_url = reverse("accounts:login")
        page = client.get(login_url)
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode()).group(1)
        response = client.post(login_url, {
            "username": "owner", "password": "good-password-981!",
            "csrfmiddlewaretoken": token,
        }, HTTP_ORIGIN="http://attacker.example")
        self.assertEqual(response.status_code, 403)

    def test_conversation_list_only_contains_owner_rows(self):
        Conversation.objects.create(user=self.other, title="Other private chat")
        self.client.force_login(self.user)
        response = self.client.get(reverse("conversations:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Private")
        self.assertNotContains(response, "Other private chat")

    def test_workspace_has_navigation_new_chat_and_confirmed_delete_controls(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("conversations:list"))
        self.assertContains(response, "New conversation")
        self.assertContains(response, "Recent conversations")
        self.assertContains(response, "data-confirm=")
        self.assertContains(response, "name=\"csrfmiddlewaretoken\"")
        self.assertNotContains(response, "Other private chat")
        self.assertContains(response, 'aria-haspopup="menu"')
        self.assertContains(response, 'aria-expanded="false"')
        self.assertContains(response, 'role="menu"')
        self.assertContains(response, 'data-dropdown-panel hidden')

    def test_create_conversation_uses_authenticated_owner_and_normalized_title(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("conversations:create"), {"title": "  My   research  "})
        created = Conversation.objects.get(user=self.user, title="My research")
        self.assertRedirects(response, reverse("conversations:detail", args=(created.pk,)))
        self.assertFalse(Conversation.objects.filter(user=self.other, title="My research").exists())

    @override_settings(RAG_ADAPTER="mock")
    def test_detail_renders_chat_composer_mock_disclosure_and_escaped_content(self):
        Message.objects.create(conversation=self.conversation, role=Message.Role.USER,
                               content="<script>alert('x')</script>")
        self.client.force_login(self.user)
        response = self.client.get(reverse("conversations:detail", args=(self.conversation.pk,)))
        self.assertContains(response, "Development mode")
        self.assertContains(response, "synthetic examples, not real RAG results")
        self.assertContains(response, "satell")
        self.assertContains(response, "SECURE RAG CHAT WORKSPACE")
        self.assertContains(response, 'maxlength="5000"')
        self.assertContains(response, "0 / 5,000")
        self.assertContains(response, "Shift + Enter for a new line")
        self.assertContains(response, reverse("conversations:message_create", args=(self.conversation.pk,)))
        self.assertContains(response, reverse("conversations:delete", args=(self.conversation.pk,)))
        self.assertContains(response, "data-message-form")
        self.assertContains(response, "data-send-label")
        self.assertContains(response, "name=\"csrfmiddlewaretoken\"")
        self.assertContains(response, "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert('x')</script>")
        self.assertContains(response, "is-active")

    def test_assistant_markdown_is_rendered_from_escaped_text_without_exposing_request_id(self):
        assistant = Message.objects.create(conversation=self.conversation, role=Message.Role.ASSISTANT,
            content="## Safe heading\n\n- **Fact** with `code` [S1]\n\n<script>bad()</script>")
        GenerationMetadata.objects.create(message=assistant, request_id="private-correlation-value",
            retrieval_mode="dense", verification_status=GenerationMetadata.VerificationStatus.VERIFIED)
        self.client.force_login(self.user)
        response = self.client.get(reverse("conversations:detail", args=(self.conversation.pk,)))
        self.assertContains(response, "data-markdown-content")
        self.assertContains(response, "data-copy-response")
        self.assertContains(response, "&lt;script&gt;bad()&lt;/script&gt;")
        self.assertNotContains(response, "private-correlation-value")
        script = Path(__file__).resolve().parents[1] / "chat" / "static" / "chat" / "app.js"
        source = script.read_text(encoding="utf-8")
        self.assertIn("container.replaceChildren(fragment)", source)
        self.assertIn("document.createTextNode", source)
        self.assertNotIn("innerHTML", source)

    def test_copy_controls_expose_only_answer_code_and_public_citation_reference(self):
        assistant = Message.objects.create(conversation=self.conversation, role=Message.Role.ASSISTANT,
            content='Example:\n```python\nprint("safe")\n```')
        CitationSnapshot.objects.create(message=assistant, citation_id="S1", source_id="internal-source",
            document_id="internal-document", chunk_id="internal-chunk", title="Public guide title",
            source_reference="https://docs.example.test/guide")
        self.client.force_login(self.user)
        response = self.client.get(reverse("conversations:detail", args=(self.conversation.pk,)))
        html = response.content.decode()
        self.assertContains(response, "data-copy-response")
        self.assertContains(response, "data-copy-citation")
        citation_value = re.search(r'data-copy-citation="([^"]+)"', html)
        self.assertIsNotNone(citation_value)
        self.assertIn("Public guide title", citation_value.group(1))
        self.assertIn("https://docs.example.test/guide", citation_value.group(1))
        self.assertNotIn("internal-source", citation_value.group(1))
        self.assertNotIn("internal-document", citation_value.group(1))
        self.assertNotIn("internal-chunk", citation_value.group(1))
        self.assertNotIn("internal-source", html)
        self.assertNotIn("internal-document", html)
        self.assertNotIn("internal-chunk", html)
        script = Path(__file__).resolve().parents[1] / "chat" / "static" / "chat" / "app.js"
        source = script.read_text(encoding="utf-8")
        self.assertIn('copy.querySelectorAll("[data-copy-code]")', source)
        self.assertIn('code.textContent = codeLines.join("\\n")', source)
        self.assertIn("document.execCommand(\"copy\")", source)

    def test_detail_paginates_long_message_history(self):
        Message.objects.bulk_create([
            Message(conversation=self.conversation, role=Message.Role.USER, content=f"Question {i}")
            for i in range(51)
        ])
        self.client.force_login(self.user)
        url = reverse("conversations:detail", args=(self.conversation.pk,))
        first_page = self.client.get(url)
        second_page = self.client.get(url, {"page": "2"})
        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(len(first_page.context["messages_list"]), 50)
        self.assertContains(first_page, "View older messages")
        self.assertEqual(len(second_page.context["messages_list"]), 1)

    def test_invalid_or_oversized_message_is_not_persisted(self):
        self.client.force_login(self.user)
        url = reverse("conversations:message_create", args=(self.conversation.pk,))
        response = self.client.post(url, {"content": " "})
        oversized = self.client.post(url, {"content": "x" * 5001})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(oversized.status_code, 302)
        self.assertEqual(self.conversation.messages.count(), 0)

    def test_exactly_5000_characters_reach_rag_client_without_truncation(self):
        from unittest.mock import patch
        self.client.force_login(self.user)
        prompt = "🙂" * 5000
        adapter = MockRAGClient()
        with patch.object(adapter, "query", wraps=adapter.query) as query:
            with patch("chat.views.get_rag_client", return_value=adapter):
                response = self.client.post(
                    reverse("conversations:message_create", args=(self.conversation.pk,)),
                    {"content": prompt},
                )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(query.call_args.args[0], prompt)
        self.assertEqual(self.conversation.messages.get(role=Message.Role.USER).content, prompt)

    def test_5001_character_message_is_rejected_without_persisting(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("conversations:message_create", args=(self.conversation.pk,)),
            {"content": "x" * 5001},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.conversation.messages.count(), 0)

    def test_composer_counter_uses_unicode_code_points_and_configured_limit(self):
        script = Path(__file__).resolve().parents[1] / "chat" / "static" / "chat" / "app.js"
        source = script.read_text(encoding="utf-8")
        self.assertIn("Array.from(input.value).length", source)
        self.assertIn("input.maxLength = maxChars * 2", source)
        self.assertIn("Keep your message within", source)
        self.assertIn('sendButton.setAttribute("aria-busy", "true")', source)
        self.assertIn('sendLabel.textContent = "Sending…"', source)

    def test_cross_user_read_update_and_delete_are_rejected(self):
        message = Message.objects.create(conversation=self.conversation, role=Message.Role.ASSISTANT,
            content="PRIVATE-HISTORY-MARKER", status=Message.Status.COMPLETE)
        CitationSnapshot.objects.create(message=message, citation_id="S1", source_id="private",
            document_id="private-document", chunk_id="private-chunk", title="PRIVATE-CITATION-MARKER")
        self.client.force_login(self.other)
        detail = reverse("conversations:detail", args=(self.conversation.pk,))
        delete = reverse("conversations:delete", args=(self.conversation.pk,))
        send = reverse("conversations:message_create", args=(self.conversation.pk,))
        self.assertEqual(self.client.get(detail).status_code, 404)
        response = self.client.get(detail)
        self.assertNotContains(response, "PRIVATE-HISTORY-MARKER", status_code=404)
        self.assertNotContains(response, "PRIVATE-CITATION-MARKER", status_code=404)
        self.assertEqual(self.client.post(delete).status_code, 404)
        self.assertEqual(self.client.post(send, {"content": "try access"}).status_code, 404)
        self.assertTrue(Conversation.objects.filter(pk=self.conversation.pk).exists())
        self.assertEqual(self.conversation.messages.count(), 1)

    def test_owner_can_delete_and_cascade_related_data(self):
        msg = Message.objects.create(conversation=self.conversation, role=Message.Role.ASSISTANT,
                                     content="synthetic", status=Message.Status.COMPLETE)
        CitationSnapshot.objects.create(message=msg, citation_id="S1", source_id="s",
            document_id="d", chunk_id="c", title="t")
        GenerationMetadata.objects.create(message=msg, request_id="rid", retrieval_mode="mock",
            verification_status=GenerationMetadata.VerificationStatus.SYNTHETIC)
        self.client.force_login(self.user)
        response = self.client.post(reverse("conversations:delete", args=(self.conversation.pk,)))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Conversation.objects.filter(pk=self.conversation.pk).exists())
        self.assertFalse(Message.objects.filter(pk=msg.pk).exists())
        self.assertEqual(CitationSnapshot.objects.count(), 0)
        self.assertEqual(GenerationMetadata.objects.count(), 0)

    def test_message_role_rejects_invalid_values(self):
        invalid = Message(conversation=self.conversation, role="system", content="forbidden")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                invalid.save()

    def test_message_persistence_citation_snapshot_and_mock_label(self):
        self.client.force_login(self.user)
        with override_settings(RAG_ADAPTER="mock", RAG_API_TOP_K=8):
            from unittest.mock import patch
            with patch("chat.views.get_rag_client", return_value=MockRAGClient()):
                response = self.client.post(
                    reverse("conversations:message_create", args=(self.conversation.pk,)),
                    {"content": "How does this work?"},
                )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.conversation.messages.filter(role=Message.Role.USER).count(), 1)
        assistant = self.conversation.messages.get(role=Message.Role.ASSISTANT)
        self.assertEqual(assistant.status, Message.Status.COMPLETE)
        self.assertIn("not a real RAG result", assistant.content)
        citation = assistant.citations.get()
        self.assertEqual(citation.citation_id, "S1")
        self.assertEqual(citation.source_id, "synthetic_source")
        metadata = assistant.generation_metadata.get()
        self.assertEqual(metadata.verification_status, GenerationMetadata.VerificationStatus.SYNTHETIC)
        self.assertEqual(metadata.retrieval_mode, "synthetic_mock")

    def test_real_response_verification_and_retrieval_diagnostics_are_persisted(self):
        self.client.force_login(self.user)
        response_data = SimpleNamespace(
            answer="A grounded answer [S1]", citations=(), request_id="diagnostic-request",
            retrieval_mode="dense", stage_timings={"generation": 5.0}, synthetic=False,
            verification_status="partially_verified",
            diagnostics={"retrieval_hit_count": 1, "context_bytes": 42,
                "context_token_estimate": 12, "reranker_active": False,
                "retrieval_hits": [{"document_id": "d" * 64, "source_id": "docs",
                    "chunk_id": "c" * 64, "score": 0.81, "rank": 1}]},
        )
        client = SimpleNamespace(query=lambda *args, **kwargs: response_data, close=lambda: None)
        with patch("chat.views.get_rag_client", return_value=client):
            response = self.client.post(
                reverse("conversations:message_create", args=(self.conversation.pk,)),
                {"content": "diagnostics persistence check"},
            )
        self.assertEqual(response.status_code, 302)
        assistant = self.conversation.messages.get(role=Message.Role.ASSISTANT)
        metadata = assistant.generation_metadata.get()
        self.assertEqual(metadata.verification_status,
                         GenerationMetadata.VerificationStatus.PARTIALLY_VERIFIED)
        self.assertEqual(metadata.diagnostics["retrieval_hits"][0]["score"], 0.81)
        self.assertEqual(metadata.diagnostics["context_bytes"], 42)
        self.assertGreaterEqual(metadata.stage_timings["django_rag_http"], 0)
        self.assertGreaterEqual(metadata.stage_timings["django_persistence"], 0)

    def test_rag_metrics_command_reports_bounded_aggregates_without_message_content(self):
        message = Message.objects.create(conversation=self.conversation, role=Message.Role.ASSISTANT,
                                         content="PRIVATE-ANSWER-MUST-NOT-APPEAR")
        GenerationMetadata.objects.create(message=message, request_id="private-request-id",
            retrieval_mode="dense", stage_timings={"dense_search": 12.0},
            diagnostics={"failure_code": "safe_test_code"},
            verification_status=GenerationMetadata.VerificationStatus.FAILED)
        output = StringIO()
        call_command("rag_metrics", "--limit", "1", stdout=output)
        self.assertIn('"sample_size": 1', output.getvalue())
        self.assertIn('"dense_search"', output.getvalue())
        self.assertIn('"safe_test_code": 1', output.getvalue())
        self.assertNotIn("PRIVATE-ANSWER-MUST-NOT-APPEAR", output.getvalue())
        self.assertNotIn("private-request-id", output.getvalue())
        with self.assertRaises(CommandError):
            call_command("rag_metrics", "--limit", "10001", stdout=StringIO())

    def test_rag_failure_is_persisted_without_internal_error_details(self):
        from unittest.mock import patch
        self.client.force_login(self.user)
        with patch("chat.views.get_rag_client") as get_client:
            get_client.return_value.query.side_effect = RAGClientTimeout("private upstream detail")
            response = self.client.post(
                reverse("conversations:message_create", args=(self.conversation.pk,)),
                {"content": "question"}, follow=True,
            )
        self.assertEqual(response.status_code, 200)
        assistant = self.conversation.messages.get(role=Message.Role.ASSISTANT)
        self.assertEqual(assistant.status, Message.Status.FAILED)
        self.assertNotIn("private upstream detail", assistant.content)
        self.assertEqual(assistant.generation_metadata.get().verification_status,
                         GenerationMetadata.VerificationStatus.FAILED)

    def test_context_overflow_displays_actionable_message_without_upstream_detail(self):
        from unittest.mock import patch
        self.client.force_login(self.user)
        with patch("chat.views.get_rag_client") as get_client:
            get_client.return_value.query.side_effect = RAGClientInputTooLarge("private upstream detail")
            response = self.client.post(
                reverse("conversations:message_create", args=(self.conversation.pk,)),
                {"content": "question"}, follow=True,
            )
        self.assertEqual(response.status_code, 200)
        assistant = self.conversation.messages.get(role=Message.Role.ASSISTANT)
        self.assertEqual(assistant.status, Message.Status.FAILED)
        self.assertIn("Shorten it and try again", assistant.content)
        self.assertNotIn("private upstream detail", assistant.content)
        self.assertContains(response, "Shorten it and try again")

    def test_browser_page_does_not_expose_rag_service_secret(self):
        secret = "not-for-browser-service-secret-123456"
        self.client.force_login(self.user)
        with override_settings(RAG_API_TOKEN=secret, RAG_ADAPTER="mock"):
            response = self.client.get(reverse("conversations:detail", args=(self.conversation.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, secret)

    def test_csrf_middleware_rejects_missing_and_invalid_tokens(self):
        client = Client(enforce_csrf_checks=True)
        login_url = reverse("accounts:login")
        client.get(login_url)
        payload = {"username": "owner", "password": "good-password-981!"}
        missing = client.post(login_url, payload)
        invalid = client.post(login_url, {**payload, "csrfmiddlewaretoken": "invalid-token"})
        self.assertEqual(missing.status_code, 403)
        self.assertEqual(invalid.status_code, 403)

    def test_csrf_protects_message_and_logout_posts(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        detail_url = reverse("conversations:detail", args=(self.conversation.pk,))
        page = client.get(detail_url)
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode()).group(1)
        message_url = reverse("conversations:message_create", args=(self.conversation.pk,))
        self.assertEqual(client.post(message_url, {"content": "no token"}).status_code, 403)
        self.assertEqual(client.post(message_url, {"content": "bad token", "csrfmiddlewaretoken": "invalid"}).status_code, 403)
        self.assertEqual(client.post(reverse("accounts:logout")).status_code, 403)
        self.assertTrue(client.session.get("_auth_user_id"))
        self.assertEqual(self.conversation.messages.count(), 0)
        self.assertTrue(token)


class ConversationManagementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="manage-owner", password="good-password-981!")
        self.other = get_user_model().objects.create_user(username="manage-other", password="good-password-982!")
        self.conversation = Conversation.objects.create(user=self.user)
        self.client.force_login(self.user)

    def test_title_generation_is_short_and_redacts_sensitive_questions(self):
        from .title_utils import title_from_first_question
        self.assertEqual(title_from_first_question("How does Qdrant perform vector similarity search?"),
                         "Qdrant Vector Similarity Search")
        self.assertEqual(title_from_first_question(
            "In FastAPI, what is a path parameter? Give one concise fact from its documentation."
        ), "FastAPI Path Parameter")
        self.assertEqual(title_from_first_question("My password is abc123 and how do I rotate it?"),
                         "New conversation")
        self.assertLessEqual(len(title_from_first_question("explain " + "a detailed subject " * 12)), 64)

    def test_first_message_creates_title_and_manual_title_is_preserved(self):
        from unittest.mock import patch
        with patch("chat.views.get_rag_client", return_value=MockRAGClient()):
            self.client.post(reverse("conversations:message_create", args=(self.conversation.pk,)),
                {"content": "How does Qdrant perform vector similarity search?"})
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.title, "Qdrant Vector Similarity Search")
        self.assertFalse(self.conversation.title_is_manual)
        self.client.post(reverse("conversations:message_create", args=(self.conversation.pk,)), {"content": "Follow up"})
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.title, "Qdrant Vector Similarity Search")
        self.conversation.title = "My chosen title"
        self.conversation.title_is_manual = True
        self.conversation.save()
        with patch("chat.views.get_rag_client", return_value=MockRAGClient()):
            self.client.post(reverse("conversations:message_create", args=(self.conversation.pk,)), {"content": "Third question"})
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.title, "My chosen title")

    def test_owner_can_rename_and_title_survives_refresh(self):
        url = reverse("conversations:rename", args=(self.conversation.pk,))
        response = self.client.post(url, {"title": "Database indexes"})
        self.assertRedirects(response, reverse("conversations:detail", args=(self.conversation.pk,)))
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.title, "Database indexes")
        self.assertTrue(self.conversation.title_is_manual)
        self.assertContains(self.client.get(reverse("conversations:detail", args=(self.conversation.pk,))), "Database indexes")

    def test_export_formats_include_safe_content_but_no_internal_ids_or_diagnostics(self):
        assistant = Message.objects.create(conversation=self.conversation, role=Message.Role.ASSISTANT,
            content="A grounded answer.")
        CitationSnapshot.objects.create(message=assistant, citation_id="S1", source_id="internal-source-marker",
            document_id="internal-document-marker", chunk_id="internal-chunk-marker", title="Guide",
            section="Install", source_reference="https://docs.example.org/guide?tracking=secret#part")
        GenerationMetadata.objects.create(message=assistant, request_id="private-request-marker",
            diagnostics={"secret": "do-not-export"}, verification_status=GenerationMetadata.VerificationStatus.VERIFIED)
        for fmt, content_type in (("md", "text/markdown"), ("txt", "text/plain"), ("json", "application/json")):
            response = self.client.get(reverse("conversations:export", args=(self.conversation.pk, fmt)))
            self.assertEqual(response.status_code, 200)
            self.assertIn(content_type, response["Content-Type"])
            data = response.content.decode()
            self.assertIn("A grounded answer.", data)
            self.assertIn("https://docs.example.org/guide", data)
            for hidden in ("internal-source-marker", "internal-document-marker", "internal-chunk-marker",
                           "private-request-marker", "do-not-export", "tracking=secret"):
                self.assertNotIn(hidden, data)
        import json
        parsed = json.loads(self.client.get(reverse("conversations:export", args=(self.conversation.pk, "json"))).content)
        self.assertEqual(parsed["messages"][0]["role"], "Satell")

    def test_lock_blocks_message_and_delete_until_owner_unlocks(self):
        lock_url = reverse("conversations:lock", args=(self.conversation.pk,))
        self.client.post(lock_url)
        self.conversation.refresh_from_db()
        self.assertIsNotNone(self.conversation.locked_at)
        with patch("chat.views.get_rag_client") as get_client:
            response = self.client.post(reverse("conversations:message_create", args=(self.conversation.pk,)), {"content": "Blocked"})
            get_client.assert_not_called()
        self.assertRedirects(response, reverse("conversations:detail", args=(self.conversation.pk,)))
        self.assertEqual(self.conversation.messages.count(), 0)
        delete = self.client.post(reverse("conversations:delete", args=(self.conversation.pk,)))
        self.assertTrue(Conversation.objects.filter(pk=self.conversation.pk).exists())
        self.client.post(reverse("conversations:unlock", args=(self.conversation.pk,)))
        self.conversation.refresh_from_db()
        self.assertIsNone(self.conversation.locked_at)
        self.client.post(reverse("conversations:delete", args=(self.conversation.pk,)))
        self.assertFalse(Conversation.objects.filter(pk=self.conversation.pk).exists())

    def test_share_is_off_by_default_hashes_token_and_is_read_only_revocable_and_scoped(self):
        message = Message.objects.create(conversation=self.conversation, role=Message.Role.ASSISTANT,
            content="Shared grounded answer.")
        CitationSnapshot.objects.create(message=message, citation_id="S1", source_id="hidden-source-id",
            document_id="hidden-document-id", chunk_id="hidden-chunk-id", title="Guide {#guide}",
            section="Guide {#guide}", source_reference="https://docs.example.org/guide?private=x")
        self.assertFalse(self.conversation.share_token_hash)
        response = self.client.post(reverse("conversations:share_create", args=(self.conversation.pk,)),
                                    {"expiration_days": "7"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Referrer-Policy"], "same-origin")
        share_link = response.context["share_link_once"]
        token = share_link.rstrip("/").rsplit("/", 1)[-1]
        self.conversation.refresh_from_db()
        self.assertNotEqual(self.conversation.share_token_hash, token)
        self.assertEqual(len(self.conversation.share_token_hash), 64)
        public = self.client.get(reverse("conversations:shared", kwargs={"token": token}))
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public["X-Robots-Tag"], "noindex, nofollow, noarchive")
        self.assertIn("private, no-store", public["Cache-Control"])
        self.assertEqual(public["Referrer-Policy"], "no-referrer")
        self.assertContains(public, "Shared grounded answer.")
        self.assertContains(public, "Guide")
        self.assertNotContains(public, "hidden-source-id")
        self.assertNotContains(public, "hidden-document-id")
        self.assertNotContains(public, "hidden-chunk-id")
        self.assertNotContains(public, "private=x")
        self.client.post(reverse("conversations:share_revoke", args=(self.conversation.pk,)))
        self.assertEqual(self.client.get(reverse("conversations:shared", kwargs={"token": token})).status_code, 404)

    def test_share_expiration_and_unknown_token_fail_closed(self):
        self.conversation.share_token_hash = "a" * 64
        self.conversation.share_expires_at = timezone.now() - timedelta(seconds=1)
        self.conversation.save()
        self.assertEqual(self.client.get(reverse("conversations:shared", kwargs={"token": "x" * 43})).status_code, 404)
        self.assertEqual(self.client.get(reverse("conversations:shared", kwargs={"token": "y" * 43})).status_code, 404)

    def test_share_creation_and_revocation_remain_csrf_protected(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        detail_url = reverse("conversations:detail", args=(self.conversation.pk,))
        detail = client.get(detail_url)
        token_match = re.search(rb'name="csrfmiddlewaretoken" value="([^\"]+)"', detail.content)
        self.assertIsNotNone(token_match)
        share = client.post(reverse("conversations:share_create", args=(self.conversation.pk,)),
                            {"expiration_days": "7", "csrfmiddlewaretoken": token_match.group(1).decode()})
        self.assertEqual(share.status_code, 200)
        token_match = re.search(rb'name="csrfmiddlewaretoken" value="([^\"]+)"', share.content)
        self.assertIsNotNone(token_match)
        revoked = client.post(reverse("conversations:share_revoke", args=(self.conversation.pk,)),
                              {"csrfmiddlewaretoken": token_match.group(1).decode()})
        self.assertEqual(revoked.status_code, 302)
        self.conversation.refresh_from_db()
        self.assertFalse(self.conversation.share_token_hash)

    def test_other_user_cannot_rename_export_share_lock_or_delete(self):
        self.client.force_login(self.other)
        endpoints = [
            ("conversations:rename", "post", {"title": "Stolen title"}),
            ("conversations:lock", "post", {}),
            ("conversations:share_create", "post", {"expiration_days": "7"}),
            ("conversations:delete", "post", {}),
        ]
        for route, method, data in endpoints:
            response = getattr(self.client, method)(reverse(route, args=(self.conversation.pk,)), data)
            self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get(reverse("conversations:export", args=(self.conversation.pk, "json"))).status_code, 404)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.title, "New conversation")
        self.assertIsNone(self.conversation.locked_at)
        self.assertFalse(self.conversation.share_token_hash)

    def test_citation_title_anchor_and_unsafe_link_are_not_displayed(self):
        assistant = Message.objects.create(conversation=self.conversation, role=Message.Role.ASSISTANT, content="Answer [S1].")
        CitationSnapshot.objects.create(message=assistant, citation_id="S1", source_id="s", document_id="d",
            chunk_id="c", title="Dependencies {#dependencies}", section="Dependencies {#dependencies}",
            source_reference="javascript:alert(1)")
        response = self.client.get(reverse("conversations:detail", args=(self.conversation.pk,)))
        self.assertContains(response, "Dependencies")
        self.assertNotContains(response, "{#dependencies}")
        self.assertNotContains(response, "javascript:")

    def test_spaced_markdown_anchor_is_removed_from_citation_titles(self):
        assistant = Message.objects.create(conversation=self.conversation, role=Message.Role.ASSISTANT, content="Answer [S1].")
        CitationSnapshot.objects.create(message=assistant, citation_id="S1", source_id="s", document_id="d",
            chunk_id="c", title="Path Parameters { #path-parameters }", section="Path parameters { #path-parameters }",
            source_reference="https://docs.example.org/guide")
        response = self.client.get(reverse("conversations:detail", args=(self.conversation.pk,)))
        self.assertContains(response, "Path Parameters")
        self.assertNotContains(response, "{ #path-parameters }")

    def test_partial_status_is_visible_without_technical_footer(self):
        assistant = Message.objects.create(conversation=self.conversation, role=Message.Role.ASSISTANT, content="Supported answer.")
        GenerationMetadata.objects.create(message=assistant, request_id="r1",
            verification_status=GenerationMetadata.VerificationStatus.PARTIALLY_VERIFIED)
        response = self.client.get(reverse("conversations:detail", args=(self.conversation.pk,)))
        self.assertContains(response, "Partially verified")
        self.assertNotContains(response, "Partial evidence support. Unsupported claims were omitted.")
