"""Pluggable text embedding backends (local or OpenAI-compatible HTTP)."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger("codegraph_mcp.semantic.embeddings")


class EmbeddingCountMismatch(Exception):
    """Response contained a different number of vectors than inputs (often local OpenAI-compat quirk)."""

    def __init__(self, got: int, expected: int) -> None:
        self.got = got
        self.expected = expected
        super().__init__(f"got {got} embedding vectors for {expected} inputs")


@runtime_checkable
class EmbeddingBackend(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _post_json(url: str, headers: dict[str, str], body: dict[str, Any], timeout: float = 120.0) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class OpenAICompatibleEmbeddings:
    """Embeddings via ``POST {base_url}/v1/embeddings`` (OpenAI shape; works with LM Studio, Ollama, etc.)."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        batch_size: int | None = None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY") or ""
        self.model = model or os.environ.get("OPENAI_EMBEDDING_MODEL") or "text-embedding-3-small"
        raw_bs = batch_size if batch_size is not None else os.environ.get("CODEGRAPH_EMBED_BATCH_SIZE", "64")
        try:
            self.batch_size = max(1, int(raw_bs))
        except (TypeError, ValueError):
            self.batch_size = 64
        # Some OpenAI-compatible servers return one vector (or wrong count) for batched ``input``; auto-fallback.
        self._single_only = False

    def _post_embeddings_payload(self, chunk: list[str]) -> dict[str, Any]:
        url = f"{self.base_url}/embeddings"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {"model": self.model, "input": chunk}
        try:
            return _post_json(url, headers, payload)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            logger.error("Embedding HTTP %s: %s", e.code, body)
            raise RuntimeError(f"embedding request failed: {e.code}") from e
        except OSError as e:
            logger.error("Embedding request failed: %s", e)
            raise

    def _vectors_from_items(self, items: list[Any], *, expected: int) -> list[list[float]]:
        if len(items) != expected:
            raise EmbeddingCountMismatch(len(items), expected)
        raw: list[list[float]] = []
        indexed: dict[int, list[float]] = {}
        all_have_index = True
        for item in items:
            vec = item.get("embedding")
            if not isinstance(vec, list):
                raise RuntimeError("invalid embedding response")
            emb = [float(x) for x in vec]
            raw.append(emb)
            idx = item.get("index")
            if idx is None:
                all_have_index = False
            else:
                indexed[int(idx)] = emb
        if (
            all_have_index
            and len(indexed) == expected
            and set(indexed.keys()) == set(range(expected))
        ):
            return [indexed[i] for i in range(expected)]
        return raw

    def _vectors_for_chunk(self, chunk: list[str]) -> list[list[float]]:
        data = self._post_embeddings_payload(chunk)
        items = data.get("data") or []
        try:
            return self._vectors_from_items(items, expected=len(chunk))
        except EmbeddingCountMismatch:
            raise
        except Exception:
            logger.debug("Embedding response sample: %s", json.dumps(data)[:800])
            raise

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        i = 0
        while i < len(texts):
            bs = 1 if self._single_only else self.batch_size
            chunk = texts[i : i + bs]
            try:
                part = self._vectors_for_chunk(chunk)
            except EmbeddingCountMismatch as e:
                if len(chunk) == 1:
                    raise RuntimeError(
                        f"embedding API returned {e.got} vectors for 1 input; check server logs and model id"
                    ) from e
                logger.warning(
                    "Embedding API returned %d vectors for %d inputs (batched); retrying one string per request",
                    e.got,
                    e.expected,
                )
                self._single_only = True
                continue
            out.extend(part)
            i += len(chunk)
        return out


class LocalSentenceEmbeddings:
    """In-process embeddings (sentence-transformers). Requires ``semantic`` extra."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.environ.get("CODEGRAPH_LOCAL_EMBED_MODEL") or "all-MiniLM-L6-v2"
        self._model = None

    def _get_model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise ImportError(
                    "Local embeddings require sentence-transformers. Install with: pip install sentence-transformers"
                ) from e
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        vectors = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return [vectors[i].tolist() for i in range(len(texts))]


def describe_embedding_backend(backend: EmbeddingBackend) -> str:
    """Short label for log messages (no secrets)."""
    if isinstance(backend, OpenAICompatibleEmbeddings):
        return (
            f"OpenAI-compatible HTTP (model={backend.model!r}, base_url={backend.base_url!r})"
        )
    if isinstance(backend, LocalSentenceEmbeddings):
        return f"local sentence-transformers (model={backend.model_name!r})"
    return type(backend).__name__


def get_backend_from_env() -> EmbeddingBackend:
    backend = (os.environ.get("CODEGRAPH_EMBED_BACKEND") or "openai").strip().lower()
    if backend in ("local", "sentence", "sentence_transformers"):
        return LocalSentenceEmbeddings()
    return OpenAICompatibleEmbeddings()
