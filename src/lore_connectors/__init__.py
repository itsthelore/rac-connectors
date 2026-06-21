"""lore-connectors — outbound connectors that push Lore's export into backends.

Companion to Lore (the product) / RAC (the engine). RAC serves a team's product
knowledge read-only over MCP; this package consumes RAC's stable export contract
(``rac export --documents`` / ``--graph``) and pushes it into the external
memory / RAG / graph backends a team already runs, so an agent can recall fuzzily
there and then verify in Lore.

One repo, one module per backend (ADR-073). Supermemory is module one.
"""

from __future__ import annotations

from .base import Connector, PushSummary
from .records import MalformedRecordError, Record, parse_documents

__all__ = [
    "Connector",
    "MalformedRecordError",
    "PushSummary",
    "Record",
    "parse_documents",
]
