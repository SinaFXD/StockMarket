"""Rebuild the Sector Screener and the per-stock trade-idea pages: ``python -m pipeline.screener [--offline] [--budget N]``."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from ..config import RAW_DIR, SITE_DATA_DIR
from ..store import RawCache
from ..workbench.build import write_stock_pages
from .build import ScreenerBuilder, market_inputs, status_of, write


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--offline", action="store_true", help="use cached downloads only")
    parser.add_argument("--budget", type=int, default=None, help="max estimate downloads this run")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stdout)
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    params = {"summary_budget": args.budget, "iv_budget": args.budget} if args.budget is not None else None
    builder = ScreenerBuilder(
        RawCache(RAW_DIR), offline=args.offline, params=params, **market_inputs(SITE_DATA_DIR)
    )
    data = builder.build(date.today())
    write(SITE_DATA_DIR, data)
    write_stock_pages(SITE_DATA_DIR, builder, SITE_DATA_DIR, data["as_of"])
    print(status_of(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
