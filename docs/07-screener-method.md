# Sector Screener: method and implementation notes

The screener follows lessons 22–29 (see `docs/01-course-map.md`, "Micro: quantitative processing"). This file
records how the course's steps are coded and every number that is our choice (*(tune)*). Numbers live in
`pipeline/config.py` (`SCREENER`).

## Universe (2a)
- Yahoo Finance's equity screener, one query per Yahoo sector (11 sectors), region US, exchanges NYSE, Nasdaq
  (all tiers) and NYSE American, market cap above **$2bn** *(tune; Anton works with a universe of ~2,200+ US
  stocks — this filter gives ~2,000 common stocks)*.
- Not common stock and left out: preferred shares, warrants, units, rights (`-P…`, `-WT`, `-U`, `-RT`).
- Sector = Yahoo's sector; industry, country and the estimates come from each stock's `quoteSummary`.

## The 11 numbers (2a)
| Number | Definition |
|---|---|
| Price | last price (screener) |
| Market cap | screener |
| EPS0 | EPS of the last reported fiscal year (`earningsTrend` 0y `yearAgoEps`) |
| EPS1, EPS2 | consensus EPS for the current and the next fiscal year (0y and +1y `avg`) |
| EG1, EG2 | EPS1/EPS0 − 1 and EPS2/EPS1 − 1, in % — **only from a positive base**: growth out of a loss is a turnaround, not a rate |
| PE1, PE2 | price / EPS1 and price / EPS2 — **only when EPS > 0** (lesson 25) |
| PEG1, PEG2 | PE / growth in % — **only with positive growth** (PEG is erratic with negative growth, lesson 26) |

Extra columns for later steps: revenue growth (consensus, current and next year), the change in the EPS1
consensus over 90 days, analyst count, fiscal-year end, next earnings date.

## Data checks (lesson 28) — 2a
Each check is a flag on the row. "Left out" flags keep the stock out of the sector averages; the others only
blank the numbers that are not meaningful.

| Check | Rule | Left out |
|---|---|---|
| No estimates | EPS1 or EPS2 missing | yes |
| Few analysts | fewer than **3** analysts behind EPS1 *(tune)* | no |
| Stale estimates | downloaded more than **10** days ago *(tune)* | no |
| EPS ≤ 0 | EPS1 or EPS2 ≤ 0 (P/E, PEG blank) | no |
| Loss base | EPS0 or EPS1 ≤ 0 (growth blank; turnaround candidate) | no |
| Extreme growth | \|EG\| > **300%** *(tune)* | yes |
| Extreme P/E | P/E > **200** *(tune)* | yes |
| Other currency | estimates or reporting currency ≠ price currency (most ADRs) | yes |
| Feeds disagree | Yahoo's screener EPS1 and its estimates EPS1 differ by > **25%** *(tune)*; seen live on GOOGL in Oct 2026 | yes |
| Second share class | same company name and the same EPS0 or a P/E within 5%: keep one line, the one with usable numbers first, then the most traded | yes |
| Based abroad | headquarters outside the US; kept when it reports in US dollars | no |
| Awaiting details | estimates not downloaded yet | yes |

## Sector averages (2a)
Mean and median of market cap, EG1, EG2, PE1, PE2, PEG1, PEG2 over the stocks without a "left out" flag, each
metric only where it is meaningful (see above). The website recomputes the same averages for an industry or a
market-cap filter (`site/assets/screener.js`, keep in sync with `numbers.py`).

## Refresh
Universe, prices and realised volatility every run. Estimates: one `quoteSummary` per stock, re-downloaded when older than 20 hours,
at most 2,500 per run (CI dry runs: 100), oldest first; after 25 failures in a row the run stops downloading and
keeps the cached copies. A full refresh takes ~5 minutes.

## Outlier types (2b)
Each stock is placed against its sector's clean stocks (no "left out" check): the percentile of its EG1, EG2 and
PE1 among them. A sector with fewer than **10** clean stocks is compared with the whole universe *(tune)*. The
course names the types but gives no cut-offs; ours are the **top and bottom quarter** *(tune)*. Rules are tried in
this order; the first that matches wins (`pipeline/screener/outliers.py`):

| Type | Rule | Course |
|---|---|---|
| Not classified | a "left out" data check | lesson 28 |
| Negative outlier | EPS1 > 0 and EPS2 ≤ 0 (profits turning into losses) | lesson 26 |
| Positive outlier | EG1 > 0 and EG2 > 0, both ≥ 75th percentile | lesson 25: highest growth, ideally consecutive |
| Negative outlier | EG1 < 0 and EG2 < 0, both ≤ 25th percentile | lesson 26: lowest, ideally consecutive negative |
| Post-growth | EG1 > 0 at ≥ 75th percentile, EG2 ≤ 25th percentile | lesson 26: post-growth "stage two" shorts |
| Turnaround | EPS0 ≤ 0 < EPS1 (back to profit) | lesson 27 |
| Loss-making | EPS1 ≤ 0 and EPS2 ≤ 0 | growth and P/E not meaningful |
| Turnaround | EG1 < 0 < EG2 with EG2 ≥ sector median | lesson 27 |
| Value trap | PE1 ≤ 25th percentile (cheap) while EG1 or EG2 < 0 | lesson 27: cheap for a reason |
| Boring | EG1 and EG2 both between the 25th and 75th percentile | lesson 22 |
| In between | anything else | |

Next to the type, the reason text and the supporting evidence the course looks for: sales growing or falling in
both years ("revenue estimates expanding"), the EPS1 consensus raised or cut by ≥ 2% in 90 days, and the P/E
premium or discount to the sector median ≥ 20% ("money likes it") *(tune)*.

## Volatility filter (2b)
Anton: realised and implied volatility roughly **≥ 1.5× VIX**, so a stock can move enough within 20–60 days.
- Realised: annualised standard deviation of daily log returns over the last **63** trading days (~3 months) and
  the **14**-day ATR in % of the price, from one batch download of six months of daily bars for the universe.
- Implied: at-the-money options (the 2 strikes nearest the price, calls and puts, median) of the expiry closest to
  **45** days. Yahoo's `impliedVolatility` field is unusable when bid/ask are zero (outside market hours), so the
  volatility is backed out with Black-Scholes from the mid price, else the last trade, with the 3-month T-bill rate.
  Only for the candidate types (positive/negative outliers, post-growth, turnarounds, value traps), largest first,
  at most **400** chains per run, refreshed after 20 hours; an empty answer from Yahoo (throttling) is retried
  next run, not cached.
- `vol_ok` = every available measure (realised, implied) ≥ 1.5 × the latest VIX close; the page's "Vol ÷ VIX"
  shows the lower of the two ratios.

## Next
- 2c: Evidence metrics from SEC EDGAR (margins, EV/EBIT, EV/EBITDA, balance-sheet and cash-flow ratios).
