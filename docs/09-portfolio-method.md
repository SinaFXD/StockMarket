# Portfolio Lab: method and implementation notes

Lessons 16–21 (see `docs/01-course-map.md`, "Long/short portfolio management"). The page is `portfolio.html`; the
arithmetic is `site/assets/portfolio-math.js`, tested by `tests/js/portfolio.test.mjs` (`node --test`).

## Books
- Two books, **current** and **proposed** (the course models both before adding, removing or resizing positions).
  A position is a ticker, a side and a size in dollars; the account size turns sizes into weights.
- Kept in the browser (`localStorage` key `ptm.portfolio.v1`) with Export / Import as a JSON file. Nothing is sent
  anywhere. "Add my active ideas" (current) and "Add my open ideas" (proposed) take the ideas from the Ideas page,
  sized at capital ÷ 10 *(our default)*.
- History: daily dividend-adjusted closes of the screener's stocks (`site/data/stocks/<T>.json`, two years) and of
  the ETFs the site publishes (`site/data/series/yahoo/`). Other tickers are listed as "left out". Window: 3M, 6M,
  1Y or 2Y, on SPY's trading days; a missing day repeats the previous close; a stock listed later enters on its
  first close.

## Backtests (lesson 16)
- **CEW** (constant equal weight, rebalanced daily): each day's return = average of the positions' returns, a short
  earning minus the stock's return. The quickest read of which basket out- or under-performs.
- **Non-rebalanced**: each position's dollars are invested on the first day and left to drift; equity = account +
  total P&L (a short's P&L is minus the long's). The practical one: it is what an account would have done.
- Both as an index (start = 100) with SPY for reference, and their **drawdowns** (% below the previous peak).
- Annualised return (compounded), volatility and Sharpe ratio (excess over the 3-month T-bill) of the
  non-rebalanced book. One short sample: a description, not a forecast.

## Risk (lessons 17–19)
- **Portfolio volatility** = √(wᵀ Σ w × 252), w = signed dollars ÷ account, Σ = covariance of daily returns over the
  window. Target **15–30%** a year, practical aim **17.5–22.5%** (course).
- **Risk share** of a position = wᵢ (Σw)ᵢ ÷ wᵀΣw: its part of the portfolio variance (sums to 100%; a hedge is
  negative).
- **Correlation matrix**: as positions (default; a short's returns are flipped, so a long and a short in stocks that
  move together show a negative number) or as stock prices. Average pairwise correlation target **−0.3 to +0.3**.
  Rolling correlation over **60** trading days *(our choice; half the window for 3M)*: the positions' average
  pairwise correlation and the book against the S&P 500.

## Exposure (lesson 19)
- Long, short, gross (long + short) and net (long − short) exposure in % of the account.
- **Beta** of each holding = cov(stock, SPY) ÷ var(SPY) over the window; **beta-adjusted net** = Σ side × dollars ×
  beta ÷ account (a holding without enough history counts with beta 1).
- Against the Macro Desk's automatic bias: net long → beta-adjusted net should be positive, net short → negative,
  neutral → within **±30%** *(our choice)*. Information only.
- Median market cap of the longs and of the shorts, with the course's note that in GDP-growth regimes mid-cap longs
  against large-cap shorts tended to beat large against large.

## Diversification and Sharpe framing (lessons 20–21)
- Positions by account size: up to $250k **8–12** (the course's retail $25k–$100k margin account), $250k–$2m **10–14**
  (course: $250k–$1m), $2m and above **12–16** (course: $2–5m; more is over-diversification). The gaps between the
  course's brackets are filled with the lower bracket's numbers *(our choice)*.
- Required return = minimum Sharpe × portfolio volatility: CFDs (≈4× leverage) Sharpe 1.5 → 22.5–45% a year at
  15–30% volatility; US stocks long/short (2×) Sharpe 2 → 30–60%; options (3–10× implied) Sharpe ≈3.3 → 50–100%.
  The page also shows the numbers at the book's own volatility.
