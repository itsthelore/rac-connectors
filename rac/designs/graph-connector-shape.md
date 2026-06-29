---
schema_version: 1
id: LCON-KVMK1G2259TS
type: design
---
# Graph Connector Shape

## Context

The documents target shipped first: a flat JSONL stream pushed through the
`Connector.push(records)` seam into Supermemory. The `--graph` projection
(rac-core ADR-074) is a different shape — a single JSON object of typed **nodes
and edges**, not a stream of independent records — so it needs its own reader
and its own push seam. This design fixes that shape, and the Cypher mapping for
the first graph backend, Neo4j, before any code is written. It is the "short
design the graph projection carries when scheduled" that the rac-core export
design anticipated.

## User Need

- **A team running a graph database** wants Lore's real, validated relationship
  graph loaded into it — typed edges with direction — so an agent can traverse
  the actual decision graph rather than one inferred from prose, and still
  verify any node back in Lore by its canonical `id`.
- **The connector author** needs the graph path to slot into the existing
  companion without disturbing the documents path: shared CLI, shared summary,
  shared dry-run, a new seam only where the shape genuinely differs.

## Design

### The graph reader

`graph.py` parses the `--graph` object into frozen dataclasses mirroring the
contract: `GraphNode(id, type, status, title)`, `GraphEdge(source, target,
type, directed, resolved)`, and `Graph(source, nodes, edges, schema_version)`.
It applies the same malformed-input discipline as `records.py`: a structurally
invalid graph raises a guarded error; unknown additive fields are tolerated
(rac-core ADR-007).

### The push seam

A sibling protocol in `base.py`, leaving the documents `Connector` untouched:

```python
class GraphConnector(Protocol):
    name: str
    def push_graph(self, graph: Graph, *, dry_run: bool = False) -> PushSummary: ...
```

It reuses the existing `PushSummary` (nodes and edges are counted as `pushed`;
skipped unresolved edges as `skipped`). Documents and graph stay separate seams
because their inputs differ; the CLI, summary, and dry-run are shared.

### The Neo4j mapping

Idempotency comes from Cypher `MERGE` keyed on the canonical `id`:

- **Nodes:** `MERGE (n:Artifact {id: $id}) SET n.type=$type, n.status=$status,
  n.title=$title, n.source=$source`. One label (`:Artifact`) plus a `type`
  property keeps the schema simple and the `MERGE` key single.
- **Edges:** `MATCH (a:Artifact {id:$source}), (b:Artifact {id:$target})
  MERGE (a)-[r:REL {type:$type}]->(b) SET r.directed=$directed`. The Cypher
  relationship type is a fixed label `REL` with the real kind carried in a
  `type` property — because a relationship type cannot be a query parameter, and
  carrying it as a property keeps every edge parameterised and injection-safe.

A re-push of an edited corpus updates node properties in place and creates no
duplicate nodes or relationships, because both `MERGE`s are keyed on stable
identity.

### Direction and unresolved references

- **Undirected edges** (`directed: false`, e.g. `related_*`) are written as a
  **single** relationship carrying `directed=false`; the connector does not
  invent a reciprocal edge. The graph stays a faithful image of the export, and
  a consumer that wants symmetric traversal reads the property.
- **Unresolved edges** (`resolved: false`, whose `target` is literal reference
  text, not a canonical id) are **skipped** and counted, never written. This
  mirrors the documents side's no-phantom-nodes rule: the connector will not
  `MERGE` a target node that Lore could not resolve.

### Auth and CLI

Auth is read from the environment (`NEO4J_URI`, `NEO4J_USERNAME`,
`NEO4J_PASSWORD`), never hard-coded. The CLI adds one subcommand:
`rac export rac/ --graph | rac-connect neo4j`, with the shared `--dry-run`,
`--input`, and `--strict` flags.

## Constraints

- **Additive only.** The documents `Connector`, reader, and CLI are unchanged;
  the graph path is new modules and a new subcommand (rac-core ADR-007, ADR-063).
- **Outbound only.** `push_graph` writes nodes and edges and never reads back,
  queries, or analyses — the verify-in-Lore loop stays the agent's job, and no
  embeddings or analytics run in the connector (rac-core ADR-002, ADR-066).
- **Injection-safe.** Node and edge properties are always query parameters;
  the only interpolated identifiers are the fixed labels `Artifact`/`REL`, so no
  corpus content reaches Cypher as code.
- **Offline-testable.** The Neo4j driver sits behind a thin client Protocol so
  CI drives a fake and never connects to a database.

## Rationale

- A **separate seam** (not an overloaded `push`) keeps each input type honest:
  documents are an `Iterable[Record]`, a graph is one `Graph`. Sharing the CLI
  and summary captures the real commonality without forcing one signature over
  two different shapes.
- **`MERGE` on `id`** is the simplest idempotency that exists in Cypher and maps
  exactly to the canonical-id contract, so re-sync is safe by construction.
- A **single `:Artifact` label and `REL` type** keep the loaded schema small and
  every value parameterised; richer per-type labels can be added additively
  later without breaking the `MERGE` keys.

## Alternatives

- **Overload `push` for both shapes** — rejected: it blurs two genuinely
  different inputs and weakens typing for no gain.
- **Reciprocal edges for undirected relationships** — rejected as the default:
  it double-counts and diverges from the export; a consumer can derive symmetry
  from the `directed` property.
- **Placeholder nodes for unresolved edges** — rejected: it invents graph
  structure Lore deliberately did not resolve, contradicting the no-phantom rule.
- **Per-type node labels and per-kind relationship types** — deferred, not
  rejected: it is a richer schema that can land additively once a real query
  workload asks for it.

## Accessibility

A machine contract, but the provenance concern carries over: every node keeps
the canonical `id`, `type`, and `status`, so an operator auditing what an agent
traversed can always trace a graph node back to the authoritative, current Lore
artifact rather than to the backend's copy.

## Style Guidance

- Dataclass field names mirror the `--graph` contract exactly
  (`source`/`target`/`type`/`directed`/`resolved`), lowercase snake_case.
- Cypher keeps fixed labels (`Artifact`, `REL`) and parameterises everything
  else; relationship kinds live in a `type` property.
- The graph subcommand mirrors the documents one: `--dry-run`, `--input`,
  `--strict`.

## Open Questions

- Whether to add per-type node labels (`:Decision`, `:Design`, …) once a query
  workload needs them, alongside the base `:Artifact` label.
- Whether multi-corpus graphs should namespace by `source` with a label or only
  a property, when more than one corpus is loaded into one database.
- The `--strict` policy for a malformed graph object versus a single bad edge.

## Related Decisions

- adr-003
- adr-002

## Related Roadmaps

- graph-connector
