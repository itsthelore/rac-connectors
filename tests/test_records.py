"""Parsing the ``rac export --documents`` contract into records."""

from __future__ import annotations

from pathlib import Path

import pytest

from rac_connectors.records import (
    MalformedRecordError,
    Record,
    parse_documents,
)

FIXTURE = Path(__file__).parent / "fixtures_documents.jsonl"


def test_parses_real_export_fixture() -> None:
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    records = list(parse_documents(lines))
    assert len(records) == 3
    first = records[0]
    assert first.id.startswith("RAC-")
    assert first.type == "decision"
    assert first.source == "rac"  # from metadata.source
    assert first.text  # Markdown body, not empty


def test_blank_lines_are_skipped() -> None:
    lines = [
        '{"id":"RAC-1","type":"decision","status":"Accepted",'
        '"title":"t","text":"body"}',
        "",
        "   ",
    ]
    records = list(parse_documents(lines))
    assert [r.id for r in records] == ["RAC-1"]


def test_malformed_json_skipped_by_default_raises_in_strict() -> None:
    lines = ["not json at all"]
    assert list(parse_documents(lines)) == []
    with pytest.raises(MalformedRecordError) as exc:
        list(parse_documents(lines, strict=True))
    assert exc.value.line_number == 1


def test_missing_required_field_is_malformed() -> None:
    # No 'text' field — recognisable JSON, but not a valid record.
    lines = ['{"id":"RAC-1","type":"decision","status":"Accepted","title":"t"}']
    assert list(parse_documents(lines)) == []
    with pytest.raises(MalformedRecordError):
        list(parse_documents(lines, strict=True))


def test_empty_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        Record.from_dict(
            {
                "id": "",
                "type": "decision",
                "status": "Accepted",
                "title": "t",
                "text": "b",
            }
        )


def test_metadata_defaults_and_source_typing() -> None:
    record = Record.from_dict(
        {
            "id": "RAC-1",
            "type": "decision",
            "status": "Accepted",
            "title": "t",
            "text": "b",
        }
    )
    assert record.metadata == {}
    assert record.source is None  # absent source is None, not a crash
