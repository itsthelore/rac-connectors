"""The Supermemory connector — module one of rac-connectors (ADR-073).

A one-way, outbound push: read ``rac export --documents`` records and upsert each
into Supermemory. The mapping is fixed by the rac-core design
``corpus-export-shape-contract``::

    each record  ->  add(content=text,
                         container_tag=metadata.source,
                         metadata={id, type, status, title, path, ...},
                         custom_id=id)

Embeddings live in Supermemory, never here (ADR-002, ADR-066). The connector
keeps the backend fresh; the verify-in-Lore loop is the reading agent's job.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..base import PushSummary
from ..records import Record
from .client import SupermemoryClient

BACKEND = "supermemory"


class SupermemoryConnector:
    """Push ``--documents`` records into Supermemory, idempotently on ``id``."""

    name = BACKEND

    def __init__(self, client: SupermemoryClient | None = None) -> None:
        # The client is optional so a dry run needs no credentials and no SDK.
        self._client = client

    def _metadata_for(self, record: Record) -> dict[str, Any]:
        """The metadata payload shipped with each memory.

        Carries the record's own ``metadata`` (path, aliases, tags, source) plus
        the load-bearing ``id``/``type``/``status``/``title`` so the
        verify-in-Lore loop can re-fetch the authoritative artifact and a reader
        can filter retired/superseded items on read.
        """
        metadata = dict(record.metadata)
        metadata.update(
            {
                "id": record.id,
                "type": record.type,
                "status": record.status,
                "title": record.title,
            }
        )
        return metadata

    def push(self, records: Iterable[Record], *, dry_run: bool = False) -> PushSummary:
        summary = PushSummary(backend=self.name, dry_run=dry_run)
        for record in records:
            container_tag = record.source
            metadata = self._metadata_for(record)
            if dry_run:
                tag = container_tag or "<none>"
                summary.record_push(
                    record.id,
                    f"container_tag={tag} type={record.type} "
                    f"status={record.status} ({len(record.text)} chars)",
                )
                continue
            if self._client is None:
                raise RuntimeError(
                    "a SupermemoryClient is required for a live push; "
                    "pass one or use dry_run=True"
                )
            result = self._client.add(
                content=record.text,
                container_tag=container_tag,
                metadata=metadata,
                custom_id=record.id,  # idempotency key: re-push updates, never dupes
            )
            detail = f"status={result.status}" if result.status else "ok"
            summary.record_push(record.id, detail)
        return summary
