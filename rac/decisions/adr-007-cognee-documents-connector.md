---
schema_version: 1
id: LCON-KVMPXA7MQ5VR
type: decision
---
# ADR-007: Cognee Is a Documents Backend — Two-Phase Pipeline, Content-Hash Idempotent

## Context

Cognee is a documents-export backend (ADR-002: one module and one CLI subcommand
per backend), but it is unlike the memory backends that came before it. Verified
against cognee 1.2.0, it is:

- **A module-level async pipeline**, not a client with an API key:
  `await cognee.add(data, dataset_name=…)` stages data, then
  `await cognee.cognify(datasets=[…])` builds a knowledge graph and embeds it
  locally.
- **Idempotent by content hash already** — `incremental_loading` (its default)
  skips re-ingesting unchanged data, so a re-push is naturally a no-op without
  any resync.
- **Without a per-record metadata filter** — Cognee derives a graph from content;
  it does not store per-document metadata you can later filter on the way
  Supermemory/Mem0/Zep/Letta do.

These three properties mean the Mem0/Zep/Letta pattern (a thin add + a resync)
does not transfer directly. This ADR records how Cognee fits the seam anyway.

## Decision

- **Cognee is a documents backend on the `push(records)` seam**, but its client
  is a **two-phase stage-then-commit**: `add(payload, container)` stages a
  document into a dataset, and `commit()` runs `cognee.add(list) + cognee.cognify`
  **once per dataset** — so the expensive graph build happens once, not per
  record. The async pipeline is run from the sync connector via `asyncio.run`
  inside the adapter; `cognee` is imported lazily so a dry run never loads it.
- **A corpus `source` maps to a Cognee dataset** (and a `node_set` tag).
- **Idempotency is Cognee's native content-hash dedup** (`incremental_loading`),
  not a resync. Re-pushing unchanged records is a no-op; changed records are
  reprocessed.
- **Provenance is carried as a header line in each document**, because Cognee has
  no per-record metadata filter: every payload is prefixed with `Lore-Id`, type,
  status, and title, keeping the verify-in-Lore handle recoverable from Cognee's
  graph.
- **Cognee builds the graph and embeds; nothing is embedded here** (rac-core
  ADR-002, ADR-066). Auth is `LLM_API_KEY` (Cognee needs an LLM to cognify); an
  optional `[cognee]` extra (ADR-073).

## Consequences

### Positive

- Cognee composes graph + vector recall over the corpus with idempotency it
  provides natively — no destructive resync, and no per-record reprocessing of
  unchanged content.
- The two-phase client and the provenance header are isolated in the Cognee
  module; the CLI and `PushSummary` are unchanged.

### Negative / trade-offs

- **Deletions are not pruned.** Content-hash idempotency keeps the store free of
  duplicates but does not remove artifacts deleted from the corpus, unlike the
  wipe-and-rebuild backends. Accepted for this backend: Cognee's per-dataset
  delete is not a clean primitive, and a global prune would wipe unrelated
  datasets. Pruning deletions is a documented follow-up.
- **Provenance lives in the document text**, not in a metadata field, so it
  slightly pollutes the content Cognee reasons over. Accepted: it is the only way
  to keep the canonical `id` recoverable given Cognee's model, and it is a small,
  structured header.
- **Heavier and async.** The pipeline is expensive and pulls a large dependency;
  isolated behind the `[cognee]` extra and a lazy import.

## Status

Accepted

## Category

Architecture

## Alternatives Considered

### A resync like Mem0/Zep/Letta (prune then re-add)

Rejected: Cognee's `prune` is global (it would wipe unrelated datasets), and it
exposes no clean per-dataset reset. Its native `incremental_loading` is the
intended idempotency mechanism, so the connector uses that instead.

### Per-record `add` + `cognify` (no batching)

Rejected: `cognify` is an expensive graph build; running it per record would be
needlessly slow. Staging all records and building once per dataset is the correct
shape.

### Carry provenance in `node_set` tags instead of a text header

Considered: `node_set` tags the dataset's nodes but is a poor fit for a unique
per-document `id` (it is a small set of shared tags). A header line keeps the
`id` attached to the specific document, so it was preferred; `node_set` still
carries the coarse `source` tag.

## Related Decisions

- adr-001
- adr-002

## Review Date

Revisit when Cognee exposes a clean per-dataset reset (to prune deletions) or a
per-record metadata filter (to move provenance out of the document text).
