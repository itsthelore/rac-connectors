"""End-to-end CLI behaviour for the `lore-connect cognee` subcommand."""

from __future__ import annotations

import io

from lore_connectors import cli


def _line(record_id: str = "RAC-1") -> str:
    return (
        f'{{"schema_version":"1","id":"{record_id}","type":"decision",'
        f'"status":"Accepted","title":"t","text":"body",'
        f'"metadata":{{"source":"rac"}}}}'
    )


def test_dry_run_prints_actions_and_runs_nothing(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(_line() + "\n"))
    rc = cli.main(["cognee", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr()
    assert "push RAC-1" in out.out
    assert "dataset=rac" in out.out
    assert "1 pushed, 0 skipped" in out.err


def test_malformed_line_skipped_by_default(monkeypatch, capsys) -> None:
    stream = _line("RAC-1") + "\n" + "garbage{\n" + _line("RAC-2") + "\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(stream))
    rc = cli.main(["cognee", "--dry-run"])
    assert rc == 0
    assert "2 pushed, 1 skipped" in capsys.readouterr().err


def test_strict_mode_fails_on_malformed_line(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(_line() + "\n" + "garbage{\n"))
    rc = cli.main(["cognee", "--dry-run", "--strict"])
    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_live_push_without_llm_key_errors(monkeypatch, capsys) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO(_line() + "\n"))
    rc = cli.main(["cognee"])
    assert rc == 2
    assert "LLM_API_KEY" in capsys.readouterr().err
