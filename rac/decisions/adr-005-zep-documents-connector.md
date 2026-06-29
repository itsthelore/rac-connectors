---
schema_version: 1
id: LCON-KVMN69KS0WWS
type: decision
---
# ADR-005: Zep Is a Documents Backend, Idempotent by Graph Resync

## Context

Zep is a documents-export backend (ADR-002: one module and one CLI subcommand
per backend). Zep Cloud ingests data as **episodes** into a per-namespace
knowledge **graph** that it derives and embeds server-side, so it fits the
existing `Connector.push(records)` seam — no new seam, unlike the graph-export
path (ADR-003).

As with Mem0 (ADR-004), Zep's ingestion has **no per-record upsert key**
(verified against zep-cloud 3.23.0: `graph.add(*, data, type, graph_id,
metadata, …)` returns an `Episode` with no caller-supplied id). Re-running would
duplicate episodes. Unlike Mem0, Zep exposes explicit graph lifecycle methods —
`graph.create(graph_id=…)` and `graph.delete(graph_id)` — which give a clean way
to resync a namespace.

## Decision

- **Zep is a documents backend on the existing `push(records)` seam.** It reuses
  the documents reader, CLI, `PushSummary`, and `--dry-run`.
- **Idempotency is a graph resync.** A corpus `source` maps to a Zep `graph_id`.
  On a push, the first time a graph is seen it is cleared — `graph.delete(id)`
  (tolerating absence on a first sync) then `graph.create(graph_id=id)` — and
  every record for it is added as a `type="text"` episode. Re-running yields
  exactly the corpus, no duplicates, satisfying the contract's "containerTag as
  the upsert key".
- **Records are added as text episodes carrying provenance metadata.** The
  canonical `rac_id`, `type`, `status`, and `title` ride in episode metadata for
  the verify-in-Lore loop and retired-item filtering. Zep derives its graph and
  embeds; no embeddings in the connector (rac-core ADR-002, ADR-066).
- **Auth from the environment** (`ZEP_API_KEY`), the SDK behind a thin, mockable
  client, an optional `[zep]` extra — the standard backend shape (ADR-073).

## Consequences

### Positive

- A third documents backend with no new seam — pure reuse of the documents path.
- Graph resync is unambiguously idempotent and uses Zep's first-class lifecycle
  methods (`create` / `delete`), cleaner than a metadata-filtered prune.
- Provenance (`rac_id`/`status`) is preserved for the verify-in-Lore loop.

### Negative / trade-offs

- A resync deletes and recreates the whole graph before re-adding, so a push is a
  wipe-and-rebuild: there is a window where the graph is incomplete, and Zep
  re-derives the graph from scratch each sync. Accepted: Zep exposes no
  per-record upsert key, the sync is a one-shot job, and the contract permits
  container-level idempotency.
- Zep's stored form is an LLM-derived knowledge graph, not the verbatim artifact.
  Accepted and by design: Zep's copy is an associative index; authoritative text
  is always re-fetched from Lore (the verify-in-Lore loop). Mirrors how the
  Supermemory copy is treated.

## Status

Accepted

## Category

Architecture

## Alternatives Considered

### Per-episode delete keyed on a `rac_id` metadata filter

Rejected: Zep deletes episodes by uuid, which the connector does not persist, and
there is no documented metadata-filtered episode delete. Graph-level resync via
`create`/`delete` is the supported, unambiguous primitive.

### Map a corpus to a Zep user/session instead of a graph

Rejected: a graph namespace (`graph_id`) is the natural home for a body of
reference knowledge and has direct lifecycle methods; users/sessions model
conversational memory, which the corpus is not.

### Add episodes without resync and rely on Zep dedup

Rejected: Zep does not guarantee idempotency on the canonical `id`, so re-runs
would accrete duplicate episodes and a drifting derived graph.

## Related Decisions

- adr-001
- adr-002

## Review Date

Revisit if Zep introduces a per-record upsert key (move to a surgical upsert), or
when the documents-backend count makes a shared resync helper worthwhile.
