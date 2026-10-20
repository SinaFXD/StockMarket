"""Paths and tunable constants. Every threshold that is our choice (not Anton's) lives here."""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT = PACKAGE_DIR.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
MANUAL_DIR = DATA_DIR / "manual"
SITE_DIR = ROOT / "site"
SITE_DATA_DIR = SITE_DIR / "data"
CATALOG_FILE = PACKAGE_DIR / "catalog.yaml"

REPO_URL = "https://github.com/SinaFXD/StockMarket"
USER_AGENT = f"PTM-Fundamental-Dashboard/0.1 (+{REPO_URL})"

# FRED allows 120 requests per minute per key; stay comfortably below it.
FRED_MIN_INTERVAL_S = 0.55
YAHOO_MIN_INTERVAL_S = 0.4

# A series is "stale" when its last observation is older than this many calendar days.
# Generous on purpose: they must absorb publication lags and holidays, and only catch a source that
# stopped updating. Per-series overrides live in catalog.yaml (max_age_days).
MAX_AGE_DAYS = {
    "daily": 10,
    "weekly": 21,
    "monthly": 100,
    "quarterly": 250,
    "annual": 500,
}

# Manual data: after a report's release date, the missing month is "due" for this many days, then the
# indicator becomes "awaiting data" (shown with its last date and excluded from scores).
MANUAL_GRACE_DAYS = 5
