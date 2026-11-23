"""Check local conservative token budgets against actual Ollama input counts."""

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rag_pipeline.chunking import NomicEmbeddingTokenizer  # noqa: E402
from rag_pipeline.configuration import load_embedding_provider, load_chunking_components  # noqa: E402


def main() -> int:
    tokenizer, _, _, _ = load_chunking_components(
        PROJECT_ROOT,
        PROJECT_ROOT / "configs" / "chunking.json",
        PROJECT_ROOT / "configs" / "embedding.json",
    )
    samples = [
        "This is a tokenizer validation example.",
        "def calculate_total(items: list[int]) -> int:\n    return sum(items)",
        "RAG uses retrieval-augmented generation; query_key=HTTPResponse(404).",
        "Unicode café naïve résumé — 東京 中文",
        "  leading and trailing spaces\n\nmultiple lines  ",
        "[CLS] [SEP] [UNK] special-token collision test",
        "https://example.org/a?x=1&y=two",
        "The Nomic BERT tokenizer should be tested against the local Ollama runtime.",
    ]
    mismatches = []
    with load_embedding_provider(PROJECT_ROOT / "configs" / "embedding.json") as provider:
        provider.health_check()
        for index, text in enumerate(samples):
            local_count = tokenizer.count(text)
            actual = provider.embed([text]).input_token_count
            safe = actual is not None and actual <= local_count
            record = {"sample_id": index + 1, "conservative_local_token_budget": local_count,
                      "ollama_prompt_eval_count": actual, "within_budget": safe}
            print(json.dumps(record))
            if not safe:
                mismatches.append(index + 1)
    print(json.dumps({"samples": len(samples), "mismatches": mismatches, "tokenizer": tokenizer.identifier}))
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
