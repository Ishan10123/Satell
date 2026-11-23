"""Opt-in, bounded local evaluation diagnostics; never part of an API response."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any


class EvaluationArtifactStore:
    """Store restricted evaluation records under the project root with FIFO bounds."""

    def __init__(self, path: str | Path, project_root: str | Path,
                 max_records: int = 200, max_bytes: int = 10_000_000) -> None:
        if not 1 <= max_records <= 10_000 or not 4096 <= max_bytes <= 100_000_000:
            raise ValueError("Evaluation artifact retention bounds are invalid.")
        root = Path(project_root).resolve(strict=True)
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = root / candidate
        # Resolve the parent but reject a symlink at the target itself.
        parent = candidate.parent.resolve()
        if parent != root and root not in parent.parents:
            raise ValueError("Evaluation artifact path must remain inside the project root.")
        if candidate.exists() and candidate.is_symlink():
            raise ValueError("Evaluation artifact file cannot be a symbolic link.")
        self.path = parent / candidate.name
        self.root = root
        self.max_records = max_records
        self.max_bytes = max_bytes
        self._lock = threading.RLock()
        parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(parent, 0o700)
        except OSError:
            pass

    def record_result(self, *, request_id: str, query: str, result: Any,
                      model_configuration: dict[str, Any] | None = None) -> None:
        generation = getattr(result, "generation", None)
        error = getattr(result, "generation_error", None)
        diagnostics = getattr(result, "diagnostics", {})
        diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
        self._write({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "question": query[:5000],
            "response_status": getattr(result, "verification_status", "not_reported"),
            "answer": getattr(result, "answer", "")[:32_000],
            "retrieval": _retrieval_diagnostics(diagnostics),
            "stage_timings_ms": _safe_timings(getattr(result, "timings_ms", {})),
            "raw_generated_answer": (getattr(generation, "raw_generated_answer", None)
                                     or getattr(error, "raw_generated_answer", None)),
            "parsed_claims": _json_value(getattr(generation, "parsed_claims", ())
                                          or getattr(error, "parsed_claims", ()))[:100],
            "parsed_citation_ids": _json_value(getattr(generation, "parsed_citation_ids", ())
                                               or getattr(error, "parsed_citation_ids", ()))[:100],
            "citation_mapping": _json_value(getattr(generation, "citation_mapping", ())
                                            or getattr(error, "citation_mapping", ()))[:100],
            "citation_validation": {
                "status": getattr(result, "diagnostics", {}).get("citation_validation_status"),
                "failure_code": getattr(result, "diagnostics", {}).get("failure_code"),
                "failure_reason": getattr(result, "diagnostics", {}).get("failure_reason")
                                  or getattr(error, "failure_reason", None),
            },
            "claim_verifier": {
                "overall_verdict": getattr(getattr(generation, "claim_verification", None), "overall_verdict", None)
                                   or _overall(getattr(generation, "claim_verdicts", ())
                                               or getattr(error, "claim_verification", None)),
                "claims": _claim_verdicts(generation, error),
            },
            "consistency_findings": _json_value(getattr(generation, "consistency_findings", ())
                                                or getattr(error, "consistency_findings", ()))[:100],
            "model_configuration": _safe_model_config(model_configuration, generation),
        })

    def record_error(self, *, request_id: str, query: str, error: Exception,
                     model_configuration: dict[str, Any] | None = None) -> None:
        self._write({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "question": query[:5000],
            "response_status": "failed",
            "answer": None,
            "retrieval": _retrieval_diagnostics(getattr(error, "rag_diagnostics", {})),
            "stage_timings_ms": _safe_timings(getattr(error, "rag_timings_ms", {})),
            "generation_timings_ms": {
                key: value for key, value in {
                    "generation": getattr(error, "answer_generation_ms", None),
                    "claim_verification": getattr(error, "claim_verification_ms", None),
                    "total_generation": getattr(error, "total_generation_ms", None),
                }.items() if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0
            },
            "raw_generated_answer": getattr(error, "raw_generated_answer", None),
            "parsed_claims": _json_value(getattr(error, "parsed_claims", ()))[:100],
            "parsed_citation_ids": _json_value(getattr(error, "parsed_citation_ids", ()))[:100],
            "citation_mapping": _json_value(getattr(error, "citation_mapping", ()))[:100],
            "citation_validation": {"failure_code": getattr(error, "error_code", "generation_error"),
                                    "failure_reason": getattr(error, "failure_reason", None)},
            "claim_verifier": {"overall_verdict": _overall(getattr(error, "claim_verification", None)),
                               "claims": _claim_verdicts(None, error)},
            "consistency_findings": _json_value(getattr(error, "consistency_findings", ()))[:100],
            "model_configuration": _safe_model_config(model_configuration, None),
        })

    def _write(self, record: dict[str, Any]) -> None:
        # Refuse target replacement if the path became a symlink after startup.
        with self._lock:
            if self.path.is_symlink():
                raise OSError("Evaluation artifact target changed type.")
            rows = []
            if self.path.exists():
                rows = [line for line in self.path.read_text(encoding="utf-8").splitlines() if line]
            rows.append(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            rows = rows[-self.max_records:]
            while rows and sum(len(item.encode("utf-8")) + 1 for item in rows) > self.max_bytes:
                rows.pop(0)
            data = ("\n".join(rows) + ("\n" if rows else "")).encode("utf-8")
            fd, temp_name = tempfile.mkstemp(prefix=".evaluation-", dir=self.path.parent)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    os.chmod(temp_name, 0o600)
                except OSError:
                    pass
                os.replace(temp_name, self.path)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)


def _json_value(value: Any) -> Any:
    if is_dataclass(value):
        return _json_value(asdict(value))
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()
                if str(key).lower() not in {"text", "passage", "evidence_text", "token", "password", "authorization"}}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _claim_verdicts(generation: Any, error: Any) -> list[dict[str, Any]]:
    rows = getattr(generation, "claim_verdicts", ()) if generation is not None else ()
    run = getattr(error, "claim_verification", None) if error is not None else None
    if not rows and run is not None:
        rows = getattr(run, "verdicts", ())
    return _json_value(rows)[:100]


def _overall(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "overall_verdict"):
        return value.overall_verdict
    statuses = [getattr(item, "status", None) for item in value]
    if statuses and all(status == "supported" for status in statuses):
        return "verified"
    return "partially_verified" if "supported" in statuses else "rejected"


def _safe_model_config(config: dict[str, Any] | None, generation: Any) -> dict[str, Any]:
    safe = {key: value for key, value in (config or {}).items()
            if key in {"model_name", "model_digest", "context_window_tokens", "output_tokens", "safety_margin_tokens"}
            and isinstance(value, (str, int, float, bool, type(None)))}
    if generation is not None:
        safe.setdefault("model_name", getattr(generation, "model_name", None))
        safe.setdefault("verification_model", getattr(generation, "verification_model", None))
        safe.setdefault("context_window_tokens", getattr(generation, "verification_context_window_tokens", None))
        safe.setdefault("output_tokens", getattr(generation, "verification_output_tokens", None))
        safe.setdefault("safety_margin_tokens", getattr(generation, "verification_safety_margin_tokens", None))
    return safe


def _safe_timings(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {key: float(number) for key, number in value.items()
            if isinstance(key, str) and len(key) <= 64 and isinstance(number, (int, float))
            and not isinstance(number, bool) and 0 <= number < 86_400_000}


def _retrieval_diagnostics(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    allowed = {
        "retrieval_strategy", "retrieval_hits", "retrieval_hit_count", "reranker_active",
        "context_chunk_ids", "context_chunk_count", "context_token_estimate", "context_bytes",
        "context_exclusion_count", "context_exclusion_reasons", "context_exclusion_details",
        "citation_validation_status", "claim_verifier_status", "failure_code", "failure_stage",
        "failure_reason", "generation_model", "verification_model", "claim_count",
        "supported_claim_count", "rejected_claim_count", "prompt_tokens_estimated",
    }
    return _json_value({key: value[key] for key in allowed if key in value})
