# Sectors side by side

`sectors.html` ("Stocks → Sectors" in the menu) puts the eleven sectors next to each other so the user can choose which
ones to screen first. **It is an extension of the course's method, not a lesson step**: the course screens one
sector at a time against the sector's own averages (lessons 22–29) and reads cyclical vs defensive behaviour as
part of the macro picture; it does not prescribe a sector-ranking page. Everything here is **context only**: it never
changes the Macro Desk bias, the screener's types or any score.

Pipeline: `pipeline/sectors/build.py` → `site/data/sectors.json`, built after the Macro ideas from the published
files (`screener/stocks.json`, `themes.json`, `macro/latest.json`, the SPDR sector ETFs and SPY in
`series/yahoo/`). `python -m pipeline.sectors` rebuilds it from local data. Thresholds: `config.SECTORS`.
Page: `site/assets/sectors.js`. Tests: `tests/test_sectors.py`.

## Per sector
| Part | Rule |
|---|---|
| Sector ↔ ETF | Yahoo's sector names → SPDR ETFs (`workbench.stock.SECTOR_ETF`): XLB, XLC, XLY, XLP, XLE, XLF, XLV, XLI, XLRE, XLK, XLU |
| Group | Morningstar's super-sectors: **cyclical** (Basic Materials, Consumer Cyclical, Financial Services, Real Estate), **sensitive** (Communication Services, Energy, Industrials, Technology), **defensive** (Consumer Defensive, Healthcare, Utilities) |
| Fundamentals | medians over the sector's *clean* stocks (no check that leaves a stock out of the sector averages, same as the Screener): EG1, EG2, PE1, PEG1, sales growth, realised volatility; market cap and type counts over all its stocks |
| Revision breadth | among clean stocks with a 90-day EPS1 revision: % raised by ≥ `revision_pct` (1%) and % cut by ≥ 1% |
| Relative strength | ETF return minus SPY return over 21 / 63 / 126 trading days (1 / 3 / 6 months), adjusted closes, in percentage points |
| Relative line | ETF ÷ SPY on common days, last `spark_days` (126), rebased to 100 |
| Rotation | on the relative line: **rs** = its change over `rs_days` (63); **change** = rs now minus rs `rs_momentum_days` (21) ago. Leading: rs ≥ 0 and change ≥ 0; weakening: rs ≥ 0, change < 0; lagging: rs < 0, change < 0; improving: rs < 0, change ≥ 0 (the idea of a relative-rotation graph, computed simply) |
| Macro wind | stock-weighted average of the Macro ideas net score of the sector's industries (`themes.json`), with the three strongest tail- and headwinds |
| Candidates | up to `candidates` (5) longs (positive outliers) and shorts (negative outliers, post-growth), those passing the volatility filter first, then by market cap |

## Cyclicals vs defensives
- Each group is an equal-weight basket of its sector ETFs' relative lines, rebased on the first day of the last
  `group_days` (252). The chart is (cyclical + sensitive basket) ÷ defensive basket, start = 100.
- **spread_3m** = the ratio's change over 63 days. ≥ `rotation_pp` (2) → the market prefers cyclicals; ≤ −2 →
  defensives; otherwise mixed.
- **Agreement** with the Macro Desk bias: net long + cyclicals, or net short + defensives = agree; the opposite =
  disagree; a neutral bias or a mixed market = mixed. A disagreement is a prompt to read both again, not a signal.

## Limits
- ETFs are cap-weighted and the fundamentals are medians of the screener's universe (US-listed, above $2 billion),
  so the two halves of a card do not describe exactly the same basket.
- Relative strength describes the past; sector momentum is a well-documented tendency, but it is not a course rule and
  is never scored here.
