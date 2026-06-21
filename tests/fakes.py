"""A fake Supermemory client for the test-suite — no live API in CI."""

from __future__ import annotations

from typing import Any

from lore_connectors.supermemory.client import AddResult


class FakeSupermemoryClient:
    """In-memory stand-in for the Supermemory SDK.

    Records every ``add`` call and upserts by ``custom_id`` so a test can assert
    both the record->call mapping and that re-pushing the same ``id`` updates the
    stored copy instead of creating a duplicate.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.store: dict[str, dict[str, Any]] = {}

    def add(
        self,
        *,
        content: str,
        container_tag: str | None,
        metadata: dict[str, Any],
        custom_id: str,
    ) -> AddResult:
        call = {
            "content": content,
            "container_tag": container_tag,
            "metadata": metadata,
            "custom_id": custom_id,
        }
        self.calls.append(call)
        self.store[custom_id] = call  # upsert by canonical id
        return AddResult(id=custom_id, status="queued")
