"""The Cognee connector — a documents backend (ADR-007).

A one-way, outbound push of the ``rac export --documents`` stream into Cognee. A
corpus ``source`` maps to a Cognee **dataset**; each record is staged with a
provenance header (Cognee has no per-record metadata filter), then the whole
dataset is built into a knowledge graph once via ``cognify``. Idempotency is
Cognee's native content-hash dedup (``incremental_loading``), not a resync —
re-pushing unchanged records is a no-op. Cognee builds the graph and embeds;
nothing is embedded here (rac-core ADR-002, ADR-066).
"""

from __future__ import annotations

from collections.abc import Iterable

from ..base import PushSummary
from ..records import Record
from .client import CogneeClient, provenance_payload

BACKEND = "cognee"
# A corpus without a source still needs a Cognee dataset; this is the fallback.
DEFAULT_CONTAINER = "main_dataset"


class CogneeConnector:
    """Push ``--documents`` records into Cognee, idempotent by content hash."""

    name = BACKEND

    def __init__(self, client: CogneeClient | None = None) -> None:
        # The client is optional so a dry run needs no credentials and no SDK.
        self._client = client

    def _container_for(self, record: Record) -> str:
        return record.source or DEFAULT_CONTAINER

    def push(self, records: Iterable[Record], *, dry_run: bool = False) -> PushSummary:
        summary = PushSummary(backend=self.name, dry_run=dry_run)
        for record in records:
            container = self._container_for(record)
            if dry_run:
                summary.record_push(
                    record.id,
                    f"dataset={container} type={record.type} "
                    f"status={record.status} ({len(record.text)} chars)",
                )
                continue
            payload = provenance_payload(
                text=record.text,
                lore_id=record.id,
                type=record.type,
                status=record.status,
                title=record.title,
            )
            self._require_client().add(payload=payload, container=container)
            summary.record_push(record.id, f"dataset={container}")
        # Build the graph once, after every record is staged.
        if not dry_run and summary.pushed:
            self._require_client().commit()
        return summary

    def _require_client(self) -> CogneeClient:
        if self._client is None:
            raise RuntimeError(
                "a CogneeClient is required for a live push; "
                "pass one or use dry_run=True"
            )
        return self._client
