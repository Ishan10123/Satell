"""Opt-in live Django -> FastAPI -> Qdrant/Ollama persistence smoke test.

Set SATELL_LIVE_RAG_E2E=1 only for a local instance explicitly configured with
the signed local_academic_demo policy. The test uses Django's isolated test DB.
"""

import os
import unittest

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import CitationSnapshot, Conversation, GenerationMetadata, Message


@unittest.skipUnless(os.environ.get("SATELL_LIVE_RAG_E2E") == "1",
                     "requires explicit local live RAG authorization")
class LocalAcademicDemoEndToEndTests(TestCase):
    def test_real_answer_and_citations_persist_through_django(self):
        api_url = os.environ.get("SATELL_RAG_API_URL", "http://rag-api:8000")
        token = os.environ.get("RAG_API_TOKEN", "")
        self.assertGreaterEqual(len(token), 32)
        user = get_user_model().objects.create_user(username="local-rag-e2e", password="test-password-only")
        conversation = Conversation.objects.create(user=user, title="Local academic RAG E2E")
        client = Client()
        self.assertTrue(client.login(username="local-rag-e2e", password="test-password-only"))
        with override_settings(RAG_ADAPTER="http", RAG_API_BASE_URL=api_url, RAG_API_TOKEN=token,
                               RAG_API_TIMEOUT_SECONDS=180, RAG_API_TOP_K=8):
            response = client.post(reverse("conversations:message_create", kwargs={"conversation_id": conversation.pk}), {
                "content": "What is a Docker container? Answer with one concise fact from the Docker documentation.",
            }, follow=True)
        self.assertEqual(response.status_code, 200)
        messages = list(Message.objects.filter(conversation=conversation).order_by("created_at", "id"))
        self.assertEqual(len(messages), 2)
        assistant = messages[-1]
        self.assertEqual(assistant.role, Message.Role.ASSISTANT)
        self.assertEqual(assistant.status, Message.Status.COMPLETE)
        self.assertTrue(assistant.content.strip())
        self.assertNotIn("Synthetic mock response", assistant.content)
        citations = list(CitationSnapshot.objects.filter(message=assistant))
        self.assertTrue(citations, "Real response should persist grounded citation metadata.")
        self.assertTrue(all(len(c.document_id) == 64 for c in citations))
        self.assertFalse(any(c.source_id.startswith("arxiv_") for c in citations))
        metadata = GenerationMetadata.objects.get(message=assistant)
        self.assertIn(metadata.verification_status, {
            GenerationMetadata.VerificationStatus.VERIFIED,
            GenerationMetadata.VerificationStatus.PARTIALLY_VERIFIED,
        })
        self.assertIn("retrieval_hits", metadata.diagnostics)
        self.assertIn("context_bytes", metadata.diagnostics)
        self.assertFalse(metadata.diagnostics["reranker_active"])
        self.assertTrue(metadata.request_id)
