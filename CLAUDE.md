# PTM Fundamental Dashboard — project instructions

## What this is
Final project for the ITPM **Professional Trading Masterclass (PTM)** by Anton Kreil. A **fully automatic,
self-updating website** that implements the course's whole fundamental process for a 20–60 day long/short
equity book: top-down macro (portfolio bias) → bottom-up sector/stock screening → trade-idea template →
portfolio risk. It must be clearly better than the benchmark site (see `docs/03-reza-benchmark.md`).

## Working with the user
- The user is a PTM student. **Reply in Persian (Farsi)**; keep code, UI text, docs and commit messages in English.
- The user is not a professional developer: explain what they must do (GitHub settings, secrets, data entry)
  as short numbered steps with exact UI labels.
- Decisions already made (do not re-ask):
  1. Scope: the **whole course, built phase by phase** (`docs/05-roadmap.md`).
  2. **Free data only.** No paid APIs.
  3. **Site language: English.**
  4. **ISM Manufacturing, ISM Services, NFIB SBET and the China PMIs (NBS official + RatingDog, formerly Caixin)
     are entered MANUALLY by the user** in `data/manual/*.csv`. Do **not** substitute proxies
     (no regional-Fed stand-in for ISM, no OECD CLI stand-in for China). If a manual file is empty or stale,
     show the indicator as "awaiting data" with the last date, and exclude it from the score — never fake it.
  5. Repo: this one. Build here in Claude Code cloud sessions.

## Source of truth for the method
- `docs/01-course-map.md` — what each of the 36 lessons covers and how it maps to dashboard modules.
- `docs/02-indicator-rules.md` — Anton's interpretation of every leading indicator (levels, components,
  what matters most). **Scoring rules must be derived from this file, not invented.** Where Anton gives
  ranges (e.g. UMich 55–70 / 70–95 / 95–110, ISM troughs 40–45 / peaks ~60, NFIB 95 / 100), use them.
  Anton repeats that there is "no rulebook": every automatic signal is a *first reading*; the UI must let
  the user override it and must show the reasoning text next to it.
- `docs/04-data-sources.md` — series IDs and endpoints; mark anything unverified and verify before use.
- The course transcripts are copyrighted and are **not** in this repo. Never commit course material,
  and never copy text or code from the benchmark site.

## Architecture (target)
- `pipeline/` — Python 3.11+. One fetcher per source (FRED, ALFRED vintages, Eurostat, DBnomics/OECD,
  Yahoo Finance via `yfinance`, SEC EDGAR, official calendars) + readers for `data/manual/*.csv`.
  Each fetcher caches raw data in `data/raw/` and **keeps the last good copy if a source fails**.
- `pipeline/signals/` — one module per indicator implementing the rule from `docs/02`, returning
  `{score: -1|0|+1, state, reason_en, as_of, percentile_10y, history}`.
- `site/data/*.json` — everything the frontend needs; `site/` — static frontend (no backend), deployable to
  GitHub Pages. Charts client-side. Must work on phone width.
- `.github/workflows/update.yml` — daily cron + on push to `data/manual/**` → run pipeline → commit JSON →
  deploy Pages. Also `workflow_dispatch`.
- Tests: `pytest` for every signal rule with hand-made fixtures; a data-health report (`site/data/health.json`)
  listing each series, last observation, staleness, and fetch status — shown on a "Data health" page.

## Conventions (established in Phase 0)
- Commands: `pip install -e ".[dev]"`, `pytest`, `ruff check . && ruff format --check .`,
  `python -m pipeline.manual --check`, `python -m pipeline.run [--offline] [--only fred,yahoo]`.
- New automatic series go in `pipeline/catalog.yaml` (verify the ID live first); tunable thresholds in
  `pipeline/config.py`; manual-file schemas and release calendars in `pipeline/manual/`.
- `site/data/` is generated and git-ignored; **only the workflow commits it** (`git add -f`). Never commit it from a
  session, or work branches will conflict with the daily data commits on `main`.
- Error messages can reach the public `health.json`: pass them through `pipeline.http.redact`.
- Commit with explicit paths (`git add pipeline tests site/*.html site/assets docs ...`), never `git add -A`: the
  generated `site/data/` files are tracked on `main`, so `-A` would stage them.

## Conventions (Phase 1)
- `pipeline/signals/`: one function per indicator (`money_markets`, `surveys`, `prices`, `international`), all
  reading data through the point-in-time `View` (`data.py`) so the same code serves today and every past month.
  Thresholds in `config.SIGNALS`; record every interpretation in `docs/02` ("Implementation notes").
- Site charts live in `site/assets/charts.js` (shared by the indicator and Global pages); their panels come from
  `pipeline/signals/charts.py` and `global_view.py`. Format site files with `npx prettier@3 --write site`
  (`.prettierrc.json`: width 120).
- `python -m pipeline.signals` rebuilds only the Macro Desk from local data; `site/assets/macro.js` repeats the
  bias arithmetic of `signals/bias.py` (keep them in sync).

## Quality bar (why ours beats the benchmark)
- Course-faithful indicator set (ISM incl. sub-indices, custom ITPM NFIB SBO index, RatingDog vs NBS
  "potential lie" flag, UMich expectations, international money markets Japan/UK/Germany/Italy/China,
  Brent + copper, regional equity dispersion US vs Europe vs China vs Japan).
- Honest backtests: use **ALFRED real-time vintages** where available so history uses only data known at the time;
  report hit-rates and forward returns with sample sizes; never tune weights on the same sample you report.
- Then the micro side the benchmark lacks: sector screener ("11 numbers"), outlier detection, price targets,
  trade-idea template pages, catalyst calendar, portfolio vol/correlation/beta tools.

## Network in cloud sessions
The cloud environment must allow (Custom network access + defaults): `*.stlouisfed.org`, `*.europa.eu`,
`api.db.nomics.world`, `sdmx.oecd.org`, `*.finance.yahoo.com`, `*.sec.gov`, `*.federalreserve.gov`,
`*.bls.gov`, `*.bea.gov`, `*.census.gov`, `*.treasury.gov`, `*.umich.edu`, `*.cftc.gov`.
If a request is blocked, tell the user which domain to add instead of working around it.
GitHub Actions runners have open internet, so production fetching happens there.

## Secrets
- `FRED_API_KEY` (free, fredaccount.stlouisfed.org) — GitHub repo secret for Actions; in cloud sessions as an
  environment variable. Never commit keys.
- SEC EDGAR requires a descriptive `User-Agent` with a contact email — read it from env `SEC_USER_AGENT`.

## Disclaimers
Educational tool, not investment advice. Show this on every page footer.
