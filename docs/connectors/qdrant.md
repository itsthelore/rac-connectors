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

### Live smoke test

The connector is wired and unit-tested against fakes, but the live path (a real
Qdrant plus a real embeddings endpoint) is unproven until someone runs it — this
page is `drafted (live run pending)`. To validate end to end:

1. **Start Qdrant:** `docker run -p 6333:6333 qdrant/qdrant`.
2. **Pick an embeddings endpoint** — a LiteLLM (or any OpenAI-compatible)
   `/embeddings` gateway; note the model and its vector dimension.
3. **Configure the environment:**

   ```bash
   export QDRANT_URL=http://localhost:6333       # + QDRANT_API_KEY if needed
   export RAC_EMBED_BASE_URL=https://your-litellm/v1
   export RAC_EMBED_MODEL=text-embedding-3-small
   export RAC_EMBED_API_KEY=sk-...                # if the endpoint requires it
   ```

4. **Dry-run first** (no embed, no calls) — confirms records and collections:
   `rac export rac/ --documents | rac-connect qdrant --dry-run`.
5. **Live push:** `rac export rac/ --documents | rac-connect qdrant`.
6. **Verify in Qdrant:** the collection (named after the corpus `source`,
   default `lore`) exists with the model's vector size; the point count equals the
   artifact count; a point's payload carries `rac_id`, `type`, `status`, `title`,
   and `text`.
7. **Re-run the push** and confirm the point count is unchanged — the upsert is
   idempotent on `uuid5(rac_id)`.

Then flip this page's `status` to `shipped`.
