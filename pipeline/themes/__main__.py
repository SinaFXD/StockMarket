"""Rebuild the macro-driven ideas from the published data: ``python -m pipeline.themes``."""

from __future__ import annotations

import sys

from ..config import SITE_DATA_DIR
from ..store import write_json
from .build import build, status_of


def main(argv: list[str] | None = None) -> int:
    data = build(SITE_DATA_DIR)
    write_json(SITE_DATA_DIR / "themes.json", data, indent=None)
    print(status_of(data))
    if data["unknown_industries"]:
        print("map.yaml names not in the screener:", ", ".join(data["unknown_industries"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
