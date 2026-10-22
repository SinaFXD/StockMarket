"""Rebuild the sectors view from the published data: ``python -m pipeline.sectors``."""

from __future__ import annotations

import sys

from ..config import SITE_DATA_DIR
from ..store import write_json
from .build import build


def main(argv: list[str] | None = None) -> int:
    data = build(SITE_DATA_DIR)
    write_json(SITE_DATA_DIR / "sectors.json", data, indent=None)
    for s in data["sectors"]:
        r = s["rotation"] or {}
        print(
            f"{s['etf']:5} {s['sector']:24} rs3m {s['price']['rs3m']!s:>7}  {r.get('quadrant', '-'):10} macro {(s['macro'] or {}).get('score')}"
        )
    print(
        "groups:", {k: v for k, v in data["groups"].items() if k != "ratio"}, "agreement:", data["agreement"]
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
