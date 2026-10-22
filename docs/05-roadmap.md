# Roadmap

Each phase ends with: tests passing, pipeline green on GitHub Actions, site deployed, a short Persian summary
for the user, and this file updated (tick the boxes).

## Phase 0 — Skeleton & automation
- [x] Repo layout (`pipeline/`, `site/`, `data/raw/`, `data/manual/`, `tests/`), `pyproject.toml`/requirements.
- [x] FRED fetcher (+ ALFRED vintages), Yahoo fetcher, manual CSV loader with validation (clear error messages
      for the user: wrong month format, value out of 0–100, duplicate month).
- [x] `update.yml`: daily cron, on push to `data/manual/**`, manual dispatch; commit JSON; deploy GitHub Pages.
- [x] Data-health page.
- [x] Persian step-by-step for the user: enable Pages (Settings → Pages → Source: GitHub Actions), add
      `FRED_API_KEY` secret (Settings → Secrets and variables → Actions → New repository secret).
      → `docs/06-setup.md`
- [x] Phase exit: first green `update.yml` run on `main` (2026-10-20: 76/76 series ok) and site deployed at
      https://sinafxd.github.io/StockMarket/.

Phase 0 notes (2026-10-20): 76 series in `pipeline/catalog.yaml` (48 FRED incl. 8 with ALFRED vintages, 28 Yahoo),
all verified live; full run ≈ 75 s, later runs ≈ 45 s (FRED observations are only re-downloaded when the series
changed). 90 offline tests. Last good copy: raw cache in `data/raw/` (kept between Actions runs with
`actions/cache`) → published `site/data/series/*.json` (committed by the workflow).

## Phase 1 — Macro Desk (lessons 1–15)
Built in parts: **1a** signals + bias + Macro Desk page (done 2026-10-22), **1b** indicator pages (done 2026-10-22), **1c** international
money markets & regional dispersion, **1d** evidence page & calendar.
- [x] 1a: 18 indicators from `docs/02` in four blocks (US money markets, US surveys, prices/FX/equities, international:
      ESI + China), bias with overrides, "what changed" brief, alerts, point-in-time monthly history since 2000,
      "as of" view, daily log (`site/data/macro/log.csv`). New sources: UMich components, Eurostat ESI.
- [ ] All indicators in `docs/02-indicator-rules.md`, four blocks, bias with overrides, "what changed" brief
      (remaining: Japan/UK/Germany/Italy/China money markets in 1c).
- [x] Indicator pages: chart (1Y/3Y/5Y/10Y/Max), percentile, rule, Anton-style reading guide, components
      (ISM sub-indices, UMich expectations, NFIB custom index with 4m MA, RatingDog vs NBS gap). Done in 1b
      (2026-10-22): `indicator.html?id=<signal>`, chart data in `site/data/macro/indicators/`, guides in
      `pipeline/signals/guides.yaml`.
- [ ] International: ESI (+ sectors/countries), China, Japan/UK/Germany/Italy money markets; regional equity
      dispersion (US vs Europe vs China vs Japan, relative strength).
- [ ] Confirmers (coincident/lagging), calendar of releases & central banks with the 20–60 day window highlighted.
- [ ] Evidence page using real-time vintages where possible; sample sizes; no in-sample weight tuning.

## Phase 2 — Sector Screener (lessons 22–29)
- [ ] Universe build + market-cap filter; sector/industry grouping.
- [ ] The 11 numbers per stock; data cleaning checks (lesson 28); sector averages.
- [ ] Outlier classification: positive/negative outliers, consecutive growth patterns, turnaround, value trap,
      post-growth, boring. Volatility filter (realised & implied ≥ ~1.5× VIX).
- [ ] Evidence metrics from SEC EDGAR: margins, EV/EBIT, EV/EBITDA, balance-sheet and cash-flow ratios.

## Phase 3 — Trade Idea Workbench (lessons 30–33)
- [ ] Stock page = trade-idea template sections 1–5, auto-filled where data exists.
- [ ] Price targets (EPS-based upper, sales-based lower) with editable assumptions; expected 1–3 month move vs targets.
- [ ] Earnings date & analyst range; user notes for business description, KPIs, non-earnings catalysts, timing,
      structure — saved (decide storage: commit to `data/ideas/*.md` via GitHub, or browser storage + export).
- [ ] Idea pipeline view (10–15 ideas), status, staleness.

## Phase 4 — Portfolio Lab (lessons 16–21)
- [ ] Enter current/proposed portfolio; CEW and non-rebalanced backtests; drawdowns.
- [ ] Portfolio vol (target 15–30%), correlation matrix & rolling correlation (target −0.3..+0.3), beta & beta-adjusted
      net exposure; position-count guidance by account size; Sharpe/return framing.

## Phase 5 — Macro-driven ideas & ADRs (lessons 34–35)
- [ ] Map macro signals to sectors/industries (ISM industry lists, commodities → sectors, housing → XHB, consumer).
- [ ] ADR screener for international ideas (incl. Chinese ADRs vs official-data flags).
