from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Sequence

from tokenizers import Tokenizer

from .chunkers import ChunkConfig


class TokenizerConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class TokenSpan:
    source_text: str
    token_id: int
    start: int
    end: int


class NomicTokenSequence(Sequence[TokenSpan]):
    """Token offsets retain original text so window decoding preserves case/code bytes."""

    def __init__(self, source_text: str, token_ids: Sequence[int], offsets: Sequence[tuple[int, int]]) -> None:
        if len(token_ids) != len(offsets):
            raise ValueError("Tokenizer IDs and offsets have different lengths.")
        self.source_text = source_text
        self.token_ids = tuple(token_ids)
        self.offsets = tuple(offsets)

    def __len__(self) -> int:
        return len(self.token_ids)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return NomicTokenSequence(self.source_text, self.token_ids[index], self.offsets[index])
        start, end = self.offsets[index]
        return TokenSpan(self.source_text, self.token_ids[index], start, end)


class NomicEmbeddingTokenizer:
    """Pinned BERT tokenizer shipped with nomic-embed-text-v1.5."""

    model_id = "nomic-ai/nomic-embed-text-v1.5"
    model_revision = "e9b6763023c676ca8431644204f50c2b100d9aab"
    tokenizer_version = "0.22.1"
    special_tokens_per_input = 2  # [CLS] and [SEP], validated against local Ollama.

    def __init__(self, tokenizer_path: str | Path, expected_sha256: str, max_context_tokens: int = 2048) -> None:
        self.tokenizer_path = Path(tokenizer_path).resolve()
        if not self.tokenizer_path.is_file():
            raise TokenizerConfigurationError(f"Tokenizer asset is missing: {self.tokenizer_path}")
        digest = hashlib.sha256(self.tokenizer_path.read_bytes()).hexdigest()
        if digest != expected_sha256.lower():
            raise TokenizerConfigurationError("Tokenizer asset checksum does not match configuration.")
        if max_context_tokens < 3:
            raise TokenizerConfigurationError("Embedding model context limit is invalid.")
        try:
            self._tokenizer = Tokenizer.from_file(str(self.tokenizer_path))
        except Exception as exc:
            raise TokenizerConfigurationError("Tokenizer asset could not be loaded.") from exc
        self.sha256 = digest
        self.max_context_tokens = max_context_tokens
        self.identifier = f"{self.model_id}@{self.model_revision}"
        self.runtime_version = self.tokenizer_version

    def encode(self, text: str) -> NomicTokenSequence:
        if not isinstance(text, str):
            raise TypeError("Tokenizer input must be text.")
        encoded = self._tokenizer.encode(text, add_special_tokens=False)
        unknown_id = self._tokenizer.token_to_id("[UNK]")
        if unknown_id is None or unknown_id not in encoded.ids:
            return NomicTokenSequence(text, encoded.ids, encoded.offsets)

        # Hugging Face WordPiece can collapse a long unrecognized run to one
        # [UNK], while the Ollama runtime tokenizer splits the same text into
        # many tokens. Expand those spans by UTF-8 byte so chunk budgets remain
        # conservative for runtime tokenizers that split unknown text.
        token_ids: list[int] = []
        offsets: list[tuple[int, int]] = []
        for token_id, (start, end) in zip(encoded.ids, encoded.offsets):
            if token_id != unknown_id or end <= start:
                token_ids.append(token_id)
                offsets.append((start, end))
                continue
            for position in range(start, end):
                byte_weight = len(text[position].encode("utf-8"))
                token_ids.extend([unknown_id] * byte_weight)
                offsets.extend([(position, position + 1)] * byte_weight)
        return NomicTokenSequence(text, token_ids, offsets)

    def decode(self, tokens: Sequence[TokenSpan]) -> str:
        spans = [token for token in tokens if token.end > token.start]
        if not spans:
            return ""
        first = min(token.start for token in spans)
        last = max(token.end for token in spans)
        source_text = spans[0].source_text
        if any(token.source_text is not source_text for token in spans):
            raise ValueError("Cannot decode tokens from different source texts.")
        return source_text[first:last]

    def count(self, text: str) -> int:
        return len(self.encode(text)) + self.special_tokens_per_input

    def validate_config(self, config: ChunkConfig) -> None:
        budgets = (config.max_tokens, config.child_max_tokens, config.parent_max_tokens)
        if any(budget + self.special_tokens_per_input > self.max_context_tokens for budget in budgets):
            raise TokenizerConfigurationError(
                f"Chunk token budgets plus {self.special_tokens_per_input} BERT special tokens "
                f"must fit the {self.max_context_tokens}-token embedding context."
            )
