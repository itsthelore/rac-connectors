<!-- lore-connector
name: Zep
tagline: documents → a Zep knowledge graph; idempotent by graph resync
extra: zep
order: 30
status: drafted (live run pending)
-->
# Zep

A one-way, outbound push of the `rac export --documents` stream into
[Zep Cloud](https://getzep.com). Same stream and flags as the other documents
backends, a different subcommand:

```bash
pip install 'lore-connectors[zep]'
export ZEP_API_KEY=z_...

rac export rac/ --documents | lore-connect zep            # upsert every record
rac export rac/ --documents | lore-connect zep --dry-run  # preview, no API call
lore-connect zep --input corpus.jsonl                     # read a file, not stdin
```

- **A corpus maps to a Zep graph.** A `source` becomes a Zep `graph_id`; each
  record is added as a `type="text"` episode carrying the canonical `lore_id`,
  `type`, `status`, and `title` in metadata.
- **Idempotent by graph resync.** Zep has no per-record upsert key, so each push
  deletes and recreates the corpus graph, then re-adds — re-running never
  duplicates.
- **No embeddings here.** Zep derives its knowledge graph and embeds; the
  connector only ships text + metadata. Zep's copy is an associative index, not a
  citation — authoritative text is always re-fetched from Lore.
- **Auth via `ZEP_API_KEY`** — never hard-coded.

Decision: [`rac/decisions/`](../../rac/decisions/) — ADR-005 (Zep backend, graph-resync idempotency).
