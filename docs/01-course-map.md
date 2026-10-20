# PTM course map → dashboard modules

Notes taken from the Persian subtitles of the 36 PTM lessons (Anton Kreil, ITPM; spreadsheet lessons by
Chris Coyle). Lesson numbers below are the course's own. Summaries are paraphrased, not transcripts.

## The framework (lessons 1–2, 15)
- A **trade idea** needs all four: **Fundamentals + Timing + Catalysts + Trade structure**. Missing one = not a trade idea.
- Horizon **20–60 days** (1–3 month volatility). 60–120 days is the "grey zone" where trades turn into
  investments; >120 days = investment. We do not hold trades into investments.
- Fundamentals = 80–90% of the work: **macro (top-down, quantitative)** + **micro (bottom-up, quantitative + qualitative)**.
- Macro output = **portfolio bias: net long / net short / neutral (balanced)**, plus clues about which kinds of
  longs/shorts and which regions (is the world up or down? is the US beating Europe? China weaker?).
- Indicator time ladder: **leading** (money markets, surveys, cyclical commodities, equity markets, FX — prices
  already discount the future) → **coincident**, monthly (CPI, PPI, Employment Situation Report: NFP +
  unemployment; weekly initial & continuing claims; durable goods orders & shipments; industrial production) →
  **lagging**, quarterly (corporate earnings, GDP). Coincident = confirming indicators. Weekly claims mean
  payroll day should hold few surprises.
- Prices move ahead of reports; buying on the "beat" day is providing liquidity to people who positioned 20–60 days earlier.
- ITPM principles: self-reliance, work ethic, free information, work smart. Retail weekly routine 8–12 h.
- Proactive risk management (rules applied before a position exists) vs reactive (managing after it moves).

## Macro: leading indicators (lessons 3–14) → **Module 1: Macro Desk**
| Lesson | Indicator | Dashboard element |
|---|---|---|
| 3 | GDP (nominal vs real; GDP growth direction ↔ S&P 500 direction) | Lagging confirmers, regime |
| 4 | LI#1 Real interest rates + yield curve (US; template for Japan, UK, Germany, Italy) | Money markets |
| 5 | LI#2 Corporate bond spreads AA / BBB / CCC vs 10y | Money markets |
| 6 | Accessory: M2 money supply growth (distribution-of-returns method) + Fed watch | Liquidity / Fed |
| (IPLT) | VIX | Volatility |
| 7 | LI#3 ISM Manufacturing + sub-indices + industry comments | US surveys (manual data) |
| 8 | LI#4 ISM Services (NMI) | US surveys (manual data) |
| 9 | LI#5 University of Michigan Consumer Sentiment (expectations matter most) | US surveys |
| 10 | LI#6 Census building permits | US surveys/housing |
| 11 | LI#7 NFIB SBO + **custom ITPM NFIB SBO leading index** | US surveys (manual data) |
| 12 | LI#8 Cyclical commodities (oil, copper, lumber, iron ore), COT, US trade-weighted dollar, CPI/PPI basics | Prices & FX |
| 13 | LI#9 Euro-area Economic Sentiment Indicator (+ country & sector detail), STOXX 600 | International |
| 14 | LI#10 China: RatingDog (ex-Caixin) vs official NBS PMI, China real rates | International (manual PMI data) |
| 15 | Recap: leading → coincident → lagging; global dispersion questions | Overview, confirmers |
Homework items Anton lists (include them): money markets for Japan, UK, Germany, Italy, China real rates;
Markit/S&P Global PMIs for Japan, UK, Brazil, Canada; Brent, LME copper, Shanghai copper.

## Long/short portfolio management (lessons 16–21) → **Module 4: Portfolio Lab**
- Portfolio modelling: **CEW** (constant equal weight, daily rebalanced — quickest read of which basket
  out/under-performs) and **non-rebalanced** (buy-and-hold dollar positions — the practical one). Use both for
  current and proposed portfolios, before adding/removing positions or resizing, and for drawdown analysis.
- Portfolio volatility from variance/covariance of holdings; target base equity-portfolio vol **15–30% annual**
  (practical aim ~17.5–22.5%).
- Correlation between holdings drives portfolio vol once you hold 8–12 positions; target pairwise/portfolio
  correlation **−0.3 to +0.3**. Correlation time series (rolling).
- Beta of each stock and of the portfolio (net and beta-adjusted exposure).
- Diversification: retail $25k–$100k margin → **8–12 positions**; $250k–$1m → 10–14; $2–5m → 12–16.
  Beyond that = over-diversification and lower idea quality.
- Sharpe/return framing: CFD 4× leverage, minimum Sharpe 1.5 → 22.5–45%/yr; US stock long/short 2× → Sharpe 2
  → 30–60%; options (implied 3–10× leverage) Sharpe ~3.3 → 50–100%. Absolute-return mandate.
- In GDP-growth regimes, **mid-cap longs vs large-cap shorts** tended to beat large vs large (earnings more
  sensitive to the cycle).

## Micro: quantitative processing (lessons 22–29) → **Module 2: Sector Screener**
- Universe: ~2,200+ US stocks; sectors cyclical vs defensive; stocks growth / post-growth / value.
- Discovery uses **forward** data. The **"11 numbers"** per stock: price, market cap, EPS0 (last reported),
  EPS1, EPS2 (next two fiscal-year estimates), EG1, EG2 (EPS growth), PE1, PE2, PEG1, PEG2.
- Process: download sector data → **clean it** (lesson 28: common data-mining mistakes) → build the sector
  table + **sector averages** → identify **positive outliers** (long candidates) and **negative outliers**
  (short candidates), and what sits between: turnarounds, value traps, post-growth stocks, "boring" stocks.
- Filters: market-cap filter; realised and implied volatility roughly **≥ 1.5× VIX**.
- Longs: highest EPS growth, ideally **consecutive** positive growth over the two forward periods; revenue
  estimates expanding; P/E premium = "money likes it"; PE2 vs PE1 gap → potential price target; PEG gap.
- Shorts: lowest / consecutive negative EPS growth; don't draw conclusions from PEG (erratic with negative
  growth); P/E only meaningful when EPS > 0; consider the "five phases" for shorts (lesson 26) and post-growth
  stage-two stocks.
- Non-ideal patterns (lesson 27): turnarounds and value traps — needed for diversification; use balance sheet
  and combined balance-sheet/income ratios.
- **Evidence** step uses **backward-looking** accounting data: revenue growth; gross, pre-tax and net margins;
  EV, EBIT, EBITDA, EV/EBIT, EV/EBITDA; balance sheet; combined ratios; cash-flow statement metrics.
  Evidence explains *why* money likes/dislikes a stock; it is not a forecasting tool.

## Micro: qualitative, catalysts, template (lessons 30–33) → **Module 3: Trade Idea Workbench**
- Qualitative: what the company does (1–2 sentences), **KPIs** = business drivers behind revenue and
  earnings → infer **management's operating plan**; resolve ambiguity; quality assessment; range of market
  expectations; earnings-call transcripts; management track record; board; insider ownership/options and
  trading history; analyst estimate ranges and ratings.
- **Catalysts** (lesson 32) turn an investment into a trade: earnings-related (date, call time, quarterly and
  annual expectations, analyst range) and **non-earnings catalysts** expected between reports, before the next
  earnings date. If you cannot find non-earnings catalysts within the horizon, it is probably an investment,
  not a trade.
- **Trade Idea Template** (lesson 33), sections:
  1. Quant table: price, market cap, EPS estimates & reported, EPS growth, P/E, PEG, sales ($m), sales growth,
     sales multiple (P/S), net income, shares outstanding (E = estimate). Comment on what kind of story it is
     (e.g. revenue-growth vs earnings-growth story; GAAP vs non-GAAP).
     **Price targets:** upper/bullish = EPS growth with constant P/E (price × (1+EG)); lower/realistic =
     consensus sales estimate × constant P/S ÷ shares outstanding. Example Zendesk May 2020: price 76 → targets
     102.60 (sales-based) and 136.80 (EPS-based) for 2020, 166.69 for 2021. Always a range: conservative and optimistic.
  2. Sector quant table vs sector averages (PE1, EG1, EG2, PEG1, market cap) + comment: outlier type,
     **industry drivers** (tailwinds/headwinds in 20–60 days, e.g. oil for energy, DRAM for hardware),
     **volatility assessment** (realised via distribution of returns and ATR; implied from options → expected
     1–3 month move vs peers) and adjust targets if unrealistic for the horizon.
  3. Qualitative: business description; KPIs / management plan.
  4. Earnings & catalysts: next earnings date & call time, expectations and analyst range; non-earnings catalysts.
  5. Timing & structure: chart with technical/price-action analysis, short-interest check (path of least
     resistance), chosen structure and why (stock, margin, CFD; options are POTM, out of scope), horizon.
  Template = discipline and consistency; aim for "7 out of 10" ideas in 2–4 hours; ~2 new ideas/week;
  pipeline of 10–15 ideas; be active around price targets (probabilistic, not exit-on-day-60).

## Macro-driven ideas and ADRs (lessons 34–35) → **Module 5**
- Macro indicators mainly set the bias, but some single-stock ideas come straight from macro (ISM industry
  comments, commodity moves, housing, consumer).
- International ideas through **ADRs** (e.g. Chinese ADRs report under US standards — useful when official
  Chinese data looks unreliable).
