# lore-connectors

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/itsthelore/lore-connectors/main/rac/assets/images/lore-header-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/itsthelore/lore-connectors/main/rac/assets/images/lore-header-light.png">
  <img alt="Lore — agents that know why. Deterministic. Read-only. No RAG, no guessing." src="https://raw.githubusercontent.com/itsthelore/lore-connectors/main/rac/assets/images/lore-header-light.png">
</picture>

<p align="center">
<a href="#quickstart">Quickstart</a> ·
<a href="#how-it-works">How it works</a> ·
<a href="#connectors">Connectors</a> ·
<a href="#add-a-backend">Add a backend</a> ·
<a href="https://github.com/itsthelore/rac-core">Lore / RAC</a>
</p>

<p align="center">
<a href="https://github.com/itsthelore/lore-connectors/actions/workflows/ci.yml"><img src="https://github.com/itsthelore/lore-connectors/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
<img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python">
<a href="https://mypy-lang.org/"><img src="https://img.shields.io/badge/types-Mypy-blue.svg" alt="Typed"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License: Apache 2.0"></a>
</p>

> **Push the decisions your team already recorded into the memory and RAG tools your agent already uses — so it can recall fuzzily there, then verify in Lore.**

lore-connectors is the **outbound** companion to [Lore](https://github.com/itsthelore/rac-core) — the product surface of **RAC — Requirements as Code**, the open-source engine underneath. RAC keeps your team's requirements, decisions, designs, roadmaps, and prompts as typed Markdown and serves them **read-only** over MCP. This repo holds the connectors that ship RAC's export payloads into the external memory, RAG, and graph backends a team already runs. It is a *consumer of a stable export contract*, not part of the engine: no embeddings, vectors, or model calls happen here — those live in the backend. The first connector is **Supermemory**.

## How it compares

A connector isn't a sync tool or a second source of truth — it keeps a fuzzy
backend **fresh** so an agent can recall loosely, then return to Lore for the
exact, current decision. Recall fuzzily, verify in Lore.

| | Lore | The backend (Supermemory / RAG / memory) |
|---|---|---|
| Good at | the exact, current decision | finding what's *near* a question |
| Retrieval | deterministic, reproducible | similarity-ranked, varies by run |
| Role | source of truth, read-only | a fast index this connector keeps fresh |
| Direction | the agent verifies here | this connector pushes here, one-way |

## Quickstart

1. **Install** a connector — pick your backend from [Connectors](#connectors) and
   install its extra (see [Install](#install) for the from-source command until
   it's on PyPI):

   ```bash
   pip install 'lore-connectors[supermemory]'
   ```

2. **Authenticate** the backend via the environment (never hard-coded):

   ```bash
   export SUPERMEMORY_API_KEY=sk-...
   ```

3. **Push** the corpus — pipe a `rac export --documents` stream straight in:

   ```bash
   rac export rac/ --documents | lore-connect supermemory
   ```

4. **Preview** first if you like — `--dry-run` calls no API:

   ```bash
   rac export rac/ --documents | lore-connect supermemory --dry-run
   ```

Re-running is idempotent: a re-push updates rather than duplicates. Each
backend's exact commands, auth, and flags live under [Connectors](#connectors).

## Install

There is nothing to build — it's pure Python. Installing puts a `lore-connect`
command on your PATH.

**From PyPI** (once published — the name is reserved):

```bash
pip install 'lore-connectors[supermemory]'
```

**From source today** (pre-release — install straight from the repo):

```bash
# one-liner, no clone:
pip install 'lore-connectors[supermemory] @ git+https://github.com/itsthelore/lore-connectors.git'

# or from a clone (editable, for hacking on it):
git clone https://github.com/itsthelore/lore-connectors.git
cd lore-connectors
pip install -e '.[supermemory]'
```

| Extra | Gets you |
|---|---|
| *(none)* | the `lore-connect` CLI + the connector library + `--dry-run` |
| `[<backend>]` | + that backend's SDK, needed for a live push — one per connector (see [Connectors](#connectors)) |
| `[dev]` | + ruff, mypy, and pytest for development |

Requires Python 3.11+, and the [`rac`](https://github.com/itsthelore/rac-core)
engine (`pip install requirements-as-code`) to produce the export. The core
install and the whole test-suite are dependency-free — provider SDKs are
optional extras, so CI never needs a live backend.

## How it works

```text
rac export rac/ --documents        # Lore emits one JSON line per artifact
        │
        ▼
lore-connect supermemory           # this repo: upsert each record into the backend
        │
        ▼
Supermemory  (fuzzy, associative recall)
        │
        ▼  the agent recalls a candidate by id, then…
get_artifact / rac resolve         # …verifies the authoritative text in Lore
```

- **One-way, outbound only.** The connector pushes to the backend and never
  pulls, re-ranks, or routes; the verify-in-Lore loop is the reading agent's
  job, not this connector's.
- **Idempotent on the canonical `id`.** Each record maps to
  `add(content=text, container_tag=metadata.source, metadata={id, type, status, …}, custom_id=id)`,
  so re-exporting and re-pushing updates the stored copy instead of duplicating
  it.
- **No embeddings here.** The backend embeds; the connector only ships text and
  metadata (rac-core ADR-002, ADR-066).

## Connectors

One package, one CLI: pick a backend with a subcommand (`lore-connect
<backend>`) and pull only its SDK via the matching extra. Each connector's full
page lives in [`docs/connectors/`](docs/connectors/); the collapsible sections
below are generated from those pages, so this README and the pages never drift.

<!-- GENERATED:CONNECTORS -->
<!-- Generated from docs/connectors/*.md by scripts/sync_readme.py — do not edit by hand. -->

<details>
<summary><strong>Supermemory</strong> — documents → server-side embedding, idempotent on the canonical id</summary>

A one-way, outbound push of the `rac export --documents` stream into
[Supermemory](https://supermemory.ai).

```bash
pip install 'lore-connectors[supermemory]'
export SUPERMEMORY_API_KEY=sk-...

rac export rac/ --documents | lore-connect supermemory            # upsert every record
rac export rac/ --documents | lore-connect supermemory --dry-run  # preview, no API call
lore-connect supermemory --input corpus.jsonl                     # read a file, not stdin
```

Each record maps to a Supermemory upsert:

```
record → add(content=text,
             container_tag=metadata.source,
             metadata={lore id, type, status, title, path, …},
             custom_id=id)
```

| Flag | Meaning |
|---|---|
| `--dry-run` | Print what would be sent; make no API call. |
| `--input`, `-i` | Read JSONL from a file (default: stdin; `-` also means stdin). |
| `--strict` | Fail on a malformed line instead of skipping it. |
| `--verbose`, `-v` | Print per-record actions on a live push too. |

- **Idempotent on the canonical `id`.** `custom_id=id` makes a re-push an update,
  not a duplicate.
- **No embeddings here.** Supermemory embeds; the connector only ships text +
  metadata.
- **Auth via `SUPERMEMORY_API_KEY`** — never hard-coded. Set
  `SUPERMEMORY_BASE_URL` to point at a self-hosted instance.

Decision: [`rac/decisions/`](rac/decisions) — the connector seam (ADR-002).

**Full page:** [`docs/connectors/supermemory.md`](docs/connectors/supermemory.md)

</details>

<details>
<summary><strong>Neo4j</strong> — graph → typed nodes & edges via Cypher MERGE; idempotent on the canonical id</summary>

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

Design + decision: [`rac/designs/`](rac/designs) (graph-connector-shape) and
[`rac/decisions/`](rac/decisions) (ADR-003).

**Full page:** [`docs/connectors/neo4j.md`](docs/connectors/neo4j.md)

</details>

<!-- /GENERATED:CONNECTORS -->

## Run it in CI

`lore-connect` is a one-shot command — it pushes and exits — so keeping a
backend fresh is just a job that runs the pipe whenever the corpus changes. A
GitHub Actions step on merge to `main`:

```yaml
name: Sync corpus to Supermemory
on:
  push:
    branches: [main]
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with:
          python-version: "3.11"
      - run: pip install requirements-as-code 'lore-connectors[supermemory]'
      - run: rac export rac/ --documents | lore-connect supermemory
        env:
          SUPERMEMORY_API_KEY: ${{ secrets.SUPERMEMORY_API_KEY }}
```

The same one-liner works from a cron job or a git post-commit hook. Because the
push is idempotent on the canonical `id`, running it on every change only
updates — it never duplicates — so you don't need to diff or prune first.

## The export contract

`rac export <dir> --documents` emits JSON Lines, one record per artifact:

```json
{"schema_version":"1","id":"RAC-…","type":"decision","status":"Accepted",
 "title":"ADR-001: Markdown First","text":"…Markdown body, frontmatter stripped…",
 "metadata":{"path":"…","aliases":["adr-001"],"tags":[],"source":"rac"}}
```

`text` is the Markdown body (backends embed text, not HTML); `id` is the
canonical handle for the verify-in-Lore round-trip; `status` lets a reader drop
retired or superseded items. The contract is additive and stable (rac-core
ADR-007) — connectors depend only on it.

## Python API

The connector is a library too. Parse a `--documents` stream into records and
push them through any backend module:

```python
from lore_connectors import parse_documents
from lore_connectors.supermemory import SupermemoryConnector, client_from_env

records = parse_documents(open("corpus.jsonl"))
summary = SupermemoryConnector(client_from_env()).push(records)
print(summary.summary_line())       # -> "supermemory push: 263 pushed, 0 skipped"
```

Pass `dry_run=True` to preview without a client or an API call.

## One package, many backends

There is **one** `lore-connectors` package on PyPI, not one per provider. As
more backends land, you don't install or learn a new tool — you:

- **pick the backend with a CLI subcommand:** `lore-connect supermemory`,
  later `lore-connect mem0`, `lore-connect neo4j`, …; and
- **pull only the SDKs you use, as extras:**
  `pip install 'lore-connectors[supermemory,mem0]'`. The base install and the
  test-suite stay dependency-free; a provider's SDK arrives only with its extra.

This is a recorded decision, not a convenience: rac-core ADR-073 keeps all
backend connectors in one repo (the export contract is the product, so most
backends need no per-provider package), and this repo's ADR-002 fixes "one
outbound `push` seam, one module per backend, one CLI subcommand each." A
provider only graduates to its own package if it grows into an installable
product with independent cadence — the documented escape hatch, not the default.

## Add a backend

A new backend is a module under `src/lore_connectors/` implementing one outbound
seam — record parsing, the CLI, dry-run, and the summary shape are shared:

```python
class Connector(Protocol):
    name: str
    def push(self, records: Iterable[Record], *, dry_run: bool = False) -> PushSummary: ...
```

The module supplies the upsert mapping behind a thin, mockable client, and adds
its subcommand and optional `[backend]` extra. Document it once in
`docs/connectors/<backend>.md` (with a `<!-- lore-connector -->` metadata header)
and run `python scripts/sync_readme.py` — that stitches the page into the
[Connectors](#connectors) section above, so each connector owns its own file and
the README never drifts. Named future targets (shape only, not built):
documents → Mem0, Zep, Letta, Cognee, Pinecone, Weaviate, Qdrant, Chroma, Milvus,
pgvector, LanceDB; graph → Neo4j, Zep Graphiti, Cognee, Microsoft GraphRAG.

## Who it's for

- **Teams running Lore** who also run a memory or RAG backend and want the
  agent to recall fuzzily there, then verify against the authoritative corpus.
- **Teams who want semantic recall over their decisions** without putting a
  fuzzy component inside Lore's deterministic serving path.
- **Anyone wiring Lore's export into the backend they already operate** — the
  export contract is the product; this repo is the reference adapter.

## Documentation

This repo consumes Lore's export contract; the engine and its CLI are
documented with Lore.

- [Lore / RAC](https://github.com/itsthelore/rac-core) — the engine, CLI, and MCP server
- [CLI reference — `rac export`](https://itsthelore.github.io/rac-core/cli/#export) — the `--documents` / `--graph` contract this consumes

## Origin

lore-connectors is the **connector companion** to Lore / RAC. rac-core ADR-073
settles the topology: backend connectors are export-contract consumers, so they
consolidate into **one** repo with one module per backend — not a repo per
provider, and never inside the engine (it stays pure-Python, AI-optional, and
offline). This repo dogfoods Lore for its own decisions under `rac/`.

## Repository layout

```text
lore-connectors/
  src/lore_connectors/   the connector library: the documents reader, the shared
                         push seam, the lore-connect CLI, and one module per
                         backend (supermemory/ first)
  tests/                 the suite, driven against a fake client — no live API
  rac/                   the dogfood corpus: this repo's own decisions (ADRs),
                         keyed LCON
  .github/workflows/     CI — ruff, mypy, and the test-suite
```

## Test

```bash
pip install -e .[dev]
python -m pytest
```

`ruff check`, `ruff format --check`, and `mypy src/` run in CI alongside the
test-suite across Python 3.11–3.13.

## Project status

Early and evolving alongside Lore. The Supermemory connector ships today;
further backends slot in as new modules (see [Add a backend](#add-a-backend)).
Contributions, ideas, and experiments welcome.

## License

[Apache License 2.0](LICENSE). Matches `rac-core`.
