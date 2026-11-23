from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class EmbeddingModelSpec:
    model_name: str
    model_digest: str | None = None
    dimensions: int | None = None
    max_batch_size: int = 16
    max_input_characters: int = 12000

    def __post_init__(self) -> None:
        if not self.model_name or any(character.isspace() for character in self.model_name):
            raise ValueError("Embedding model name must be a non-empty tag without whitespace.")
        if self.dimensions is not None and self.dimensions < 1:
            raise ValueError("Embedding dimensions must be positive.")
        if self.max_batch_size < 1 or self.max_input_characters < 1:
            raise ValueError("Embedding request limits must be positive.")


@dataclass(frozen=True)
class EmbeddingDescriptor:
    provider: str
    model_name: str
    model_digest: str | None
    dimensions: int
    vectors_are_unit_normalized: bool
    runtime_version: str | None


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: tuple[tuple[float, ...], ...]
    descriptor: EmbeddingDescriptor
    input_token_count: int | None = None


class EmbeddingError(RuntimeError):
    pass


class EmbeddingProvider(Protocol):
    def embed(self, texts: Sequence[str]) -> EmbeddingBatch: ...
