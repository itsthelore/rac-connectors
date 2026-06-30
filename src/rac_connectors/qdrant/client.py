"""The thin client seam the Qdrant connector upserts through.

The connector depends only on :class:`QdrantClient` (a Protocol), so the
test-suite drives an in-memory fake and CI never touches a real server.
:class:`SdkQdrantClient` is the real adapter over the official ``qdrant-client``,
imported lazily so the package installs and tests run without it.
"""

from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable

URL_ENV = "QDRANT_URL"
API_KEY_ENV = "QDRANT_API_KEY"


class MissingCredentialsError(RuntimeError):
    """No Qdrant connection details were found in the environment."""

    def __init__(self) -> None:
        super().__init__(
            f"set {URL_ENV} (and {API_KEY_ENV} if the server requires auth) "
            "in the environment (never hard-code credentials)"
        )


@runtime_checkable
class QdrantClient(Protocol):
    """What the connector needs from a Qdrant client.

    Two operations: ensure a collection exists with the right vector size, and
    upsert one point. ``upsert`` must be idempotent on ``point_id`` so re-running
    an export updates rather than duplicates.
    """

    def ensure_collection(self, *, collection: str, dimension: int) -> None: ...

    def upsert(
        self,
        *,
        collection: str,
        point_id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None: ...


class SdkQdrantClient:
    """Adapter over the official ``qdrant-client`` (lazy import).

    Lazily constructs the client so importing this module never requires the
    package; the import error only surfaces on a live push without the ``qdrant``
    extra installed. Collections are created on first use with cosine distance.
    """

    def __init__(self, *, url: str | None = None, api_key: str | None = None) -> None:
        self._url = url or os.environ.get(URL_ENV)
        self._api_key = api_key or os.environ.get(API_KEY_ENV)
        if not self._url:
            raise MissingCredentialsError()
        self._client: Any = None
        self._ensured: set[str] = set()

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                from qdrant_client import QdrantClient as _SdkClient
            except ImportError as exc:  # pragma: no cover - exercised via message
                raise RuntimeError(
                    "the 'qdrant-client' package is not installed; "
                    "install the connector's 'qdrant' extra"
                ) from exc
            self._client = _SdkClient(url=self._url, api_key=self._api_key)
        return self._client

    def ensure_collection(  # pragma: no cover - network
        self, *, collection: str, dimension: int
    ) -> None:
        if collection in self._ensured:
            return
        client = self._ensure_client()
        from qdrant_client.models import Distance, VectorParams

        if not client.collection_exists(collection):
            client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
            )
        self._ensured.add(collection)

    def upsert(  # pragma: no cover - network
        self,
        *,
        collection: str,
        point_id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        client = self._ensure_client()
        from qdrant_client.models import PointStruct

        client.upsert(
            collection_name=collection,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )


def client_from_env() -> SdkQdrantClient:
    """Build the real client from environment variables (``QDRANT_URL`` etc.)."""
    return SdkQdrantClient()
