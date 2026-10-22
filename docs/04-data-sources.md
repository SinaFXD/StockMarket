# Data sources (free only)

Status: ✅ well-known ID · 🔎 verify before use · ✍️ entered manually by the user (`data/manual/`)

Everything fetched automatically is listed in `pipeline/catalog.yaml`; all of those IDs and symbols were checked
live on 2026-10-20 (FRED via the API with a key; Yahoo via `yfinance` 1.7 and the public chart endpoint).

## US money markets (FRED, `api.stlouisfed.org`; ALFRED vintages via the same API with `realtime_start/end`)
| Item | Series | |
|---|---|---|
| 10y, 2y, 3m, 1m, 6m Treasury | DGS10, DGS2, DGS3MO, DGS1MO, DGS6MO | ✅ |
| Curve spreads | T10Y2Y, T10Y3M | ✅ |
| CPI (headline, core) | CPIAUCSL, CPILFESL | ✅ |
| 10y TIPS real yield (cross-check) | DFII10 | ✅ |
| Fed funds, Fed balance sheet | DFF / FEDFUNDS, WALCL | ✅ |
| ICE BofA OAS: AA, BBB, CCC & lower, IG, HY | BAMLC0A2CAA, BAMLC0A4CBBB, BAMLH0A3HYC, BAMLC0A0CM, BAMLH0A0HYM2 | ✅ (FRED history starts 2023-10-20 only) |
| Long-history credit spreads | BAA10Y, AAA10Y (Moody's) | ✅ |
| M2 | M2SL | ✅ |
| VIX | VIXCLS (also Yahoo `^VIX`) | ✅ |

## US surveys
| Item | Source | |
|---|---|---|
| ISM Manufacturing (PMI + all sub-indices + industry lists/comments) | ismworld.org monthly Report on Business | ✍️ `ism_manufacturing.csv`, `ism_industries.csv` |
| ISM Services | ismworld.org | ✍️ `ism_services.csv` |
| UMich sentiment (composite) | FRED UMCSENT | ✅ |
| UMich sentiment, current conditions & expectations | sca.isr.umich.edu `files/tbmics.csv`, `files/tbmiccice.csv` (monthly since 1978, final values by month-end) | ✅ verified 2026-10-22 |
| Building permits (total, 1-unit), starts, completions | FRED PERMIT, PERMIT1, HOUST, COMPUTSA | ✅ |
| NFIB SBO + 10 components | nfib.com monthly SBET report (PDF) | ✍️ `nfib_sbet.csv` |

## Cyclical prices, FX, equities
| Item | Source | |
|---|---|---|
| WTI, Brent (daily) | FRED DCOILWTICO, DCOILBRENTEU; Yahoo `CL=F`, `BZ=F` | ✅ |
| Copper | FRED PCOPPUSDM (monthly, IMF, ~2.5 months behind); Yahoo `HG=F` (COMEX daily) | ✅ |
| Iron ore | FRED PIORECRUSDM (monthly) | ✅ |
| Lumber | FRED WPU081 (PPI lumber & wood); futures via Yahoo 🔎 | ✅/🔎 |
| PPI final demand, PPI industrial commodities sub-indices | FRED PPIFIS + WPU series 🔎 | ✅/🔎 |
| US dollar trade-weighted: Broad, AFE, EME | FRED DTWEXBGS, DTWEXAFEGS, DTWEXEMEGS | ✅ |
| COT managed-money positioning | CFTC public reporting API (`publicreporting.cftc.gov`) | 🔎 |
| Equity indices / ETFs (regional dispersion) | Yahoo: `^GSPC`, `^STOXX` (STOXX Europe 600, from 2004), `^N225`, `000001.SS`, ETFs SPY, VGK, EWJ, FXI, MCHI, EEM, ACWI, IWM, XHB, sector SPDRs | ✅ (unofficial API) |

## International
| Item | Source | |
|---|---|---|
| Euro-area ESI + sector & country components | Eurostat API `.../statistics/1.0/data/ei_bssi_m_r2?indic=<code>&s_adj=SA` (one request per indicator returns every country; geo `EA21` = euro area since 2026, history back-calculated to 1980). ESI `BS-ESI-I` for EA, DE, FR, IT, ES, NL; sector confidence for EA: `BS-ICI-BAL` industry, `BS-SCI-BAL` services, `BS-CSMCI-BAL` consumers, `BS-RCI-BAL` retail, `BS-CCI-BAL` construction | ✅ verified 2026-10-22 |
| Japan, UK, Germany, Italy, China: 10y yield, short rate | OECD SDMX `sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_FINMARK,/<areas>.M.IRLT+IRSTCI+IR3TIB.PA.....?format=csvfile` (monthly averages). Short rate = `IRSTCI` overnight (JP, GB, DE, IT); China `IR3TIB` 3m interbank (its `IRSTCI` ended 2025-06; UK `IR3TIB` ended 2026-02). China 10y from 2014. FRED's `IRLTLT01…` copies are the same OECD data; no longer used. | ✅ verified 2026-10-22 |
| Those countries' CPI YoY | OECD `DSD_PRICES@DF_PRICES_ALL,1.0` key `GBR+DEU+CHN.M.N.CPI.PA._T.N.GY`; Japan and Italy only current in `DSD_PRICES_COICOP2018@DF_PRICES_C2018_ALL` (same key). FRED's `CPALTT01…` copies stopped in 2021–2025. | ✅ verified 2026-10-22 |
| China PMIs: NBS official (mfg & non-mfg) and RatingDog (ex-Caixin, since Aug 2025) | NBS release / S&P Global press release | ✍️ `china_pmi.csv` |
| Other PMIs (Japan, UK, Brazil, Canada) | S&P Global press releases | ✍️ optional later |

## Coincident & lagging confirmers (FRED)
CPIAUCSL, PPIFIS, PAYEMS, UNRATE, ICSA, CCSA, DGORDER, INDPRO, GDPC1 (real GDP), CP (corporate profits). ✅

## Calendars (catalyst page, `pipeline/calendar/`)
| Item | Source | |
|---|---|---|
| US data releases (CPI, jobs, GDP, PCE, PPI, retail sales, IP, durable goods, housing, UMich, claims) | FRED `release/dates?release_id=<id>&include_release_dates_with_no_data=true` (ids 10, 50, 53, 54, 46, 9, 13, 95, 27, 91, 180); FRED lists the scheduled dates to year end | ✅ verified 2026-10-22 |
| BLS schedule (`bls.gov/schedule/news_release/bls.ics`) | blocks automated requests ("Access Denied"); not used, FRED has the same dates | ❌ |
| FOMC | `federalreserve.gov/monetarypolicy/fomccalendars.htm` (HTML; current and next year) | ✅ verified 2026-10-22 |
| ECB | `ecb.europa.eu/press/calendars/mgcgc/html/index.en.html` (HTML; ~2 years ahead) | ✅ verified 2026-10-22 |
| Bank of Japan | `boj.or.jp/en/mopo/mpmsche_minu/index.htm` (HTML; current and next year) | ✅ verified 2026-10-22 |
| Bank of England | `bankofengland.co.uk/monetary-policy/upcoming-mpc-dates` (HTML; blocks the default `python-requests` user agent) | ✅ verified 2026-10-22 |
| ISM, NFIB, NBS, RatingDog | release rules in `pipeline/manual/releases.py` (approximate) | ✅ |

## Micro (Phase 2+)
| Item | Source | |
|---|---|---|
| Universe + sector | Yahoo equity screener via `yfinance.screen` (`EquityQuery`: region us, sector, exchange NYQ/NMS/NGM/NCM/ASE, intradaymarketcap > $2bn), 250 per page | ✅ verified 2026-10-22 (2,101 stocks; sector sums match the unfiltered total) |
| Forward EPS & revenue estimates (current/next FY), # analysts, EPS trend/revisions, industry, country, next earnings date | Yahoo `quoteSummary` (`earningsTrend,assetProfile,calendarEvents,price`) via `yfinance`'s session, one request per stock (~0.15 s) | ✅ verified 2026-10-22 (2,033 stocks, 0 failures) |
| Analyst price targets, ratings | `yfinance` (`analyst_price_targets`, `recommendations`) | ✅ (unofficial; Phase 3) |
| Next earnings date | `yfinance` calendar / earnings dates | ✅ |
| Historical statements (income, balance sheet, cash flow), shares outstanding | SEC EDGAR XBRL `data.sec.gov/api/xbrl/companyfacts/CIK##########.json` (needs `User-Agent` with email) | ✅ |
| Insider transactions & holders | `yfinance` insider/institutional tables; SEC Form 4 🔎 | ✅/🔎 |
| Prices (realised vol, ATR, beta, correlation) | `yfinance` daily OHLC | ✅ |
| Implied volatility | `yfinance` option chains (compute ATM IV) | ✅ |
| Short interest | `yfinance` info fields 🔎 | 🔎 |

Rules for every fetcher: retries with backoff, polite rate limits, cache raw responses, keep last good copy,
write status into `site/data/health.json`.
