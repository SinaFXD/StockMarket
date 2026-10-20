"""Validate the hand-entered CSVs: ``python -m pipeline.manual --check``.

Exit code 1 when any file has errors, so the GitHub run turns red and GitHub emails the owner. The
website is still rebuilt (in a separate job) from every row that is valid.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .. import gha
from ..config import MANUAL_DIR
from . import freshness, load_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="validate the files (the default action)")
    parser.add_argument("--dir", type=Path, default=MANUAL_DIR, help="folder with the CSV files")
    parser.add_argument("--today", type=date.fromisoformat, default=None, help="pretend today is YYYY-MM-DD")
    args = parser.parse_args(argv)
    today = args.today or date.today()

    total_errors = 0
    summary = [
        "## Manual data check",
        "",
        "| File | Rows | Last month | Status | Errors | Warnings |",
        "|---|---|---|---|---|---|",
    ]
    for ds in load_all(today, args.dir):
        fresh = freshness(ds, today)
        rel = f"data/manual/{ds.spec.filename}"
        print(
            f"{rel}: {fresh['rows']} valid rows, last month {fresh['last_month'] or '-'}, "
            f"status {fresh['status']}, {len(ds.errors)} error(s), {len(ds.warnings)} warning(s)"
        )
        for t in fresh["tracked"]:
            if t["status"] != "ok":
                print(f"  - {t['label']}: {t['status']} ({t['reason']})")
        for issue in ds.errors:
            print(f"  ERROR   {issue.text()}")
            gha.annotate("error", issue.text(), file=rel, line=issue.line, title="Manual data error")
        for issue in ds.warnings:
            print(f"  warning {issue.text()}")
            gha.annotate("warning", issue.text(), file=rel, line=issue.line, title="Manual data warning")
        total_errors += len(ds.errors)
        summary.append(
            f"| `{ds.spec.filename}` | {fresh['rows']} | {fresh['last_month'] or '-'} | "
            f"{fresh['status']} | {len(ds.errors)} | {len(ds.warnings)} |"
        )
    gha.step_summary("\n".join(summary))
    if total_errors:
        print(
            f"\n{total_errors} error(s) found. Fix them in the CSV file(s) above; "
            "rows with errors are not used."
        )
        return 1
    print("\nAll manual data files are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
