"""The Letta connector — a documents backend (ADR-006).

A one-way, outbound push of the ``rac export --documents`` stream into Letta. A
corpus ``source`` maps to a Letta **archive**; each record is added as a passage.
Letta has no per-record upsert key, so idempotency is an **archive resync**: the
first time a source is seen in a push, its archive is cleared (deleted and
recreated), then every record for it is added. Re-running yields the same
archive — no duplicates. Letta embeds the passages; nothing is embedded here
(rac-core ADR-002, ADR-066).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..base import PushSummary
from ..records import Record
from .client import LettaClient

BACKEND = "letta"
# A corpus without a source still needs a Letta archive; this is the fallback.
DEFAULT_CONTAINER = "lore"


class LettaConnector:
    """Push ``--documents`` records into Letta, idempotent by archive resync."""

    name = BACKEND

    def __init__(self, client: LettaClient | None = None) -> None:
        # The client is optional so a dry run needs no credentials and no SDK.
        self._client = client

    def _container_for(self, record: Record) -> str:
        return record.source or DEFAULT_CONTAINER

    def _metadata_for(self, record: Record) -> dict[str, Any]:
        """Metadata shipped with each passage.

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
                    f"archive={container} type={record.type} "
                    f"status={record.status} ({len(record.text)} chars)",
                )
                continue
            client = self._require_client()
            # Clear the archive once per push, before its first add, so the adds
            # are a clean resync rather than an append.
            if container not in cleared:
                client.clear_container(container=container)
                cleared.add(container)
            client.add(text=record.text, container=container, metadata=metadata)
            summary.record_push(record.id, f"archive={container}")
        return summary

    def _require_client(self) -> LettaClient:
        if self._client is None:
            raise RuntimeError(
                "a LettaClient is required for a live push; "
                "pass one or use dry_run=True"
            )
        return self._client
