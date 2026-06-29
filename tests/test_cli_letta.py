"""End-to-end CLI behaviour for the `rac-connect letta` subcommand."""

from __future__ import annotations

import io

from rac_connectors import cli


def _line(record_id: str = "RAC-1") -> str:
    return (
        f'{{"schema_version":"1","id":"{record_id}","type":"decision",'
        f'"status":"Accepted","title":"t","text":"body",'
        f'"metadata":{{"source":"rac"}}}}'
    )


def test_dry_run_prints_actions_and_makes_no_call(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(_line() + "\n"))
    rc = cli.main(["letta", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr()
    assert "push RAC-1" in out.out
    assert "archive=rac" in out.out
    assert "1 pushed, 0 skipped" in out.err


def test_malformed_line_skipped_by_default(monkeypatch, capsys) -> None:
    stream = _line("RAC-1") + "\n" + "garbage{\n" + _line("RAC-2") + "\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(stream))
    rc = cli.main(["letta", "--dry-run"])
    assert rc == 0
    assert "2 pushed, 1 skipped" in capsys.readouterr().err


def test_strict_mode_fails_on_malformed_line(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(_line() + "\n" + "garbage{\n"))
    rc = cli.main(["letta", "--dry-run", "--strict"])
    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_live_push_without_credentials_errors(monkeypatch, capsys) -> None:
    monkeypatch.delenv("LETTA_API_KEY", raising=False)
    monkeypatch.delenv("LETTA_BASE_URL", raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO(_line() + "\n"))
    rc = cli.main(["letta"])
    assert rc == 2
    assert "LETTA_API_KEY" in capsys.readouterr().err
