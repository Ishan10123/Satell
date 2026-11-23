"""Local ONNX cross-encoder reranking for a bounded candidate list."""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
from pathlib import Path
import re
import time
from typing import Callable, Sequence

import numpy as np

from .hybrid import HybridSearchHit


MODEL_SHA256 = "b585f2d0cb5dac59d28334df5b9badc0417dced4626c86a9815c4c6b78a86ba1"
TOKENIZER_SHA256 = "d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66"


@dataclass(frozen=True)
class RerankResult:
    hits: tuple[HybridSearchHit, ...]
    elapsed_ms: float
    model_id: str


class LocalCrossEncoderReranker:
    """Score (query, passage) pairs locally; never loads remote model code."""

    def __init__(self, model_dir: Path, *, batch_size: int = 16, max_length: int = 256,
                 scorer: Callable[[str, Sequence[str]], Sequence[float]] | None = None) -> None:
        if batch_size < 1 or batch_size > 64:
            raise ValueError("Reranker batch_size must be between 1 and 64.")
        if max_length < 16 or max_length > 512:
            raise ValueError("Reranker max_length must be between 16 and 512.")
        self.model_dir = Path(model_dir)
        self.batch_size = batch_size
        self.max_length = max_length
        self.scorer = scorer or self._load_local_scorer()

    def _load_local_scorer(self):
        model_path = self.model_dir / "model_O4.onnx"
        tokenizer_path = self.model_dir / "tokenizer.json"
        if not model_path.is_file() or not tokenizer_path.is_file():
            raise FileNotFoundError(f"Reranker model files are missing under {self.model_dir}.")
        with model_path.open("rb") as model_file:
            digest = hashlib.file_digest(model_file, "sha256").hexdigest()
        if digest != MODEL_SHA256:
            raise ValueError("Reranker ONNX model checksum does not match the pinned model revision.")
        if model_path.stat().st_size > 50 * 1024 * 1024 or tokenizer_path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("Reranker model assets exceed configured size limits.")
        with tokenizer_path.open("rb") as tokenizer_file:
            tokenizer_digest = hashlib.file_digest(tokenizer_file, "sha256").hexdigest()
        if tokenizer_digest != TOKENIZER_SHA256:
            raise ValueError("Reranker tokenizer checksum does not match the pinned model revision.")
        import onnxruntime as ort
        from tokenizers import Tokenizer

        tokenizer = Tokenizer.from_file(str(tokenizer_path))
        session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        input_names = {item.name for item in session.get_inputs()}
        required = {"input_ids", "attention_mask", "token_type_ids"}
        if not required.issubset(input_names):
            raise ValueError(f"Unexpected reranker model inputs: {sorted(input_names)}")

        def score(query: str, passages: Sequence[str]) -> Sequence[float]:
            scores: list[float] = []
            for start in range(0, len(passages), self.batch_size):
                batch = passages[start:start + self.batch_size]
                tokenizer.enable_truncation(max_length=self.max_length)
                tokenizer.enable_padding(pad_id=0, pad_token="[PAD]", length=None)
                encoded = tokenizer.encode_batch([(query, passage) for passage in batch])
                ids = np.asarray([item.ids for item in encoded], dtype=np.int64)
                masks = np.asarray([item.attention_mask for item in encoded], dtype=np.int64)
                types = np.asarray([item.type_ids for item in encoded], dtype=np.int64)
                logits = session.run(["logits"], {
                    "input_ids": ids, "attention_mask": masks, "token_type_ids": types,
                })[0]
                values = np.asarray(logits, dtype=np.float32).reshape(-1)
                if len(values) != len(batch) or not np.isfinite(values).all():
                    raise ValueError("Reranker returned invalid scores.")
                scores.extend(float(value) for value in values)
            return scores

        return score

    @staticmethod
    def is_comparison_query(query: str, terms: Sequence[str] | None = None) -> bool:
        configured = terms or ("compare", "comparison", "contrast", "difference", "differ", "versus", "vs", "between", "relate", "relationship")
        alternatives = "|".join(re.escape(term) for term in configured if isinstance(term, str) and term)
        return bool(alternatives and re.search(rf"\b(?:{alternatives})\b", query, re.I))

    @staticmethod
    def expected_comparison_sources(query: str, aliases: dict[str, Sequence[str]]) -> tuple[str, ...]:
        folded = query.casefold()
        expected = []
        for source_id, source_aliases in aliases.items():
            if any(isinstance(alias, str) and alias and re.search(
                rf"(?<!\w){re.escape(alias.casefold())}(?!\w)", folded
            ) for alias in source_aliases):
                expected.append(source_id)
        return tuple(sorted(set(expected)))

    @classmethod
    def comparison_evidence_complete(cls, query: str, citations, aliases: dict[str, Sequence[str]]) -> bool:
        expected_sources = cls.expected_comparison_sources(query, aliases)
        observed_sources = {citation.source_id for citation in citations}
        if len(expected_sources) >= 2:
            return set(expected_sources).issubset(observed_sources)
        return len({citation.document_id for citation in citations}) >= 2

    def rerank(self, query: str, hits: Sequence[HybridSearchHit], limit: int = 8, *,
               max_per_source: int | None = None, max_per_document: int | None = None) -> RerankResult:
        if not query.strip():
            raise ValueError("Reranker query must not be empty.")
        if not 1 <= limit <= 100:
            raise ValueError("Reranker result limit must be between 1 and 100.")
        started = time.perf_counter()
        candidates = tuple(hits[:100])
        if not candidates:
            return RerankResult((), (time.perf_counter() - started) * 1000,
                                "cross-encoder/ms-marco-MiniLM-L2-v2")
        passages = [str(hit.payload.get("chunk_text") or "") for hit in candidates]
        scores = tuple(self.scorer(query, passages))
        if len(scores) != len(candidates):
            raise ValueError("Reranker returned a different number of scores than candidates.")
        if not all(np.isfinite(float(score)) for score in scores):
            raise ValueError("Reranker returned a non-finite score.")
        rescored = [(replace(hit, rerank_score=float(score)), hit.rank) for hit, score in zip(candidates, scores)]
        rescored.sort(key=lambda pair: (-float(pair[0].rerank_score), pair[1], pair[0].chunk_id))
        if max_per_source is not None and max_per_source < 1 or max_per_document is not None and max_per_document < 1:
            raise ValueError("Diversity caps must be positive when provided.")
        if max_per_source is None and max_per_document is None:
            chosen = rescored[:limit]
        else:
            chosen = []
            source_counts: dict[str, int] = {}
            document_counts: dict[str, int] = {}
            deferred = []
            for pair in rescored:
                hit = pair[0]
                source = hit.source_id
                document = hit.document_id
                if ((max_per_source is not None and source_counts.get(source, 0) >= max_per_source)
                        or (max_per_document is not None and document_counts.get(document, 0) >= max_per_document)):
                    deferred.append(pair)
                    continue
                chosen.append(pair)
                source_counts[source] = source_counts.get(source, 0) + 1
                document_counts[document] = document_counts.get(document, 0) + 1
                if len(chosen) == limit:
                    break
            if len(chosen) < limit:
                chosen.extend(deferred[:limit - len(chosen)])
            chosen = chosen[:limit]
            chosen.sort(key=lambda pair: (-float(pair[0].rerank_score), pair[1], pair[0].chunk_id))
        ranked = tuple(replace(hit, rank=rank) for rank, (hit, _old_rank) in enumerate(chosen, start=1))
        return RerankResult(ranked, (time.perf_counter() - started) * 1000,
                            "cross-encoder/ms-marco-MiniLM-L2-v2")
