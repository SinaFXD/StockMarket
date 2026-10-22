"""``python -m pipeline.regime``: rebuild ``site/data/regime.json`` from the local data (no downloads)."""

from __future__ import annotations

import logging
from datetime import date

from ..config import SITE_DATA_DIR
from ..store import write_json
from .build import build


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    data = build(SITE_DATA_DIR, date.today())
    write_json(SITE_DATA_DIR / "regime.json", data, indent=None)
    now, rec, tay = (
        data["now"] or {},
        (data["recession"] or {}).get("latest") or {},
        (data["taylor"] or {}).get("latest") or {},
    )
    print(f"regime {now.get('label')} ({now.get('month')}): {now.get('reason_en')}")
    print(
        f"history {len(data['history'])} months, counts {data['counts']}, real-time from {data['realtime_from']}"
    )
    print(f"recession odds for {rec.get('for_month')}: {rec.get('prob')}% (spread {rec.get('spread')})")
    print(
        f"Taylor {tay.get('taylor')} vs fed funds {tay.get('fed_funds')} (gap {tay.get('gap')}, core PCE {tay.get('inflation')})"
    )
    for row in data["sectors"] + data["assets"]:
        a = row["all"]
        cells = ", ".join(f"{g} {a[g].get('mean')} (n={a[g]['n']})" for g in data["regimes"])
        print(f"  {row['id']:5} since {row['first']}: {cells}")
    c = data["curve"] or {}
    print(
        f"curve: {len(c.get('dates', []))} weekly curves, last {c.get('dates', [None])[-1]}: {c.get('yields', [[]])[-1]}"
    )


if __name__ == "__main__":
    main()
