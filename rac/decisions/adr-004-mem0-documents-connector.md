---
schema_version: 1
id: LCON-KVMMTWY928WN
type: decision
---
# ADR-004: Mem0 Is a Documents Backend, Idempotent by Container Resync

## Context

Mem0 is the second documents-export backend (ADR-002: one module per backend,
one CLI subcommand). It is a memory layer that embeds server-side, so it fits the
existing `Connector.push(records)` seam — no new seam, unlike the graph path
(ADR-003).

One thing does not carry over from Supermemory. Supermemory's `add` takes a
`custom_id`, so re-pushing an edited artifact is a per-record upsert keyed on the
canonical `id`. Mem0's `add` has **no per-record upsert key** (verified against
mem0ai 2.0.7: `MemoryClient.add(messages, *, user_id, agent_id, metadata, infer,
…)` — no `custom_id`). So the connector needs a different, explicit idempotency
strategy, or re-running would duplicate every memory.

## Decision

- **Mem0 is a documents backend on the existing `push(records)` seam.** No new
  interface; it reuses the documents reader, CLI, `PushSummary`, and `--dry-run`.
- **Idempotency is a container resync, not a per-record upsert.** A corpus
  `source` maps to a Mem0 partition (`user_id`). On a push, the first time a
  partition is seen it is **cleared** (`delete_all(user_id=source)`), then every
  record for it is added. Re-running yields exactly the corpus — no duplicates —
  which satisfies the export contract's "containerTag as the upsert key". This is
  the cleanest idempotency Mem0's API supports, since it lacks `custom_id`.
- **Records are stored as-is, not LLM-rewritten.** `add(..., infer=False)` skips
  Mem0's fact-extraction so it only embeds the artifact text; the canonical
  `lore_id`, `type`, `status`, and `title` ride in metadata for the
  verify-in-Lore loop and retired-item filtering. No embeddings in the connector
  (rac-core ADR-002, ADR-066).
- **Auth from the environment** (`MEM0_API_KEY`), the SDK behind a thin, mockable
  client, an optional `[mem0]` extra — the same shape as every backend (ADR-073).

## Consequences

### Positive

- A second documents backend with zero new seam — pure reuse of the documents
  path.
- Re-sync is unambiguously idempotent and uses only well-supported Mem0
  operations (`delete_all` by partition, `add`).
- Provenance (`lore_id`/`status`) is preserved for the verify-in-Lore loop.

### Negative / trade-offs

- A resync clears the partition before re-adding, so a push is a wipe-and-rebuild
  rather than a surgical per-record update: there is a brief window where the
  partition is incomplete, and unchanged records are re-embedded. Accepted: Mem0
  exposes no per-record upsert key, the sync is a one-shot job, and the contract
  permits container-level idempotency. If Mem0 adds a stable upsert key, this can
  move to a surgical upsert without changing the seam.
- The corpus maps to a Mem0 `user_id` partition, which is a semantic stretch
  (`user_id` names a partition, not a person). Accepted: `user_id` is Mem0's
  primary, broadly-supported scope for add and delete.

## Status

Accepted

## Category

Architecture

## Alternatives Considered

### Per-record delete-then-add keyed on a `lore_id` metadata filter

Rejected for now: it is more surgical, but depends on Mem0's metadata-filtered
delete semantics, which vary across platform and OSS and could not be verified
offline. The container resync relies only on partition-level `delete_all`, which
is unambiguous. Revisit if a verified metadata-filter delete makes per-record
upsert reliable.

### Plain `add` and rely on Mem0's own dedup

Rejected: dedup is heuristic and not guaranteed idempotent on the canonical `id`,
so re-runs could accumulate near-duplicate memories.

### `infer=True` (let Mem0 extract memories)

Rejected: it would let an LLM rewrite the artifact into extracted "memories",
making the stored copy a non-faithful, non-deterministic derivative — contrary to
shipping the artifact text for the backend to embed.

## Related Decisions

- adr-001
- adr-002

## Review Date

Revisit if Mem0 introduces a stable per-record upsert key (move to a surgical
upsert), or when a third documents backend tests the seam's generality.
