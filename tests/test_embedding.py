"""The external embedding seam: env config + OpenAI-compatible response parsing."""

from __future__ import annotations

import json

import pytest

from rac_connectors.embedding import (
    ExternalEmbedder,
    MissingEmbeddingConfigError,
    embedder_from_env,
)


def test_embedder_from_env_requires_base_url_and_model(monkeypatch) -> None:
    monkeypatch.delenv("RAC_EMBED_BASE_URL", raising=False)
    monkeypatch.delenv("RAC_EMBED_MODEL", raising=False)
    with pytest.raises(MissingEmbeddingConfigError):
        embedder_from_env()


def test_embedder_from_env_builds_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("RAC_EMBED_BASE_URL", "https://litellm.example/v1")
    monkeypatch.setenv("RAC_EMBED_MODEL", "text-embedding-3-small")
    monkeypatch.delenv("RAC_EMBED_API_KEY", raising=False)
    assert isinstance(embedder_from_env(), ExternalEmbedder)


def test_embed_posts_openai_shape_and_parses_vectors(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _Resp:
        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *exc: object) -> bool:
            return False

        def read(self) -> bytes:
            return json.dumps(
                {"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]}
            ).encode("utf-8")

    def fake_urlopen(request):  # type: ignore[no-untyped-def]
        captured["url"] = request.full_url
        captured["auth"] = request.get_header("Authorization")
        captured["body"] = json.loads(request.data)
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    embedder = ExternalEmbedder(
        base_url="https://litellm.example/v1", model="m", api_key="k"
    )
    vectors = embedder.embed(["a", "bb"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert str(captured["url"]).endswith("/embeddings")
    assert captured["auth"] == "Bearer k"
    assert captured["body"] == {"model": "m", "input": ["a", "bb"]}


def test_embed_empty_returns_empty_without_a_call() -> None:
    assert ExternalEmbedder(base_url="https://x/v1", model="m").embed([]) == []
