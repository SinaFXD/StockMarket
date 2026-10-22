# Leading indicators — Anton's interpretation and the dashboard's first-reading rules

Each section has two parts:
- **Anton says** — paraphrased from the lesson (the method; source of truth).
- **Proposed rule** — the dashboard's mechanical first reading derived from it (score +1 / 0 / −1 plus a
  plain-English reason). Thresholds marked *(tune)* are our choice where Anton gives no number; keep them
  configurable in one file and record changes in this doc.

General principle (repeated in every lesson): there is **no rulebook**. The Fed watches the same data and
reacts (2019: curve flat, ISM < 50, Fed cut three times, S&P +30%). Indicators are read **together**, in the
context of business-cycle history. Automatic scores are a starting point; the user can override every one.

---

## 1. Real interest rates & yield curve (lesson 4)
**Anton says**
- P/E framing: growth sets E (denominator), liquidity sets P (numerator) — read growth *and* liquidity.
- Real rate = nominal 10y Treasury yield − CPI YoY (other countries: their benchmark/official rate − their CPI).
- Low or negative real rates *relative to history* → abundant liquidity → higher P/E, lower VIX, equities up.
  High real rates vs history → scarce liquidity, higher volatility. (2011–2020: real < 1% ⇒ VIX mostly 10–19.)
- Yield curve benchmark = **10y − 2y**. Normal (upward) = expansion expected; flat = transition; inverted =
  contraction expected. **Direction of transition matters**: flattening toward inversion is bearish;
  steepening out of inversion/flatness is bullish. Watch the short end too (1m/3m/6m above 10y — Feb 2020 the
  inversion was only at the short end). 2006–07: 10y−2y negative most of the time → GFC.
- Caveat: a transitioning curve has often signalled the Fed's next move rather than a crash.
- Same template applies to Japan, UK, Germany, Italy (and China real rates — lesson 14).

**Proposed rule**
- Curve (10y−2y, also show 10y−3m): inverted → −1; positive and steepening over 3m → +1; flat (0–0.5pp *(tune)*)
  and flattening → −1; flat and steepening → +1; otherwise 0. Reason text names the shape and direction.
- Real 10y: percentile vs 10y history ≤ 25th → +1; ≥ 75th and rising over 3m → −1; else 0 *(tune)*. Also show
  the real-rate vs VIX chart.

## 2. Corporate bond spreads (lesson 5)
**Anton says**
- Track ICE BofA US corporate **AA**, **BBB** (lowest investment grade) and **CCC** (junk) spreads vs the 10y.
- CCC is the most sensitive — "junk moves first" — and moves are large (≈300→700bp in 2014–15, ≈300→1000bp in 2020).
- Widening = market prices more contraction/default risk → sells credit → equities fall; tightening → equities rise.
  Reinforcing loop via cost of debt → cash flows → borrowing. Good but not always reliable (Fed reacts). Read with
  real rates, curve and VIX.
- ETFs as gauges/hedges: LQD, VCSH, VCIT, VCLT, HYG, JNK.

**Proposed rule**
- For CCC, BBB and AA: 3-month change in OAS above its own 90th percentile of 3m changes → −1; below 10th → +1;
  else 0 *(tune)*. Highlight when CCC widens while BBB/AA haven't yet ("junk first").
- History note: FRED's ICE BofA series currently expose only a few recent years; use Moody's BAA10Y/AAA10Y for long
  history and backtests, clearly labelled as the long-history series.

## 3. M2 money supply — confirming indicator of Fed policy (lesson 6)
**Anton says**
- Use M2 (monthly, seasonally adjusted, since 1959). Compute MoM % and YoY %.
- Distribution-of-returns analysis of MoM growth (Chris Coyle): mean ≈ 0.57%/month, ±1σ ≈ 0.1%–1.0%, fat tails;
  ≈ 5% of months above ≈ 1.15% → **abnormal upside = Fed injecting liquidity**.
- Not tightly correlated with GDP or returns (velocity changed). Use it to **confirm or contradict** the bond-market
  indicators: healthy bond markets but shrinking M2 → Fed withdrawing stimulus; an expansion plus an abnormal M2
  surge → "what does the Fed see that we don't?".
- Also watch the Fed directly: policy rate, FOMC dates (8/yr), minutes (3 weeks later), press conferences, size and
  pace of asset purchases (balance sheet), inflation target and GDP projections. Fed action can be pre-emptive or late.

**Proposed rule**
- Show MoM growth with its percentile in the 1959-to-date distribution and the ±1/2/3σ bands.
- Score: MoM in top 5% → flag "abnormal liquidity injection" (+1 for liquidity, but raise a consistency alert if
  money-market signals are positive); YoY < 0 → −1; else 0. Consistency alert when M2 direction disagrees with the
  money-market block.

## 4. VIX (from IPLT)
**Proposed rule**: VIX percentile and 3m change; high and rising (≥ 75th pct and up) → −1; low and stable (≤ 25th)
→ +1; else 0 *(tune)*. Plot against the real rate (lesson 4 relationship).

## 5. ISM Manufacturing (lesson 7) — **manual data**
**Anton says**
- Diffusion index; 50 = no change. PMI = equal weights of **New Orders, Production, Employment, Supplier Deliveries,
  Inventories**. Outside the PMI: Customers' Inventories, Prices, Backlog, New Export Orders, Imports.
- **New Orders is the most sensitive — "the leading indicator of the leading indicator"**; it leads the headline.
  Production follows orders. **Inventories** is sensitive (rising = management optimistic; falling = pessimistic;
  watch turning points). Employment and Supplier Deliveries lag (deliveries reveal supply-chain problems by industry).
- History: troughs usually 40–45 (GFC 32.5–35); peaks ≈ 60, near peaks in S&P annual returns. Above 50 → expect
  positive GDP growth and S&P returns; below 50 → contraction. Gets GDP direction right ≈ 60–80% of the time.
  After a fall below 50 (with a 6–12 month lag) you can start tilting the portfolio short.
- Use the industry rankings (which industries report growth/contraction) and respondents' comments for trade ideas;
  log them monthly.

**Proposed rule**
- PMI ≥ 50 and New Orders ≥ 50 → +1; PMI < 50 and New Orders < 50 → −1; else 0.
- Extra flags: New Orders minus Inventories (orders leading); "near peak" (≥ 58 *(tune)*) and "near trough" (≤ 45);
  trend length in months above/below 50 for each component.
- Industry table from `data/manual/ism_industries.csv` (growth/contraction lists + comments).

## 6. ISM Services (lesson 8) — **manual data**
**Anton says**
- Composite = 25% each: **Business Activity, New Orders**, Employment, Supplier Deliveries. Business Activity and
  New Orders matter by far the most; Employment and Deliveries lag. **Backlog of Orders** (outside the index) is a
  confirming indicator.
- Services ≈ 80% of the US economy. Give Manufacturing and Services **equal weight**.
- Peaks ≈ 60 (S&P ≈ +20%/yr); 55–60 ≈ +15–20%; 50–55 often still fine; troughs 40–45. Business Activity can lead the
  composite down (March 2020).

**Proposed rule**: composite ≥ 50 and Business Activity ≥ 50 and New Orders ≥ 50 → +1; composite < 50 or both BA
and NO < 50 → −1; else 0. Show backlog as confirmation.

## 7. University of Michigan Consumer Sentiment (lesson 9)
**Anton says**
- Consumer spending ≈ 67% of US GDP. Index = 50% Current Conditions + 50% **Expectations**.
- **The Expectations index and its monthly change matter most** (Aug 2019: expectations −10.6 to 79.9 while
  current conditions stayed 105.3).
- Range approach: **95–110 peak zone; 70–95 balanced; 55–70 trough/pessimistic zone**. Simpler composite bands:
  several readings > 80 → optimistic (GDP ≥ 2%, strong S&P); 70–80 balanced (GDP 0–2%, positive S&P);
  55–70 pessimistic (GDP −5% to +1%). Worry when falling sharply from a peak toward or below 70.
- Peaks = consumer at capacity (likely to fall later); troughs = paradox of thrift, capacity to spend later.

**Proposed rule**: composite and expectations zones as above; expectations 3m change ≤ −10 *(tune)* → −1 regardless
of level; several readings < 70 → −1; > 80 and not falling → +1; else 0.

## 8. Building permits (lesson 10)
**Anton says**
- Permits → starts (coincident) → completions (lagging). 94% of starts begin within 0–3 months of the permit;
  permits lead completions by 12–16 months.
- Levels: long-run trend 1.3–1.4m (SAAR); troughs 700–800k in earlier cycles, 500–600k in the GFC (521k);
  peaks ≥ 2m (2004–early 2006; falling below 2m in May 2006 was an early GFC warning).
- MoM moves of ±20% are rarely followed by equally big moves. YoY turning negative often precedes negative GDP YoY
  (not always). 12-month MA of permits YoY vs 12-month MA of S&P YoY move together; permits sometimes lead.
- Read together with UMich (a powerful combination).

**Proposed rule**: 12m MA of YoY % > 0 and rising → +1; YoY < 0 and 12m MA falling → −1; else 0. Show level vs
the 1.3–1.4m trend band and historical troughs/peaks.

## 9. NFIB Small Business Optimism + custom ITPM NFIB SBO leading index (lesson 11) — **manual data**
**Anton says**
- SBO = 10 equal-weight components (base 1986 = 100): plans to increase employment; plans to make capital outlays;
  plans to increase inventories; expect economy to improve; expect real sales higher; current inventory; current job
  openings; expected credit conditions; now a good time to expand; earnings trends.
- **Custom ITPM leading index = simple average of 5 leading components** (20% each): plans to increase employment,
  good time to expand, plans to increase inventories, expect economy to improve, expect real sales higher (you may
  swap "good time to expand" for capex plans). Plot with a **4-month moving average**; track each component's trend
  length in months.
- Composite levels: consistently > 100 → strong GDP and S&P YoY ≈ 15–20%+; 95–100 → S&P 0–15%; ≤ 95 → zero growth
  or contraction. Dropping below 100 is a warning.

**Proposed rule**: composite > 100 and custom index above its 4m MA → +1; composite ≤ 95 or (custom index below its
4m MA and falling for 3 months) → −1; else 0.

## 10. Cyclical commodities & the US dollar (lesson 12)
**Anton says**
- Track oil, copper, iron ore (energy & industrial metals) and lumber (construction); PPI industrial-commodity
  sub-indices (fuels & power, lumber & wood, metals) as leading measures; CPI/PPI are coincident.
- Decide whether a move is **demand-driven** (strong signal for real GDP and future CPI/PPI) or **supply-driven**
  (weak growth signal — be cautious).
- COT: managed-money long % of open interest − short % = net positioning; turning points are sentiment context,
  not a trade rule.
- Dollar: Fed trade-weighted indices (Broad, AFE, EME). Dollar down = inflationary for USD-priced commodities;
  dollar up = deflationary. Use distribution of daily/weekly returns: 1/2/3σ moves signal a change in macro conditions.
- International benchmarks too: Brent, LME copper, Shanghai copper.

**Proposed rule**: each commodity YoY > +5% → +1, < −5% → −1 *(tune)*; tag "demand vs supply" as a manual
annotation field; dollar YoY > +5% → −1 (headwind), < −5% → +1. Daily/weekly σ-move alerts for every series.

## 11. Euro-area Economic Sentiment Indicator (lesson 13)
**Anton says**
- Use the **euro-area** composite (not EU). Mean 100, SD 10. > 100 above average. Peaks usually ≈ 115+; sharp
  2–3 SD falls tend to mark troughs. Look at sector components (industry, services, consumer, retail, construction)
  and big-country ESIs (Germany, France, Italy, Spain, Netherlands).
- STOXX 600 and euro-area GDP rose together in ~63% of quarters.

**Proposed rule**: ≥ 100 and rising over 3m → +1; < 100 and falling → −1; else 0. Peak/trough zone flags at
±1.5 SD *(tune)*.

## 12. China (lesson 14) — **manual PMI data**
**Anton says**
- Official data (GDP, NBS PMI) is unreliable; **prefer the private PMI** (Caixin, now **RatingDog China PMI**
  compiled by S&P Global since Aug 2025). Weights: New Orders 30%, Output 25%, Employment 20%, Suppliers' Delivery
  Times 15%, Stocks of Purchases 10%. 50 = no change.
- Official PMI has lived in a tight band, capped near 52 since ~2013.
- **"Potential lie" metric**: private − official (mostly negative). Flag months where **official > 50 and private < 50**.
- China real 10y = China 10y yield − CPI. China bonds are mostly domestic → weak as a leading indicator.
- Use Chinese ADRs for ideas when official data looks fake.

**Proposed rule**: RatingDog ≥ 50 and rising → +1; < 50 and falling → −1; else 0. Show the private − official gap
and the "potential lie" flag. Official PMI shown but not scored.

---

## Combining into the portfolio bias
Anton gives no formula; he reads the indicators together. Proposal:
- Four blocks, as in the course: **US money markets** (curve, real rate, credit, M2, VIX), **US surveys** (ISM M,
  ISM S, UMich, permits, NFIB), **cyclical prices/FX/equities** (commodities, dollar, S&P trend), **international**
  (ESI, China, other money markets).
- Block score = mean of its indicators; bias = mean of blocks (so one block with many series can't dominate).
  Net long ≥ +0.25, net short ≤ −0.25, else neutral *(tune)*. Manual overrides recalculate live.
- Show "what changed since last month" and every disagreement between blocks (e.g. surveys weak but money markets
  strong — the 2019 pattern).
- Evidence page: forward 1/3/6-month S&P 500 and regional index returns after each bias state, computed with
  **real-time vintages (ALFRED)** where available, with sample sizes, and a clear note where only revised data exists.

---

## Implementation notes (Phase 1a, 2026-10-22)
How the rules above are coded in `pipeline/signals/`. Every number lives in `pipeline/config.py` (`SIGNALS`);
*(tune)* = our choice where Anton gives no number.

- **"Over 3 months"** = 91 calendar days for daily series, 3 monthly observations for monthly series *(tune)*.
  **Percentiles** use the last 10 years of the series (less where the source is shorter, e.g. ICE spreads).
- **Curve**: 10y−2y scored; a 3-month move smaller than ±0.10pp counts as stable *(tune)*. 10y−3m below zero while
  10y−2y is positive raises a "short end inverted" flag.
- **Real 10y** = latest 10y yield − latest published CPI YoY; percentile against the monthly real rate of the last
  10 years; "rising" = higher than the same calculation 3 months earlier.
- **Credit** combines the three spreads into one signal *(tune)*: two or more components at −1 → −1, two or more at
  +1 → +1, CCC alone at −1 → −1 ("junk moves first"), else 0. Each component compares the latest 3-month change with
  the distribution of its own 3-month changes (≥ 90th → −1, ≤ 10th → +1). With less than a year of ICE history
  (all dates before late 2024 on FRED) Moody's Baa−10y is used on its own and flagged.
- **M2**: an abnormal month (top 5% of MoM since 1959) is checked first, then YoY < 0. Consistency alerts compare
  M2 with the other money-market signals.
- **VIX**: whichever of FRED VIXCLS and Yahoo ^VIX is fresher.
- **UMich** (sentiment, current conditions and expectations from the survey's own tables; monthly since 1978):
  "several readings" = 3 months *(tune)*; a fall of 15+ points from the 12-month high raises a flag *(tune)*.
- **Permits**: "rising/falling" = 12-month average of YoY compared with 3 months earlier *(tune)*.
- **NFIB**: the ITPM index needs all five leading components in a month; "falling for 3 months" = three
  consecutive monthly declines. Component trend lengths are reported, not scored.
- **Commodities**: Brent (EIA daily via FRED, Yahoo futures if fresher), copper (COMEX futures, IMF monthly as
  fallback), iron ore (IMF), lumber (PPI). Demand vs supply is left to the user's override.
- **S&P 500 trend (new proposal, not from the lessons' numbers)**: Anton treats equity prices as a leading
  indicator; first reading: close above its 200-day average and up over 3 months → +1, below and down → −1, else 0
  *(tune)*.
- **ESI** uses the largest euro-area aggregate Eurostat publishes (EA21 since 2026).
- **China**: "rising/falling" = RatingDog manufacturing vs 3 months earlier *(tune)*; RatingDog services and NBS are
  shown, NBS is never scored.
- **International money markets (1c)**: Japan, UK, Germany and Italy are each read with the US template (section 1):
  curve = 10y yield − overnight rate (no free 2y series for all four; the lesson's "watch the short end" view),
  real 10y = latest 10y − latest CPI YoY, percentile vs the country's last 10 years. Curve and real-rate rules and
  thresholds are the US ones; "over 3 months" = 3 monthly observations. Country = sign of curve + real score
  *(tune)*. Signal = net of the four countries: ≥ +2 → +1, ≤ −2 → −1, else 0; fewer than 3 countries with data →
  awaiting *(tune)*. Data: OECD monthly averages, known 45 days after the month ends; rates and CPI are not
  revised in practice, so they are not flagged "revised". China's real rate is shown (China and Global pages)
  but not scored (lesson 14: weak leading indicator). The Italy − Germany 10y spread is shown, not scored.
- **ESI components (1c)**: big-country ESIs (DE, FR, IT, ES, NL) and the euro-area sector confidence indicators
  are shown on the ESI page; "countries above 100" is reported, the score still uses the euro-area ESI only.
- **Regional equity dispersion (1c, Global page)**: US / Europe / Japan / China, local indices and US-dollar ETFs;
  1/3/6/12-month and YTD returns, distance from the 200-day average and the 12-month high, relative strength
  vs the US. Context for lesson 15's "global or local?" question, **not scored**: the course gives no rule that
  turns regional relative strength into a portfolio bias.
- **Confirmers (1d)**: coincident (payrolls, unemployment, initial and continuing claims, industrial production,
  durable goods orders, CPI/core CPI/PPI) and lagging (real GDP, corporate profits) data are shown on the Macro
  Desk and **never scored** (lesson 1: prices move before the reports). Growth confirmers get a tone with
  thresholds in `config.CONFIRMERS` *(tune)*: payrolls 3m average ≥ +100k supportive, < 0 weak; unemployment
  ±0.2pp over 3 months; claims 4-week average ±10% vs 13 weeks earlier; industrial production YoY ±1%; durable
  orders (3-month sum) YoY ±3%; real GDP ≥ 2% annualised supportive (Anton's "GDP ≥ 2%" band in lesson 9),
  < 0 weak; profits YoY ≥ 5% supportive, < 0 weak. Inflation shows its direction only. The summary says
  whether the confirmers agree with the leading bias.
- **Evidence (1d)**: forward 1/3/6-month price returns of the S&P 500, STOXX 600, Nikkei 225, Shanghai Composite
  and ACWI from each month-end snapshot (month-end close to month-end close), grouped by bias state and by each
  signal's score, with n and an "independent windows" count (n / horizon). Samples: all months, 2000–2012,
  2013–now, and months with no revised input. An exposure illustration holds the S&P 500 at +1 / 0 / −1 per
  the bias, no costs. Nothing on this page feeds back into the rules.
- **Data-vs-prices alert (added 2026-10, after the Evidence review)**: when the bias is net short while the S&P 500
  trend signal is +1 (above its 200-day average and up over 3 months), or net long while it is −1, the Macro Desk
  shows an alert (lesson 1: prices move before the reports; Anton's 2019 example of weak data, a Fed that reacts
  and a rising market). It never changes a score. Its history on the Evidence page is in-sample (it was designed
  after looking at 2022–24), so it is reported as context, not as proof.
- **Bias**: block = mean of its available signals, bias = mean of blocks, ±0.25 *(tune)*. Awaiting-data signals are
  excluded. Overrides on the website recalculate the same arithmetic in the browser.
- **Point in time**: month-end snapshots since 2000 use ALFRED vintages (CPI, M2, permits, iron ore, lumber, …),
  report release calendars for hand-entered data, market prices up to that day, UMich/ESI from the end of their
  month, and a 45-day lag for other monthly FRED series. Dates before a series' ALFRED history are marked
  "revised data".
