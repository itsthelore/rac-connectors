"""End-to-end CLI behaviour driven through stdin, against a dry run / fake."""

from __future__ import annotations

import io

import pytest

from rac_connectors import cli


def _line(record_id: str = "RAC-1") -> str:
    return (
        f'{{"schema_version":"1","id":"{record_id}","type":"decision",'
        f'"status":"Accepted","title":"t","text":"body",'
        f'"metadata":{{"source":"rac"}}}}'
    )


def test_dry_run_prints_actions_and_makes_no_call(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(_line() + "\n"))
    rc = cli.main(["supermemory", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr()
    assert "push RAC-1" in out.out
    assert "1 pushed, 0 skipped" in out.err


def test_malformed_line_skipped_by_default(monkeypatch, capsys) -> None:
    stream = _line("RAC-1") + "\n" + "garbage{\n" + _line("RAC-2") + "\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(stream))
    rc = cli.main(["supermemory", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr()
    assert "push RAC-1" in out.out
    assert "push RAC-2" in out.out
    assert "skip line 2" in out.out
    assert "2 pushed, 1 skipped" in out.err


def test_strict_mode_fails_on_malformed_line(monkeypatch, capsys) -> None:
    stream = _line("RAC-1") + "\n" + "garbage{\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(stream))
    rc = cli.main(["supermemory", "--dry-run", "--strict"])
    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_live_push_without_api_key_errors(monkeypatch, capsys) -> None:
    monkeypatch.delenv("SUPERMEMORY_API_KEY", raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO(_line() + "\n"))
    rc = cli.main(["supermemory"])
    assert rc == 2
    assert "SUPERMEMORY_API_KEY" in capsys.readouterr().err


def test_input_file_is_read(tmp_path, capsys) -> None:
    path = tmp_path / "docs.jsonl"
    path.write_text(_line("RAC-9") + "\n", encoding="utf-8")
    rc = cli.main(["supermemory", "--dry-run", "--input", str(path)])
    assert rc == 0
    assert "push RAC-9" in capsys.readouterr().out


def test_no_backend_is_an_error(capsys) -> None:
    with pytest.raises(SystemExit):
        cli.main([])
