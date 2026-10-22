"""The list of automatically fetched series (``catalog.yaml``)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import yaml

from .config import CATALOG_FILE

BLOCKS = {
    "money_markets": "US money markets",
    "surveys": "US surveys",
    "prices_fx_equities": "Cyclical prices, FX & equities",
    "international": "International",
    "confirmers": "Coincident & lagging confirmers",
}
SOURCES = {
    "fred": "FRED",
    "yahoo": "Yahoo Finance",
    "umich": "University of Michigan",
    "eurostat": "Eurostat",
}


@dataclass(frozen=True)
class CatalogEntry:
    source: str
    id: str
    label: str
    block: str
    vintages: bool = False
    max_age_days: int | None = None

    @property
    def name(self) -> str:
        """File-name-safe id: ``^GSPC`` -> ``GSPC``, ``CL=F`` -> ``CL_F``."""
        return re.sub(r"[^A-Za-z0-9_-]", "_", self.id.lstrip("^"))

    @property
    def key(self) -> str:
        return f"{self.source}/{self.name}"

    @property
    def source_url(self) -> str:
        if self.source == "fred":
            return f"https://fred.stlouisfed.org/series/{self.id}"
        if self.source == "umich":
            return "https://www.sca.isr.umich.edu/tables.html"
        if self.source == "eurostat":
            return "https://ec.europa.eu/eurostat/databrowser/view/ei_bssi_m_r2/default/table"
        return f"https://finance.yahoo.com/quote/{quote(self.id)}"


def load_catalog(path: Path = CATALOG_FILE) -> list[CatalogEntry]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries: list[CatalogEntry] = []
    for source, items in raw.items():
        if source not in SOURCES:
            raise ValueError(f"{path.name}: unknown source '{source}' (expected one of {sorted(SOURCES)})")
        for item in items or []:
            entry = CatalogEntry(
                source=source,
                id=str(item["id"]),
                label=str(item["label"]),
                block=str(item["block"]),
                vintages=bool(item.get("vintages", False)),
                max_age_days=item.get("max_age_days"),
            )
            if entry.block not in BLOCKS:
                raise ValueError(f"{path.name}: {entry.id} has unknown block '{entry.block}'")
            if entry.vintages and source != "fred":
                raise ValueError(f"{path.name}: {entry.id}: vintages are only available for FRED series")
            entries.append(entry)
    keys = [e.key for e in entries]
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    if dupes:
        raise ValueError(f"{path.name}: duplicate entries {dupes}")
    return entries
