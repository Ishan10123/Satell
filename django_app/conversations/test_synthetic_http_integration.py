"""Opt-in end-to-end Django persistence check against the synthetic-only API."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import CitationSnapshot, Conversation, GenerationMetadata, Message


@unittest.skipUnless(os.environ.get("RUN_SYNTHETIC_RAG_HTTP_TESTS") == "1", "opt-in Docker synthetic integration")
class SyntheticRAGHTTPIntegrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="synthetic-user", password="test-pass-981!")
        self.conversation = Conversation.objects.create(user=self.user, title="Synthetic integration")

    @override_settings(
        RAG_ADAPTER="http",
        RAG_API_BASE_URL="http://rag-api-synthetic:8000",
        RAG_API_TOKEN="synthetic-test-token-only-never-use-for-real-rag",
        RAG_API_TIMEOUT_SECONDS=3,
        RAG_API_TOP_K=8,
    )
    def test_synthetic_http_response_is_correlated_and_persisted(self):
        client = Client()
        client.force_login(self.user)
        with patch("chat.views.uuid.uuid4", return_value=SimpleNamespace(hex="satell-synthetic-test-001")):
            response = client.post(
                reverse("conversations:message_create", args=(self.conversation.pk,)),
                {"content": "synthetic contract check"},
            )
        self.assertEqual(response.status_code, 302)
        assistant = self.conversation.messages.get(role=Message.Role.ASSISTANT)
        self.assertIn("not a real RAG result", assistant.content)
        self.assertEqual(assistant.citations.count(), 1)
        citation = assistant.citations.get()
        self.assertEqual(citation.source_id, "synthetic_source")
        metadata = assistant.generation_metadata.get()
        self.assertEqual(metadata.request_id, "satell-synthetic-test-001")
        self.assertEqual(metadata.verification_status, GenerationMetadata.VerificationStatus.SYNTHETIC)
        self.assertEqual(metadata.retrieval_mode, "synthetic_integration_fixture")
        self.assertContains(client.get(reverse("conversations:detail", args=(self.conversation.pk,))),
                            "Synthetic test response; not a real RAG result.")
