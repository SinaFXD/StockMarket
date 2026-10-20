# PTM Fundamental Dashboard

A fully automatic, self-updating fundamental dashboard built as the final project for the ITPM Professional
Trading Masterclass (PTM). It follows the course's process for a 20–60 day long/short equity book:
macro leading indicators → portfolio bias → sector screening → trade-idea template → portfolio risk.

**Status:** Phase 0 (skeleton & automation) is built: daily data pipeline, manual-data checks and a Data health
page. Next: Phase 1, the Macro Desk. See `docs/05-roadmap.md`.

- One-time setup (GitHub Pages, FRED key): `docs/06-setup.md`
- Method: `docs/02-indicator-rules.md` · Data sources: `docs/04-data-sources.md`
- Monthly manual data (ISM, NFIB, China PMIs): `data/manual/README.md`

## How it works
| Part | What it does |
|---|---|
| `pipeline/` | Python. `python -m pipeline.run` fetches every series in `pipeline/catalog.yaml` (FRED, ALFRED real-time vintages, Yahoo Finance), validates `data/manual/*.csv`, and writes `site/data/` (series JSON, manual JSON, `health.json`). A failing source never stops the run: the last good copy is kept and flagged. |
| `site/` | Static website (no build step, no backend). Reads `site/data/*.json` in the browser. |
| `.github/workflows/update.yml` | Daily at 22:23 UTC, on changes to manual data or code on `main`, or by hand: tests → pipeline → commit `site/data/` → deploy GitHub Pages. |
| `.github/workflows/ci.yml` | On work branches: lint, tests, manual-data check and a pipeline dry run. |
| `tests/` | `pytest`, offline, hand-made fixtures. |

## Local commands
```bash
pip install -e ".[dev]"                 # Python 3.11+
pytest                                  # unit tests (no network)
python -m pipeline.manual --check       # validate data/manual/*.csv
FRED_API_KEY=... python -m pipeline.run # fetch everything into site/data/ (data/raw/ keeps the raw cache)
python -m http.server -d site 8000      # preview at http://localhost:8000
```
`site/data/` is generated: only the GitHub workflow commits it.

Educational tool. Not investment advice.
