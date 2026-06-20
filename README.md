# lore-connectors

**Outbound connectors that push [Lore](https://github.com/itsthelore/rac-core)'s
product knowledge into the memory, RAG, and graph backends your team already
runs** — so an agent can recall fuzzily there, then **verify in Lore**.

This is a companion to **Lore** (the product) / **RAC** (the engine — package
`requirements-as-code`, repo
[`itsthelore/rac-core`](https://github.com/itsthelore/rac-core)). RAC keeps a
team's requirements, decisions, designs, roadmaps, and prompts as typed Markdown
and serves them read-only over MCP. This repo holds the **one-way, outbound**
connectors that ship RAC's export payloads into external backends.

It is a *consumer of a stable export contract*, not part of the engine. No
embeddings, vectors, or LLM ever run here — those live in the backend. If a
connector needs the contract to change, that is a change in `rac-core`, never
worked around from this side.

## How it fits together

```
rac export rac/ --documents        # RAC emits one JSON line per artifact
        │
        ▼
lore-connect supermemory           # this repo: upsert each record into the backend
        │
        ▼
Supermemory  (fuzzy, associative recall)
        │
        ▼  agent recalls a candidate, then…
get_artifact / rac resolve         # …verifies the authoritative text in Lore
```

The connector only keeps the backend **fresh**. The *verify-in-Lore* loop — re-fetch
the authoritative artifact by `id`, drop retired ones by `status`, act on Lore's
verbatim text — is the reading agent's job, not this connector's.

## First connector: Supermemory

A one-way push: read a `rac export --documents` JSON Lines stream and upsert each
record into [Supermemory](https://supermemory.ai).

```bash
pip install -e '.[supermemory]'
export SUPERMEMORY_API_KEY=sk-...

# Push the whole corpus (idempotent — re-running updates, never duplicates):
rac export rac/ --documents | lore-connect supermemory

# Preview without calling the API:
rac export rac/ --documents | lore-connect supermemory --dry-run

# Read from a file instead of stdin:
lore-connect supermemory --input corpus.jsonl
```

Each record maps to a Supermemory upsert:

```
record  →  add(content=text,
               container_tag=metadata.source,
               metadata={id, type, status, title, path, …},
               custom_id=id)
```

- **One-way / outbound only.** Pushes to the backend; never pulls, re-ranks, or
  routes.
- **Idempotent on the canonical `id`.** `custom_id=id` makes a re-push an update,
  not a duplicate.
- **No embeddings here.** Supermemory embeds; the connector only ships text +
  metadata.
- **`--dry-run`** prints what would be sent without calling the API.
- **Auth via `SUPERMEMORY_API_KEY`** — never hard-coded.

### Flags

| Flag | Meaning |
| --- | --- |
| `--dry-run` | Print what would be sent; make no API call. |
| `--input`, `-i` | Read JSONL from a file (default: stdin; `-` also means stdin). |
| `--strict` | Fail on a malformed line instead of skipping it. |
| `--verbose`, `-v` | Print per-record actions on a live push too. |

## The export contract consumed

`rac export <dir> --documents` emits JSON Lines, one record per artifact:

```json
{"schema_version":"1","id":"RAC-…","type":"decision","status":"Accepted",
 "title":"ADR-001: Markdown First","text":"…Markdown body, frontmatter stripped…",
 "metadata":{"path":"…","aliases":["adr-001"],"tags":[],"source":"rac"}}
```

`text` is the Markdown body (backends embed text, not HTML); `id` is the
canonical handle for the verify-in-Lore round-trip; `status` lets a reader drop
retired/superseded items. The contract is additive and stable — connectors
depend only on it.

## Adding a backend

One repo, one module per backend (see `rac/decisions/`, ADR-002). A new backend
is a module under `src/lore_connectors/` implementing one seam:

```python
class Connector(Protocol):
    name: str
    def push(self, records: Iterable[Record], *, dry_run: bool = False) -> PushSummary: ...
```

Record parsing, the CLI, dry-run, and the summary shape are shared; a module
provides the upsert mapping behind a thin, mockable client. Named future targets
(shape only, not built): documents → Mem0, Zep, Letta, Cognee, Pinecone,
Weaviate, Qdrant, Chroma, Milvus, pgvector, LanceDB; graph → Neo4j, Zep
Graphiti, Cognee, Microsoft GraphRAG.

## Development

```bash
pip install -e '.[dev]'
pytest          # no live API — drives a fake client
ruff check .
```

This repo dogfoods Lore: its own decisions live in `rac/decisions/` and are
validated with the `rac` CLI (`rac validate rac/`).

## License

Apache-2.0 — see [LICENSE](LICENSE). Matches `rac-core`.
