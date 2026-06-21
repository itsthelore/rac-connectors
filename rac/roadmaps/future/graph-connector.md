---
schema_version: 1
id: LCON-KVMK1FV4M38X
type: roadmap
---
# Graph Connector Track

## Outcomes

Lore's corpus is not only a set of documents — it is a typed relationship graph
(decisions supersede decisions, designs relate to requirements, and so on). The
`rac export --graph` projection already emits that graph as typed nodes and
edges (rac-core ADR-074). The outcome this track delivers is the **consumer**
side: an agent (and its operator) can load Lore's *real, validated* decision
graph into a graph backend they already run, instead of one an LLM infers from
prose — and then still verify any node back in Lore by its canonical `id`.

This matters now because the documents target (Supermemory) has shipped, the
`--graph` producer is live, and graph/GraphRAG backends are a distinct,
high-value recall surface that the documents projection cannot serve.

## Initiatives

- **A graph reader and push seam.** Parse the `--graph` JSON into typed nodes
  and edges, and add a sibling outbound seam (`push_graph`) alongside the
  documents `push`, so graph backends slot into the same companion (rac-core
  ADR-073) without disturbing the documents path.
- **A first graph connector: Neo4j.** The most widely-run graph database, with a
  Cypher `MERGE` model that makes node/edge upserts idempotent on the canonical
  `id`. It is the portable reference the later graph backends (Zep Graphiti,
  Cognee, Microsoft GraphRAG) are measured against.
- **Dogfood the decision as RAC artifacts.** A design for the *how* and an ADR
  for the locked choices, validated by the corpus gates in this repo.

## Success Measures

- `rac export rac/ --graph | lore-connect neo4j` upserts every node and edge,
  and re-running is idempotent (no duplicate nodes or relationships).
- `--dry-run` reports the planned nodes/edges with no database connection.
- The connector is covered by offline tests against a fake driver — no live
  Neo4j in CI — including idempotent re-push and unresolved-edge handling.
- The graph reader and seam are additive: the documents path and its contract
  are unchanged.

## Assumptions

- The `--graph` contract (schema_version 1, typed edges with `directed` /
  `resolved` flags) stays additive and stable (rac-core ADR-007).
- Edge `type` values come from rac's closed relationship registry, so they can
  be sanitised to safe Cypher relationship types from a known set.
- Embedding, similarity, and any graph analytics live in the backend, never in
  the connector (rac-core ADR-002, ADR-066).

## Risks

- **Backend API churn.** A young driver API could drift; mitigated by hiding the
  driver behind a thin, mockable client and pinning the verified major.
- **Edge-direction modelling.** Undirected relationships and unresolved
  references need explicit, recorded handling or the loaded graph misrepresents
  the corpus; settled in the design and ADR rather than left implicit.
- **Scope creep into analytics.** The connector must stay an outbound upsert and
  resist becoming a query/recall surface — the verify-in-Lore loop stays the
  agent's job.

## Related Decisions

- adr-003

## Related Designs

- graph-connector-shape
