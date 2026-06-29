"""The live SDK adapter (`SdkMem0Client`) against a stubbed ``mem0``.

CI runs offline, so this stubs ``mem0.MemoryClient`` into ``sys.modules`` rather
than importing the real SDK. The stub mirrors the signature verified against
mem0ai 2.0.7: ``MemoryClient(api_key=...)`` with ``.add(messages, user_id=,
metadata=, infer=)`` and ``.delete_all(user_id=)``.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from rac_connectors.mem0.client import MissingApiKeyError, SdkMem0Client


class _StubMemoryClient:
    last: _StubMemoryClient | None = None

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
        self.adds: list[dict[str, Any]] = []
        self.deletes: list[dict[str, Any]] = []
        _StubMemoryClient.last = self

    def add(self, messages: Any, **kwargs: Any) -> dict[str, Any]:
        self.adds.append({"messages": messages, **kwargs})
        return {}

    def delete_all(self, **kwargs: Any) -> dict[str, Any]:
        self.deletes.append(kwargs)
        return {}


@pytest.fixture
def stub_mem0(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("mem0")
    module.MemoryClient = _StubMemoryClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mem0", module)
    _StubMemoryClient.last = None


def test_add_maps_to_sdk_with_infer_false(stub_mem0: None) -> None:
    client = SdkMem0Client(api_key="k")
    client.add(text="body", container="rac", metadata={"rac_id": "RAC-1"})
    call = _StubMemoryClient.last.adds[0]
    assert call["messages"] == "body"
    assert call["user_id"] == "rac"  # container maps to the user_id partition
    assert call["metadata"] == {"rac_id": "RAC-1"}
    assert call["infer"] is False  # store as-is; no LLM rewrite


def test_clear_container_deletes_the_partition(stub_mem0: None) -> None:
    client = SdkMem0Client(api_key="k")
    client.clear_container(container="rac")
    assert _StubMemoryClient.last.deletes[0] == {"user_id": "rac"}


def test_api_key_passed_to_client(stub_mem0: None) -> None:
    client = SdkMem0Client(api_key="k-123")
    client.add(text="b", container="rac", metadata={})
    assert _StubMemoryClient.last.api_key == "k-123"


def test_api_key_read_from_env(
    monkeypatch: pytest.MonkeyPatch, stub_mem0: None
) -> None:
    monkeypatch.setenv("MEM0_API_KEY", "from-env")
    client = SdkMem0Client()
    client.add(text="b", container="rac", metadata={})
    assert _StubMemoryClient.last.api_key == "from-env"


def test_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MEM0_API_KEY", raising=False)
    with pytest.raises(MissingApiKeyError):
        SdkMem0Client()
