"""The thin client seam the Cognee connector pushes through.

Cognee is unlike the other documents backends: a module-level **async** pipeline
(``await cognee.add(...)`` then ``await cognee.cognify(...)``) that builds a
knowledge graph and embeds locally, with native content-hash idempotency
(``incremental_loading``). The connector depends only on :class:`CogneeClient`
(a Protocol), so the test-suite drives an in-memory fake and CI never runs the
pipeline. :class:`SdkCogneeClient` is the real adapter; it buffers staged
payloads and flushes them — one ``add`` + one ``cognify`` per dataset — on commit.
"""

from __future__ import annotations

import asyncio
import os
from typing import Protocol, runtime_checkable

# Cognee needs an LLM to cognify; this is its primary credential.
LLM_API_KEY_ENV = "LLM_API_KEY"


class MissingCredentialsError(RuntimeError):
    """No Cognee LLM credentials were found in the environment."""

    def __init__(self) -> None:
        super().__init__(
            f"set {LLM_API_KEY_ENV} in the environment so Cognee can cognify "
            "(never hard-code the key)"
        )


@runtime_checkable
class CogneeClient(Protocol):
    """What the connector needs from Cognee: stage a payload, then commit.

    ``add`` stages one prepared document into a dataset; ``commit`` runs the
    two-phase ``add`` + ``cognify`` pipeline once per dataset. Idempotency is
    Cognee's own content-hash dedup (``incremental_loading``) — see ADR-007.
    """

    def add(self, *, payload: str, container: str) -> None: ...

    def commit(self) -> None: ...


class SdkCogneeClient:
    """Adapter over the real ``cognee`` package.

    Buffers staged payloads per dataset and, on :meth:`commit`, runs
    ``cognee.add(list, dataset_name=…)`` then ``cognee.cognify(datasets=[…])``
    for each — so the expensive graph build happens once per dataset, not per
    record. ``cognee`` is imported lazily inside :meth:`commit` so importing this
    module never pulls the (heavy) pipeline.
    """

    def __init__(self) -> None:
        if not os.environ.get(LLM_API_KEY_ENV):
            raise MissingCredentialsError()
        self._pending: dict[str, list[str]] = {}

    def add(self, *, payload: str, container: str) -> None:
        self._pending.setdefault(container, []).append(payload)

    def commit(self) -> None:
        if self._pending:
            asyncio.run(self._ingest_all())
            self._pending.clear()

    async def _ingest_all(self) -> None:
        try:
            import cognee
        except ImportError as exc:  # pragma: no cover - exercised via message
            raise RuntimeError(
                "the 'cognee' package is not installed; "
                "install the connector's 'cognee' extra"
            ) from exc
        for container, payloads in self._pending.items():
            # incremental_loading (Cognee's default) dedups by content hash, so a
            # re-push of unchanged payloads is a no-op. node_set tags the dataset.
            await cognee.add(payloads, dataset_name=container, node_set=[container])
            await cognee.cognify(datasets=[container])


def client_from_env() -> SdkCogneeClient:
    """Build the real client; requires ``LLM_API_KEY`` for Cognee's pipeline."""
    return SdkCogneeClient()


def provenance_payload(
    *, text: str, rac_id: str, type: str, status: str, title: str
) -> str:
    """Prefix a document with a provenance header.

    Cognee carries no per-record metadata filter, so the canonical ``rac_id``
    (and lifecycle) is embedded as a header line — keeping the verify-in-Lore
    handle recoverable from Cognee's graph (ADR-007).
    """
    header = f"Rac-Id: {rac_id}\nType: {type}\nStatus: {status}\nTitle: {title}"
    return f"{header}\n\n{text}"
