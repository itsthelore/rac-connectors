"""The export-contract version guard (the real cross-repo dependency, ADR-008)."""

from __future__ import annotations

import json

import pytest

from lore_connectors import (
    SUPPORTED_CONTRACT_VERSION,
    ContractVersionWarning,
    check_contract_version,
    parse_documents,
    parse_graph,
)


def _doc(schema_version: str) -> str:
    return json.dumps(
        {
            "schema_version": schema_version,
            "id": "RAC-1",
            "type": "decision",
            "status": "Accepted",
            "title": "t",
            "text": "body",
            "metadata": {"source": "rac"},
        }
    )


def _graph(schema_version: str) -> str:
    return json.dumps(
        {"schema_version": schema_version, "source": "rac", "nodes": [], "edges": []}
    )


def test_supported_version_is_one() -> None:
    assert SUPPORTED_CONTRACT_VERSION == "1"


def test_check_is_silent_on_supported_major() -> None:
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning would fail the test
        check_contract_version("1")


def test_check_warns_on_different_major() -> None:
    with pytest.warns(ContractVersionWarning, match="schema_version '2'"):
        check_contract_version("2")


def test_documents_reader_warns_on_unknown_version() -> None:
    with pytest.warns(ContractVersionWarning):
        list(parse_documents([_doc("2")]))


def test_documents_reader_silent_on_version_one() -> None:
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        records = list(parse_documents([_doc("1")]))
    assert [r.id for r in records] == ["RAC-1"]


def test_graph_reader_warns_on_unknown_version() -> None:
    with pytest.warns(ContractVersionWarning):
        parse_graph(_graph("2"))


def test_graph_reader_silent_on_version_one() -> None:
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        graph = parse_graph(_graph("1"))
    assert graph.source == "rac"
