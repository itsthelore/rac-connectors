"""The thin client seam the Zep connector pushes through.

The connector depends only on :class:`ZepClient` (a Protocol), so the test-suite
drives an in-memory fake and CI never touches the live API. :class:`SdkZepClient`
is the real adapter over the ``zep-cloud`` SDK, imported lazily so the package
installs and tests run without it.
"""

from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable

API_KEY_ENV = "ZEP_API_KEY"


class MissingApiKeyError(RuntimeError):
    """No Zep API key was found in the environment."""

    def __init__(self) -> None:
        super().__init__(
            f"set {API_KEY_ENV} in the environment (never hard-code the key)"
        )


@runtime_checkable
class ZepClient(Protocol):
    """What the connector needs from a Zep client.

    Two operations: clear a graph namespace, and add a text episode to it. Zep
    has no per-record upsert key, so idempotency is a graph resync (clear then
    add) the connector drives — see ADR-005.
    """

    def clear_container(self, *, container: str) -> None: ...

    def add(self, *, text: str, container: str, metadata: dict[str, Any]) -> None: ...


class SdkZepClient:
    """Adapter over the real ``zep-cloud`` SDK.

    Lazily constructs ``zep_cloud.client.Zep`` so importing this module never
    requires the SDK; the import error only surfaces on a live push without the
    ``zep`` extra installed. A corpus ``source`` maps to a Zep ``graph_id``.
    """

    def __init__(self, *, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get(API_KEY_ENV)
        if not self._api_key:
            raise MissingApiKeyError()
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                from zep_cloud.client import Zep
            except ImportError as exc:  # pragma: no cover - exercised via message
                raise RuntimeError(
                    "the 'zep-cloud' SDK is not installed; "
                    "install the connector's 'zep' extra"
                ) from exc
            self._client = Zep(api_key=self._api_key)
        return self._client

    def clear_container(self, *, container: str) -> None:
        client = self._ensure_client()
        try:
            client.graph.delete(container)
        except Exception:
            # The graph may not exist yet on a first sync; create it below.
            pass
        client.graph.create(graph_id=container)

    def add(self, *, text: str, container: str, metadata: dict[str, Any]) -> None:
        # type="text" ingests the artifact body; Zep derives its graph and
        # embeds — no embedding happens here (rac-core ADR-002, ADR-066).
        self._ensure_client().graph.add(
            data=text, type="text", graph_id=container, metadata=metadata
        )


def client_from_env() -> SdkZepClient:
    """Build the real client from environment variables (``ZEP_API_KEY``)."""
    return SdkZepClient()
