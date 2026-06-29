"""The Neo4j graph connector — first graph backend (ADR-003).

A one-way, outbound push of the ``rac export --graph`` projection: ``MERGE`` each
node by canonical ``id`` and each edge by type, so re-syncing an edited corpus
updates in place and never duplicates. Outbound only — it writes nodes and edges
and never queries, traverses, or analyses (rac-core ADR-002, ADR-066).

Cypher is injection-safe: every node and edge value is a query parameter; only
the fixed labels ``Artifact`` and ``REL`` are interpolated, so no corpus content
reaches Cypher as code.
"""

from __future__ import annotations

from ..base import PushSummary
from ..graph import Graph, GraphEdge, GraphNode
from .client import Neo4jClient

BACKEND = "neo4j"

# Fixed, parameterised statements (ADR-003 / graph-connector-shape design).
_MERGE_NODE = (
    "MERGE (n:Artifact {id: $id}) "
    "SET n.type = $type, n.status = $status, n.title = $title, n.source = $source"
)
_MERGE_EDGE = (
    "MATCH (a:Artifact {id: $source}), (b:Artifact {id: $target}) "
    "MERGE (a)-[r:REL {type: $type}]->(b) "
    "SET r.directed = $directed"
)


class Neo4jConnector:
    """Upsert a Lore graph into Neo4j, idempotently on canonical identity."""

    name = BACKEND

    def __init__(self, client: Neo4jClient | None = None) -> None:
        # The client is optional so a dry run needs no driver and no credentials.
        self._client = client

    def _node_params(self, node: GraphNode, source: str) -> dict[str, object]:
        return {
            "id": node.id,
            "type": node.type,
            "status": node.status,
            "title": node.title,
            "source": source,
        }

    def _edge_params(self, edge: GraphEdge) -> dict[str, object]:
        return {
            "source": edge.source,
            "target": edge.target,
            "type": edge.type,
            "directed": edge.directed,
        }

    def push_graph(self, graph: Graph, *, dry_run: bool = False) -> PushSummary:
        summary = PushSummary(backend=self.name, dry_run=dry_run)

        for node in graph.nodes:
            params = self._node_params(node, graph.source)
            if dry_run:
                summary.record_push(node.id, f"node type={node.type}")
            else:
                self._require_client().run(_MERGE_NODE, params)
                summary.record_push(node.id, f"node type={node.type}")

        for edge in graph.edges:
            label = f"{edge.source}-[{edge.type}]->{edge.target}"
            if not edge.resolved:
                # No phantom target node — mirror the documents no-phantom rule.
                summary.record_skip_item(label, "unresolved edge")
                continue
            if dry_run:
                summary.record_push(label, "edge")
            else:
                self._require_client().run(_MERGE_EDGE, self._edge_params(edge))
                summary.record_push(label, "edge")

        return summary

    def _require_client(self) -> Neo4jClient:
        if self._client is None:
            raise RuntimeError(
                "a Neo4jClient is required for a live push; "
                "pass one or use dry_run=True"
            )
        return self._client
