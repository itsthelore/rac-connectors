"""The Qdrant connector — a documents backend that embeds via an external service.

A one-way, outbound push of the ``rac export --documents`` stream into Qdrant.
Unlike the server-side-embedding backends (Supermemory, Mem0, Zep), Qdrant stores
vectors but does not produce them, so the connector embeds each record's text
through an external :class:`~rac_connectors.embedding.Embedder` before upserting
(ADR-009). The point id is derived deterministically from the canonical ``rac_id``
(a UUID5), so re-exporting upserts in place rather than duplicating. Embeddings
live in the configured external endpoint, never in the engine (rac-core ADR-002,
ADR-066).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Any

from ..base import PushSummary
from ..embedding import Embedder
from ..records import Record
from .client import QdrantClient

BACKEND = "qdrant"
# A corpus without a source still needs a collection; this is the fallback.
DEFAULT_COLLECTION = "lore"
# A fixed namespace so a canonical rac_id always maps to the same point id; the
# upsert is then idempotent on that id. (RFC-4122 URL namespace.)
_ID_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


class QdrantConnector:
    """Push ``--documents`` records into Qdrant, idempotent on the canonical id."""

    name = BACKEND

    def __init__(
        self,
        client: QdrantClient | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        # Both are optional so a dry run needs no credentials, SDK, or endpoint.
        self._client = client
        self._embedder = embedder

    def _collection_for(self, record: Record) -> str:
        return record.source or DEFAULT_COLLECTION

    def _point_id(self, record: Record) -> str:
        return str(uuid.uuid5(_ID_NAMESPACE, record.id))

    def _payload_for(self, record: Record) -> dict[str, Any]:
        """Payload stored alongside the vector.

        ``rac_id`` carries the canonical handle for the verify-in-Lore loop;
        ``type``/``status``/``title`` ride along so a reader can filter retired or
        superseded items, and ``text`` is kept so a hit need not round-trip for
        the body before verifying in Lore.
        """
        payload = dict(record.metadata)
        payload.update(
            {
                "rac_id": record.id,
                "type": record.type,
                "status": record.status,
                "title": record.title,
                "text": record.text,
            }
        )
        return payload

    def push(self, records: Iterable[Record], *, dry_run: bool = False) -> PushSummary:
        summary = PushSummary(backend=self.name, dry_run=dry_run)
        ensured: set[str] = set()
        for record in records:
            collection = self._collection_for(record)
            if dry_run:
                summary.record_push(
                    record.id,
                    f"collection={collection} type={record.type} "
                    f"status={record.status} ({len(record.text)} chars)",
                )
                continue
            client = self._require_client()
            embedder = self._require_embedder()
            vector = embedder.embed([record.text])[0]
            # Create the collection on first use with the embedder's dimension.
            if collection not in ensured:
                client.ensure_collection(collection=collection, dimension=len(vector))
                ensured.add(collection)
            client.upsert(
                collection=collection,
                point_id=self._point_id(record),
                vector=vector,
                payload=self._payload_for(record),
            )
            summary.record_push(record.id, f"collection={collection} dim={len(vector)}")
        return summary

    def _require_client(self) -> QdrantClient:
        if self._client is None:
            raise RuntimeError(
                "a QdrantClient is required for a live push; "
                "pass one or use dry_run=True"
            )
        return self._client

    def _require_embedder(self) -> Embedder:
        if self._embedder is None:
            raise RuntimeError(
                "an Embedder is required for a live push; pass one or use dry_run=True"
            )
        return self._embedder
