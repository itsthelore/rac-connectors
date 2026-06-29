"""The thin client seam the Neo4j connector writes through.

The connector depends only on :class:`Neo4jClient` (a Protocol), so the
test-suite drives an in-memory fake and CI never touches a real database.
:class:`DriverNeo4jClient` is the real adapter over the official ``neo4j``
driver, imported lazily so the package installs and tests run without it.
"""

from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable

URI_ENV = "NEO4J_URI"
USER_ENV = "NEO4J_USERNAME"
PASSWORD_ENV = "NEO4J_PASSWORD"
DATABASE_ENV = "NEO4J_DATABASE"


class MissingCredentialsError(RuntimeError):
    """Neo4j connection details were not found in the environment."""

    def __init__(self) -> None:
        super().__init__(
            f"set {URI_ENV}, {USER_ENV}, and {PASSWORD_ENV} in the environment "
            "(never hard-code credentials)"
        )


@runtime_checkable
class Neo4jClient(Protocol):
    """What the connector needs from a Neo4j client: run a parameterised Cypher
    statement.

    One method. The connector builds every statement with fixed labels and
    parameterised values, so the client just executes ``(cypher, params)``.
    """

    def run(self, cypher: str, parameters: dict[str, Any]) -> None: ...

    def close(self) -> None: ...


class DriverNeo4jClient:
    """Adapter over the official ``neo4j`` Python driver.

    Lazily constructs the driver so importing this module never requires the
    ``neo4j`` package; the import error only surfaces on a live push without the
    ``neo4j`` extra installed.
    """

    def __init__(
        self,
        *,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
    ) -> None:
        self._uri = uri or os.environ.get(URI_ENV)
        self._user = user or os.environ.get(USER_ENV)
        self._password = password or os.environ.get(PASSWORD_ENV)
        if not (self._uri and self._user and self._password):
            raise MissingCredentialsError()
        self._database = database or os.environ.get(DATABASE_ENV)
        self._driver: Any = None

    def _ensure_driver(self) -> Any:
        if self._driver is None:
            try:
                from neo4j import GraphDatabase
            except ImportError as exc:  # pragma: no cover - exercised via message
                raise RuntimeError(
                    "the 'neo4j' driver is not installed; "
                    "install the connector's 'neo4j' extra"
                ) from exc
            self._driver = GraphDatabase.driver(
                self._uri, auth=(self._user, self._password)
            )
        return self._driver

    def run(self, cypher: str, parameters: dict[str, Any]) -> None:
        driver = self._ensure_driver()
        kwargs = {"database": self._database} if self._database else {}
        with driver.session(**kwargs) as session:
            session.run(cypher, parameters)

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None


def client_from_env() -> DriverNeo4jClient:
    """Build the real client from environment variables (``NEO4J_URI`` etc.)."""
    return DriverNeo4jClient()
