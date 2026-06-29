"""The live SDK adapter (`SdkZepClient`) against a stubbed ``zep_cloud``.

CI runs offline, so this stubs ``zep_cloud.client.Zep`` into ``sys.modules``
rather than importing the real SDK. The stub mirrors the signature verified
against zep-cloud 3.23.0: ``Zep(api_key=...)`` with ``.graph.add(data=, type=,
graph_id=, metadata=)``, ``.graph.create(graph_id=)``, and ``.graph.delete(id)``.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from rac_connectors.zep.client import MissingApiKeyError, SdkZepClient


class _StubGraph:
    def __init__(self) -> None:
        self.adds: list[dict[str, Any]] = []
        self.created: list[str] = []
        self.deleted: list[str] = []
        self.raise_on_delete = False

    def add(self, **kwargs: Any) -> None:
        self.adds.append(kwargs)

    def create(self, **kwargs: Any) -> None:
        self.created.append(kwargs["graph_id"])

    def delete(self, graph_id: str) -> None:
        if self.raise_on_delete:
            raise RuntimeError("not found")
        self.deleted.append(graph_id)


class _StubZep:
    last: _StubZep | None = None

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
        self.graph = _StubGraph()
        _StubZep.last = self


@pytest.fixture
def stub_zep(monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = types.ModuleType("zep_cloud")
    client_mod = types.ModuleType("zep_cloud.client")
    client_mod.Zep = _StubZep  # type: ignore[attr-defined]
    pkg.client = client_mod  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "zep_cloud", pkg)
    monkeypatch.setitem(sys.modules, "zep_cloud.client", client_mod)
    _StubZep.last = None


def test_add_maps_to_graph_add(stub_zep: None) -> None:
    client = SdkZepClient(api_key="k")
    client.add(text="body", container="rac", metadata={"rac_id": "RAC-1"})
    call = _StubZep.last.graph.adds[0]
    assert call == {
        "data": "body",
        "type": "text",
        "graph_id": "rac",
        "metadata": {"rac_id": "RAC-1"},
    }


def test_clear_deletes_then_creates(stub_zep: None) -> None:
    client = SdkZepClient(api_key="k")
    client.clear_container(container="rac")
    graph = _StubZep.last.graph
    assert graph.deleted == ["rac"]
    assert graph.created == ["rac"]


def test_clear_tolerates_missing_graph(stub_zep: None) -> None:
    client = SdkZepClient(api_key="k")
    # Force delete to fail (graph absent); create must still run.
    client._ensure_client().graph.raise_on_delete = True
    client.clear_container(container="rac")
    assert _StubZep.last.graph.created == ["rac"]


def test_api_key_passed_to_client(stub_zep: None) -> None:
    client = SdkZepClient(api_key="k-123")
    client.add(text="b", container="rac", metadata={})
    assert _StubZep.last.api_key == "k-123"


def test_api_key_read_from_env(monkeypatch: pytest.MonkeyPatch, stub_zep: None) -> None:
    monkeypatch.setenv("ZEP_API_KEY", "from-env")
    client = SdkZepClient()
    client.add(text="b", container="rac", metadata={})
    assert _StubZep.last.api_key == "from-env"


def test_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZEP_API_KEY", raising=False)
    with pytest.raises(MissingApiKeyError):
        SdkZepClient()
