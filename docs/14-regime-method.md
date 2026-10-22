# Regime, recession odds, Fed policy and the Treasury curve

`regime.html` ("Regime" in the menu, after the Macro Desk) adds the bigger picture behind the bias: the growth and
inflation regime (lesson 3: GDP growth and inflation set the backdrop for equities), what did well in each regime,
recession odds from the yield curve and the Fed against a policy rule (lessons 4-6). **Context only**: nothing here
feeds the bias or any score. Built after the benchmark review of 22 Oct 2026 (`docs/03-reza-benchmark.md`), with
our own definitions and point-in-time history.

Pipeline: `pipeline/regime/build.py` -> `site/data/regime.json`, after the Macro Desk, from the same point-in-time
`Library`. `python -m pipeline.regime` rebuilds it from local data. Thresholds: `config.REGIME`. Page:
`site/assets/regime.js`. Tests: `tests/test_regime.py`.

## Regime (growth vs inflation)
| Axis | Rule |
|---|---|
| Growth | Chicago Fed National Activity Index (FRED `CFNAI`, a weighted average of 85 monthly US indicators; 0 = growth at its historical trend), averaged over the last 3 months (the Chicago Fed's own CFNAI-MA3). ≥ 0 = at or above trend |
| Inflation | core PCE price index (`PCEPILFE`): inflation over the last 6 months, annualised, minus inflation over 12 months, in pp. ≥ 0 = inflation speeding up |

The latest month that both inputs cover sets the regime: **Recovery** (growth ≥ trend, inflation easing),
**Overheat** (≥ trend, rising), **Stagflation** (below trend, rising), **Reflation** (below trend, easing) (the
quadrant names of the well-known "investment clock"). A reading within 0.1 of the growth line or 0.15 pp of the
inflation line is shown as **borderline**: the next release can flip it (both indexes are noisy month to month).

- The map shows the last 24 months with today's (revised) data.
- The timeline is **point in time**: at each month-end since 1999 the regime is read from the data published by that
  day (ALFRED vintages: CFNAI from May 2011, core PCE from Aug 2000). Earlier months use revised data with a 45-day
  publication lag and are flagged; the page offers a "real-time data only" view.

## Two questions: direction and level
The map reads **directions**, as the course does (lesson 3: the direction of GDP growth and of the S&P 500). Levels
answer a different question, "how hot is it?", and can disagree with the map (e.g. Oct 2026: Recovery on direction,
running hot on levels). The page shows both side by side:

| Level | Hot | Cold |
|---|---|---|
| Core PCE inflation (12 months) vs the Fed's 2% target | ≥ +0.5 pp | ≤ −0.5 pp |
| Output gap (real GDP vs CBO potential) | ≥ +0.5% | ≤ −0.5% |
| Unemployment (`UNRATE`) vs CBO's natural rate (`NROU`) | ≤ −0.25 pp | ≥ +0.25 pp |

Two of three hot = "running hot", two of three cold = "running cold", else "near balance". The Fed's stance against
the Taylor rule (≥ 1 pp below = loose, above = tight) is shown as its response, not counted. Thresholds in
`config.REGIME` (`level_*`): our first reading, not course rules.

**Core CPI cross-check.** Core CPI (`CPILFESL`) is published about two weeks before core PCE. The same momentum
measure on core CPI, with today's growth reading, gives the regime the next PCE release may bring; when its direction
disagrees with core PCE the page warns that the regime may flip. Note: FRED has no CPI for October 2025 (US government
shutdown); every year-on-year change is aligned by date, never by row count.

## What did well in each regime
- For every month-end since 1999-01 the next **3 months'** return (adjusted closes, dividends included) is grouped by
  the regime known that day. Sectors: SPDR ETF return minus SPY's over the same months. Asset classes (absolute):
  SPY (S&P 500), IEF (Treasuries 7-10y, from 2002), GLD (gold, 2004), DBC (commodities, 2006), UUP (US dollar, 2007).
- Each cell: mean, n; hover for median, share positive, worst, best and the number of independent 3-month windows
  (n ÷ 3; consecutive months overlap). Past averages describe the sample; they are not forecasts and were not used to
  tune anything.

## Recession odds (New York Fed model)
- P(recession 12 months later) = Φ(α + β × spread), α = −0.5333, β = −0.6330, spread = monthly average of the 10-year
  minus 3-month Treasury yield. Parameters verified from the New York Fed's `Prob_Rec.pdf` (fitted 1959-2009;
  Sep 2026: spread 0.955 -> 12.76% for Sep 2027; `tests/test_regime.py` checks this number).
- We use FRED's constant-maturity `T10Y3M` (from Jan 1982); the Fed uses a bond-equivalent 3-month bill, so our
  spread can differ by a few hundredths and the probability by about a point (Sep 2026: 0.896 -> 13.6%).
- Only complete months; plotted at the month the forecast is about (the line runs 12 months ahead). NBER recessions
  (`USREC`) are shaded; the table lists the highest probability the model gave to each recession's months, and the
  page names the highest reading ever when no recession followed it (a false alarm so far).

## Fed funds vs a Taylor rule
- Taylor (1993): rate = 2 + π + 0.5 × (π − 2) + 0.5 × output gap. π = core PCE inflation over 12 months; output gap =
  100 × (real GDP `GDPC1` ÷ CBO potential `GDPPOT` − 1), the latest quarter carried forward. Compared with the monthly
  effective fed funds rate (`FEDFUNDS`). One simple rule among many; shown for context, not as a prediction.

## Treasury curve
- Constant-maturity yields 1M, 3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 20Y, 30Y (`DGS1MO` ... `DGS30`), the last day of each
  week for 10 years plus the latest day. The chart spaces maturities by their square root; the slider and buttons
  pick any week to compare; the table shows the change in basis points.

## Macro Desk additions (same review)
- The bias history chart draws the S&P 500 at each month-end on a right-hand log axis (`history.json` → `sp500`,
  from `^GSPC`).
- **Copy brief**: a plain-text summary of the view on screen (bias with your overrides, blocks, what changed, alerts,
  indicators at the top or bottom tenth of their 10 years, and the Regime page's regime, recession odds and Taylor
  rule). **Download CSV**: every indicator with its automatic score, your override and the score used.
  `site/assets/brief.js` (pure, `tests/js/brief.test.mjs`).
