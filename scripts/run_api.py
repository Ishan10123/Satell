"""Start the authenticated local API after its managed Qdrant index is ready."""

import os
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rag_pipeline.api import MAX_QUERY_CHARACTERS, create_app  # noqa: E402
from rag_pipeline.generation.evaluation_artifact import EvaluationArtifactStore  # noqa: E402
from rag_pipeline.configuration import load_embedding_provider, load_generator, load_chunking_components  # noqa: E402
from rag_pipeline.embeddings import EmbeddingDescriptor  # noqa: E402
from rag_pipeline.retrieval import (BM25Retriever, ContextAssembler, DenseRetriever, HybridRetriever,
                                    LocalCrossEncoderReranker, sparse_index_directory)  # noqa: E402
from rag_pipeline.service import LocalRAGService  # noqa: E402
from rag_pipeline.storage import QdrantVectorStore  # noqa: E402
from rag_pipeline.storage.index_manifest import validate_index_manifest  # noqa: E402
from rag_pipeline.ingestion.approval_workflow import load_approval_paths  # noqa: E402


def required_environment(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"Required environment variable is not set: {name}")
    return value


def main() -> None:
    api_token = required_environment("RAG_API_TOKEN")
    tenant_id = required_environment("RAG_TENANT_ID")
    principal_id = required_environment("RAG_PRINCIPAL_ID")
    index_config = json.loads((PROJECT_ROOT / "configs" / "indexing.json").read_text(encoding="utf-8-sig"))
    collection_name = os.environ.get("RAG_QDRANT_COLLECTION", index_config["collection_name"])
    chunking_version = os.environ.get("RAG_CHUNKING_VERSION", index_config["chunking_version"])
    port = int(os.environ.get("RAG_API_PORT", "8000"))
    if not 1024 <= port <= 65535:
        raise RuntimeError("RAG_API_PORT must be between 1024 and 65535.")
    bind_host = os.environ.get("RAG_API_BIND_HOST", "127.0.0.1")
    if bind_host not in {"127.0.0.1", "0.0.0.0"}:
        raise RuntimeError("RAG_API_BIND_HOST must be loopback or the container wildcard address.")

    ollama_base_url = os.environ.get("RAG_OLLAMA_BASE_URL")
    embedding = load_embedding_provider(PROJECT_ROOT / "configs" / "embedding.json", base_url=ollama_base_url)
    generator = load_generator(PROJECT_ROOT / "configs" / "generation.json", base_url=ollama_base_url)
    retrieval_config = json.loads((PROJECT_ROOT / "configs" / "retrieval.json").read_text(encoding="utf-8-sig"))
    configured_query_limit = retrieval_config.get("query_max_characters", MAX_QUERY_CHARACTERS)
    if configured_query_limit != MAX_QUERY_CHARACTERS:
        raise RuntimeError("retrieval.json query_max_characters must match the API query limit.")
    tokenizer, chunk_config, strategy, _chunking = load_chunking_components(
        PROJECT_ROOT, PROJECT_ROOT / "configs" / "chunking.json", PROJECT_ROOT / "configs" / "embedding.json",
    )
    qdrant_url = os.environ.get("RAG_QDRANT_URL", index_config["qdrant_url"])
    descriptor = EmbeddingDescriptor(
        provider="ollama",
        model_name=embedding.spec.model_name,
        model_digest=embedding.spec.model_digest,
        dimensions=embedding.spec.dimensions,
        vectors_are_unit_normalized=True,
        runtime_version=None,
    )
    store = QdrantVectorStore(
        PROJECT_ROOT,
        collection_name,
        descriptor,
        chunking_version,
        qdrant_url=qdrant_url,
    )
    retrieval_mode = retrieval_config.get("strategy", "dense")
    hybrid = None
    reranker = None
    candidate_limit = retrieval_config.get("candidate_top_k", 30)
    if retrieval_mode in {"hybrid", "hybrid_rerank"}:
        manifest = json.loads((PROJECT_ROOT / "knowledge_base" / "metadata" / "index_manifests" / f"{collection_name}.json").read_text(encoding="utf-8-sig"))
        sparse = BM25Retriever(sparse_index_directory(PROJECT_ROOT, manifest["index_id"]))
        hybrid = HybridRetriever(DenseRetriever(embedding, store, max_query_characters=configured_query_limit), sparse, retrieval_config.get("rrf_constant", 60))
    if retrieval_mode == "hybrid_rerank":
        rerank_config = retrieval_config.get("reranker", {})
        if not rerank_config.get("enabled"):
            raise RuntimeError("hybrid_rerank retrieval requires reranker.enabled=true in configs/retrieval.json.")
        reranker = LocalCrossEncoderReranker(
            PROJECT_ROOT / Path(rerank_config["artifact"]).parent,
            batch_size=rerank_config.get("batch_size", 16), max_length=rerank_config.get("max_length", 256),
        )
    # Production remains blocked until a reviewed index passes readiness. The
    # local academic demo is a separate opt-in policy with its own signed allowlist.
    service = LocalRAGService(
        DenseRetriever(embedding, store, max_query_characters=configured_query_limit),
        ContextAssembler(max_budget=retrieval_config.get("max_evidence_context_bytes", 2500), max_chunks=8),
        generator,
        retrieval_mode=retrieval_mode,
        hybrid_retriever=hybrid,
        reranker=reranker,
        candidate_limit=candidate_limit,
        comparison_source_cap=retrieval_config.get("comparison_diversity", {}).get("max_per_source", 4),
        comparison_document_cap=retrieval_config.get("comparison_diversity", {}).get("max_per_document", 2),
        comparison_diversity_enabled=retrieval_config.get("comparison_diversity", {}).get("enabled", False),
        comparison_terms=tuple(retrieval_config.get("comparison_diversity", {}).get("terms", ())),
        comparison_context_group_budget_tokens=retrieval_config.get("comparison_diversity", {}).get("context_group_budget_tokens", 1200),
        comparison_source_aliases={key: tuple(value) for key, value in retrieval_config.get("comparison_diversity", {}).get("source_aliases", {}).items()},
    )
    diagnostics_enabled = os.environ.get("RAG_EVALUATION_DIAGNOSTICS_ENABLED", "0")
    if diagnostics_enabled not in {"0", "1"}:
        raise RuntimeError("RAG_EVALUATION_DIAGNOSTICS_ENABLED must be 0 or 1.")
    evaluation_artifact_store = None
    if diagnostics_enabled == "1":
        artifact_path = os.environ.get(
            "RAG_EVALUATION_ARTIFACT_PATH",
            "knowledge_base/logs/phase4b_evaluation_diagnostics.jsonl",
        )
        evaluation_artifact_store = EvaluationArtifactStore(
            artifact_path,
            PROJECT_ROOT,
            max_records=int(os.environ.get("RAG_EVALUATION_MAX_RECORDS", "200")),
            max_bytes=int(os.environ.get("RAG_EVALUATION_MAX_BYTES", "10000000")),
        )
    app = create_app(
        service,
        api_token=api_token,
        tenant_id=tenant_id,
        principal_id=principal_id,
        approval_registry_path=PROJECT_ROOT / "knowledge_base" / "metadata" / "source_approvals.json",
        document_approval_registry_path=load_approval_paths(PROJECT_ROOT)["document_registry"],
        project_root=PROJECT_ROOT,
        authorization_mode=os.environ.get("RAG_AUTHORIZATION_MODE", "production"),
        local_academic_demo_enabled=os.environ.get("RAG_LOCAL_ACADEMIC_DEMO_ENABLED", "0") == "1",
        local_academic_demo_registry_path=PROJECT_ROOT / "knowledge_base" / "metadata" / "local_academic_demo_document_authorizations_phase1_v3.json",
        local_academic_demo_source_registry_path=PROJECT_ROOT / "knowledge_base" / "metadata" / "local_academic_demo_source_authorizations_phase1_v3.json",
        local_academic_demo_policy_path=PROJECT_ROOT / "configs" / "local_academic_demo_policy.json",
        evaluation_artifact_store=evaluation_artifact_store,
        evaluation_model_configuration={
            "model_name": generator.model_name,
            "context_window_tokens": generator.context_window_tokens,
            "output_tokens": generator.max_output_tokens,
            "safety_margin_tokens": generator.input_safety_margin_tokens,
        },
        index_validator=lambda: validate_index_manifest(
            store, PROJECT_ROOT, tokenizer, _chunking,
            PROJECT_ROOT / "knowledge_base" / "metadata" / "ingestion_inventory.jsonl",
        ),
    )

    import uvicorn

    # Keep the API private to this host. External exposure needs a different auth/TLS deployment.
    uvicorn.run(app, host=bind_host, port=port, access_log=False, server_header=False)


if __name__ == "__main__":
    main()
