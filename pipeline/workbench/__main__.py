"""Check or rebuild the saved trade ideas: ``python -m pipeline.workbench [--check]``.

``--check`` only validates ``data/ideas/*.md`` and exits 1 when a file has errors (like ``pipeline.manual``).
Without it, ``site/data/ideas.json`` is rebuilt. The per-stock pages are rebuilt by ``python -m pipeline.screener``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..config import IDEAS_DIR, SITE_DATA_DIR
from .build import build_ideas, write_ideas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only validate data/ideas/*.md")
    parser.add_argument("--ideas-dir", type=Path, default=IDEAS_DIR)
    parser.add_argument("--out-dir", type=Path, default=SITE_DATA_DIR)
    args = parser.parse_args(argv)
    data = build_ideas(args.ideas_dir)
    failed = False
    for p in data["problems"]:
        for e in p["errors"]:
            print(f"ERROR   {p['file']}: {e}")
            failed = True
        for w in p["warnings"]:
            print(f"warning {p['file']}: {w}")
    print(f"{len(data['ideas'])} idea file(s) read from {args.ideas_dir}")
    if not args.check:
        write_ideas(args.out_dir, data)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
