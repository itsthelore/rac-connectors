---
schema_version: 1
id: LCON-KVKGQD9Y4W0D
type: decision
---
# ADR-002: One Outbound `push` Seam, One Module per Backend

## Context

ADR-073 (rac-core) fixes the repo topology: **one** `lore-connectors` repo with
**one module per backend**, not a repo per provider. Supermemory is module one;
Mem0, Zep, Letta, Cognee, and the vector/graph stores are named future targets.
This ADR fixes the *code seam* those modules share, so a new backend slots in
without reworking the CLI or the record-parsing layer — while honouring the rule
(from the interplay design in rac-core) that a connector is **outbound only**: it
pushes, and never pulls, re-ranks, or routes. The re-rank / memory-router shape
was explicitly rejected there; the seam must not even tempt it.

The forces:

- **A shared shape, not premature generality.** Two layers are common to every
  backend — parsing the `--documents` JSONL into records, and the CLI — and only
  the upsert mapping is backend-specific. The seam should capture exactly that
  split and nothing speculative, since only one backend exists today.
- **Outbound-only, idempotent.** Every backend must upsert on the canonical
  `id` so re-running an export updates rather than duplicates, and none may
  expose a read-back path.
- **Dry-run and testability are universal.** Every backend needs a `--dry-run`
  that makes no network call and a fake-client test path (no live API in CI), so
  those belong in the shared shape, not re-invented per module.

## Decision

Every backend module implements one small seam:

```python
class Connector(Protocol):
    name: str
    def push(self, records: Iterable[Record], *, dry_run: bool = False) -> PushSummary: ...
```

- **`push` is the only required method** — outbound, idempotent on each record's
  canonical `id`, returning a deterministic `PushSummary` (pushed/skipped counts
  plus a per-record action log). There is deliberately no `pull`, `search`, or
  `rerank` on the seam; recall and verify-in-Lore are the reading agent's job.
- **Records are shared, parsed once.** A single `parse_documents` reader turns
  the `rac export --documents` JSONL into `Record` objects for every backend; a
  module never re-parses raw Markdown (ADR-073, and ADR-063 in rac-core).
- **`dry_run` is part of the seam**, not a per-module flag, so every backend
  gets a no-network preview for free.
- **The backend SDK sits behind a thin client Protocol** the module depends on,
  so the test-suite drives a fake and CI stays offline. Auth is read from the
  environment by that client, never hard-coded.
- **The CLI is one subcommand per backend** (`lore-connect <backend>`), each
  wiring stdin/`--input` and `--dry-run` to the module's `push`.

The seam stays this small until a second backend proves a wider shape is needed;
the graph projection (`--graph`, ADR-074 in rac-core) will add a sibling reader
and, if required, a `push_graph` seam at that time — not now.

## Consequences

### Positive

- A new backend is one module implementing `push` plus a thin client; record
  parsing, the CLI, dry-run, and the summary shape are reused.
- The outbound-only, idempotent-on-`id` contract is enforced by the seam's
  shape, so the rejected re-rank/router pattern cannot creep in accidentally.
- Offline, fake-client testing is the default for every backend.

### Negative / trade-offs

- The seam covers documents only; graph backends will need an additive sibling
  seam later. Accepted: `--graph` is out of scope for the Supermemory-first
  phase, and designing its seam now would be speculative.
- One `push` signature may feel thin for a backend with a richer API. Accepted:
  modules keep their own specifics behind the client; the seam is the common
  denominator, not the whole surface.

## Status

Accepted

## Category

Architecture

## Alternatives Considered

### A fat base class with batching, retry, and pull hooks

Rejected as premature: with one backend it would be generality without evidence,
and a `pull`/read hook invites exactly the bidirectional coupling the interplay
design rejected. Add capability when a second backend demands it.

### No shared seam — each module is bespoke

Rejected: it would re-implement record parsing, dry-run, and CLI wiring per
backend and let each drift on the idempotency and outbound-only guarantees that
must hold uniformly.

### One combined documents+graph connector now

Rejected: documents and graph serve different consumers (memory vs graph) and
`--graph` is unscheduled here (ADR-074 in rac-core). Separate seams compose
better; Supermemory needs only documents.

## Related Decisions

- adr-001

## Review Date

Revisit when the second backend module lands, or when the `--graph` projection
is scheduled and needs its own push seam.
