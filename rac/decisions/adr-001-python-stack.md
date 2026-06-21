---
schema_version: 1
id: LCON-KVKGQD318KM8
type: decision
---
# ADR-001: lore-connectors Is a Python Package

## Context

`lore-connectors` is the companion that pushes RAC's export payloads into the
external memory / RAG / graph backends a team already runs (ADR-073 in
rac-core). The export contract it consumes is language-agnostic JSON/JSONL
(`rac export --documents` / `--graph`), so the connector could be written in any
language. The first backend, Supermemory, ships both Python and TypeScript SDKs,
so the SDK does not force the choice either.

The decision is which stack the reference connectors in this repo are built on.
The forces:

- **Ecosystem match.** RAC (the engine) is a pure-Python CLI; its contributors,
  tooling (`ruff`, `pytest`, `mypy`), and CI conventions are Python. A Python
  companion is the lowest-friction repo for the same maintainers.
- **Dogfooding Lore.** A Python repo can carry its own `rac/` corpus and run the
  `rac` CLI to validate its decisions (this ADR is the proof), so the companion
  records its own knowledge the way the product intends.
- **Thin-client posture (ADR-063 in rac-core).** Whatever the language, a
  connector is a thin consumer of the published contract — it adds no engine
  logic — so the choice is about maintainer ergonomics, not capability.
- **Per-backend SDKs.** Supermemory, Mem0, Zep, Pinecone, and the rest all
  publish Python SDKs; Python keeps every future backend module in one toolchain.

## Decision

`lore-connectors` is a **Python package** (`lore_connectors`, Python 3.11+),
matching the RAC ecosystem.

- One installable package with a `lore-connect` console entrypoint; one module
  per backend under it (ADR-073), Supermemory first.
- Tooling mirrors rac-core: `ruff` for lint, `pytest` for tests, `mypy`
  available; Apache-2.0 licensed to match.
- The repo dogfoods Lore: its own decisions live in `rac/` and are validated by
  the `rac` CLI.
- Provider SDKs are **optional extras** (e.g. `lore-connectors[supermemory]`) so
  the core install and the whole test-suite stay dependency-free and CI never
  needs a live backend.

This does not bind non-Python clients: per ADR-063 the contract is the product,
so a TypeScript or Go connector remains valid against the same JSONL — it simply
lives elsewhere, not in this reference repo.

## Consequences

### Positive

- Same maintainers, same toolchain, same CI conventions as rac-core.
- The repo can dogfood Lore for its own ADRs, validated deterministically.
- Optional-extra SDKs keep the core install and CI light and offline.
- Every future backend module shares one Python toolchain.

### Negative / trade-offs

- A team whose stack is entirely TypeScript gets a reference in a second
  language. Accepted: the contract is language-agnostic (ADR-063), so a TS
  connector is fully supported — it just is not the reference implementation
  here.

## Status

Accepted

## Category

Technical

## Alternatives Considered

### TypeScript / Node

Rejected as the reference stack: it diverges from the Python engine ecosystem
and would split maintainer tooling, with no offsetting capability gain since the
contract is language-agnostic. Supermemory's TS SDK does not justify it on its
own. A TypeScript connector against the same contract remains welcome (ADR-063);
it just is not this repo's baseline.

### A polyglot repo (Python + TypeScript side by side)

Rejected for the first phase: it doubles CI, lint, and release surface before a
second-language connector is even requested. Revisit only if real demand for a
TS reference appears.

## Related Decisions

- adr-002

## Review Date

Revisit if a non-Python reference connector is requested often enough to justify
a second toolchain in this repo, or if rac-core's ecosystem stack changes.
