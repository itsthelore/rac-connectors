"""The Qdrant connector: record->point mapping, idempotent upsert, dry-run."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from rac_connectors.qdrant import DEFAULT_COLLECTION, QdrantConnector
from rac_connectors.qdrant.connector import _ID_NAMESPACE
from rac_connectors.records import Record


class FakeEmbedder:
    """Deterministic 3-dim embedder; records the texts it was asked to embed."""

    def __init__(self) -> None:
        self.texts: list[str] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.texts.extend(texts)
        return [[float(len(text)), 1.0, 0.0] for text in texts]


class FakeQdrantClient:
    """In-memory Qdrant: upsert by point id so a re-push overwrites in place."""

    def __init__(self) -> None:
        self.collections: dict[str, int] = {}
        self.ensure_calls = 0
        self.upserts: list[dict[str, Any]] = []
        self.points: dict[tuple[str, str], dict[str, Any]] = {}

    def ensure_collection(self, *, collection: str, dimension: int) -> None:
        self.ensure_calls += 1
        self.collections[collection] = dimension

    def upsert(
        self,
        *,
        collection: str,
        point_id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        call = {
            "collection": collection,
            "point_id": point_id,
            "vector": vector,
            "payload": payload,
        }
        self.upserts.append(call)
        self.points[(collection, point_id)] = call  # upsert by canonical id


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


def test_record_maps_to_point_with_payload() -> None:
    client = FakeQdrantClient()
    embedder = FakeEmbedder()
    summary = QdrantConnector(client, embedder).push([_record()])

    assert summary.pushed == 1
    call = client.upserts[0]
    assert call["collection"] == "rac"  # source maps to the collection
    assert call["vector"] == [float(len("## Context\n\nbody")), 1.0, 0.0]
    assert call["payload"]["rac_id"] == "RAC-ABC"  # the verify-in-Lore handle
    assert call["payload"]["status"] == "Accepted"
    assert call["payload"]["text"] == "## Context\n\nbody"
    assert client.collections["rac"] == 3  # dimension comes from the embedder


def test_point_id_is_deterministic_uuid5_of_canonical_id() -> None:
    client = FakeQdrantClient()
    QdrantConnector(client, FakeEmbedder()).push([_record(id="RAC-1")])
    assert client.upserts[0]["point_id"] == str(uuid.uuid5(_ID_NAMESPACE, "RAC-1"))


def test_repush_is_idempotent_by_point_id() -> None:
    client = FakeQdrantClient()
    connector = QdrantConnector(client, FakeEmbedder())

    connector.push([_record(id="RAC-1"), _record(id="RAC-2")])
    connector.push([_record(id="RAC-1"), _record(id="RAC-2")])

    # Upsert overwrote in place — two distinct points even after a re-push.
    assert len(client.points) == 2


def test_collection_ensured_once_per_collection() -> None:
    client = FakeQdrantClient()
    QdrantConnector(client, FakeEmbedder()).push(
        [_record(id="RAC-1"), _record(id="RAC-2")]
    )
    assert client.ensure_calls == 1  # one collection, ensured once, not per record
    assert client.collections == {"rac": 3}


def test_dry_run_makes_no_calls() -> None:
    client = FakeQdrantClient()
    embedder = FakeEmbedder()
    summary = QdrantConnector(client, embedder).push([_record()], dry_run=True)

    assert summary.dry_run is True
    assert summary.pushed == 1
    assert client.upserts == [] and embedder.texts == []  # nothing embedded or sent


def test_dry_run_needs_no_client_or_embedder() -> None:
    summary = QdrantConnector().push([_record()], dry_run=True)
    assert summary.pushed == 1


def test_live_push_without_client_errors() -> None:
    with pytest.raises(RuntimeError, match="QdrantClient is required"):
        QdrantConnector(embedder=FakeEmbedder()).push([_record()])


def test_live_push_without_embedder_errors() -> None:
    with pytest.raises(RuntimeError, match="Embedder is required"):
        QdrantConnector(FakeQdrantClient()).push([_record()])


def test_missing_source_uses_default_collection() -> None:
    client = FakeQdrantClient()
    QdrantConnector(client, FakeEmbedder()).push([_record(metadata={"path": "x.md"})])
    assert client.upserts[0]["collection"] == DEFAULT_COLLECTION
