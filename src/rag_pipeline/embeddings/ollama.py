import ipaddress
import math
import time
from urllib.parse import urlsplit
from typing import Sequence

import httpx

from .base import EmbeddingBatch, EmbeddingDescriptor, EmbeddingError, EmbeddingModelSpec


class OllamaEmbeddingProvider:
    def __init__(
        self,
        spec: EmbeddingModelSpec,
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: float = 60.0,
        max_retries: int = 1,
        client: httpx.Client | None = None,
    ) -> None:
        self.spec = spec
        self.base_url = self._validate_local_url(base_url)
        if timeout_seconds <= 0 or max_retries < 0:
            raise ValueError("Timeout must be positive and retries cannot be negative.")
        self.max_retries = max_retries
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 5.0)),
            follow_redirects=False,
        )
        self._owns_client = client is None
        self._runtime_version: str | None = None
        self._model_digest: str | None = spec.model_digest
        self._dimension = spec.dimensions

    @staticmethod
    def _validate_local_url(value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Ollama URL must be an unauthenticated HTTP loopback URL.")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("Ollama base URL cannot contain a path, query, or fragment.")
        host = parsed.hostname.lower()
        is_loopback = host == "localhost"
        if not is_loopback:
            try:
                is_loopback = ipaddress.ip_address(host).is_loopback
            except ValueError:
                is_loopback = False
        # Docker-only host gateway for Ollama bound to Windows host loopback.
        # Do not accept arbitrary hostnames or IP addresses here.
        docker_host_gateway = host == "host.docker.internal" and parsed.port == 11434
        if not is_loopback and not docker_host_gateway:
            raise ValueError("Ollama provider is restricted to loopback addresses.")
        return f"http://{parsed.netloc}"

    def _request_json(self, path: str, payload: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        for attempt in range(self.max_retries + 1):
            try:
                if payload is None:
                    response = self._client.get(url)
                else:
                    response = self._client.post(url, json=payload)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt < self.max_retries:
                    time.sleep(min(0.1 * (2 ** attempt), 0.5))
                    continue
                raise EmbeddingError(f"Ollama request failed: {type(exc).__name__}") from exc
            if response.status_code >= 500 and attempt < self.max_retries:
                time.sleep(min(0.1 * (2 ** attempt), 0.5))
                continue
            if response.is_error:
                raise EmbeddingError(f"Ollama returned HTTP {response.status_code} for {path}.")
            try:
                value = response.json()
            except ValueError as exc:
                raise EmbeddingError("Ollama returned invalid JSON.") from exc
            if not isinstance(value, dict):
                raise EmbeddingError("Ollama returned an unexpected response shape.")
            return value
        raise EmbeddingError("Ollama request failed after retries.")

    def health_check(self) -> dict[str, str | bool | None]:
        version_response = self._request_json("/api/version")
        runtime_version = version_response.get("version")
        if not isinstance(runtime_version, str) or not runtime_version:
            raise EmbeddingError("Ollama version response is missing its version.")
        tags_response = self._request_json("/api/tags")
        models = tags_response.get("models")
        if not isinstance(models, list):
            raise EmbeddingError("Ollama tags response is missing its model list.")
        match = next((model for model in models if isinstance(model, dict) and model.get("name") == self.spec.model_name), None)
        if match is None:
            raise EmbeddingError(f"Embedding model is not installed: {self.spec.model_name}")
        digest = match.get("digest")
        if self.spec.model_digest and digest != self.spec.model_digest:
            raise EmbeddingError("Installed embedding model digest does not match the configured digest.")
        self._runtime_version = runtime_version
        self._model_digest = digest if isinstance(digest, str) else None
        return {"available": True, "runtime_version": runtime_version, "model_name": self.spec.model_name, "model_digest": self._model_digest}

    def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        if isinstance(texts, (str, bytes)) or not texts:
            raise ValueError("Embedding input must be a non-empty sequence of texts.")
        if len(texts) > self.spec.max_batch_size:
            raise ValueError(f"Embedding batch exceeds {self.spec.max_batch_size} inputs.")
        validated = []
        for index, text in enumerate(texts):
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"Embedding input {index} must be non-empty text.")
            if len(text) > self.spec.max_input_characters:
                raise ValueError(f"Embedding input {index} exceeds the character limit.")
            validated.append(text)
        if self._runtime_version is None:
            self.health_check()
        response = self._request_json("/api/embed", {
            "model": self.spec.model_name,
            "input": validated,
            "truncate": False,
            "keep_alive": "5m",
        })
        returned_model = response.get("model")
        if returned_model is not None and returned_model != self.spec.model_name:
            raise EmbeddingError("Ollama returned embeddings from an unexpected model.")
        raw_vectors = response.get("embeddings")
        if not isinstance(raw_vectors, list) or len(raw_vectors) != len(validated):
            raise EmbeddingError("Ollama returned a different number of vectors than inputs.")
        input_token_count = response.get("prompt_eval_count")
        if input_token_count is not None and (type(input_token_count) is not int or input_token_count < 0):
            raise EmbeddingError("Ollama returned an invalid input token count.")
        vectors = []
        dimension = self._dimension
        norms = []
        for vector_index, raw_vector in enumerate(raw_vectors):
            if not isinstance(raw_vector, list) or not raw_vector:
                raise EmbeddingError(f"Embedding vector {vector_index} is empty or invalid.")
            values = []
            for value in raw_vector:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise EmbeddingError(f"Embedding vector {vector_index} contains a non-finite value.")
                values.append(float(value))
            if dimension is None:
                dimension = len(values)
            if len(values) != dimension:
                raise EmbeddingError("Embedding vectors have inconsistent dimensions.")
            norm = math.sqrt(sum(value * value for value in values))
            if norm == 0:
                raise EmbeddingError("Embedding model returned a zero vector.")
            norms.append(norm)
            vectors.append(tuple(values))
        if dimension is None:
            raise EmbeddingError("Embedding dimensions could not be determined.")
        self._dimension = dimension
        unit_normalized = all(abs(norm - 1.0) <= 0.01 for norm in norms)
        descriptor = EmbeddingDescriptor(
            provider="ollama",
            model_name=self.spec.model_name,
            model_digest=self._model_digest,
            dimensions=dimension,
            vectors_are_unit_normalized=unit_normalized,
            runtime_version=self._runtime_version,
        )
        return EmbeddingBatch(tuple(vectors), descriptor, input_token_count)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "OllamaEmbeddingProvider":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
