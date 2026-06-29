"""The live SDK adapter (`SdkSupermemoryClient`) translates to the real
``supermemory`` call shape.

CI runs offline, so this stubs ``supermemory.Supermemory`` into ``sys.modules``
rather than importing the real SDK. The stub mirrors the signature verified
against supermemory 3.48.0: ``client.add(content=, container_tag=, metadata=,
custom_id=)`` returning an object with ``.id`` / ``.status``. The test exists so
that if the adapter drifts from that shape, it fails here instead of only on a
live push.
"""

from __future__ import annotations

import sys
import types

import pytest

from rac_connectors.supermemory.client import (
    MissingApiKeyError,
    SdkSupermemoryClient,
)


class _StubResponse:
    def __init__(self, id: str, status: str) -> None:
        self.id = id
        self.status = status


class _StubSupermemory:
    """Stand-in for ``supermemory.Supermemory`` — records construction + calls."""

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.calls: list[dict[str, object]] = []

    def add(self, **kwargs: object) -> _StubResponse:
        self.calls.append(kwargs)
        return _StubResponse(id="mem_abc", status="queued")


@pytest.fixture
def stub_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("supermemory")
    module.Supermemory = _StubSupermemory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "supermemory", module)


def test_adapter_constructs_client_with_api_key(stub_sdk: None) -> None:
    client = SdkSupermemoryClient(api_key="k-123")
    client.add(content="body", container_tag="rac", metadata={}, custom_id="RAC-1")
    assert client._client.kwargs == {"api_key": "k-123"}


def test_adapter_passes_the_real_add_shape(stub_sdk: None) -> None:
    client = SdkSupermemoryClient(api_key="k")
    result = client.add(
        content="## Context\n\nbody",
        container_tag="rac",
        metadata={"id": "RAC-1", "status": "Accepted", "aliases": ["adr-001"]},
        custom_id="RAC-1",
    )
    call = client._client.calls[0]
    assert call == {
        "content": "## Context\n\nbody",
        "container_tag": "rac",
        "metadata": {"id": "RAC-1", "status": "Accepted", "aliases": ["adr-001"]},
        "custom_id": "RAC-1",
    }
    # The SDK response maps into our minimal AddResult.
    assert result.id == "mem_abc"
    assert result.status == "queued"


def test_adapter_omits_container_tag_when_none(stub_sdk: None) -> None:
    client = SdkSupermemoryClient(api_key="k")
    client.add(content="b", container_tag=None, metadata={}, custom_id="RAC-1")
    # container_tag is left out entirely rather than sent as None.
    assert "container_tag" not in client._client.calls[0]


def test_adapter_forwards_base_url(
    monkeypatch: pytest.MonkeyPatch, stub_sdk: None
) -> None:
    client = SdkSupermemoryClient(api_key="k", base_url="https://self-hosted.example")
    client.add(content="b", container_tag=None, metadata={}, custom_id="RAC-1")
    assert client._client.kwargs["base_url"] == "https://self-hosted.example"


def test_api_key_read_from_env(monkeypatch: pytest.MonkeyPatch, stub_sdk: None) -> None:
    monkeypatch.setenv("SUPERMEMORY_API_KEY", "from-env")
    client = SdkSupermemoryClient()
    client.add(content="b", container_tag=None, metadata={}, custom_id="RAC-1")
    assert client._client.kwargs["api_key"] == "from-env"


def test_missing_key_raises_before_any_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPERMEMORY_API_KEY", raising=False)
    with pytest.raises(MissingApiKeyError):
        SdkSupermemoryClient()
