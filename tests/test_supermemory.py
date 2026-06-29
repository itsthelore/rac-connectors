"""The Supermemory connector: record->call mapping, idempotency, dry-run."""

from __future__ import annotations

import pytest

from rac_connectors.records import Record
from rac_connectors.supermemory import SupermemoryConnector
from rac_connectors.supermemory.client import MissingApiKeyError, SdkSupermemoryClient

from .fakes import FakeSupermemoryClient


def _record(**overrides) -> Record:
    base = {
        "id": "RAC-ABC",
        "type": "decision",
        "status": "Accepted",
        "title": "ADR-001: Example",
        "text": "## Context\n\nbody",
        "metadata": {
            "path": "rac/decisions/adr-001.md",
            "source": "rac",
            "aliases": ["adr-001"],
            "tags": [],
        },
    }
    base.update(overrides)
    return Record.from_dict(base)


def test_record_maps_to_add_call() -> None:
    client = FakeSupermemoryClient()
    connector = SupermemoryConnector(client)

    summary = connector.push([_record()])

    assert summary.pushed == 1
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["content"] == "## Context\n\nbody"  # Markdown body, not HTML
    assert call["container_tag"] == "rac"  # from metadata.source
    assert call["custom_id"] == "RAC-ABC"  # idempotency key is the canonical id
    # Load-bearing metadata rides along for the verify-in-Lore loop.
    assert call["metadata"]["id"] == "RAC-ABC"
    assert call["metadata"]["status"] == "Accepted"
    assert call["metadata"]["type"] == "decision"
    assert call["metadata"]["path"] == "rac/decisions/adr-001.md"


def test_repush_is_idempotent_on_id() -> None:
    client = FakeSupermemoryClient()
    connector = SupermemoryConnector(client)

    connector.push([_record()])
    # Re-export with edited body, same canonical id.
    connector.push([_record(text="## Context\n\nedited body")])

    assert len(client.calls) == 2  # both adds were issued
    assert len(client.store) == 1  # but only one stored item — an update
    assert client.store["RAC-ABC"]["content"] == "## Context\n\nedited body"


def test_dry_run_makes_no_calls() -> None:
    client = FakeSupermemoryClient()
    connector = SupermemoryConnector(client)

    summary = connector.push([_record()], dry_run=True)

    assert summary.dry_run is True
    assert summary.pushed == 1
    assert client.calls == []  # nothing sent to the backend
    assert "RAC-ABC" in summary.actions[0]


def test_dry_run_needs_no_client() -> None:
    connector = SupermemoryConnector()  # no client at all
    summary = connector.push([_record()], dry_run=True)
    assert summary.pushed == 1


def test_live_push_without_client_errors() -> None:
    connector = SupermemoryConnector()
    with pytest.raises(RuntimeError, match="required for a live push"):
        connector.push([_record()])


def test_missing_source_uses_no_container_tag() -> None:
    client = FakeSupermemoryClient()
    connector = SupermemoryConnector(client)
    connector.push([_record(metadata={"path": "x.md"})])
    assert client.calls[0]["container_tag"] is None


def test_sdk_client_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("SUPERMEMORY_API_KEY", raising=False)
    with pytest.raises(MissingApiKeyError):
        SdkSupermemoryClient()
