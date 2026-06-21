"""The live adapter (`SdkCogneeClient`) against a stubbed async ``cognee``.

CI runs offline, so this stubs the ``cognee`` module (async ``add`` / ``cognify``)
into ``sys.modules``. The stub mirrors the signature verified against cognee
1.2.0: ``await cognee.add(list, dataset_name=…, node_set=[…])`` then
``await cognee.cognify(datasets=[…])``. The adapter buffers and flushes on commit.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from lore_connectors.cognee.client import MissingCredentialsError, SdkCogneeClient


class _StubCognee(types.ModuleType):
    def __init__(self) -> None:
        super().__init__("cognee")
        self.adds: list[dict[str, Any]] = []
        self.cognifies: list[dict[str, Any]] = []

    async def add(self, data: Any, **kwargs: Any) -> None:
        self.adds.append({"data": data, **kwargs})

    async def cognify(self, **kwargs: Any) -> None:
        self.cognifies.append(kwargs)


@pytest.fixture
def stub_cognee(monkeypatch: pytest.MonkeyPatch) -> _StubCognee:
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    module = _StubCognee()
    monkeypatch.setitem(sys.modules, "cognee", module)
    return module


def test_commit_runs_add_then_cognify_per_dataset(stub_cognee: _StubCognee) -> None:
    client = SdkCogneeClient()
    client.add(payload="doc-a", container="rac")
    client.add(payload="doc-b", container="rac")
    client.commit()

    # One batched add (both payloads) and one cognify for the dataset.
    assert len(stub_cognee.adds) == 1
    add_call = stub_cognee.adds[0]
    assert add_call["data"] == ["doc-a", "doc-b"]
    assert add_call["dataset_name"] == "rac"
    assert add_call["node_set"] == ["rac"]
    assert stub_cognee.cognifies[0]["datasets"] == ["rac"]


def test_commit_is_noop_when_nothing_staged(stub_cognee: _StubCognee) -> None:
    client = SdkCogneeClient()
    client.commit()
    assert stub_cognee.adds == [] and stub_cognee.cognifies == []


def test_commit_clears_buffer(stub_cognee: _StubCognee) -> None:
    client = SdkCogneeClient()
    client.add(payload="doc-a", container="rac")
    client.commit()
    client.commit()  # second commit has nothing left to flush
    assert len(stub_cognee.adds) == 1


def test_missing_llm_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(MissingCredentialsError):
        SdkCogneeClient()
