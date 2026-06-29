"""rac-connectors — outbound connectors that push Lore's export into backends.

Companion to Lore (the product) / RAC (the engine). RAC serves a team's product
knowledge read-only over MCP; this package consumes RAC's stable export contract
(``rac export --documents`` / ``--graph``) and pushes it into the external
memory / RAG / graph backends a team already runs, so an agent can recall fuzzily
there and then verify in Lore.

One repo, one module per backend (ADR-073). Supermemory is module one.
"""

from __future__ import annotations

from .base import Connector, GraphConnector, PushSummary
from .contract import (
    SUPPORTED_CONTRACT_VERSION,
    ContractVersionWarning,
    check_contract_version,
)
from .graph import (
    Graph,
    GraphEdge,
    GraphNode,
    MalformedGraphError,
    parse_graph,
)
from .records import MalformedRecordError, Record, parse_documents

__all__ = [
    "SUPPORTED_CONTRACT_VERSION",
    "Connector",
    "ContractVersionWarning",
    "Graph",
    "GraphConnector",
    "GraphEdge",
    "GraphNode",
    "MalformedGraphError",
    "MalformedRecordError",
    "PushSummary",
    "Record",
    "check_contract_version",
    "parse_documents",
    "parse_graph",
]
