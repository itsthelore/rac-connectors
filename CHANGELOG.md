# Changelog

All notable changes to `rac-connectors` are recorded here. Versions are CalVer
(`YYYY.M.N`, ADR-008); the version is derived from the git tag by setuptools-scm,
and the published distribution is `rac-connectors`.

## 2026.6.1

First published release of **rac-connectors** — the integrations companion for
RAC (requirements-as-code): one distribution covering the backend connectors
(ADR-073), renamed from the former `lore-connectors` under the `rac-*` topology
(ADR-092, ADR-095).

### Added

- The `rac-connect` CLI and the connector library, one subdir per integration
  under `src/rac_connectors/`: `supermemory`, `mem0`, `zep`, `letta`, `cognee`,
  and the `neo4j` graph connector.
- Thin export-contract consumers over `rac export --documents` / `--graph` and the
  public `rac` CLI — no engine internals, no embeddings or model calls (ADR-063,
  ADR-002).

### Changed

- Renamed from `lore-connectors` / `lore_connectors`: distribution
  `rac-connectors`, import package `rac_connectors`, CLI `lore-connect` →
  `rac-connect`.
- Outbound record id field `lore_id` → `rac_id` (cognee header `Lore-Id:` →
  `Rac-Id:`); the value is unchanged (the canonical `RAC-*` id). `lore-connectors`
  was never published to PyPI, so there is no migration (ADR-095).
