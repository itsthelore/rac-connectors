"""The Mem0 connector: record->add mapping, container-resync idempotency, dry-run."""

from __future__ import annotations

from typing import Any

import pytest

from lore_connectors.mem0 import DEFAULT_CONTAINER, Mem0Connector
from lore_connectors.records import Record


class FakeMem0Client:
    """In-memory stand-in for the Mem0 client.

    Emulates a partitioned store: ``clear_container`` wipes a partition and
    ``add`` appends to it, so a test can assert that a re-push (which clears then
    re-adds) leaves no duplicates.
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
    client = FakeMem0Client()
    summary = Mem0Connector(client).push([_record()])

    assert summary.pushed == 1
    call = client.adds[0]
    assert call["text"] == "## Context\n\nbody"
    assert call["container"] == "rac"  # source maps to the Mem0 partition
    assert call["metadata"]["lore_id"] == "RAC-ABC"  # the verify-in-Lore handle
    assert call["metadata"]["status"] == "Accepted"
    assert call["metadata"]["path"] == "rac/decisions/adr-001.md"


def test_container_cleared_once_before_adds() -> None:
    client = FakeMem0Client()
    Mem0Connector(client).push([_record(id="RAC-1"), _record(id="RAC-2")])
    # One clear for the partition, then both adds — not a clear per record.
    assert client.clears == ["rac"]
    assert len(client.adds) == 2


def test_repush_is_idempotent_via_resync() -> None:
    client = FakeMem0Client()
    connector = Mem0Connector(client)

    connector.push([_record(id="RAC-1"), _record(id="RAC-2")])
    connector.push([_record(id="RAC-1"), _record(id="RAC-2")])

    # The partition was cleared each push, so it holds exactly two memories.
    assert len(client.store["rac"]) == 2
    assert client.clears == ["rac", "rac"]


def test_dry_run_makes_no_calls() -> None:
    client = FakeMem0Client()
    summary = Mem0Connector(client).push([_record()], dry_run=True)

    assert summary.dry_run is True
    assert summary.pushed == 1
    assert client.adds == [] and client.clears == []  # nothing touched


def test_dry_run_needs_no_client() -> None:
    summary = Mem0Connector().push([_record()], dry_run=True)
    assert summary.pushed == 1


def test_live_push_without_client_errors() -> None:
    with pytest.raises(RuntimeError, match="required for a live push"):
        Mem0Connector().push([_record()])


def test_missing_source_uses_default_container() -> None:
    client = FakeMem0Client()
    Mem0Connector(client).push([_record(metadata={"path": "x.md"})])
    assert client.adds[0]["container"] == DEFAULT_CONTAINER
