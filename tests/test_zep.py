"""The Zep connector: record->add mapping, graph-resync idempotency, dry-run."""

from __future__ import annotations

from typing import Any

import pytest

from rac_connectors.records import Record
from rac_connectors.zep import DEFAULT_CONTAINER, ZepConnector


class FakeZepClient:
    """In-memory stand-in for the Zep client.

    ``clear_container`` wipes a graph namespace and ``add`` appends a text
    episode, so a test can assert that a re-push (clear then re-add) leaves no
    duplicates.
    """

    def __init__(self) -> None:
        self.adds: list[dict[str, Any]] = []
        self.clears: list[str] = []
        self.store: dict[str, list[dict[str, Any]]] = {}

    def clear_container(self, *, container: str) -> None:
        self.clears.append(container)
        self.store[container] = []

    def add(self, *, text: str, container: str, metadata: dict[str, Any]) -> None:
        call = {"text": text, "container": container, "metadata": metadata}
        self.adds.append(call)
        self.store.setdefault(container, []).append(call)


def _record(**overrides: Any) -> Record:
    base = {
        "id": "RAC-ABC",
        "type": "decision",
        "status": "Accepted",
        "title": "ADR-001: Example",
        "text": "## Context\n\nbody",
        "metadata": {"path": "rac/decisions/adr-001.md", "source": "rac"},
    }
    base.update(overrides)
    return Record.from_dict(base)


def test_record_maps_to_add_with_metadata() -> None:
    client = FakeZepClient()
    summary = ZepConnector(client).push([_record()])

    assert summary.pushed == 1
    call = client.adds[0]
    assert call["text"] == "## Context\n\nbody"
    assert call["container"] == "rac"  # source maps to the Zep graph_id
    assert call["metadata"]["lore_id"] == "RAC-ABC"
    assert call["metadata"]["status"] == "Accepted"
    assert call["metadata"]["path"] == "rac/decisions/adr-001.md"


def test_graph_cleared_once_before_adds() -> None:
    client = FakeZepClient()
    ZepConnector(client).push([_record(id="RAC-1"), _record(id="RAC-2")])
    assert client.clears == ["rac"]
    assert len(client.adds) == 2


def test_repush_is_idempotent_via_resync() -> None:
    client = FakeZepClient()
    connector = ZepConnector(client)

    connector.push([_record(id="RAC-1"), _record(id="RAC-2")])
    connector.push([_record(id="RAC-1"), _record(id="RAC-2")])

    assert len(client.store["rac"]) == 2  # graph holds exactly the two records
    assert client.clears == ["rac", "rac"]


def test_dry_run_makes_no_calls() -> None:
    client = FakeZepClient()
    summary = ZepConnector(client).push([_record()], dry_run=True)

    assert summary.dry_run is True
    assert summary.pushed == 1
    assert client.adds == [] and client.clears == []


def test_dry_run_needs_no_client() -> None:
    summary = ZepConnector().push([_record()], dry_run=True)
    assert summary.pushed == 1


def test_live_push_without_client_errors() -> None:
    with pytest.raises(RuntimeError, match="required for a live push"):
        ZepConnector().push([_record()])


def test_missing_source_uses_default_container() -> None:
    client = FakeZepClient()
    ZepConnector(client).push([_record(metadata={"path": "x.md"})])
    assert client.adds[0]["container"] == DEFAULT_CONTAINER
