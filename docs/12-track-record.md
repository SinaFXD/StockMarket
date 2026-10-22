# Proving the process: forward test and track record

The site's rules are a first reading of the course; whether they add value has to be shown on data that did not
exist when the rules were set. Three records do that, all reported as they come, never used to tune a rule.

| Record | What it tests | Where |
|---|---|---|
| Macro Desk daily log (`site/data/macro/log.csv`, since 2026-10-22) | the bias, out of sample | Evidence page (and the 2000–2026 backtest on real-time vintages) |
| **Forward test of the Screener's types** (`site/data/forward/outliers.csv`, since 2026-10-21) | do positive outliers beat negative outliers? | Evidence page, "Forward test" |
| **Track record of closed ideas** (the ideas themselves) | does the whole process (template, timing, structure) make money? | Ideas page, "Track record" |

## Forward test of the Screener's types (`pipeline/forward/`)
- Why not a backtest: there is no free point-in-time history of analysts' estimates; using today's estimates on
  past prices would leak the future, and stocks that disappeared would be missing.
- **Cohorts:** the first update whose last close falls in a new ISO week writes down every stock of a candidate
  type (positive, negative, post-growth, turnaround, value trap) with its type, sector, volatility filter and the
  close of that day (~500 stocks a week).
- **Returns:** every update fills, for each row whose horizon has passed, the return over **20, 40 and 60**
  trading days (counted on SPY's trading days), and the same-period return of SPY and of the stock's SPDR sector
  ETF. A stock that left the screener's universe is priced from a separate download; a missing day uses the last
  close up to 5 days earlier; a stock with no price keeps an empty cell (counted as missing, never guessed).
- **Results** (`summary.json`): per type the average return, the excess over SPY and over the sector ETF and the
  share that beat SPY; the **long-short spread** = average of positive outliers minus average of negative outliers
  within each cohort. Weekly cohorts overlap when the horizon is longer than a week, so the number of independent
  windows is cohorts × 5 ÷ horizon and the t-statistic uses it. Also shown for the stocks that passed the
  volatility filter only.
- The record is committed daily by the workflow (like `macro/log.csv`); it starts from the first cohort and only
  grows. Costs and borrow fees are not included.

- **Cohort day:** the last trading day both the screener's bars and SPY have closed (a run during US market hours
  would otherwise see today's unfinished session in the bars, which SPY's published series leaves out).

### Pre-registered: estimate revisions vs forecast growth (fixed 2026-10-22, before the first cohort)
Research finds that stocks whose analysts' estimates are being **raised** tend to do better afterwards, while stocks
with the **highest forecast growth** often do not (the growth is already in the price). The Screener's types use
forecast growth levels, so the same record now also tests revisions:
- **Groups:** within each sector with at least 8 stocks that have one, the top quarter of the 90-day change in the
  EPS1 consensus (`eps1_rev90`, measured only from a positive base) = **up**, the bottom quarter = **down**. These
  stocks join the weekly cohort even when their type is not a candidate; every row keeps `rev90` and `rev_group`.
- **H1:** "up" minus "down", per cohort (sector-neutral by construction; also shown against SPY and the sector ETF).
- **H2:** positive outliers in "up" minus the other positive outliers, per cohort.
- Reported next to the types' spread at 20 / 40 / 60 days with the same independent-window t-statistic, whatever they
  show. Hypotheses, groups and horizons are not changed after the fact; a new idea gets a new, dated hypothesis.

## Track record of closed ideas (`site/assets/journal-math.js`)
- An idea counts when its status is **closed** and it has an entry price and date (default: the date it was
  opened) and an exit price and date (set on the idea's page; the exit defaults to today's price when you close it).
- **Return** for the side: long = exit ÷ entry − 1; short = minus that.
- **Alpha** = return − side × beta × S&P 500 (SPY) return over the same dates. Beta is measured on daily returns
  over the year before the entry (at least 60 days, else 1 is assumed and shown as such).
- **Summary:** number of trades (long / short), hit rate, average win and loss, payoff ratio (average win ÷ average
  loss), average alpha and the share of trades with positive alpha, average holding period.
- Ideas kept only in the browser count in that browser; published ideas count everywhere. Costs are not included.

## Reading the results
A few weeks or a handful of trades prove nothing. A long-short spread with |t| above about 2 over many independent
windows, and a positive average alpha over dozens of trades, start to be evidence. Judge the process against a
simple alternative (holding the market) after costs.
