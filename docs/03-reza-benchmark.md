# Benchmark: "Macro Bias Desk" (cenobar.com/tools/macro-bias-desk)

Reviewed 20 Oct 2026. Built by a fellow PTM student. Summarised here so we know what to beat.
**Do not copy its text or code.** Facts such as public series IDs are fine to reuse.

## What it covers
Only the **macro part of the course (lessons 1–15)**. Nothing from lessons 16–35 (portfolio management,
stock screening, qualitative work, catalysts, trade-idea template, ADRs).

Tabs: Overview (bias, auto-brief "what changed in the last month", signal board with per-indicator chart + rule +
manual override, equal vs evidence weighting, CSV export, bias history vs S&P 500), Learn, Regime, Sectors,
Money markets, Surveys, Prices & FX, International, Forex, Calendar, Confirmers, Evidence, Method, Disclaimer.
Refreshes daily via a scheduled job; overrides stored in the browser.

## Its 21 scored indicators (source IDs)
- Money markets: 10y−2y (T10Y2Y), 10y−3m (T10Y3M), real 10y = DGS10 − CPI YoY, IG OAS (BAMLC0A0CM), HY OAS
  (BAMLH0A0HYM2), BBB−AA (BAMLC0A4CBBB − BAMLC0A2CAA), M2 YoY (M2SL), VIX (VIXCLS).
- Surveys: **regional Fed manufacturing and services (Philadelphia + Dallas) instead of ISM**, UMich (UMCSENT,
  headline only), building permits (PERMIT), **Chicago Fed National Activity Index instead of NFIB**.
- Prices/FX/equities: copper (PCOPPUSDM), WTI (DCOILWTICO), lumber PPI (WPU081), iron ore (PIORECRUSDM), broad
  dollar (DTWEXBGS), S&P 500 vs 40-week average (FRED SP500).
- International: euro-area ESI (Eurostat ei_bssi_m_r2), **OECD China CLI instead of China PMIs** (several months
  lag — last obs May 2026 when viewed in Oct 2026).
- Scoring: each rule gives +1/0/−1 mostly from 3-month changes or fixed thresholds; bias = simple average,
  ±0.25 cut-offs. Percentile = position within the last 10 years.

## Extra views
Regime quadrant (CFNAI 3m avg vs 6m change in core PCE), NY Fed yield-curve recession probability, Taylor rule vs
fed funds, eight-currency forex strength ranking with pair candidates and a timing light, sectors/assets by regime
(Nasdaq sector indexes), coincident/lagging "confirmers" (CPI, PPI, NFP, unemployment, claims, durable goods, IP,
real GDP), calendar (FOMC, ECB, BEA GDP/PCE; CPI/jobs only with an API key), evidence tables.

## Weaknesses we should fix
1. **Not course-faithful**: Anton's ISM (with New Orders/Inventories focus), NFIB custom index, Caixin/RatingDog vs
   official PMI and UMich *expectations* are missing or replaced by proxies.
2. **Homework indicators missing** from scoring: Japan/UK/Germany/Italy money markets, China real rates, Brent,
   LME/Shanghai copper, other countries' PMIs.
3. **No regional dispersion answer** (US vs Europe vs China vs Japan) although Anton says to ask it constantly.
4. **Its own evidence shows the score doesn't separate outcomes**: in its NASDAQ sample since 1990, average
   3-month return was +3.4% after "net long" months vs +8.7% after "net short" months (39 months). It admits it uses
   revised data. → We must test with real-time vintages, report honestly, and avoid over-simple 3m-change rules.
5. Credit-spread history only ~3 years (FRED limitation) → our long-history fallback: Moody's BAA10Y/AAA10Y.
6. Calendar lacks CPI/jobs dates by default → we include BLS schedules.
7. Entire micro side absent → our Modules 2–5.
