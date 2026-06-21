"""The shared connector seam every backend module implements.

One repo, one module per backend (ADR-073). Supermemory is module one; this is
the small shape the next backend (Mem0, Zep, a vector store, a graph backend)
slots into without reworking the CLI. The seam is deliberately minimal — push a
stream of records, optionally as a dry run, get back a deterministic summary —
so it does not over-generalise before a second backend exists.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .records import Record


@dataclass
class PushSummary:
    """The outcome of a push, the same shape for every backend.

    ``actions`` records one line per record describing what was (or, under a dry
    run, would be) sent — keyed by canonical ``id`` so a re-push is legible as
    the idempotent update it is.
    """

    backend: str
    pushed: int = 0
    skipped: int = 0
    dry_run: bool = False
    actions: list[str] = field(default_factory=list)

    def record_push(self, record_id: str, detail: str) -> None:
        self.pushed += 1
        self.actions.append(f"push {record_id}: {detail}")

    def record_skip(self, line_number: int, reason: str) -> None:
        self.skipped += 1
        self.actions.append(f"skip line {line_number}: {reason}")

    def summary_line(self) -> str:
        mode = "dry-run" if self.dry_run else "push"
        return f"{self.backend} {mode}: {self.pushed} pushed, {self.skipped} skipped"


@runtime_checkable
class Connector(Protocol):
    """Outbound-only sink for export records.

    Connectors push to the backend and never read back, re-rank, or route (the
    re-rank / memory-router approach was explicitly rejected — see the interplay
    design in rac-core). ``push`` must be idempotent on each record's canonical
    ``id`` so re-running an export updates rather than duplicates.
    """

    name: str

    def push(self, records: Iterable[Record], *, dry_run: bool = False) -> PushSummary:
        """Upsert ``records`` into the backend, returning a :class:`PushSummary`.

        With ``dry_run=True`` the connector must describe what it would send
        without making any network call.
        """
        ...
