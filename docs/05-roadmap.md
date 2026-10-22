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
money markets & regional dispersion (done 2026-10-22), **1d** evidence page, confirmers & calendar (done 2026-10-22).
- [x] 1a: 18 indicators from `docs/02` in four blocks (US money markets, US surveys, prices/FX/equities, international:
      ESI + China), bias with overrides, "what changed" brief, alerts, point-in-time monthly history since 2000,
      "as of" view, daily log (`site/data/macro/log.csv`). New sources: UMich components, Eurostat ESI.
- [x] All indicators in `docs/02-indicator-rules.md`, four blocks, bias with overrides, "what changed" brief
      (1c added the 19th: international money markets).
- [x] Indicator pages: chart (1Y/3Y/5Y/10Y/Max), percentile, rule, Anton-style reading guide, components
      (ISM sub-indices, UMich expectations, NFIB custom index with 4m MA, RatingDog vs NBS gap). Done in 1b
      (2026-10-22): `indicator.html?id=<signal>`, chart data in `site/data/macro/indicators/`, guides in
      `pipeline/signals/guides.yaml`.
- [x] International: ESI (+ sectors/countries), China, Japan/UK/Germany/Italy money markets; regional equity
      dispersion (US vs Europe vs China vs Japan, relative strength). Done in 1c (2026-10-22): new OECD source
      (rates + CPI for five countries), Eurostat country ESIs and sector confidence, signal `intl_money_markets`,
      China real rate (context), `global.html` with `site/data/macro/global.json`.
- [x] Confirmers (coincident/lagging), calendar of releases & central banks with the 20–60 day window highlighted.
      Done in 1d (2026-10-22): confirmers on the Macro Desk (`site/data/macro/confirmers.json`, not scored);
      `calendar.html` from FRED release dates, the Fed/ECB/BoJ/BoE meeting pages and the manual-report rules
      (`pipeline/calendar/`, `site/data/calendar.json`).
- [x] Data-vs-prices alert on the Macro Desk (bias vs the S&P 500's own trend), information only (2026-10-22).
- [ ] Complete the history of the most important hand-entered data so the backtest tests today's model: ISM
      Manufacturing PMI + New Orders (and ideally ISM Services, NFIB) back to 2000, through a bulk-import file.
      Planned with the user for later; the user will find the historical source (no proxies).
- [ ] Shadow variants: run alternative rules side by side from today and compare them on the Evidence page
      (out-of-sample only), listing every variant tried.
- [x] Evidence page using real-time vintages where possible; sample sizes; no in-sample weight tuning.
      Done in 1d (2026-10-22): `evidence.html` (`site/data/macro/evidence.json`). First result, reported as is:
      over 2000–2026 net short readings were followed by *higher* 1–6 month index returns than net long ones
      (34 net short months, ~11 independent 3-month windows), and an index held with the bias's exposure
      lagged buy-and-hold. Rules are not changed to fit this; the live log (`log.csv`) is the out-of-sample test.

## Phase 2 — Sector Screener (lessons 22–29)
Built in parts: **2a** universe, 11 numbers, data checks, sector averages, Screener page (2026-10-22); **2b** outliers
& volatility filter (2026-10-22); **2c** SEC EDGAR evidence metrics (2026-10-22). Method: `docs/07-screener-method.md`.
- [x] Universe build + market-cap filter; sector/industry grouping. (2a: ~2,030 US-listed common stocks > $2bn
      from Yahoo's screener; `pipeline/screener/`, `site/data/screener/stocks.json`, `screener.html`.)
- [x] The 11 numbers per stock; data cleaning checks (lesson 28); sector averages.
- [x] Outlier classification: positive/negative outliers, consecutive growth patterns, turnaround, value trap,
      post-growth, boring. Volatility filter (realised & implied ≥ ~1.5× VIX). (2b: sector percentiles,
      Black-Scholes implied volatility from option prices; `outliers.py`, `volatility.py`.)
- [x] Evidence metrics from SEC EDGAR: margins, EV/EBIT, EV/EBITDA, balance-sheet and cash-flow ratios. (2c:
      SEC frames API, ~1,700 stocks with accounts; needs the `SEC_USER_AGENT` secret.)

## Phase 3 — Trade Idea Workbench (lessons 30–33)
Done in one part (2026-10-22). Method: `docs/08-workbench-method.md`.
- [x] Stock page = trade-idea template sections 1–5, auto-filled where data exists. (`stock.html?t=<TICKER>` for every
      screener stock, opened from the Screener; `site/data/stocks/<T>.json`, published but not committed.)
- [x] Price targets (EPS-based upper, sales-based lower) with editable assumptions; expected 1–3 month move vs targets.
      (Course's Zendesk example is a test; 1σ move from implied/realised volatility; targets > 2σ flagged.)
- [x] Earnings date & analyst range; user notes for business description, KPIs, non-earnings catalysts, timing,
      structure — saved. Storage decided: browser first (private, export/import), **Publish** writes
      `data/ideas/<T>.md` through GitHub's editor (public; validated by the workflow, `site/data/ideas.json`).
- [x] Idea pipeline view (10–15 ideas), status, staleness. (`ideas.html`: review after 7 days, stale after 14,
      target reached, targets against the side, earnings within 7 days.)
- [x] Phase exit: green `update.yml` run on `main` with the new pages deployed (2026-10-22, run 17).

## Phase 4 — Portfolio Lab (lessons 16–21)
Done in one part (2026-10-22). Method: `docs/09-portfolio-method.md`.
- [x] Enter current/proposed portfolio; CEW and non-rebalanced backtests; drawdowns. (`portfolio.html`: books in the
      browser, "add my ideas", 3M–2Y of daily history; price history per stock extended to 2 years.)
- [x] Portfolio vol (target 15–30%), correlation matrix & rolling correlation (target −0.3..+0.3), beta & beta-adjusted
      net exposure; position-count guidance by account size; Sharpe/return framing. (Also: risk share per position,
      beta-adjusted net vs the macro bias, long vs short market-cap tilt.)
- [x] Phase exit: green `update.yml` run on `main` with the page deployed (2026-10-22, run 19).

## Phase 5 — Macro-driven ideas & ADRs (lessons 34–35)
Done in one part (2026-10-22). Method: `docs/10-macro-ideas-method.md`.
- [x] Map macro signals to sectors/industries (ISM industry lists, commodities → sectors, housing → XHB, consumer).
      (`themes.html`: every Yahoo industry adds the Macro Desk signals that reach it and its place in the latest ISM
      growth / contraction lists; `pipeline/themes/map.yaml`; macro-driven ideas = screener outliers in tailwind /
      headwind industries.)
- [x] ADR screener for international ideas (incl. Chinese ADRs vs official-data flags). (Listings based abroad by
      region, growth leaders / laggards among them, currency rules; China check: official NBS PMI vs analysts'
      revisions for Chinese listings.)
- [x] Phase exit: green `update.yml` run on `main` with the page deployed (2026-10-22, run 20).
