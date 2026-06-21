---
schema_version: 1
id: LCON-KVMK1G6R146P
type: decision
---
# ADR-003: Graph Connectors Use a Node/Edge Push Seam, Neo4j First

## Context

ADR-002 fixed one outbound `push(records)` seam for the documents projection and
explicitly deferred graph: "documents-only for now, the graph seam deferred to
when `--graph` / ADR-074 is scheduled." That time has come — the `rac export
--graph` producer is live (rac-core ADR-074), emitting a single object of typed
nodes and edges with `directed` and `resolved` flags.

A graph push is a different shape from a documents push: one whole graph, not a
stream of independent records. ADR-002 anticipated exactly this ("a sibling seam
later"). Two questions need locking before code: the seam shape, and which graph
backend is the first reference. The design `graph-connector-shape` works the
*how*; this ADR records the *decisions*.

## Decision

- **A sibling seam, not an overload.** Add `GraphConnector.push_graph(graph, *,
  dry_run) -> PushSummary` alongside the documents `Connector`. The documents
  seam, reader, and CLI are untouched (additive — rac-core ADR-007, ADR-063).
  The CLI, `PushSummary`, and `--dry-run` are shared; only the input shape and
  the seam differ.
- **Neo4j is the first graph backend.** The most widely-run graph database, with
  an official Python driver and a Cypher `MERGE` model that makes node/edge
  upserts idempotent on the canonical `id`. It is the portable reference later
  graph backends (Zep Graphiti, Cognee, Microsoft GraphRAG) are measured
  against. It is a module under `lore-connectors`, not a new repo (rac-core
  ADR-073), with the driver behind a thin, mockable client and an optional
  `[neo4j]` extra.
- **Idempotency is `MERGE` on `id`.** Nodes `MERGE (n:Artifact {id})`; edges
  `MERGE (a)-[r:REL {type}]->(b)` after matching both endpoints by id. Re-push
  updates in place and never duplicates.
- **Undirected edges are written once.** `directed: false` relationships are
  stored as a single edge carrying `directed=false`; the connector does not
  invent a reciprocal edge.
- **Unresolved edges are skipped.** `resolved: false` edges (literal,
  unresolved target) are counted and dropped, never written — mirroring the
  documents side's no-phantom-nodes rule.
- **Cypher is injection-safe.** All node and edge properties are query
  parameters; only the fixed labels `Artifact` and `REL` are interpolated, so no
  corpus content reaches Cypher as code.

This does not reopen ADR-002; it extends the connector seam to the graph shape
ADR-002 deferred.

## Consequences

### Positive

- The graph path slots into the existing companion with shared CLI, summary, and
  dry-run; only a reader and a seam are added.
- Re-sync is safe by construction (`MERGE` on the canonical id).
- The loaded graph is a faithful image of Lore's validated relationship graph,
  with provenance (`id`/`type`/`status`) on every node for the verify-in-Lore
  loop.
- CI stays offline — the driver is mocked.

### Negative / trade-offs

- A single `:Artifact` label and `REL` relationship type is a deliberately small
  schema; richer per-type labels are deferred until a query workload needs them.
  Accepted: it can be added additively without breaking `MERGE` keys.
- A second seam (`push_graph`) sits beside `push`. Accepted: the inputs are
  genuinely different shapes, so one signature would weaken typing for no gain.

### Risks

- Driver API churn. Mitigation: a thin client Protocol and a pinned major.
- Edge-direction or unresolved-reference handling drifting from the export.
  Mitigation: both are recorded here and covered by tests.

## Status

Accepted

## Category

Architecture

## Alternatives Considered

### Overload the documents `push` for graphs

Rejected: documents are an `Iterable[Record]` and a graph is one `Graph`;
overloading blurs two different inputs and weakens typing for no benefit.

### A different first graph backend (Zep Graphiti, Cognee, Microsoft GraphRAG)

Reasonable later targets, rejected as *first*: Neo4j is the most portable and
widely-run, and its `MERGE` model is the cleanest expression of the
idempotent-on-`id` contract. The others compose in later as additional modules.

### Reciprocal edges for undirected relationships; placeholder nodes for unresolved edges

Rejected: both invent graph structure the export did not assert, diverging from
Lore's validated graph and the no-phantom rule.

## Related Decisions

- adr-002

## Related Designs

- graph-connector-shape

## Related Roadmaps

- graph-connector

## Review Date

Revisit when a second graph backend lands (testing the seam's generality), or
when a query workload asks for a richer node/edge schema than the base
`:Artifact` / `REL` shape.
