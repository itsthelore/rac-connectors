"""The Zep connector — a documents backend (ADR-005).

A one-way, outbound push of the ``rac export --documents`` stream into Zep Cloud.
Like Mem0, Zep has no per-record upsert key, so idempotency is a **graph
resync**: the first time a corpus ``source`` is seen in a push, its graph is
cleared (deleted and recreated), then every record for it is added as a text
episode. Re-running yields the same graph — no duplicates. Zep derives its
knowledge graph and embeds; nothing is embedded here (rac-core ADR-002, ADR-066).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..base import PushSummary
from ..records import Record
from .client import ZepClient

BACKEND = "zep"
# A corpus without a source still needs a Zep graph; this is the fallback.
DEFAULT_CONTAINER = "lore"


class ZepConnector:
    """Push ``--documents`` records into Zep, idempotent by graph resync."""

    name = BACKEND

    def __init__(self, client: ZepClient | None = None) -> None:
        # The client is optional so a dry run needs no credentials and no SDK.
        self._client = client

    def _container_for(self, record: Record) -> str:
        return record.source or DEFAULT_CONTAINER

    def _metadata_for(self, record: Record) -> dict[str, Any]:
        """Metadata shipped with each episode.

        ``lore_id`` carries the canonical handle for the verify-in-Lore loop;
        ``type``/``status``/``title`` ride along so a reader can filter retired
        or superseded items on read.
        """
        metadata = dict(record.metadata)
        metadata.update(
            {
                "lore_id": record.id,
                "type": record.type,
                "status": record.status,
                "title": record.title,
            }
        )
        return metadata

    def push(self, records: Iterable[Record], *, dry_run: bool = False) -> PushSummary:
        summary = PushSummary(backend=self.name, dry_run=dry_run)
        cleared: set[str] = set()
        for record in records:
            container = self._container_for(record)
            metadata = self._metadata_for(record)
            if dry_run:
                summary.record_push(
                    record.id,
                    f"graph={container} type={record.type} "
                    f"status={record.status} ({len(record.text)} chars)",
                )
                continue
            client = self._require_client()
            # Clear the graph once per push, before its first add, so the adds
            # are a clean resync rather than an append.
            if container not in cleared:
                client.clear_container(container=container)
                cleared.add(container)
            client.add(text=record.text, container=container, metadata=metadata)
            summary.record_push(record.id, f"graph={container}")
        return summary

    def _require_client(self) -> ZepClient:
        if self._client is None:
            raise RuntimeError(
                "a ZepClient is required for a live push; pass one or use dry_run=True"
            )
        return self._client
