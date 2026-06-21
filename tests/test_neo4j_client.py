"""The live driver adapter (`DriverNeo4jClient`) against a stubbed ``neo4j``.

CI runs offline, so this stubs ``neo4j.GraphDatabase`` into ``sys.modules`` rather
than importing the real driver. The stub mirrors the official driver's shape:
``GraphDatabase.driver(uri, auth=...)`` -> a driver with ``.session()`` (a context
manager exposing ``.run(cypher, params)``) and ``.close()``.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from lore_connectors.neo4j.client import DriverNeo4jClient, MissingCredentialsError


class _StubSession:
    def __init__(self, driver: _StubDriver) -> None:
        self._driver = driver

    def __enter__(self) -> _StubSession:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def run(self, cypher: str, parameters: dict[str, Any]) -> None:
        self._driver.runs.append((cypher, parameters))


class _StubDriver:
    def __init__(self, uri: str, auth: tuple[str, str]) -> None:
        self.uri = uri
        self.auth = auth
        self.runs: list[tuple[str, dict[str, Any]]] = []
        self.session_kwargs: list[dict[str, Any]] = []
        self.closed = False

    def session(self, **kwargs: Any) -> _StubSession:
        self.session_kwargs.append(kwargs)
        return _StubSession(self)

    def close(self) -> None:
        self.closed = True


class _StubGraphDatabase:
    last: _StubDriver | None = None

    @staticmethod
    def driver(uri: str, auth: tuple[str, str]) -> _StubDriver:
        _StubGraphDatabase.last = _StubDriver(uri, auth)
        return _StubGraphDatabase.last


@pytest.fixture
def stub_neo4j(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("neo4j")
    module.GraphDatabase = _StubGraphDatabase  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "neo4j", module)
    _StubGraphDatabase.last = None


def test_adapter_constructs_driver_with_auth(stub_neo4j: None) -> None:
    client = DriverNeo4jClient(uri="bolt://h:7687", user="neo4j", password="secret")
    client.run("MERGE (n:Artifact {id: $id})", {"id": "RAC-1"})
    driver = _StubGraphDatabase.last
    assert driver is not None
    assert driver.uri == "bolt://h:7687"
    assert driver.auth == ("neo4j", "secret")
    assert driver.runs[0] == ("MERGE (n:Artifact {id: $id})", {"id": "RAC-1"})


def test_database_is_forwarded_to_session(stub_neo4j: None) -> None:
    client = DriverNeo4jClient(uri="bolt://h", user="u", password="p", database="lore")
    client.run("RETURN 1", {})
    assert _StubGraphDatabase.last.session_kwargs[0] == {"database": "lore"}


def test_no_database_means_default_session(stub_neo4j: None) -> None:
    client = DriverNeo4jClient(uri="bolt://h", user="u", password="p")
    client.run("RETURN 1", {})
    assert _StubGraphDatabase.last.session_kwargs[0] == {}


def test_credentials_read_from_env(
    monkeypatch: pytest.MonkeyPatch, stub_neo4j: None
) -> None:
    monkeypatch.setenv("NEO4J_URI", "bolt://env")
    monkeypatch.setenv("NEO4J_USERNAME", "envuser")
    monkeypatch.setenv("NEO4J_PASSWORD", "envpass")
    client = DriverNeo4jClient()
    client.run("RETURN 1", {})
    assert _StubGraphDatabase.last.auth == ("envuser", "envpass")


def test_close_closes_the_driver(stub_neo4j: None) -> None:
    client = DriverNeo4jClient(uri="bolt://h", user="u", password="p")
    client.run("RETURN 1", {})
    client.close()
    assert _StubGraphDatabase.last.closed is True


@pytest.mark.parametrize("missing", ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"])
def test_missing_any_credential_raises(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    for var in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"):
        monkeypatch.setenv(var, "x")
    monkeypatch.delenv(missing, raising=False)
    with pytest.raises(MissingCredentialsError):
        DriverNeo4jClient()
