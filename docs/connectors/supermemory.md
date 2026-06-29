<!-- rac-connector
name: Supermemory
tagline: documents → server-side embedding, idempotent on the canonical id
extra: supermemory
order: 10
status: shipped
-->
# Supermemory

A one-way, outbound push of the `rac export --documents` stream into
[Supermemory](https://supermemory.ai).

```bash
pip install 'rac-connectors[supermemory]'
export SUPERMEMORY_API_KEY=sk-...

rac export rac/ --documents | rac-connect supermemory            # upsert every record
rac export rac/ --documents | rac-connect supermemory --dry-run  # preview, no API call
rac-connect supermemory --input corpus.jsonl                     # read a file, not stdin
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

Decision: [`rac/decisions/`](../../rac/decisions/) — the connector seam (ADR-002).
