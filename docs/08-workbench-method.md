# Trade Idea Workbench: method and implementation notes

The workbench follows lessons 30–33 (see `docs/01-course-map.md`, "Micro: qualitative, catalysts, template"). This
file records how the template is filled and every number that is our choice (*(tune)*). Numbers live in
`pipeline/config.py` (`WORKBENCH`).

## Pages
- `stock.html?t=<TICKER>`: the trade-idea template for every stock in the screener universe (click a ticker on the
  Screener). Data: `site/data/screener/stocks.json` (the 11 numbers, type, volatility) and
  `site/data/stocks/<TICKER>.json` (`pipeline/workbench/stock.py`).
- `ideas.html`: the idea pipeline (every saved idea, from this browser and from the repository).

## Section 1: quant table
| Row | Reported year (FY0) | FY1E, FY2E |
|---|---|---|
| EPS | analysts' "year-ago" EPS (adjusted) | consensus, with the analysts' low–high |
| EPS growth, P/E, PEG | P/E on FY0 EPS | as on the Screener (P/E only when EPS > 0, PEG only with positive growth) |
| Sales | Yahoo's "year-ago revenue" | consensus, with the low–high |
| P/S | market cap / sales | |
| Net income | GAAP, from the SEC filing for FY0 | EPS × today's shares (estimate) |
| Shares | shares outstanding today (Yahoo) | |

**Story comment** (`targets.story`): EPS growth vs sales growth in the current year. EPS growing at least **5**
percentage points *(tune)* faster than sales = earnings-growth story (margins widening); sales faster = revenue-growth
story (margins narrowing); in between = balanced. Also: margin squeeze (sales up, EPS down), cost story (EPS up,
sales down), shrinking, turnaround (loss → profit), loss-making, profits turning into losses; and whether growth
accelerates or slows next year.

**GAAP vs adjusted** (`targets.gaap_gap`): consensus EPS is usually adjusted (non-GAAP). Adjusted FY0 EPS × today's
share count against the GAAP net income filed with the SEC for the same fiscal year (the SEC year must end within
40 days of the year before the current fiscal year). A gap of **15%** or more *(tune)* is flagged ("check what is
excluded"). The share count is today's, not the year's average: a rough check, not an exact reconciliation.

## Price targets (lesson 33)
As in the course's Zendesk example (price 76 → 102.60 sales-based, 136.80 EPS-based):
- **EPS-based** (upper / bullish): constant P/E = price ÷ FY0 EPS; target = P/E × EPS1 (and × EPS2). From a loss
  (FY0 EPS ≤ 0) there is no constant P/E: the page asks for the user's own P/E.
- **Sales-based** (lower / realistic): constant P/S = price ÷ (FY0 sales ÷ shares); target = P/S × sales ÷ shares.
- The user can replace any input: P/E, P/S, EPS1, EPS2, sales, and the forward share count (buybacks, dilution);
  buttons set EPS to the analysts' low or high. The range is shown as conservative / optimistic for the idea's side
  (for a short, the higher target is the conservative one). Every target on the wrong side of the price is flagged.
- Python (`pipeline/workbench/targets.py`) computes the defaults; `site/assets/workbench.js` repeats the arithmetic
  for the user's assumptions (keep them in sync).

## Expected move and realism
1σ move over the horizon = annualised volatility × √(days ÷ 365), with implied volatility where options were read
(screener candidates), else the 3-month realised volatility. A target within **1σ** is "realistic", within **2σ**
"stretched", beyond 2σ "unrealistic for the horizon: adjust" *(tune)*, following the course's advice to adjust
targets that are unrealistic for 20–60 days. The default horizon of a new idea is **40** days *(tune; the course's
window is 20–60)*. Section 2 shows 1σ moves over 1, 2 and 3 months against the industry and sector medians
(clean stocks only), and the distribution of daily returns over the last year (bars beyond 2σ in red).

## Sections 2–5
- **Sector:** the stock against the industry median and the sector average and median (PE1, EG1, EG2, PEG1, PE2,
  market cap), its percentiles from the screener, and the industry's ten largest peers. Industry drivers: a hint
  per sector and the user's note (Phase 5 maps macro signals to sectors).
- **Qualitative:** Yahoo's company profile, insiders' and institutions' holdings, beta, analysts' rating (1 = strong
  buy … 5 = sell) and 12-month price targets; the user writes the 1–2 sentence business description and the KPIs /
  management plan.
- **Earnings and catalysts:** next earnings date and session. Yahoo keeps report times at a fixed UTC hour (an
  after-the-close report shows 15:00 or 16:00 New York time), so the session is read from the hour: before 9:30 =
  before the open, 14:00 or later = after the close; an estimated date has no session. Quarter (EPS and sales low /
  consensus / high, year ago, growth) and annual expectations with the analysts' revisions. The user lists
  non-earnings catalysts; with none before the next report the page warns "may be an investment, not a trade"
  (lesson 32). High-importance macro events inside the horizon come from the Calendar.
- **Timing and structure:** one year of daily bars (candles for 3–6 months, a line for a year), 50- and 200-day
  averages, the target and entry lines, and the horizon ahead with the earnings date and dated catalysts. Trend
  reading from the price and the two averages; 1/3/6-month returns and the 3-month return against SPY and the
  sector's SPDR ETF. Short interest: % of float and days to cover; above **10%** of the float or **5** days to cover
  = a crowded short *(tune)*; a change of 10% or more on the prior month is mentioned. Structure: stock, stock on
  margin or CFD (options are out of scope, as in the course).

## Saving ideas
- An idea starts in the browser (`localStorage`, key `ptm.ideas.v1`): private, saved on every change, but only on
  that device. Export / Import (Ideas page) moves ideas between devices as a JSON file.
- **Publish** writes `data/ideas/<TICKER>.md` through GitHub's own editor (a new file opens pre-filled; an existing
  file is replaced by pasting the copied text). The repository is public. The daily workflow (and every push to
  `data/ideas/**`) validates the files (`python -m pipeline.workbench --check`) and publishes `site/data/ideas.json`.
- File format: see `pipeline/workbench/ideas.py` (the ticker is the file name; a YAML header with side, status,
  dates, horizon, structure, entry price and optional target assumptions; one `## Heading` per note; catalysts as
  `- YYYY-MM-DD: text`). `site/assets/ideas-store.js` writes the same format (`tests/fixtures/idea_CRWD.md` is its
  output and is parsed by the tests).
- The page shows whether the browser copy matches the published one ("Published", "Changed here", "Only in this
  browser").

## Idea pipeline
Statuses: researching, ready, active, closed, dropped (the first three are "open"). Anton's pipeline is
**10–15** ideas with about **2** new ones a week. Flags: no update for **7** days = review, **14** = stale *(tune)*;
price at or beyond the conservative target = "target reached" (be active around targets); targets on the wrong side
of the price; earnings within 7 days.

## Data and refresh
- Yahoo `quoteSummary` (one call per stock, already made for the screener) now also reads `defaultKeyStatistics`
  (shares, short interest, holdings, beta) and `financialData` (analysts' targets and rating), the quarter estimate
  (`0q`), the sales range and the company profile.
- The screener's price download now takes one year of daily bars; the last **260** are kept in the raw cache
  (`data/raw/screener/prices.json`) for the chart.
- `site/data/stocks/*.json` (~2,000 files) are rebuilt every run and published with the site but **not committed**
  (the workflow excludes them); their inputs stay in the raw cache, so a failed download keeps the last good copy.
