"""The rac export contract version this connector speaks.

The only cross-repo dependency rac-connectors has on Lore / RAC is the export
**contract** — the ``schema_version`` carried by ``rac export --documents`` and
``--graph`` — not the rac-core *package* version (this connector never imports
``rac``). The contract is additive within a major and stable (rac-core ADR-007),
and non-Python clients are thin consumers of it (ADR-063). So the dependency to
capture here is the contract major, declared once and checked at read time —
never a pin on ``requirements-as-code`` (see this repo's ADR-008).
"""

from __future__ import annotations

import warnings

#: The export-contract major this connector is built against.
SUPPORTED_CONTRACT_VERSION = "1"


class ContractVersionWarning(UserWarning):
    """The export declares a contract major this connector wasn't built for."""


def _major(version: str) -> str:
    return version.split(".", 1)[0].strip()


def check_contract_version(version: str) -> None:
    """Warn if ``version``'s major differs from the supported contract major.

    A matching major is safe because the contract only grows additively within a
    major (rac-core ADR-007). A different major signals a breaking change this
    connector wasn't built for: warn rather than raise, so a best-effort push
    still runs and the operator decides — the warning goes to stderr, clear of
    the piped payload.
    """
    if _major(version) != SUPPORTED_CONTRACT_VERSION:
        warnings.warn(
            f"export contract schema_version {version!r} differs from the "
            f"supported major {SUPPORTED_CONTRACT_VERSION!r}; this connector may "
            "not handle it fully (rac-core ADR-007).",
            ContractVersionWarning,
            stacklevel=2,
        )
