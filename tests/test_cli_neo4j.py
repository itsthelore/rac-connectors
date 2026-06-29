"""End-to-end CLI behaviour for the `rac-connect neo4j` subcommand."""

from __future__ import annotations

import io
import json

import pytest

from rac_connectors import cli

_GRAPH = {
    "schema_version": "1",
    "source": "rac",
    "nodes": [{"id": "RAC-1", "type": "decision", "status": "Accepted", "title": "A"}],
    "edges": [],
}


def test_dry_run_prints_actions_and_connects_to_nothing(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_GRAPH)))
    rc = cli.main(["neo4j", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr()
    assert "push RAC-1: node" in out.out
    assert "1 pushed, 0 skipped" in out.err


def test_malformed_graph_errors(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("{not json"))
    rc = cli.main(["neo4j", "--dry-run"])
    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_live_push_without_credentials_errors(monkeypatch, capsys) -> None:
    for var in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_GRAPH)))
    rc = cli.main(["neo4j"])
    assert rc == 2
    assert "NEO4J_URI" in capsys.readouterr().err


def test_input_file_is_read(tmp_path, capsys) -> None:
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(_GRAPH), encoding="utf-8")
    rc = cli.main(["neo4j", "--dry-run", "--input", str(path)])
    assert rc == 0
    assert "push RAC-1" in capsys.readouterr().out


def test_unknown_backend_is_an_error() -> None:
    with pytest.raises(SystemExit):
        cli.main(["nope"])
