"""Run a synthetic end-to-end smoke check without reading the knowledge base."""

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import uuid
import warnings

from qdrant_client import QdrantClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rag_pipeline.configuration import load_embedding_provider, load_generator  # noqa: E402
from rag_pipeline.retrieval import ContextAssembler, DenseRetriever  # noqa: E402
from rag_pipeline.service import LocalRAGService  # noqa: E402
from rag_pipeline.storage import AccessScope, QdrantVectorStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live-qdrant",
        action="store_true",
        help="Use the local Qdrant service with a temporary collection that is deleted after the run.",
    )
    args = parser.parse_args()
    sample = "Synthetic hardware manual: The supported GPU memory safety budget for this demonstration is exactly 8 GiB."
    samples = [
        sample,
        "Synthetic manual says this GPU budget is 8 GiB, but this passage belongs to another tenant.",
        "Synthetic manual says this GPU budget is 8 GiB, but this passage is private to another user.",
        "Synthetic manual says this GPU budget is 8 GiB, but this source is not approved for this query.",
    ]
    collection_name = f"rag_synthetic_{uuid.uuid4().hex[:10]}" if args.live_qdrant else "synthetic_e2e_v1"
    client = QdrantClient(url="http://127.0.0.1:6333", timeout=10) if args.live_qdrant else QdrantClient(":memory:")
    preexisting = client.collection_exists(collection_name)
    if preexisting:
        client.close()
        raise RuntimeError("Generated validation collection name already exists; refusing to modify it.")
    try:
        with (
            TemporaryDirectory(prefix="rag-synthetic-") as temp_dir,
            load_embedding_provider(PROJECT_ROOT / "configs" / "embedding.json") as embedding,
            load_generator(PROJECT_ROOT / "configs" / "generation.json") as generator,
        ):
            vector_batch = embedding.embed(samples)
            store = QdrantVectorStore(
                temp_dir,
                collection_name,
                vector_batch.descriptor,
                "synthetic-chunk-v1",
                client=client,
            )
            chunks = []
            metadata_records = []
            for index, text in enumerate(samples):
                chunks.append({
                    "chunk_id": f"synthetic-chunk-{index + 1}",
                    "content_id": f"synthetic-document-{index + 1}",
                    "text": text,
                    "segments": [],
                    "heading_paths": [["Hardware"]],
                    "page_references": [1],
                    "parent_chunk_id": None,
                })
                metadata_records.append({
                    "tenant_id": "tenant-local",
                    "source_id": "synthetic-source",
                    "document_id": f"synthetic-document-{index + 1}",
                    "acl_principals": ["user:local"],
                    "license_review_status": "approved",
                    "source_type": "synthetic",
                    "title": "Synthetic Hardware Manual",
                    "content_hash": f"sha256:synthetic-{index + 1}",
                    "document_version": "1",
                    "ingestion_timestamp": "2026-11-15T00:00:00Z",
                })
            metadata_records[1]["tenant_id"] = "tenant-other"
            metadata_records[2]["acl_principals"] = ["user:other"]
            metadata_records[3]["source_id"] = "source-not-allowed"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                store.upsert_chunks(chunks, vector_batch.vectors, metadata_records)
            service = LocalRAGService(DenseRetriever(embedding, store), ContextAssembler(max_budget=2500), generator)
            result = service.answer(
                "According to the synthetic hardware manual, what is the GPU memory safety budget?",
                AccessScope("tenant-local", ("user:local",), ("synthetic-source",)),
            )
            if result.retrieved_count != 1:
                raise RuntimeError(f"Expected exactly one authorized result, got {result.retrieved_count}.")
            health = store.health_check()
            deleted = store.delete_document("tenant-local", "synthetic-document-1")
            remaining = client.count(collection_name, exact=True).count
            if deleted != 1 or remaining != len(samples) - 1:
                raise RuntimeError("Tenant-scoped document deletion did not preserve unrelated points.")
            print(json.dumps({
                "answer": result.answer,
                "citations": [citation["citation_id"] for citation in result.citations],
                "retrieved_count": result.retrieved_count,
                "embedding_dimensions": vector_batch.descriptor.dimensions,
                "generation_ms": round(result.generation.elapsed_ms, 1) if result.generation else None,
                "qdrant_status": health["status"],
                "authorization_check": "1 authorized result; other tenant, ACL principal, and source filtered",
                "scoped_deletion": "1 test document deleted; unrelated synthetic points remained until collection cleanup",
                "storage": "temporary local Qdrant collection; removed after run" if args.live_qdrant else "in-memory Qdrant; no persistent index written",
                "corpus": "synthetic only; knowledge_base was not accessed",
            }, indent=2))
            return 0 if result.citations else 1
    finally:
        if args.live_qdrant and client.collection_exists(collection_name) and not preexisting:
            client.delete_collection(collection_name)
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
