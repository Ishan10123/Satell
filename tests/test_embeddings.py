import json
import unittest

import httpx

from src.rag_pipeline.embeddings import EmbeddingError, EmbeddingModelSpec, OllamaEmbeddingProvider


class OllamaEmbeddingProviderTests(unittest.TestCase):
    model = "synthetic-embed:1"

    def make_provider(self, handler, **kwargs):
        client = httpx.Client(transport=httpx.MockTransport(handler))
        spec = kwargs.pop("spec", EmbeddingModelSpec(self.model, max_batch_size=2, max_input_characters=20))
        return OllamaEmbeddingProvider(spec, client=client, max_retries=kwargs.pop("max_retries", 0), **kwargs)

    def standard_handler(self, vectors):
        def handler(request):
            if request.url.path == "/api/version":
                return httpx.Response(200, json={"version": "0.40.16"})
            if request.url.path == "/api/tags":
                return httpx.Response(200, json={"models": [{"name": self.model, "digest": "sha256:synthetic"}]})
            if request.url.path == "/api/embed":
                body = json.loads(request.content)
                self.assertFalse(body["truncate"])
                self.assertEqual(body["model"], self.model)
                return httpx.Response(200, json={"model": self.model, "embeddings": vectors})
            return httpx.Response(404)
        return handler

    def test_batch_embedding_discovers_dimensions_and_checks_unit_norm(self):
        provider = self.make_provider(self.standard_handler([[0.6, 0.8], [0.8, 0.6]]))
        batch = provider.embed(["text one", "text two"])
        self.assertEqual(len(batch.vectors), 2)
        self.assertEqual(batch.descriptor.dimensions, 2)
        self.assertTrue(batch.descriptor.vectors_are_unit_normalized)
        self.assertEqual(batch.descriptor.runtime_version, "0.40.16")
        self.assertEqual(batch.descriptor.model_digest, "sha256:synthetic")

    def test_model_digest_pin_must_match_local_runtime(self):
        spec = EmbeddingModelSpec(self.model, model_digest="sha256:expected")
        provider = self.make_provider(self.standard_handler([[0.6, 0.8]]), spec=spec)
        with self.assertRaisesRegex(EmbeddingError, "digest"):
            provider.embed(["query"])

    def test_missing_model_fails_health_check_without_embedding(self):
        def handler(request):
            if request.url.path == "/api/version":
                return httpx.Response(200, json={"version": "0.40.16"})
            return httpx.Response(200, json={"models": []})
        provider = self.make_provider(handler)
        with self.assertRaisesRegex(EmbeddingError, "not installed"):
            provider.embed(["query"])

    def test_inconsistent_vector_dimensions_are_rejected(self):
        provider = self.make_provider(self.standard_handler([[1.0, 0.0], [0.0, 1.0, 0.0]]))
        with self.assertRaisesRegex(EmbeddingError, "inconsistent dimensions"):
            provider.embed(["first", "second"])

    def test_non_finite_and_zero_vectors_are_rejected(self):
        for vectors, expected in (([[0.0, 0.0]], "zero vector"), ([["NaN"]], "non-finite")):
            provider = self.make_provider(self.standard_handler(vectors))
            with self.assertRaisesRegex(EmbeddingError, expected):
                provider.embed(["query"])

    def test_batch_and_input_limits_are_enforced_before_network_use(self):
        called = []
        provider = self.make_provider(lambda request: called.append(request) or httpx.Response(200, json={}))
        with self.assertRaisesRegex(ValueError, "batch exceeds"):
            provider.embed(["one", "two", "three"])
        with self.assertRaisesRegex(ValueError, "character limit"):
            provider.embed(["x" * 21])
        with self.assertRaisesRegex(ValueError, "non-empty text"):
            provider.embed(["  "])
        self.assertEqual(called, [])

    def test_remote_hosts_and_non_http_urls_are_rejected(self):
        spec = EmbeddingModelSpec(self.model)
        for url in ("https://127.0.0.1:11434", "http://example.com:11434", "http://localhost:11434/api"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                OllamaEmbeddingProvider(spec, base_url=url)

    def test_server_error_retries_once(self):
        calls = {"embed": 0}
        def handler(request):
            if request.url.path == "/api/version":
                return httpx.Response(200, json={"version": "0.40.16"})
            if request.url.path == "/api/tags":
                return httpx.Response(200, json={"models": [{"name": self.model, "digest": "sha256:synthetic"}]})
            if request.url.path == "/api/embed":
                calls["embed"] += 1
                if calls["embed"] == 1:
                    return httpx.Response(503)
                return httpx.Response(200, json={"embeddings": [[1.0, 0.0]]})
            return httpx.Response(404)
        provider = self.make_provider(handler, max_retries=1)
        batch = provider.embed(["query"])
        self.assertEqual(len(batch.vectors), 1)
        self.assertEqual(calls["embed"], 2)

    def test_spec_rejects_invalid_dimensions_and_limits(self):
        with self.assertRaises(ValueError):
            EmbeddingModelSpec(self.model, dimensions=0)
        with self.assertRaises(ValueError):
            EmbeddingModelSpec(self.model, max_batch_size=0)


if __name__ == "__main__":
    unittest.main()