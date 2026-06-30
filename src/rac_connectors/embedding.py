"""External embedding seam for vector-store connectors (ADR-009).

A vector database stores vectors; it does not produce them. The memory/RAG
backends RAC already ships (Supermemory, Mem0, Zep) embed **server-side**, so
their connectors stay model-free (rac-core ADR-002, ADR-066). A bare vector store
(e.g. Qdrant) cannot — it needs vectors supplied. To keep RAC AI-optional and
free of bundled models, a vector-store connector embeds by calling a **configured
external service** over its OpenAI-compatible ``/embeddings`` endpoint. The model
name and credentials live in that service (a LiteLLM gateway is the reference
deployment, mirroring the grounding benchmark's ``*_BASE_URL`` pattern), never
here. This module is the small, provider-neutral seam connectors depend on; the
test-suite drives a fake, so CI never makes a network call.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Protocol, runtime_checkable

BASE_URL_ENV = "RAC_EMBED_BASE_URL"
API_KEY_ENV = "RAC_EMBED_API_KEY"
MODEL_ENV = "RAC_EMBED_MODEL"


class MissingEmbeddingConfigError(RuntimeError):
    """No external embedding endpoint/model was configured in the environment."""

    def __init__(self) -> None:
        super().__init__(
            f"set {BASE_URL_ENV} and {MODEL_ENV} (and {API_KEY_ENV} if the "
            "endpoint requires auth) to embed via an external service"
        )


@runtime_checkable
class Embedder(Protocol):
    """Turn a batch of texts into vectors, order-preserving.

    One method, so a connector depends only on this Protocol and the test-suite
    drives a deterministic fake. The returned list has one vector per input text,
    in the same order.
    """

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class ExternalEmbedder:
    """Adapter over an OpenAI-compatible ``/embeddings`` endpoint.

    Works with any gateway that speaks the OpenAI embeddings shape — a LiteLLM
    proxy is the reference deployment, but OpenAI, Ollama, or any compatible
    endpoint works the same way. Uses only the standard library, so the package
    gains no dependency; the model and credentials live in the endpoint, not here.
    """

    def __init__(
        self, *, base_url: str, model: str, api_key: str | None = None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        body = json.dumps({"model": self._model, "input": texts}).encode("utf-8")
        request = urllib.request.Request(
            f"{self._base_url}/embeddings", data=body, method="POST"
        )
        request.add_header("Content-Type", "application/json")
        if self._api_key:
            request.add_header("Authorization", f"Bearer {self._api_key}")
        with urllib.request.urlopen(request) as response:  # pragma: no cover - network
            payload = json.load(response)
        # OpenAI-compatible: {"data": [{"embedding": [...]}, ...]}, input order.
        return [item["embedding"] for item in payload["data"]]


def embedder_from_env() -> ExternalEmbedder:
    """Build the external embedder from the environment.

    Reads ``RAC_EMBED_BASE_URL`` and ``RAC_EMBED_MODEL`` (and the optional
    ``RAC_EMBED_API_KEY``). Raises :class:`MissingEmbeddingConfigError` if the
    endpoint or model is unset, so a live push fails fast with a clear message.
    """
    base_url = os.environ.get(BASE_URL_ENV)
    model = os.environ.get(MODEL_ENV)
    if not (base_url and model):
        raise MissingEmbeddingConfigError()
    return ExternalEmbedder(
        base_url=base_url, model=model, api_key=os.environ.get(API_KEY_ENV)
    )
