#!/usr/bin/env python3
"""Stitch the per-connector pages into the README's Connectors region.

Each connector documents itself once in ``docs/connectors/<backend>.md``. This
script is the single place that assembles those pages into collapsible
``<details>`` sections inside the README, between the markers::

    <!-- GENERATED:CONNECTORS -->
    ... generated, do not edit by hand ...
    <!-- /GENERATED:CONNECTORS -->

So a reader gets every connector on one page (the README) while each connector
still owns its own file (no cross-PR README conflicts). Run it after editing a
page::

    python scripts/sync_readme.py            # rewrite the README region
    python scripts/sync_readme.py --check     # CI: fail if the README is stale

Each page starts with an HTML-comment metadata block (hidden when rendered)::

    <!-- lore-connector
    name: Supermemory
    tagline: one-line summary shown in the <summary>
    extra: supermemory
    order: 10
    status: shipped
    -->
    # Supermemory
    ... body ...
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Markdown link targets: ](target) — used to rewrite page-relative links so they
# still resolve once the body is inlined into the README at the repo root.
_LINK_RE = re.compile(r"\]\(([^)]+)\)")

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
PAGES_DIR = ROOT / "docs" / "connectors"

START = "<!-- GENERATED:CONNECTORS -->"
END = "<!-- /GENERATED:CONNECTORS -->"
_NOTE = (
    "<!-- Generated from docs/connectors/*.md by scripts/sync_readme.py — "
    "do not edit by hand. -->"
)


@dataclass
class Page:
    name: str
    tagline: str
    order: int
    body: str
    path: Path


def _rewrite_links(body: str, page_dir: Path) -> str:
    """Re-express page-relative markdown links relative to the repo root.

    A page at ``docs/connectors/x.md`` links relative to itself; once inlined
    into the README at the root those targets would break, so resolve each
    relative link against the page directory and rewrite it root-relative.
    External (``http``), anchor (``#``) and absolute (``/``) links are left as is.
    """

    def repl(match: re.Match[str]) -> str:
        raw = match.group(1).strip()
        url, sep_space, title = raw.partition(" ")
        if not url or url.startswith(("http://", "https://", "mailto:", "#", "/")):
            return match.group(0)
        path, sep_hash, anchor = url.partition("#")
        if not path:
            return match.group(0)
        try:
            rel = (page_dir / path).resolve().relative_to(ROOT).as_posix()
        except ValueError:
            return match.group(0)  # points outside the repo — leave untouched
        return f"]({rel}{sep_hash}{anchor}{sep_space}{title})"

    return _LINK_RE.sub(repl, body)


def _parse_meta(block: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta


def load_pages() -> list[Page]:
    pages: list[Page] = []
    for path in sorted(PAGES_DIR.glob("*.md")):
        if path.name.lower() in {"readme.md", "index.md"}:
            continue
        text = path.read_text(encoding="utf-8")
        if not text.startswith("<!-- lore-connector"):
            raise SystemExit(f"{path}: missing <!-- lore-connector --> metadata block")
        _, _, rest = text.partition("<!-- lore-connector")
        meta_block, _, body = rest.partition("-->")
        meta = _parse_meta(meta_block)
        body = body.lstrip("\n")
        # Drop the leading H1 — the <summary> already names the connector.
        lines = body.splitlines()
        if lines and lines[0].startswith("# "):
            lines = lines[1:]
        body = "\n".join(lines).strip()
        try:
            name, tagline = meta["name"], meta["tagline"]
        except KeyError as exc:
            raise SystemExit(f"{path}: metadata missing {exc}") from None
        pages.append(
            Page(
                name=name,
                tagline=tagline,
                order=int(meta.get("order", "999")),
                body=body,
                path=path,
            )
        )
    pages.sort(key=lambda p: (p.order, p.name.lower()))
    return pages


def render(pages: list[Page]) -> str:
    blocks = [START, _NOTE, ""]
    for page in pages:
        rel = page.path.relative_to(ROOT).as_posix()
        body = _rewrite_links(page.body, page.path.parent)
        blocks += [
            "<details>",
            f"<summary><strong>{page.name}</strong> — {page.tagline}</summary>",
            "",
            body,
            "",
            f"**Full page:** [`{rel}`]({rel})",
            "",
            "</details>",
            "",
        ]
    blocks.append(END)
    return "\n".join(blocks)


def splice(readme: str, region: str) -> str:
    if START not in readme or END not in readme:
        raise SystemExit(
            f"README is missing the {START} / {END} markers; add them first."
        )
    head = readme.split(START)[0]
    tail = readme.split(END, 1)[1]
    return f"{head}{region}{tail}"


def main(argv: list[str]) -> int:
    check = "--check" in argv
    pages = load_pages()
    readme = README.read_text(encoding="utf-8")
    updated = splice(readme, render(pages))
    if check:
        if updated != readme:
            print(
                "README connectors region is stale; "
                "run `python scripts/sync_readme.py`.",
                file=sys.stderr,
            )
            return 1
        print(f"README connectors region is in sync ({len(pages)} connector(s)).")
        return 0
    README.write_text(updated, encoding="utf-8")
    print(f"Synced {len(pages)} connector(s) into the README.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
