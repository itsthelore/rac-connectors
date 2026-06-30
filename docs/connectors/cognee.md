<!-- rac-connector
name: Cognee
tagline: documents → a Cognee knowledge graph; content-hash idempotent
category: Knowledge graph
extra: cognee
order: 50
status: drafted (live run pending)
-->
# Cognee

The odd one out: [Cognee](https://www.cognee.ai) is an async pipeline that builds
the corpus into a **knowledge graph** (`add` then `cognify`) rather than a
per-record store. It still consumes the same `rac export --documents` stream:

```bash
pip install 'rac-connectors[cognee]'
export LLM_API_KEY=...        # Cognee needs an LLM to cognify

rac export rac/ --documents | rac-connect cognee            # build the graph
rac export rac/ --documents | rac-connect cognee --dry-run  # preview, no pipeline run
rac-connect cognee --input corpus.jsonl                     # read a file, not stdin
```

- **A corpus maps to a Cognee dataset.** Each record is staged with a `Rac-Id:`
  provenance header (Cognee has no per-record metadata filter), then the whole
  dataset is built once via `add` + `cognify`.
- **Content-hash idempotency, not a resync.** Cognee's native
  `incremental_loading` dedups by content hash, so re-pushing unchanged records
  is a no-op. **Caveat:** it does **not** prune artifacts deleted from the corpus
  (unlike the wipe-and-rebuild backends).
- **No embeddings here.** Cognee builds the graph and embeds; the connector only
  ships text. Auth via `LLM_API_KEY` (Cognee's LLM credential).

Decision: [`rac/decisions/`](../../rac/decisions/) — ADR-007 (Cognee backend, two-phase pipeline, the deletion-prune trade-off).
