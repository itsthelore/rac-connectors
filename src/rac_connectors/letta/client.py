"""The thin client seam the Letta connector pushes through.

The connector depends only on :class:`LettaClient` (a Protocol) — the same
``clear_container`` / ``add`` shape as the other memory backends — so the
test-suite drives an in-memory fake and CI never touches the live API.
:class:`SdkLettaClient` is the real adapter over the ``letta-client`` SDK; it maps
a corpus ``source`` to a Letta **archive** and hides the archive-id bookkeeping.
"""

from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable

API_KEY_ENV = "LETTA_API_KEY"
BASE_URL_ENV = "LETTA_BASE_URL"


class MissingCredentialsError(RuntimeError):
    """No Letta credentials were found in the environment."""

    def __init__(self) -> None:
        super().__init__(
            f"set {API_KEY_ENV} (Letta Cloud) or {BASE_URL_ENV} (self-hosted) "
            "in the environment (never hard-code credentials)"
        )


@runtime_checkable
class LettaClient(Protocol):
    """What the connector needs from a Letta client.

    Two operations: clear a container, and add a passage to it. Letta has no
    per-record upsert key, so idempotency is an archive resync (clear then add)
    the connector drives — see ADR-006.
    """

    def clear_container(self, *, container: str) -> None: ...

    def add(self, *, text: str, container: str, metadata: dict[str, Any]) -> None: ...


class SdkLettaClient:
    """Adapter over the real ``letta-client`` SDK.

    Lazily constructs ``letta_client.Letta`` so importing this module never
    requires the SDK. A corpus ``source`` maps to a Letta archive (created fresh
    on each resync); the connector pushes by container name and this adapter
    resolves the opaque ``archive_id`` internally.
    """

    def __init__(
        self, *, api_key: str | None = None, base_url: str | None = None
    ) -> None:
        self._api_key = api_key or os.environ.get(API_KEY_ENV)
        self._base_url = base_url or os.environ.get(BASE_URL_ENV)
        if not (self._api_key or self._base_url):
            raise MissingCredentialsError()
        self._client: Any = None
        self._archive_ids: dict[str, str] = {}

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                from letta_client import Letta
            except ImportError as exc:  # pragma: no cover - exercised via message
                raise RuntimeError(
                    "the 'letta-client' SDK is not installed; "
                    "install the connector's 'letta' extra"
                ) from exc
            kwargs: dict[str, Any] = {}
            if self._api_key:
                kwargs["api_key"] = self._api_key
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = Letta(**kwargs)
        return self._client

    def clear_container(self, *, container: str) -> None:
        client = self._ensure_client()
        # Delete any archive(s) by this name, then create a fresh one.
        for archive in client.archives.list(name=container):
            client.archives.delete(archive.id)
        archive = client.archives.create(name=container)
        self._archive_ids[container] = archive.id

    def add(self, *, text: str, container: str, metadata: dict[str, Any]) -> None:
        archive_id = self._archive_ids[container]
        # Letta embeds the passage server-side (rac-core ADR-002, ADR-066).
        self._ensure_client().archives.passages.create(
            archive_id, text=text, metadata=metadata
        )


def client_from_env() -> SdkLettaClient:
    """Build the real client from the environment.

    Reads ``LETTA_API_KEY`` (Letta Cloud) or ``LETTA_BASE_URL`` (self-hosted).
    """
    return SdkLettaClient()
