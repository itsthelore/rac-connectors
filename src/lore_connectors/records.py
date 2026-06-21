"""Parse the ``rac export --documents`` JSON Lines contract into records.

This module is the connector side of the export contract shipped by rac-core
(``rac export <dir> --documents``). It is intentionally a *consumer* of that
contract — it never re-derives anything from raw Markdown (ADR-073, ADR-063).
Each input line is one artifact (ADR-004, ADR-010): one document, never chunked.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any


class MalformedRecordError(ValueError):
    """A ``--documents`` line could not be parsed into a valid record.

    Carries the 1-based line number and the offending raw text so a caller can
    report exactly which line failed without re-reading the stream.
    """

    def __init__(self, line_number: int, reason: str, raw: str) -> None:
        self.line_number = line_number
        self.reason = reason
        self.raw = raw
        super().__init__(f"line {line_number}: {reason}")


@dataclass(frozen=True)
class Record:
    """One artifact from the ``--documents`` projection.

    Mirrors the export contract's per-line object. ``text`` is the Markdown body
    (frontmatter stripped) — backends embed text, not HTML. ``id`` is the
    canonical Lore handle the verify-in-Lore loop re-fetches by, and ``status``
    rides along so a reader can drop retired/superseded items.
    """

    id: str
    type: str
    status: str
    title: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1"

    @property
    def source(self) -> str | None:
        """The corpus name that namespaces this record (``metadata.source``).

        Used as the Supermemory ``container_tag``. May be absent on hand-rolled
        fixtures; the connector decides how to handle a missing source.
        """
        source = self.metadata.get("source")
        return source if isinstance(source, str) else None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Record:
        """Build a record from one decoded JSON object, validating the contract.

        Raises ``ValueError`` if a required field is missing or mistyped. The
        required set is the stable contract: ``id``, ``type``, ``status``,
        ``title``, ``text``. ``metadata`` and ``schema_version`` are optional
        with safe defaults so the parser tolerates additive contract growth
        (ADR-007).
        """
        if not isinstance(data, dict):
            raise ValueError("record is not a JSON object")

        required = ("id", "type", "status", "title", "text")
        for key in required:
            value = data.get(key)
            if not isinstance(value, str):
                raise ValueError(f"missing or non-string field {key!r}")
            if key == "id" and not value:
                raise ValueError("field 'id' must be non-empty")

        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("field 'metadata' must be an object")

        schema_version = data.get("schema_version", "1")
        if not isinstance(schema_version, str):
            schema_version = str(schema_version)

        return cls(
            id=data["id"],
            type=data["type"],
            status=data["status"],
            title=data["title"],
            text=data["text"],
            metadata=metadata,
            schema_version=schema_version,
        )


def parse_documents(lines: Iterable[str], *, strict: bool = False) -> Iterator[Record]:
    """Yield :class:`Record` objects from ``--documents`` JSON Lines.

    Blank lines (and surrounding whitespace) are skipped — JSONL files commonly
    end with a trailing newline. By default a malformed line is skipped and
    surfaced by raising only when ``strict`` is set; callers that want a
    fail-fast guard pass ``strict=True`` and catch :class:`MalformedRecordError`.

    Skipping vs. raising is a connector policy choice, so this generator does the
    minimal thing (raise in strict mode) and lets the connector layer decide how
    lenient to be. The malformed-line guard is exercised in the test-suite.
    """
    for index, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            decoded = json.loads(stripped)
        except json.JSONDecodeError as exc:
            if strict:
                raise MalformedRecordError(index, f"invalid JSON ({exc})", raw) from exc
            continue
        try:
            record = Record.from_dict(decoded)
        except ValueError as exc:
            if strict:
                raise MalformedRecordError(index, str(exc), raw) from exc
            continue
        yield record
