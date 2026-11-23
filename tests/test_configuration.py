import json
from pathlib import Path
import tempfile
import unittest

from src.rag_pipeline.configuration import ConfigurationError, load_embedding_provider, load_generator
from src.rag_pipeline.ingestion.registry import load_config


ROOT = Path(__file__).resolve().parents[1]


class ConfigurationTests(unittest.TestCase):
    def test_checked_in_model_configs_construct_pinned_loopback_clients(self):
        embedding = load_embedding_provider(ROOT / "configs" / "embedding.json")
        generation = load_generator(ROOT / "configs" / "generation.json")
        try:
            self.assertEqual(embedding.spec.dimensions, 768)
            self.assertEqual(embedding.spec.model_digest, "0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f")
            self.assertEqual(generation.model_digest, "d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04")
            self.assertEqual(generation.context_window_tokens, 8192)
            self.assertEqual(generation.max_output_tokens, 1024)
            self.assertEqual(generation.input_safety_margin_tokens, 512)
            self.assertEqual(generation._verifier.context_window_tokens, 8192)
            self.assertEqual(generation._verifier.max_output_tokens, 1024)
            self.assertEqual(generation._verifier.input_safety_margin_tokens, 512)
        finally:
            embedding.close()
            generation.close()

    def test_configuration_rejects_remote_provider_url(self):
        value = json.loads((ROOT / "configs" / "embedding.json").read_text(encoding="utf-8-sig"))
        value["base_url"] = "http://example.org:11434"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "embedding.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                load_embedding_provider(path)

    def test_explicit_docker_host_gateway_override_is_allowed(self):
        embedding = load_embedding_provider(ROOT / "configs" / "embedding.json",
                                            base_url="http://host.docker.internal:11434")
        generation = load_generator(ROOT / "configs" / "generation.json",
                                    base_url="http://host.docker.internal:11434")
        try:
            self.assertEqual(embedding.base_url, "http://host.docker.internal:11434")
            self.assertEqual(generation.base_url, "http://host.docker.internal:11434")
        finally:
            embedding.close()
            generation.close()

    def test_generation_config_must_disable_thinking(self):
        value = json.loads((ROOT / "configs" / "generation.json").read_text(encoding="utf-8-sig"))
        value["thinking"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "generation.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ConfigurationError, "disable thinking"):
                load_generator(path)

    def test_parser_support_does_not_expand_ingestion_eligibility(self):
        config = load_config(ROOT / "configs" / "ingestion_sources.json")
        self.assertEqual(config.project_root, ROOT.resolve())
        self.assertEqual(config.parser_registry_path, (ROOT / "configs" / "parser_registry.json").resolve())
        self.assertIn(".py", config.parser_supported_extensions)
        self.assertIn(".docx", config.parser_supported_extensions)
        self.assertEqual(config.allowed_extensions, frozenset({".md", ".html", ".rst", ".pdf", ".txt"}))
        self.assertTrue(config.allowed_extensions <= config.parser_supported_extensions)


if __name__ == "__main__":
    unittest.main()
