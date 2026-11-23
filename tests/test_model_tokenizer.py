from pathlib import Path
import tempfile
import unittest

from src.rag_pipeline.configuration import ConfigurationError, load_chunking_components
from src.rag_pipeline.chunking import ChunkConfig, NomicEmbeddingTokenizer, TokenizerConfigurationError


ROOT = Path(__file__).resolve().parents[1]
TOKENIZER_PATH = ROOT / "assets" / "tokenizers" / "nomic-embed-text-v1.5" / "tokenizer.json"
TOKENIZER_SHA256 = "d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66"


class ModelTokenizerTests(unittest.TestCase):
    def test_tokenizer_asset_hash_and_embedding_configuration_are_pinned(self):
        tokenizer, config, strategy, raw_config = load_chunking_components(
            ROOT, ROOT / "configs" / "chunking.json", ROOT / "configs" / "embedding.json",
        )
        self.assertEqual(tokenizer.sha256, TOKENIZER_SHA256)
        self.assertEqual(tokenizer.identifier, "nomic-ai/nomic-embed-text-v1.5@e9b6763023c676ca8431644204f50c2b100d9aab")
        self.assertEqual(tokenizer.max_context_tokens, 2048)
        self.assertEqual(strategy, "heading_aware")
        self.assertEqual(config.max_tokens, 512)

    def test_tokenizer_reports_model_special_tokens_and_preserves_text_windows(self):
        tokenizer = NomicEmbeddingTokenizer(TOKENIZER_PATH, TOKENIZER_SHA256)
        text = "Def KeepCase(value):\n    return value + 1"
        encoded = tokenizer.encode(text)
        self.assertEqual(tokenizer.count(text), len(encoded) + 2)
        self.assertEqual(tokenizer.decode(encoded), text)
        window = encoded[2:8]
        self.assertEqual(tokenizer.decode(window), text[encoded[2].start:encoded[7].end])

    def test_unknown_long_runs_use_a_conservative_character_budget(self):
        tokenizer = NomicEmbeddingTokenizer(TOKENIZER_PATH, TOKENIZER_SHA256)
        text = "x" * 200
        encoded = tokenizer.encode(text)
        self.assertGreaterEqual(len(encoded), len(text))
        self.assertGreaterEqual(tokenizer.count(text), len(text) + 2)
        self.assertEqual(tokenizer.decode(encoded), text)

    def test_tokenizer_context_budget_includes_cls_and_sep(self):
        tokenizer = NomicEmbeddingTokenizer(TOKENIZER_PATH, TOKENIZER_SHA256, max_context_tokens=1024)
        config = ChunkConfig(max_tokens=1023, overlap_tokens=0, child_max_tokens=100, parent_max_tokens=100)
        with self.assertRaisesRegex(TokenizerConfigurationError, "special tokens"):
            tokenizer.validate_config(config)

    def test_tampered_tokenizer_asset_is_rejected(self):
        with self.assertRaisesRegex(TokenizerConfigurationError, "checksum"):
            NomicEmbeddingTokenizer(TOKENIZER_PATH, "0" * 64)

    def test_chunking_loader_rejects_embedding_model_digest_mismatch(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "chunking.json"
            config = json.loads((ROOT / "configs" / "chunking.json").read_text(encoding="utf-8-sig"))
            config["tokenizer"]["embedding_model_digest"] = "0" * 64
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ConfigurationError, "not pinned"):
                load_chunking_components(ROOT, path, ROOT / "configs" / "embedding.json")


if __name__ == "__main__":
    unittest.main()
