import unittest

from src.rag_pipeline.chunking import ChunkConfig, benchmark_chunking_strategies, chunk_document


class CharacterTokenizer:
    def encode(self, text):
        return list(text)

    def decode(self, tokens):
        return "".join(tokens)


class ChunkingTests(unittest.TestCase):
    def setUp(self):
        self.tokenizer = CharacterTokenizer()
        self.content = {
            "content_id": "normalized-content-id",
            "segments": [
                {"text": "First section text.", "segment_type": "text", "headings": ["Guide", "First"]},
                {"text": "Second section text.", "segment_type": "text", "headings": ["Guide", "Second"]},
            ],
        }
        self.provenance = {
            "document_id": "document-id",
            "segment_page_numbers": [2, 3],
        }

    def test_fixed_windows_obey_budget_and_have_configured_overlap(self):
        content = {"content_id": "c", "segments": [{"text": "abcdefghijklmnop", "segment_type": "text", "headings": []}]}
        provenance = {"document_id": "d", "segment_page_numbers": [None]}
        chunks = chunk_document(content, provenance, self.tokenizer, "fixed", ChunkConfig(max_tokens=6, overlap_tokens=2))
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk.token_count <= 6 for chunk in chunks))
        self.assertEqual(chunks[0].text[-2:], chunks[1].text[:2])
        self.assertEqual(chunks, chunk_document(content, provenance, self.tokenizer, "fixed", ChunkConfig(max_tokens=6, overlap_tokens=2)))

    def test_fixed_character_strategy_uses_character_budget(self):
        content = {"content_id": "c", "segments": [{"text": "abcdefghijklmnop", "segment_type": "text", "headings": []}]}
        provenance = {"document_id": "d", "segment_page_numbers": [None]}
        config = ChunkConfig(max_tokens=100, overlap_tokens=0, max_characters=6, overlap_characters=2)
        chunks = chunk_document(content, provenance, self.tokenizer, "fixed_size", config)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk.text) <= 6 for chunk in chunks))
        self.assertEqual(chunks[0].text[-2:], chunks[1].text[:2])

    def test_recursive_strategy_splits_large_segments_at_structural_boundaries(self):
        content = {"content_id": "c", "segments": [{"text": "alpha beta\n\ngamma delta\n\nepsilon zeta", "segment_type": "text", "headings": []}]}
        provenance = {"document_id": "d", "segment_page_numbers": [None]}
        chunks = chunk_document(content, provenance, self.tokenizer, "recursive", ChunkConfig(max_tokens=13, overlap_tokens=0))
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk.token_count <= 13 for chunk in chunks))
        self.assertIn("alpha beta", chunks[0].text)

    def test_heading_aware_strategy_keeps_sections_separate(self):
        config = ChunkConfig(max_tokens=100, overlap_tokens=0)
        fixed = chunk_document(self.content, self.provenance, self.tokenizer, "fixed", config)
        aware = chunk_document(self.content, self.provenance, self.tokenizer, "heading_aware", config)
        self.assertEqual(len(fixed), 1)
        self.assertEqual(len(aware), 2)
        self.assertEqual(aware[0].page_references, [2])
        self.assertEqual(aware[1].heading_paths, [["Guide", "Second"]])

    def test_code_segments_keep_indentation_and_are_not_split_under_budget(self):
        content = {"content_id": "c", "segments": [{"text": "    if ready:\n        execute()", "segment_type": "code", "headings": ["Example"]}]}
        provenance = {"document_id": "d", "segment_page_numbers": [4]}
        chunks = chunk_document(content, provenance, self.tokenizer, "heading_aware", ChunkConfig(max_tokens=40, overlap_tokens=0))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].segments[0]["text"], "    if ready:\n        execute()")
        self.assertEqual(chunks[0].segments[0]["segment_type"], "code")

    def test_oversized_code_is_split_only_at_line_boundaries_when_possible(self):
        code = "if ready:\n    start()\n    finish()"
        content = {"content_id": "c", "segments": [{"text": code, "segment_type": "code", "headings": []}]}
        provenance = {"document_id": "d", "segment_page_numbers": [None]}
        chunks = chunk_document(content, provenance, self.tokenizer, "fixed", ChunkConfig(max_tokens=13, overlap_tokens=0))
        flattened = "".join(segment["text"] for chunk in chunks for segment in chunk.segments)
        self.assertEqual(flattened, code)
        self.assertTrue(all(not chunk.oversized for chunk in chunks))

    def test_overlong_code_line_stays_intact_and_is_marked_oversized(self):
        content = {"content_id": "c", "segments": [{"text": "long_identifier()", "segment_type": "code", "headings": []}]}
        provenance = {"document_id": "d", "segment_page_numbers": [None]}
        chunks = chunk_document(content, provenance, self.tokenizer, "token_based", ChunkConfig(max_tokens=5, overlap_tokens=0))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].text, "long_identifier()")
        self.assertTrue(chunks[0].oversized)

    def test_semantic_strategy_requires_callback_and_honors_boundaries(self):
        with self.assertRaisesRegex(ValueError, "requires a local similarity callback"):
            chunk_document(self.content, self.provenance, self.tokenizer, "semantic")
        chunks = chunk_document(
            self.content,
            self.provenance,
            self.tokenizer,
            "semantic",
            ChunkConfig(max_tokens=100, overlap_tokens=0, semantic_similarity_threshold=0.5),
            semantic_similarity=lambda left, right: 0.0,
        )
        self.assertEqual(len(chunks), 2)

    def test_parent_child_chunks_have_complete_parent_links(self):
        content = {"content_id": "c", "segments": [
            {"text": "alpha beta gamma delta epsilon", "segment_type": "text", "headings": ["A"]},
            {"text": "zeta eta theta iota kappa", "segment_type": "text", "headings": ["B"]},
        ]}
        provenance = {"document_id": "d", "segment_page_numbers": [1, 2]}
        chunks = chunk_document(
            content,
            provenance,
            self.tokenizer,
            "parent_child",
            ChunkConfig(max_tokens=30, overlap_tokens=2, child_max_tokens=12, parent_max_tokens=30),
        )
        parents = {chunk.chunk_id: chunk for chunk in chunks if chunk.strategy == "parent"}
        children = [chunk for chunk in chunks if chunk.strategy == "child"]
        self.assertTrue(parents and children)
        for child in children:
            self.assertIn(child.parent_chunk_id, parents)
            self.assertIn(child.chunk_id, parents[child.parent_chunk_id].child_chunk_ids)
            self.assertLessEqual(child.token_count, 12)

    def test_benchmark_reports_size_and_runtime_without_quality_claims(self):
        results = benchmark_chunking_strategies(
            self.content,
            self.provenance,
            self.tokenizer,
            strategies=("fixed_size", "token_based", "recursive", "heading_aware"),
            config=ChunkConfig(max_tokens=18, overlap_tokens=2),
        )
        self.assertEqual([result.strategy for result in results], ["fixed_size", "token_based", "recursive", "heading_aware"])
        self.assertTrue(all(result.elapsed_ms >= 0 and result.chunk_count > 0 for result in results))
        self.assertTrue(all(result.max_tokens > 0 for result in results))

    def test_token_budget_configuration_is_validated(self):
        with self.assertRaises(ValueError):
            ChunkConfig(max_tokens=10, overlap_tokens=10)


if __name__ == "__main__":
    unittest.main()