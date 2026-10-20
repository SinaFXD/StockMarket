# Data sources (free only)

Status: ✅ well-known ID · 🔎 verify before use · ✍️ entered manually by the user (`data/manual/`)

## US money markets (FRED, `api.stlouisfed.org`; ALFRED vintages via the same API with `realtime_start/end`)
| Item | Series | |
|---|---|---|
| 10y, 2y, 3m, 1m, 6m Treasury | DGS10, DGS2, DGS3MO, DGS1MO, DGS6MO | ✅ |
| Curve spreads | T10Y2Y, T10Y3M | ✅ |
| CPI (headline, core) | CPIAUCSL, CPILFESL | ✅ |
| 10y TIPS real yield (cross-check) | DFII10 | ✅ |
| Fed funds, Fed balance sheet | DFF / FEDFUNDS, WALCL | ✅ |
| ICE BofA OAS: AA, BBB, CCC & lower, IG, HY | BAMLC0A2CAA, BAMLC0A4CBBB, BAMLH0A3HYC, BAMLC0A0CM, BAMLH0A0HYM2 | ✅ (short history on FRED) |
| Long-history credit spreads | BAA10Y, AAA10Y (Moody's) | ✅ |
| M2 | M2SL | ✅ |
| VIX | VIXCLS (also Yahoo `^VIX`) | ✅ |

## US surveys
| Item | Source | |
|---|---|---|
| ISM Manufacturing (PMI + all sub-indices + industry lists/comments) | ismworld.org monthly Report on Business | ✍️ `ism_manufacturing.csv`, `ism_industries.csv` |
| ISM Services | ismworld.org | ✍️ `ism_services.csv` |
| UMich sentiment (composite) | FRED UMCSENT | ✅ |
| UMich current conditions & expectations | sca.isr.umich.edu data tables (CSV) | 🔎 (if unavailable, add to manual file) |
| Building permits (total, 1-unit), starts, completions | FRED PERMIT, PERMIT1, HOUST, COMPUTSA | ✅ |
| NFIB SBO + 10 components | nfib.com monthly SBET report (PDF) | ✍️ `nfib_sbet.csv` |

## Cyclical prices, FX, equities
| Item | Source | |
|---|---|---|
| WTI, Brent (daily) | FRED DCOILWTICO, DCOILBRENTEU; Yahoo `CL=F`, `BZ=F` | ✅ |
| Copper | FRED PCOPPUSDM (monthly); Yahoo `HG=F` (COMEX daily) | ✅ |
| Iron ore | FRED PIORECRUSDM (monthly) | ✅ |
| Lumber | FRED WPU081 (PPI lumber & wood); futures via Yahoo 🔎 | ✅/🔎 |
| PPI final demand, PPI industrial commodities sub-indices | FRED PPIFIS + WPU series 🔎 | ✅/🔎 |
| US dollar trade-weighted: Broad, AFE, EME | FRED DTWEXBGS, DTWEXAFEGS, DTWEXEMEGS | ✅ |
| COT managed-money positioning | CFTC public reporting API (`publicreporting.cftc.gov`) | 🔎 |
| Equity indices / ETFs (regional dispersion) | Yahoo: `^GSPC`, `^STOXX`, `^N225`, `000001.SS`, ETFs SPY, VGK, EWJ, FXI, MCHI, EEM, ACWI, IWM, XHB, sector SPDRs | ✅ (unofficial API) |

## International
| Item | Source | |
|---|---|---|
| Euro-area ESI + sector & country components | Eurostat API dataset `ei_bssi_m_r2` (`ec.europa.eu/eurostat/api/...`) | 🔎 exact query |
| Japan, UK, Germany, Italy 10y yields | FRED IRLTLT01JPM156N, IRLTLT01GBM156N, IRLTLT01DEM156N, IRLTLT01ITM156N (monthly) | ✅ |
| Those countries' CPI YoY | FRED/OECD CPI series (e.g. CPALTT01…M659N) or DBnomics | 🔎 |
| China 10y yield, China CPI | DBnomics / FRED 🔎; else manual | 🔎 |
| China PMIs: NBS official (mfg & non-mfg) and RatingDog (ex-Caixin, since Aug 2025) | NBS release / S&P Global press release | ✍️ `china_pmi.csv` |
| Other PMIs (Japan, UK, Brazil, Canada) | S&P Global press releases | ✍️ optional later |

## Coincident & lagging confirmers (FRED)
CPIAUCSL, PPIFIS, PAYEMS, UNRATE, ICSA, CCSA, DGORDER, INDPRO, GDPC1 (real GDP), CP (corporate profits). ✅

## Calendars (catalyst page)
FOMC (federalreserve.gov), BLS release schedule (CPI, PPI, jobs), BEA (GDP, PCE), Census (permits), ECB,
NBS/S&P Global PMI dates, ISM dates, NFIB dates. 🔎 scrape or maintain a small YAML.

## Micro (Phase 2+)
| Item | Source | |
|---|---|---|
| Universe + sector/industry | Yahoo screener / Nasdaq screener endpoint 🔎, SEC `company_tickers.json` | 🔎 |
| Forward EPS & revenue estimates (current/next FY), growth, analyst ranges, # analysts, price targets, ratings | `yfinance` (`earnings_estimate`, `revenue_estimate`, `growth_estimates`, `eps_trend`, `analyst_price_targets`, `recommendations`) | ✅ (unofficial; rate-limit; cache) |
| Next earnings date | `yfinance` calendar / earnings dates | ✅ |
| Historical statements (income, balance sheet, cash flow), shares outstanding | SEC EDGAR XBRL `data.sec.gov/api/xbrl/companyfacts/CIK##########.json` (needs `User-Agent` with email) | ✅ |
| Insider transactions & holders | `yfinance` insider/institutional tables; SEC Form 4 🔎 | ✅/🔎 |
| Prices (realised vol, ATR, beta, correlation) | `yfinance` daily OHLC | ✅ |
| Implied volatility | `yfinance` option chains (compute ATM IV) | ✅ |
| Short interest | `yfinance` info fields 🔎 | 🔎 |

Rules for every fetcher: retries with backoff, polite rate limits, cache raw responses, keep last good copy,
write status into `site/data/health.json`.
