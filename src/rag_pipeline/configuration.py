import json
from pathlib import Path
import re
from typing import Any

from .embeddings import EmbeddingModelSpec, OllamaEmbeddingProvider
from .generation import OllamaGenerator
from .chunking import ChunkConfig, NomicEmbeddingTokenizer, TokenizerConfigurationError


_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class ConfigurationError(ValueError):
    pass


def _read_config(path: str | Path, expected_version: str = "1.0") -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError("Model configuration could not be read as JSON.") from exc
    if not isinstance(value, dict) or value.get("config_version") != expected_version:
        raise ConfigurationError("Model configuration has an unsupported version or shape.")
    return value


def _required_string(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"Model configuration is missing {key}.")
    return value


def _pinned_digest(config: dict[str, Any]) -> str:
    digest = _required_string(config, "model_digest")
    if not _DIGEST.fullmatch(digest):
        raise ConfigurationError("Model digest must be a 64-character lowercase SHA-256 value.")
    return digest


def load_embedding_provider(config_path: str | Path, *, base_url: str | None = None) -> OllamaEmbeddingProvider:
    config = _read_config(config_path)
    if config.get("provider") != "ollama":
        raise ConfigurationError("Only the local Ollama embedding provider is supported.")
    dimensions = config.get("dimensions")
    if isinstance(dimensions, bool) or not isinstance(dimensions, int) or dimensions < 1:
        raise ConfigurationError("Embedding dimensions must be a positive integer.")
    try:
        spec = EmbeddingModelSpec(
            model_name=_required_string(config, "model_name"),
            model_digest=_pinned_digest(config),
            dimensions=dimensions,
            max_batch_size=config.get("max_batch_size", 16),
            max_input_characters=config.get("max_input_characters", 12000),
        )
        return OllamaEmbeddingProvider(
            spec,
            base_url=base_url or _required_string(config, "base_url"),
            timeout_seconds=config.get("request_timeout_seconds", 60),
            max_retries=config.get("max_retries", 1),
        )
    except (TypeError, ValueError) as exc:
        raise ConfigurationError("Embedding configuration contains invalid values.") from exc


def load_generator(config_path: str | Path, *, base_url: str | None = None) -> OllamaGenerator:
    config = _read_config(config_path)
    if config.get("provider") != "ollama":
        raise ConfigurationError("Only the local Ollama generation provider is supported.")
    if config.get("thinking") is not False or config.get("temperature") != 0:
        raise ConfigurationError("Generation config must disable thinking and use deterministic temperature 0.")
    try:
        return OllamaGenerator(
            model_name=_required_string(config, "model_name"),
            model_digest=_pinned_digest(config),
            base_url=base_url or _required_string(config, "base_url"),
            timeout_seconds=config.get("request_timeout_seconds", 120),
            max_retries=config.get("max_retries", 1),
            max_output_tokens=config.get("max_output_tokens", 512),
            context_window_tokens=config.get("context_window_configured", 4096),
            input_safety_margin_tokens=config.get("input_safety_margin_tokens", 256),
        )
    except (TypeError, ValueError) as exc:
        raise ConfigurationError("Generation configuration contains invalid values.") from exc


def load_chunking_components(
    project_root: str | Path,
    chunking_config_path: str | Path,
    embedding_config_path: str | Path,
) -> tuple[NomicEmbeddingTokenizer, ChunkConfig, str, dict[str, Any]]:
    root = Path(project_root).resolve()
    config = _read_config(chunking_config_path, expected_version="1.2")
    tokenizer_config = config.get("tokenizer")
    if not isinstance(tokenizer_config, dict) or tokenizer_config.get("provider") != "huggingface_tokenizers_json":
        raise ConfigurationError("Chunking configuration must identify a local tokenizer asset.")
    embedding_config = _read_config(embedding_config_path)
    if (
        tokenizer_config.get("embedding_model_name") != embedding_config.get("model_name")
        or tokenizer_config.get("embedding_model_digest") != embedding_config.get("model_digest")
    ):
        raise ConfigurationError("Tokenizer is not pinned to the configured embedding model and digest.")
    if tokenizer_config.get("model_id") != NomicEmbeddingTokenizer.model_id or tokenizer_config.get("revision") != NomicEmbeddingTokenizer.model_revision:
        raise ConfigurationError("Tokenizer model identifier or revision is unsupported.")
    if tokenizer_config.get("library") != "tokenizers" or tokenizer_config.get("library_version") != NomicEmbeddingTokenizer.tokenizer_version:
        raise ConfigurationError("Tokenizer library/version does not match the verified tokenizer asset.")
    asset_path = (root / str(tokenizer_config.get("asset_path", ""))).resolve()
    if not asset_path.is_relative_to(root):
        raise ConfigurationError("Tokenizer asset path escapes the project root.")
    try:
        tokenizer = NomicEmbeddingTokenizer(
            asset_path,
            expected_sha256=str(tokenizer_config.get("asset_sha256", "")),
            max_context_tokens=int(tokenizer_config.get("context_tokens", 0)),
        )
        chunk_config = ChunkConfig(
            max_tokens=config["max_tokens"],
            overlap_tokens=config["overlap_tokens"],
            child_max_tokens=config["child_max_tokens"],
            parent_max_tokens=config["parent_max_tokens"],
            semantic_similarity_threshold=config["semantic_similarity_threshold"],
            max_characters=config["max_characters"],
            overlap_characters=config["overlap_characters"],
        )
        tokenizer.validate_config(chunk_config)
    except (KeyError, TypeError, ValueError, TokenizerConfigurationError) as exc:
        raise ConfigurationError("Chunking or tokenizer configuration is invalid.") from exc
    strategy = config.get("default_strategy")
    if not isinstance(strategy, str) or strategy not in {"fixed", "fixed_size", "token_based", "recursive", "heading_aware", "semantic", "parent_child"}:
        raise ConfigurationError("Configured chunking strategy is unsupported.")
    return tokenizer, chunk_config, strategy, config
