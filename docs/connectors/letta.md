<!-- rac-connector
name: Letta
tagline: documents → Letta archives (cloud or self-hosted); idempotent by archive resync
extra: letta
order: 40
status: drafted (live run pending)
-->
# Letta

A one-way, outbound push of the `rac export --documents` stream into
[Letta](https://letta.com) archives. Same stream and flags as the other
documents backends, a different subcommand:

```bash
pip install 'rac-connectors[letta]'
export LETTA_API_KEY=...                       # Letta Cloud
# or, self-hosted:  export LETTA_BASE_URL=http://localhost:8283

rac export rac/ --documents | rac-connect letta            # upsert every record
rac export rac/ --documents | rac-connect letta --dry-run  # preview, no API call
rac-connect letta --input corpus.jsonl                     # read a file, not stdin
```

- **A corpus maps to a Letta archive.** A `source` becomes a named archive; each
  record is added as a passage carrying the canonical `rac_id`, `type`,
  `status`, and `title` in metadata. (The connector resolves the opaque
  `archive_id` internally, so you address it by the source name.)
- **Idempotent by archive resync.** Letta has no per-record upsert key, so each
  push deletes and recreates the corpus archive, then re-adds — re-running never
  duplicates.
- **Cloud or self-hosted.** Auth via `LETTA_API_KEY` (Letta Cloud) **or**
  `LETTA_BASE_URL` (a self-hosted server). Letta embeds the passages; nothing is
  embedded here.

Decision: [`rac/decisions/`](../../rac/decisions/) — ADR-006 (Letta backend, archive-resync idempotency).
