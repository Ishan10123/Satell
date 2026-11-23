"""Build a local BM25 snapshot from Qdrant without changing the collection."""

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rag_pipeline.configuration import load_chunking_components, load_embedding_provider
from rag_pipeline.retrieval import build_sparse_index, sparse_index_directory
from rag_pipeline.storage import QdrantVectorStore
from rag_pipeline.storage.index_manifest import validate_index_manifest


def main() -> int:
    config = json.loads((PROJECT_ROOT / "configs" / "indexing.json").read_text(encoding="utf-8-sig"))
    embedding = load_embedding_provider(PROJECT_ROOT / "configs" / "embedding.json")
    from rag_pipeline.embeddings import EmbeddingDescriptor
    descriptor = EmbeddingDescriptor("ollama", embedding.spec.model_name, embedding.spec.model_digest,
                                     embedding.spec.dimensions, True, None)
    store = QdrantVectorStore(PROJECT_ROOT, config["collection_name"], descriptor,
                              config["chunking_version"], qdrant_url=config["qdrant_url"])
    try:
        tokenizer, _settings, _strategy, chunking = load_chunking_components(
            PROJECT_ROOT, PROJECT_ROOT / "configs" / "chunking.json", PROJECT_ROOT / "configs" / "embedding.json",
        )
        readiness = validate_index_manifest(
            store, PROJECT_ROOT, tokenizer, chunking,
            PROJECT_ROOT / "knowledge_base" / "metadata" / "ingestion_inventory.jsonl",
        )
        report = build_sparse_index(store, PROJECT_ROOT, readiness)
        report["directory"] = str(sparse_index_directory(PROJECT_ROOT, report["index_id"]))
        report["qdrant_modified"] = False
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    finally:
        store.close()
        embedding.close()


if __name__ == "__main__":
    raise SystemExit(main())
