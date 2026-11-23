import json
import httpx
from django.test import SimpleTestCase

from .client import (
    FastAPIRAGClient,
    MockRAGClient,
    RAGClientProtocolError,
    RAGClientInputTooLarge,
    RAGClientTimeout,
    RAGClientUnavailable,
)


TOKEN = "server-only-token-that-must-never-reach-the-browser-123456"


class RAGClientTests(SimpleTestCase):
    def test_mock_response_is_explicitly_synthetic_and_validated(self):
        response = MockRAGClient().query("hello", top_k=8, correlation_id="local-request")
        self.assertTrue(response.synthetic)
        self.assertEqual(response.request_id, "local-request")
        self.assertEqual(response.retrieval_mode, "synthetic_mock")
        self.assertIn("not a real RAG result", response.answer)
        self.assertEqual(response.citations[0].citation_id, "S1")

    def test_http_response_is_structured_and_source_url_is_sanitized(self):
        def handler(request):
            self.assertEqual(request.headers["Authorization"], f"Bearer {TOKEN}")
            self.assertEqual(request.url.path, "/v1/query")
            self.assertEqual(request.headers["X-Correlation-ID"], "front-id")
            self.assertEqual(request.read(), b'{"query":"question","top_k":4}')
            return httpx.Response(200, json={
                "answer": "A verified answer [S1]", "request_id": "backend-id",
                "retrieval_mode": "dense", "timings_ms": {"embedding": 1.5},
                "verification_status": "partially_verified",
                "diagnostics": {"retrieval_hit_count": 1, "context_bytes": 42,
                    "context_token_estimate": 12, "context_chunk_count": 1,
                    "context_exclusion_count": 0, "context_exclusion_reasons": {},
                    "retrieval_strategy": "dense", "citation_validation_status": "passed",
                    "claim_verifier_status": "partially_verified", "reranker_active": False,
                    "generation_model": "qwen3.5:4b", "verification_model": "qwen3.5:4b",
                    "claim_count": 2, "supported_claim_count": 1, "rejected_claim_count": 1,
                    "prompt_tokens_estimated": 120,
                    "retrieval_hits": [{"document_id": "doc", "source_id": "src",
                        "chunk_id": "chunk", "score": 0.82, "rank": 1}]},
                "citations": [{"citation_id": "S1", "source_id": "src", "document_id": "doc",
                    "chunk_id": "chunk", "title": "Guide", "page_references": [2],
                    "section": "Install", "source_reference": "https://docs.example.org/page?q=secret#fragment"}],
            })
        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        adapter = FastAPIRAGClient("http://127.0.0.1:8000", TOKEN, client=client)
        response = adapter.query("question", top_k=4, correlation_id="front-id")
        self.assertEqual(response.request_id, "backend-id")
        self.assertEqual(response.verification_status, "partially_verified")
        self.assertEqual(response.diagnostics["retrieval_hits"][0]["score"], 0.82)
        self.assertEqual(response.diagnostics["context_chunk_count"], 1)
        self.assertEqual(response.diagnostics["citation_validation_status"], "passed")
        self.assertEqual(response.citations[0].page_references, (2,))
        self.assertEqual(response.citations[0].source_reference, "https://docs.example.org/page")
        self.assertNotIn(TOKEN, repr(response))
        client.close()

    def test_response_style_is_bounded_and_sent_only_when_non_default(self):
        observed = []
        def handler(request):
            observed.append(json.loads(request.read()))
            return httpx.Response(200, json={"answer": "A style test response.", "request_id": "r",
                "retrieval_mode": "dense", "citations": [], "timings_ms": {}, "synthetic": False})
        client = httpx.Client(transport=httpx.MockTransport(handler))
        adapter = FastAPIRAGClient("http://127.0.0.1:8000", TOKEN, client=client)
        adapter.query("question", response_style="natural")
        adapter.query("question", response_style="concise")
        self.assertNotIn("response_style", observed[0])
        self.assertEqual(observed[1]["response_style"], "concise")
        with self.assertRaises(RAGClientProtocolError):
            adapter.query("question", response_style="invented")
        client.close()

    def test_http_response_marks_synthetic_fixture_explicitly(self):
        client = httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={
            "answer": "Synthetic fixture only; not real RAG.", "request_id": "corr-1",
            "retrieval_mode": "synthetic_integration_fixture", "timings_ms": {},
            "citations": [{"citation_id": "S1", "source_id": "synthetic", "document_id": "doc",
                "chunk_id": "chunk", "title": "Fixture", "page_references": [], "section": "test"}],
            "synthetic": True,
        })))
        adapter = FastAPIRAGClient("http://rag-api-synthetic:8000", TOKEN, client=client)
        self.assertTrue(adapter.query("question", correlation_id="corr-1").synthetic)
        client.close()

    def test_http_client_rejects_arbitrary_plain_http_service_host(self):
        from .client import RAGClientConfigurationError
        with self.assertRaises(RAGClientConfigurationError):
            FastAPIRAGClient("http://example.org:8000", TOKEN)

    def test_timeout_is_mapped_to_typed_error(self):
        def handler(_request):
            raise httpx.ReadTimeout("internal timeout detail")
        client = httpx.Client(transport=httpx.MockTransport(handler))
        adapter = FastAPIRAGClient("http://127.0.0.1:8000", TOKEN, client=client)
        with self.assertRaises(RAGClientTimeout) as caught:
            adapter.query("question", top_k=8, correlation_id="rid")
        self.assertNotIn("internal timeout detail", str(caught.exception))
        client.close()

    def test_unavailable_fastapi_transport_is_typed_and_safe(self):
        def handler(_request):
            raise httpx.ConnectError("private DNS and network detail")
        client = httpx.Client(transport=httpx.MockTransport(handler))
        adapter = FastAPIRAGClient("http://127.0.0.1:8000", TOKEN, client=client)
        with self.assertRaises(RAGClientUnavailable) as caught:
            adapter.query("question", top_k=8, correlation_id="rid")
        self.assertEqual(caught.exception.error_code, "service_unavailable")
        self.assertNotIn("private DNS", str(caught.exception))
        client.close()

    def test_http_error_is_generic_and_does_not_leak_service_token(self):
        client = httpx.Client(transport=httpx.MockTransport(
            lambda _request: httpx.Response(503, json={"detail": TOKEN}, headers={
                "X-RAG-Error-Code": "ollama_timeout", "X-RAG-Error-Stage": "answer_generation"})))
        adapter = FastAPIRAGClient("http://127.0.0.1:8000", TOKEN, client=client)
        with self.assertRaises(RAGClientUnavailable) as caught:
            adapter.query("question", top_k=8, correlation_id="rid")
        self.assertNotIn(TOKEN, str(caught.exception))
        self.assertEqual(caught.exception.error_code, "ollama_timeout")
        self.assertEqual(caught.exception.error_stage, "answer_generation")
        self.assertEqual(caught.exception.http_status, 503)
        client.close()

    def test_http_error_classification_rejects_unsafe_header_values(self):
        client = httpx.Client(transport=httpx.MockTransport(
            lambda _request: httpx.Response(503, headers={
                "X-RAG-Error-Code": "secret value", "X-RAG-Error-Stage": "\r\n"})))
        adapter = FastAPIRAGClient("http://127.0.0.1:8000", TOKEN, client=client)
        with self.assertRaises(RAGClientUnavailable) as caught:
            adapter.query("question", top_k=8, correlation_id="rid")
        self.assertEqual(caught.exception.error_code, "upstream_error")
        self.assertEqual(caught.exception.error_stage, "api")
        client.close()

    def test_context_overflow_is_typed_and_does_not_expose_upstream_details(self):
        client = httpx.Client(transport=httpx.MockTransport(
            lambda _request: httpx.Response(413, json={"detail": "private upstream exception"})))
        adapter = FastAPIRAGClient("http://127.0.0.1:8000", TOKEN, client=client)
        with self.assertRaises(RAGClientInputTooLarge) as caught:
            adapter.query("question", top_k=8, correlation_id="rid")
        self.assertIn("Shorten it", str(caught.exception))
        self.assertNotIn("private upstream exception", str(caught.exception))
        client.close()

    def test_malformed_payload_and_invalid_citation_fail_closed(self):
        responses = iter([
            httpx.Response(200, json={"answer": "answer", "citations": "bad"}),
            httpx.Response(200, json={"answer": "answer", "request_id": "rid", "citations": [
                {"citation_id": "S1", "source_id": "src", "document_id": "doc", "page_references": [True]}]}),
            httpx.Response(200, content=b'{"answer":"answer","request_id":"rid","citations":[],'
                b'"diagnostics":{"retrieval_hits":[{"document_id":"doc","source_id":"src",'
                b'"chunk_id":"chunk","score":NaN}]}}'),
        ])
        client = httpx.Client(transport=httpx.MockTransport(lambda _request: next(responses)))
        adapter = FastAPIRAGClient("http://127.0.0.1:8000", TOKEN, client=client)
        with self.assertRaises(RAGClientProtocolError):
            adapter.query("question", top_k=8, correlation_id="rid1")
        with self.assertRaises(RAGClientProtocolError):
            adapter.query("question", top_k=8, correlation_id="rid2")
        with self.assertRaises(RAGClientProtocolError):
            adapter.query("question", top_k=8, correlation_id="rid3")
        client.close()

    def test_http_client_preserves_5000_character_query_and_rejects_5001(self):
        prompt = "x" * 5000
        observed = []
        client = httpx.Client(transport=httpx.MockTransport(lambda request: (
            observed.append(request.read().decode("utf-8")) or httpx.Response(200, json={
                "answer": "Answer", "request_id": "rid", "retrieval_mode": "dense",
                "citations": [], "timings_ms": {},
            })
        )))
        adapter = FastAPIRAGClient("http://127.0.0.1:8000", TOKEN, client=client)
        adapter.query(prompt, top_k=8, correlation_id="rid")
        self.assertIn(prompt, observed[0])
        with self.assertRaises(RAGClientProtocolError):
            adapter.query("x" * 5001, top_k=8, correlation_id="rid")
        self.assertEqual(len(observed), 1)
        client.close()
