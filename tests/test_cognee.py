"""The Cognee connector: stage-per-record, commit-once, provenance, dry-run."""

from __future__ import annotations

from typing import Any

import pytest

from rac_connectors.cognee import DEFAULT_CONTAINER, CogneeConnector
from rac_connectors.records import Record


class FakeCogneeClient:
    """In-memory stand-in: ``add`` stages a payload, ``commit`` flushes once.

    Emulates Cognee's content-hash dedup on commit so a test can assert that a
    re-push of the same payloads does not grow the built store.
    """

    def __init__(self) -> None:
        self.staged: list[dict[str, str]] = []
        self.commits = 0
        self.built: dict[str, set[str]] = {}

    def add(self, *, payload: str, container: str) -> None:
        self.staged.append({"payload": payload, "container": container})

    def commit(self) -> None:
        self.commits += 1
        for item in self.staged:
            self.built.setdefault(item["container"], set()).add(item["payload"])
        self.staged = []


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


def test_each_record_staged_then_committed_once() -> None:
    client = FakeCogneeClient()
    summary = CogneeConnector(client).push([_record(id="RAC-1"), _record(id="RAC-2")])

    assert summary.pushed == 2
    assert client.commits == 1  # one graph build for the whole push
    assert len(client.built["rac"]) == 2


def test_payload_carries_provenance() -> None:
    client = FakeCogneeClient()
    CogneeConnector(client).push([_record()])  # push commits internally
    payload = next(iter(client.built["rac"]))
    assert "Rac-Id: RAC-ABC" in payload  # the verify-in-Lore handle
    assert "Status: Accepted" in payload
    assert "## Context\n\nbody" in payload  # the artifact text is preserved


def test_repush_dedups_by_content() -> None:
    client = FakeCogneeClient()
    connector = CogneeConnector(client)
    connector.push([_record(id="RAC-1"), _record(id="RAC-2")])
    connector.push([_record(id="RAC-1"), _record(id="RAC-2")])
    # Same payloads — the built set stays at two (content-hash dedup).
    assert len(client.built["rac"]) == 2
    assert client.commits == 2


def test_dry_run_stages_nothing_and_does_not_commit() -> None:
    client = FakeCogneeClient()
    summary = CogneeConnector(client).push([_record()], dry_run=True)
    assert summary.dry_run is True and summary.pushed == 1
    assert client.staged == [] and client.commits == 0


def test_dry_run_needs_no_client() -> None:
    assert CogneeConnector().push([_record()], dry_run=True).pushed == 1


def test_empty_push_does_not_commit() -> None:
    client = FakeCogneeClient()
    summary = CogneeConnector(client).push([])
    assert summary.pushed == 0
    assert client.commits == 0  # nothing to build


def test_live_push_without_client_errors() -> None:
    with pytest.raises(RuntimeError, match="required for a live push"):
        CogneeConnector().push([_record()])


def test_missing_source_uses_default_dataset() -> None:
    client = FakeCogneeClient()
    CogneeConnector(client).push([_record(metadata={"path": "x.md"})])
    assert DEFAULT_CONTAINER in client.built
