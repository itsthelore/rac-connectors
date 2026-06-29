"""The Mem0 connector — a documents backend (ADR-004).

A one-way, outbound push of the ``rac export --documents`` stream into Mem0. Mem0
has no per-record upsert key (unlike Supermemory's ``custom_id``), so idempotency
is a **container resync**: the first time a corpus ``source`` is seen in a push,
its partition is cleared, then every record for it is added. Re-running yields the
same partition contents — no duplicates — which satisfies the contract's
"containerTag as the upsert key". Embeddings live in Mem0, never here (rac-core
ADR-002, ADR-066).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..base import PushSummary
from ..records import Record
from .client import Mem0Client

BACKEND = "mem0"
# A corpus without a source still needs a Mem0 partition; this is the fallback.
DEFAULT_CONTAINER = "lore"


class Mem0Connector:
    """Push ``--documents`` records into Mem0, idempotent by container resync."""

    name = BACKEND

    def __init__(self, client: Mem0Client | None = None) -> None:
        # The client is optional so a dry run needs no credentials and no SDK.
        self._client = client

    def _container_for(self, record: Record) -> str:
        return record.source or DEFAULT_CONTAINER

    def _metadata_for(self, record: Record) -> dict[str, Any]:
        """Metadata shipped with each memory.

        ``rac_id`` carries the canonical handle for the verify-in-Lore loop;
        ``type``/``status``/``title`` ride along so a reader can filter retired
        or superseded items on read.
        """
        metadata = dict(record.metadata)
        metadata.update(
            {
                "rac_id": record.id,
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
                    f"container={container} type={record.type} "
                    f"status={record.status} ({len(record.text)} chars)",
                )
                continue
            client = self._require_client()
            # Clear the partition once per push, before its first add, so the
            # adds are a clean resync rather than an append.
            if container not in cleared:
                client.clear_container(container=container)
                cleared.add(container)
            client.add(text=record.text, container=container, metadata=metadata)
            summary.record_push(record.id, f"container={container}")
        return summary

    def _require_client(self) -> Mem0Client:
        if self._client is None:
            raise RuntimeError(
                "a Mem0Client is required for a live push; pass one or use dry_run=True"
            )
        return self._client
