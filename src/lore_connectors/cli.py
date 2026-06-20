"""``lore-connect`` — the CLI entrypoint for the lore-connectors companion.

Reads a ``rac export --documents`` JSON Lines stream (stdin or ``--input``) and
pushes it into a backend. One subcommand per backend; Supermemory is the first::

    rac export rac/ --documents | lore-connect supermemory
    rac export rac/ --documents | lore-connect supermemory --dry-run
    lore-connect supermemory --input corpus.jsonl
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable, Iterator
from typing import TextIO

from .base import PushSummary
from .records import MalformedRecordError, Record, parse_documents
from .supermemory import SupermemoryConnector
from .supermemory.client import MissingApiKeyError, client_from_env


def _open_stream(path: str | None) -> tuple[TextIO, bool]:
    """Return the input stream and whether the caller owns closing it."""
    if path is None or path == "-":
        return sys.stdin, False
    return open(path, encoding="utf-8"), True


def _records_with_skip_report(
    lines: Iterable[str], summary: PushSummary, *, strict: bool
) -> Iterator[Record]:
    """Parse lines, routing malformed ones to the summary (or raising if strict).

    Wrapping ``parse_documents`` line-by-line lets a skipped malformed line be
    reported in the summary instead of silently dropped, while ``--strict`` turns
    the same guard into a hard failure.
    """
    for index, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        try:
            record = next(parse_documents([raw], strict=True))
        except MalformedRecordError as exc:
            if strict:
                raise MalformedRecordError(index, exc.reason, raw) from None
            summary.record_skip(index, exc.reason)
            continue
        yield record


def _run_supermemory(args: argparse.Namespace) -> int:
    connector = SupermemoryConnector()
    stream, owned = _open_stream(args.input)
    try:
        if args.dry_run:
            # Stream straight through the connector; it never calls the API.
            summary = _push_with_skips(
                connector, stream, dry_run=True, strict=args.strict
            )
        else:
            try:
                connector = SupermemoryConnector(client_from_env())
            except MissingApiKeyError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2
            summary = _push_with_skips(
                connector, stream, dry_run=False, strict=args.strict
            )
    except MalformedRecordError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        if owned:
            stream.close()

    if args.dry_run or args.verbose:
        for action in summary.actions:
            print(action)
    print(summary.summary_line(), file=sys.stderr)
    return 0


def _push_with_skips(
    connector: SupermemoryConnector,
    stream: Iterable[str],
    *,
    dry_run: bool,
    strict: bool,
) -> PushSummary:
    """Push a stream, accumulating malformed-line skips into the one summary."""
    summary = PushSummary(backend=connector.name, dry_run=dry_run)
    records = _records_with_skip_report(stream, summary, strict=strict)
    pushed = connector.push(records, dry_run=dry_run)
    # Merge the connector's push results onto the summary that holds the skips.
    summary.pushed = pushed.pushed
    summary.actions = pushed.actions + summary.actions
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lore-connect",
        description=(
            "Push a 'rac export --documents' stream into an external memory / "
            "RAG / graph backend. Outbound only — the verify-in-Lore loop is "
            "the reading agent's job."
        ),
    )
    sub = parser.add_subparsers(dest="backend", required=True)

    sm = sub.add_parser(
        "supermemory",
        help="Upsert documents into Supermemory (idempotent on canonical id).",
    )
    sm.add_argument(
        "--input",
        "-i",
        default=None,
        help="JSONL file to read (default: stdin). '-' also means stdin.",
    )
    sm.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be sent without calling the API.",
    )
    sm.add_argument(
        "--strict",
        action="store_true",
        help="Fail on a malformed line instead of skipping it.",
    )
    sm.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print per-record actions on a live push too.",
    )
    sm.set_defaults(func=_run_supermemory)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except BrokenPipeError:
        # A downstream consumer (e.g. `| head`) closed the pipe early; exit
        # quietly rather than tracebacking on the next write.
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
