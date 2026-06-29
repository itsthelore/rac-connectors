"""The thin client seam the Mem0 connector pushes through.

The connector depends only on :class:`Mem0Client` (a Protocol), so the test-suite
drives an in-memory fake and CI never touches the live API. :class:`SdkMem0Client`
is the real adapter over the ``mem0`` SDK's ``MemoryClient``, imported lazily so
the package installs and tests run without it.
"""

from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable

API_KEY_ENV = "MEM0_API_KEY"


class MissingApiKeyError(RuntimeError):
    """No Mem0 API key was found in the environment."""

    def __init__(self) -> None:
        super().__init__(
            f"set {API_KEY_ENV} in the environment (never hard-code the key)"
        )


@runtime_checkable
class Mem0Client(Protocol):
    """What the connector needs from a Mem0 client.

    Two operations: clear a container partition, and add a memory to it. Mem0 has
    no per-record upsert key, so idempotency is a container resync (clear then
    add) the connector drives — see ADR-004.
    """

    def clear_container(self, *, container: str) -> None: ...

    def add(self, *, text: str, container: str, metadata: dict[str, Any]) -> None: ...


class SdkMem0Client:
    """Adapter over the real ``mem0`` SDK (``MemoryClient``).

    Lazily constructs ``mem0.MemoryClient`` so importing this module never
    requires the SDK; the import error only surfaces on a live push without the
    ``mem0`` extra installed. The corpus ``source`` maps to a Mem0 ``user_id``
    partition (the primary, broadly-supported scope for add/delete).
    """

    def __init__(self, *, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get(API_KEY_ENV)
        if not self._api_key:
            raise MissingApiKeyError()
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                from mem0 import MemoryClient
            except ImportError as exc:  # pragma: no cover - exercised via message
                raise RuntimeError(
                    "the 'mem0ai' SDK is not installed; "
                    "install the connector's 'mem0' extra"
                ) from exc
            self._client = MemoryClient(api_key=self._api_key)
        return self._client

    def clear_container(self, *, container: str) -> None:
        # Wipe the partition so the subsequent adds are a clean resync.
        self._ensure_client().delete_all(user_id=container)

    def add(self, *, text: str, container: str, metadata: dict[str, Any]) -> None:
        # infer=False stores the artifact text as-is — no LLM fact-extraction or
        # rewrite — so Mem0 only embeds it (rac-core ADR-002, ADR-066).
        self._ensure_client().add(
            text, user_id=container, metadata=metadata, infer=False
        )


def client_from_env() -> SdkMem0Client:
    """Build the real client from environment variables (``MEM0_API_KEY``)."""
    return SdkMem0Client()
