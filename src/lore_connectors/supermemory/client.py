"""The thin client seam the Supermemory connector pushes through.

The connector depends only on :class:`SupermemoryClient` (a Protocol), so the
test-suite drives it with an in-memory fake and CI never touches the live API.
:class:`SdkSupermemoryClient` is the real adapter over the ``supermemory`` SDK,
imported lazily so the package installs and tests run without the SDK present.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

API_KEY_ENV = "SUPERMEMORY_API_KEY"
BASE_URL_ENV = "SUPERMEMORY_BASE_URL"


class MissingApiKeyError(RuntimeError):
    """No Supermemory API key was found in the environment."""

    def __init__(self) -> None:
        super().__init__(
            f"set {API_KEY_ENV} in the environment (never hard-code the key)"
        )


@dataclass(frozen=True)
class AddResult:
    """The minimal result of an upsert the connector cares about."""

    id: str | None
    status: str | None


@runtime_checkable
class SupermemoryClient(Protocol):
    """What the connector needs from a Supermemory client.

    One method: upsert a memory. ``custom_id`` is the idempotency key — passing
    the canonical Lore ``id`` makes re-pushing an edited artifact an update, not
    a duplicate.
    """

    def add(
        self,
        *,
        content: str,
        container_tag: str | None,
        metadata: dict[str, Any],
        custom_id: str,
    ) -> AddResult: ...


class SdkSupermemoryClient:
    """Adapter over the real ``supermemory`` Python SDK.

    Lazily constructs ``supermemory.Supermemory`` so importing this module never
    requires the SDK; the import error only surfaces if a live push is attempted
    without the ``supermemory`` extra installed.
    """

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None):
        self._api_key = api_key or os.environ.get(API_KEY_ENV)
        if not self._api_key:
            raise MissingApiKeyError()
        self._base_url = base_url or os.environ.get(BASE_URL_ENV)
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                from supermemory import Supermemory
            except ImportError as exc:  # pragma: no cover - exercised via message
                raise RuntimeError(
                    "the 'supermemory' SDK is not installed; "
                    "install the connector's 'supermemory' extra"
                ) from exc
            kwargs: dict[str, Any] = {"api_key": self._api_key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = Supermemory(**kwargs)
        return self._client

    def add(
        self,
        *,
        content: str,
        container_tag: str | None,
        metadata: dict[str, Any],
        custom_id: str,
    ) -> AddResult:
        client = self._ensure_client()
        kwargs: dict[str, Any] = {
            "content": content,
            "metadata": metadata,
            "custom_id": custom_id,
        }
        if container_tag is not None:
            kwargs["container_tag"] = container_tag
        response = client.add(**kwargs)
        return AddResult(
            id=getattr(response, "id", None),
            status=getattr(response, "status", None),
        )


def client_from_env() -> SdkSupermemoryClient:
    """Build the real client from environment variables (``SUPERMEMORY_API_KEY``)."""
    return SdkSupermemoryClient()
