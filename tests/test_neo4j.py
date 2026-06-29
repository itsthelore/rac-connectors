"""The Neo4j connector: node/edge MERGE mapping, idempotency, dry-run."""

from __future__ import annotations

from typing import Any

import pytest

from rac_connectors.graph import Graph, GraphEdge, GraphNode
from rac_connectors.neo4j import Neo4jConnector


class FakeNeo4jClient:
    """In-memory stand-in for the Neo4j driver.

    Records every statement, and emulates MERGE by keying nodes on ``id`` and
    relationships on ``(source, type, target)`` so a test can assert that a
    re-push updates in place rather than duplicating.
    """

    def __init__(self) -> None:
        self.statements: list[tuple[str, dict[str, Any]]] = []
        self.nodes: dict[str, dict[str, Any]] = {}
        self.rels: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.closed = False

    def run(self, cypher: str, parameters: dict[str, Any]) -> None:
        self.statements.append((cypher, parameters))
        if cypher.startswith("MERGE (n:Artifact"):
            self.nodes[parameters["id"]] = dict(parameters)
        else:  # edge MERGE
            key = (parameters["source"], parameters["type"], parameters["target"])
            self.rels[key] = dict(parameters)

    def close(self) -> None:
        self.closed = True


def _graph() -> Graph:
    return Graph(
        source="rac",
        nodes=[
            GraphNode("RAC-1", "decision", "Accepted", "A"),
            GraphNode("RAC-2", "design", "Proposed", "B"),
        ],
        edges=[
            GraphEdge("RAC-1", "RAC-2", "related_designs", False, True),
        ],
    )


def test_nodes_and_edges_merge_with_parameters() -> None:
    client = FakeNeo4jClient()
    summary = Neo4jConnector(client).push_graph(_graph())

    assert summary.pushed == 3  # 2 nodes + 1 edge
    assert client.nodes["RAC-1"] == {
        "id": "RAC-1",
        "type": "decision",
        "status": "Accepted",
        "title": "A",
        "source": "rac",
    }
    rel = client.rels[("RAC-1", "related_designs", "RAC-2")]
    assert rel["directed"] is False
    # Every statement is parameterised — no corpus content interpolated as Cypher.
    for cypher, params in client.statements:
        assert "$" in cypher and params


def test_repush_is_idempotent() -> None:
    client = FakeNeo4jClient()
    connector = Neo4jConnector(client)

    connector.push_graph(_graph())
    # Re-export with an edited node title, same ids.
    edited = _graph()
    edited.nodes[0] = GraphNode("RAC-1", "decision", "Accepted", "A (edited)")
    connector.push_graph(edited)

    assert len(client.nodes) == 2  # not duplicated
    assert len(client.rels) == 1
    assert client.nodes["RAC-1"]["title"] == "A (edited)"  # updated in place


def test_unresolved_edges_are_skipped() -> None:
    client = FakeNeo4jClient()
    graph = Graph(
        source="rac",
        nodes=[GraphNode("RAC-1", "decision", "Accepted", "A")],
        edges=[GraphEdge("RAC-1", "adr-999", "related_decisions", False, False)],
    )
    summary = Neo4jConnector(client).push_graph(graph)

    assert summary.pushed == 1  # the node only
    assert summary.skipped == 1  # the unresolved edge
    assert client.rels == {}  # never written — no phantom target node
    assert "unresolved" in " ".join(summary.actions)


def test_dry_run_writes_nothing() -> None:
    client = FakeNeo4jClient()
    summary = Neo4jConnector(client).push_graph(_graph(), dry_run=True)

    assert summary.dry_run is True
    assert summary.pushed == 3
    assert client.statements == []  # nothing sent to the database


def test_dry_run_needs_no_client() -> None:
    summary = Neo4jConnector().push_graph(_graph(), dry_run=True)
    assert summary.pushed == 3


def test_live_push_without_client_errors() -> None:
    with pytest.raises(RuntimeError, match="required for a live push"):
        Neo4jConnector().push_graph(_graph())
