<!-- lore-connector
name: Neo4j
tagline: graph → typed nodes & edges via Cypher MERGE; idempotent on the canonical id
extra: neo4j
order: 60
status: drafted (live run pending)
-->
# Neo4j

The other export projection, `rac export --graph`, is Lore's *real, validated*
relationship graph — typed nodes and edges (`supersedes`, `related_decisions`,
…). The [Neo4j](https://neo4j.com) connector loads it so an agent can traverse
the actual decision graph instead of one an LLM inferred from prose:

```bash
pip install 'lore-connectors[neo4j]'
export NEO4J_URI=bolt://localhost:7687 NEO4J_USERNAME=neo4j NEO4J_PASSWORD=...

rac export rac/ --graph | lore-connect neo4j            # upsert nodes + edges
rac export rac/ --graph | lore-connect neo4j --dry-run  # preview, no connection
lore-connect neo4j --input graph.json                   # read a file, not stdin
```

- **Idempotent via Cypher `MERGE`** on the canonical `id` — nodes
  `MERGE (n:Artifact {id})`, edges `MERGE (a)-[r:REL {type}]->(b)` — so a re-push
  updates in place and never duplicates a node or relationship.
- **Faithful to the export.** Undirected edges (`directed:false`) are written
  once carrying `directed=false`; unresolved references (`resolved:false`) are
  skipped, never written as phantom nodes.
- **Injection-safe.** Every node and edge value is a query parameter; only the
  fixed labels `Artifact`/`REL` are interpolated, so no corpus content reaches
  Cypher as code.
- **Outbound only.** It writes the graph and never queries, traverses, or
  analyses — the verify-in-Lore loop stays the agent's job. Auth via `NEO4J_URI`
  / `NEO4J_USERNAME` / `NEO4J_PASSWORD`.

### The `--graph` contract it consumes

`rac export <dir> --graph` emits one JSON object of typed nodes and edges:

```json
{"schema_version":"1","source":"rac",
 "nodes":[{"id":"RAC-…","type":"decision","status":"Accepted","title":"…"}],
 "edges":[{"source":"RAC-…","target":"RAC-…","type":"supersedes",
           "directed":true,"resolved":true}]}
```

`edges[].type` is the real relationship kind with its registry direction;
`resolved:false` means the reference didn't resolve and `target` is literal text.
The contract is additive and stable (rac-core ADR-007).

### Python API

```python
from lore_connectors import parse_graph
from lore_connectors.neo4j import Neo4jConnector, client_from_env

graph = parse_graph(open("graph.json").read())
summary = Neo4jConnector(client_from_env()).push_graph(graph)
print(summary.summary_line())       # -> "neo4j push: 1494 pushed, 0 skipped"
```

Pass `dry_run=True` to preview without a client or a connection.

Design + decision: [`rac/designs/`](../../rac/designs/) (graph-connector-shape) and
[`rac/decisions/`](../../rac/decisions/) (ADR-003).
