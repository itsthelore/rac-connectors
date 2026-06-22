---
schema_version: 1
id: LCON-KVPTT2RNKWDV
type: decision
---
# ADR-008: CalVer Versioning, and the Export Contract Is the Cross-Repo Dependency

## Context

RAC / Lore is adopting CalVer (`YYYY.M.<minor>`) across the org, so rac-core
releases as `2026.6.<minor>`. lore-connectors should align its scheme. But two
things must not be conflated:

- **Version *scheme* vs version *number*.** Matching the CalVer scheme aids
  ecosystem legibility. Matching the *number* in lock-step would be wrong:
  lore-connectors and rac-core have independent release cadences (a connector
  release does not correspond to a rac-core release), so any shared minor would
  diverge the first time either ships alone.
- **The real cross-repo dependency.** lore-connectors does **not** depend on the
  rac-core *package* — it never imports `rac`. Its only dependency on Lore is the
  **export contract**: the `schema_version` carried by `rac export --documents`
  and `--graph`. That contract is additive-within-a-major and stable (rac-core
  ADR-007), and non-Python clients are thin consumers of it (rac-core ADR-063).
  Pinning a rac-core version would over-constrain and contradict those decisions.

## Decision

- **Version with CalVer, independent cadence.** Tags are `YYYY.M.<minor>`
  (setuptools-scm, tag-driven). The minor is an independent counter, **not**
  lock-step with rac-core — the same scheme, not the same number. The minor
  starts at `1` each period; there is no `.0`.
- **Tag without a zero-padded month.** PEP 440 strips leading zeros, so a
  `2026.06.1` tag normalises to the package version `2026.6.1`. Tag `2026.6.1`
  directly to avoid the mismatch.
- **Capture the dependency as the contract version, in code — never as a package
  pin.** The connector declares `SUPPORTED_CONTRACT_VERSION` (currently `"1"`)
  and checks each export's `schema_version` at read time
  (`check_contract_version`): a matching major is silent; a different major emits
  a `ContractVersionWarning` to stderr and still proceeds best-effort. The
  package does **not** depend on `requirements-as-code` at any version; the
  README documents a soft minimum rac release (the one that introduced the export
  modes) as prose only.

## Consequences

### Positive

- The org-wide CalVer scheme is honoured without falsely coupling two
  independently-released repos.
- The genuine dependency — the contract major — is explicit, checked, and
  testable, instead of being implied by a package version.
- A connector keeps working against any future rac release that still emits
  `schema_version 1` (the additive-stability guarantee), and warns clearly if a
  new major ever appears.

### Negative / trade-offs

- A contract-major bump (`schema_version "2"`) only warns, it does not hard-fail,
  so a best-effort push still runs. Accepted: the contract is additive and the
  verify-in-Lore loop re-fetches authoritative text, so a stale-but-parsed push
  is safe; an operator who wants strictness can treat the warning as an error.
- CalVer carries no semver compatibility signal. Accepted: the compatibility
  contract lives in `schema_version`, not the package number.

## Status

Accepted

## Category

Process

## Alternatives Considered

### Lock-step version numbers with rac-core

Rejected: the repos release independently, so a shared minor is fictional the
moment either ships alone, and it implies a coupling that does not exist.

### Pin `requirements-as-code` to a version in `pyproject`

Rejected: the connector consumes the contract, not the package (rac-core ADR-007
additive stability, ADR-063 thin clients). A pin would break against rac releases
that are in fact compatible.

### Keep SemVer (`0.x` / `v0.0.1`)

Rejected for alignment: the org standard is CalVer. SemVer's compatibility signal
is redundant here because compatibility is expressed by the contract version.

### Hard-fail on an unknown contract major

Rejected as the default: it would abort a push the contract's additive stability
makes safe to attempt; a warning preserves best-effort behaviour while staying
loud.

## Related Decisions

- adr-001
- adr-002

## Review Date

Revisit when the export contract introduces a `schema_version "2"`, or if the
org's CalVer convention changes.
