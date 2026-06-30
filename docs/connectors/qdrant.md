<!-- rac-connector
name: Qdrant
tagline: documents → external embedding → a Qdrant collection; idempotent on the canonical id
category: Memory & RAG
extra: qdrant
order: 25
status: drafted (live run pending)
-->
# Qdrant

A one-way, outbound push of the `rac export --documents` stream into
[Qdrant](https://qdrant.tech), the open-source vector database.

Qdrant stores vectors but does **not** produce them (unlike Supermemory/Mem0/Zep,
which embed server-side). So this connector embeds each record's text through a
**configured external embedding service** — any OpenAI-compatible `/embeddings`
endpoint, with a [LiteLLM](https://litellm.ai) gateway the reference deployment —
then upserts the vector. The model and credentials live in that endpoint, never
in RAC (the engine stays AI-optional, rac-core ADR-002/ADR-066); see
[ADR-009](../../rac/decisions/adr-009-vector-store-connectors-embed-externally.md).

```bash
pip install 'rac-connectors[qdrant]'
export QDRANT_URL=http://localhost:6333          # and QDRANT_API_KEY if your server needs auth
export RAC_EMBED_BASE_URL=https://your-litellm/v1 # OpenAI-compatible /embeddings endpoint
export RAC_EMBED_MODEL=text-embedding-3-small      # whatever your gateway routes
export RAC_EMBED_API_KEY=sk-...                    # if the endpoint requires auth

rac export rac/ --documents | rac-connect qdrant            # embed + upsert every record
rac export rac/ --documents | rac-connect qdrant --dry-run  # preview, no embed, no API call
rac-connect qdrant --input corpus.jsonl                     # read a file, not stdin
```

Each record maps to one Qdrant point:

```
record → upsert(point_id=uuid5(canonical id),
                vector=embed(text),
                payload={rac_id, type, status, title, text, …metadata})
```

| Flag | Meaning |
|---|---|
| `--dry-run` | Print what would be sent; embed nothing and call no API. |
| `--input`, `-i` | Read JSONL from a file (default: stdin; `-` also means stdin). |
| `--strict` | Fail on a malformed line instead of skipping it. |
| `--verbose`, `-v` | Print per-record actions on a live push too. |

- **Idempotent on the canonical `id`.** The point id is `uuid5(id)`, so a re-push
  upserts in place rather than duplicating.
- **One collection per corpus `source`** (falling back to `lore`); the collection
  is created on first use with the embedder's vector dimension and cosine distance.
- **Embeddings live in the external endpoint**, not here. **Pin the embedding
  model** — the vectors, and the collection's dimension, are tied to it; changing
  the model means re-embedding the corpus.
- **Auth via `QDRANT_URL` / `QDRANT_API_KEY`** and the `RAC_EMBED_*` variables —
  never hard-coded.
