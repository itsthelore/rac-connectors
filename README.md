# lore-connectors

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/itsthelore/lore-connectors/main/rac/assets/images/lore-header-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/itsthelore/lore-connectors/main/rac/assets/images/lore-header-light.png">
  <img alt="Lore — agents that know why. Deterministic. Read-only. No RAG, no guessing." src="https://raw.githubusercontent.com/itsthelore/lore-connectors/main/rac/assets/images/lore-header-light.png">
</picture>

<p align="center">
<a href="#quickstart">Quickstart</a> ·
<a href="#how-it-compares">How it compares</a> ·
<a href="#how-it-works">How it works</a> ·
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

1. **Install** the connector (with the Supermemory backend extra):

   ```bash
   pip install -e '.[supermemory]'
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

Re-running is idempotent: each record upserts on its canonical Lore `id`, so a
re-push updates rather than duplicates.

## Install

| Command | Gets you |
|---|---|
| `pip install -e .` | the `lore-connect` CLI + the connector library |
| `pip install -e '.[supermemory]'` | + the Supermemory backend SDK (live push) |
| `pip install -e '.[dev]'` | + ruff, mypy, and pytest for development |

Requires Python 3.11+. The core install and the whole test-suite are
dependency-free — provider SDKs are optional extras, so CI never needs a live
backend.

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

## Add a backend

One repo, one module per backend (rac-core ADR-073; this repo's ADR-002). A new
backend is a module under `src/lore_connectors/` implementing one outbound seam:

```python
class Connector(Protocol):
    name: str
    def push(self, records: Iterable[Record], *, dry_run: bool = False) -> PushSummary: ...
```

Record parsing, the CLI, dry-run, and the summary shape are shared; a module
supplies the upsert mapping behind a thin, mockable client. Named future targets
(shape only, not built): documents → Mem0, Zep, Letta, Cognee, Pinecone,
Weaviate, Qdrant, Chroma, Milvus, pgvector, LanceDB; graph → Neo4j, Zep
Graphiti, Cognee, Microsoft GraphRAG.

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
