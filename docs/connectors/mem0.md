<!-- lore-connector
name: Mem0
tagline: documents → server-side embedding; idempotent by container resync
extra: mem0
order: 20
status: drafted (live run pending)
-->
# Mem0

A one-way, outbound push of the `rac export --documents` stream into
[Mem0](https://mem0.ai). Same stream and flags as the other documents backends,
a different subcommand:

```bash
pip install 'lore-connectors[mem0]'
export MEM0_API_KEY=m0-...

rac export rac/ --documents | lore-connect mem0            # upsert every record
rac export rac/ --documents | lore-connect mem0 --dry-run  # preview, no API call
lore-connect mem0 --input corpus.jsonl                     # read a file, not stdin
```

- **Stores the text as-is.** `infer=False` skips Mem0's LLM fact-extraction, so it
  only embeds the artifact text; the canonical `lore_id`, `type`, `status`, and
  `title` ride in metadata for the verify-in-Lore loop.
- **Idempotent by container resync.** Mem0 has no per-record upsert key, so each
  push clears the corpus partition (Mem0 `user_id = source`) and re-adds —
  re-running never duplicates. The trade-off (a wipe-and-rebuild rather than a
  surgical update) is recorded in the decision.
- **No embeddings here.** Mem0 embeds; the connector only ships text + metadata.
- **Auth via `MEM0_API_KEY`** — never hard-coded.

Decision: [`rac/decisions/`](../../rac/decisions/) — ADR-004 (Mem0 backend, resync idempotency).
