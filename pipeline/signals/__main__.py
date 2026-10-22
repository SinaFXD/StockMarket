"""Rebuild only the Macro Desk from the data already in site/data and data/raw: ``python -m pipeline.signals``."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from ..config import SITE_DATA_DIR
from .build import build


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--today", type=date.fromisoformat, default=None)
    parser.add_argument("--out-dir", type=Path, default=SITE_DATA_DIR)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stdout)
    latest = build(args.out_dir, args.today or date.today())
    for s in latest["signals"]:
        score = "  -" if s["score"] is None else f"{s['score']:+d}"
        print(f"{score}  {s['name']:<52} {s['state']:<24} {s['as_of'] or ''}")
    print(f"\nBias: {latest['bias']['label']} ({latest['bias']['score']})")
    for a in latest["alerts"]:
        print(f"! {a}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
