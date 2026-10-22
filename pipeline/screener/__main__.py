"""Rebuild the Sector Screener: ``python -m pipeline.screener [--offline] [--budget N]``."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from ..config import RAW_DIR, SITE_DATA_DIR
from ..store import RawCache
from .build import ScreenerBuilder, market_inputs, status_of, write


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--offline", action="store_true", help="use cached downloads only")
    parser.add_argument("--budget", type=int, default=None, help="max estimate downloads this run")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stdout)
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    params = {"summary_budget": args.budget, "iv_budget": args.budget} if args.budget is not None else None
    data = ScreenerBuilder(
        RawCache(RAW_DIR), offline=args.offline, params=params, **market_inputs(SITE_DATA_DIR)
    ).build(date.today())
    write(SITE_DATA_DIR, data)
    print(status_of(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
