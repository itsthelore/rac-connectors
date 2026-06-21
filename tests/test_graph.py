"""Parsing the ``rac export --graph`` contract into a typed graph."""

from __future__ import annotations

import json

import pytest

from lore_connectors.graph import (
    Graph,
    GraphEdge,
    GraphNode,
    MalformedGraphError,
    parse_graph,
)

_GRAPH = {
    "schema_version": "1",
    "source": "rac",
    "nodes": [
        {"id": "RAC-1", "type": "decision", "status": "Accepted", "title": "A"},
        {"id": "RAC-2", "type": "design", "status": "Proposed", "title": "B"},
    ],
    "edges": [
        {
            "source": "RAC-1",
            "target": "RAC-2",
            "type": "related_designs",
            "directed": False,
            "resolved": True,
        },
        {
            "source": "RAC-2",
            "target": "adr-999",
            "type": "related_decisions",
            "directed": False,
            "resolved": False,
        },
    ],
}


def test_parses_nodes_and_edges() -> None:
    graph = parse_graph(json.dumps(_GRAPH))
    assert isinstance(graph, Graph)
    assert graph.source == "rac"
    assert graph.schema_version == "1"
    assert [n.id for n in graph.nodes] == ["RAC-1", "RAC-2"]
    assert graph.nodes[0] == GraphNode("RAC-1", "decision", "Accepted", "A")
    first = graph.edges[0]
    assert first == GraphEdge("RAC-1", "RAC-2", "related_designs", False, True)


def test_unresolved_edge_keeps_literal_target() -> None:
    graph = parse_graph(json.dumps(_GRAPH))
    unresolved = graph.edges[1]
    assert unresolved.resolved is False
    assert unresolved.target == "adr-999"  # literal reference, not a canonical id


def test_edge_flags_default_when_absent() -> None:
    payload = {
        "source": "rac",
        "nodes": [],
        "edges": [{"source": "A", "target": "B", "type": "supersedes"}],
    }
    edge = parse_graph(json.dumps(payload)).edges[0]
    assert edge.directed is True  # additive-tolerant defaults
    assert edge.resolved is True


def test_empty_payload_is_malformed() -> None:
    with pytest.raises(MalformedGraphError, match="empty"):
        parse_graph("   ")


def test_non_object_payload_is_malformed() -> None:
    with pytest.raises(MalformedGraphError, match="not a JSON object"):
        parse_graph("[1, 2, 3]")


def test_invalid_json_is_malformed() -> None:
    with pytest.raises(MalformedGraphError, match="invalid JSON"):
        parse_graph("{not json")


def test_missing_source_is_malformed() -> None:
    with pytest.raises(MalformedGraphError, match="source"):
        parse_graph(json.dumps({"nodes": [], "edges": []}))


def test_node_missing_field_is_malformed() -> None:
    payload = {
        "source": "rac",
        "edges": [],
        "nodes": [{"id": "RAC-1", "type": "decision", "status": "Accepted"}],
    }
    with pytest.raises(MalformedGraphError, match="title"):
        parse_graph(json.dumps(payload))


def test_nodes_not_a_list_is_malformed() -> None:
    with pytest.raises(MalformedGraphError, match="arrays"):
        parse_graph(json.dumps({"source": "rac", "nodes": {}, "edges": []}))
