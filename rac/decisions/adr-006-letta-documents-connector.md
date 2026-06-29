---
schema_version: 1
id: LCON-KVMPF68SA4BW
type: decision
---
# ADR-006: Letta Is a Documents Backend, Mapped to Archives, Resync-Idempotent

## Context

Letta is a documents-export backend (ADR-002: one module and one CLI subcommand
per backend). Letta organises long-term knowledge as **archives** — named
passage stores that agents attach as archival memory and that Letta embeds
server-side. That makes it a fit for the existing `Connector.push(records)` seam,
not a new seam (unlike the graph path, ADR-003).

Two specifics shape the connector (verified against letta-client 1.12.1):

- Ingestion is `client.archives.passages.create(archive_id, *, text, metadata)`,
  addressed by an **opaque `archive_id`**, not by a caller-chosen name — so the
  connector must resolve a name to an id.
- Like Mem0 (ADR-004) and Zep (ADR-005), there is **no per-record upsert key**,
  so re-running would duplicate passages.

## Decision

- **Letta is a documents backend on the existing `push(records)` seam.** It
  reuses the documents reader, CLI, `PushSummary`, and `--dry-run`.
- **A corpus `source` maps to a Letta archive (by name).** The thin client
  resolves the name to an `archive_id` internally, so the connector pushes by
  container name exactly like the other memory backends — the archive-id
  bookkeeping never leaks into the seam.
- **Idempotency is an archive resync.** On a push, the first time a source is
  seen its archive is cleared — list archives by that name, delete them, create a
  fresh one — then every record is added as a passage carrying the canonical
  `rac_id`/`type`/`status`/`title` in metadata. Re-running yields exactly the
  corpus, no duplicates — the contract's "containerTag as the upsert key".
- **Letta embeds the passages; nothing is embedded here** (rac-core ADR-002,
  ADR-066).
- **Auth from the environment**, supporting both Letta Cloud (`LETTA_API_KEY`)
  and self-hosted (`LETTA_BASE_URL`); the SDK sits behind a thin, mockable
  client, an optional `[letta]` extra (ADR-073).

## Consequences

### Positive

- A fourth documents backend with no new seam; the archive-id indirection is
  hidden in the adapter, so the connector and tests match the other backends.
- Archive resync is unambiguously idempotent and uses Letta's first-class archive
  lifecycle (`list`/`create`/`delete`).
- Works against both Letta Cloud and a self-hosted server.

### Negative / trade-offs

- A resync deletes and recreates the archive before re-adding, so a push is a
  wipe-and-rebuild: a brief incomplete window, and unchanged passages are
  re-embedded. Accepted: Letta exposes no per-record upsert key, the sync is a
  one-shot job, and the contract permits container-level idempotency.
- The connector creates an unattached archive; wiring it to specific agents is
  left to the operator. Accepted: the connector's job is to keep the store fresh,
  not to manage agent memory topology.

## Status

Accepted

## Category

Architecture

## Alternatives Considered

### Per-passage delete keyed on a `rac_id` metadata filter

Rejected: Letta deletes passages by id (not persisted by the connector) and
exposes no metadata-filtered passage delete. Archive-level resync via
`list`/`create`/`delete` is the supported, unambiguous primitive.

### Push into a specific agent's archival memory instead of a standalone archive

Rejected: it couples the corpus to one agent. A named archive is agent-agnostic
and can be attached to any number of agents by the operator.

### Add passages without resync and rely on Letta dedup

Rejected: Letta does not guarantee idempotency on the canonical `id`, so re-runs
would accrete duplicate passages.

## Related Decisions

- adr-001
- adr-002

## Review Date

Revisit if Letta introduces a per-record upsert key (move to a surgical upsert),
or when the documents-backend count makes a shared resync helper worthwhile.
