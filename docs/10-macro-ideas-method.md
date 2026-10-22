# Macro ideas and international listings: method and implementation notes

Lessons 34–35 (see `docs/01-course-map.md`, "Macro-driven ideas and ADRs"). Page: `themes.html` ("Macro ideas");
data: `site/data/themes.json` from `pipeline/themes/build.py` and `pipeline/themes/map.yaml`. Context only: nothing
here feeds the portfolio bias. Numbers that are our choice are in `config.THEMES` *(tune)*.

## Macro → industries
- **Signals** (`map.yaml`, `signals`): each Macro Desk signal reaches a list of Yahoo industries with a sign. Effect =
  sign × the signal's score. The scores are those of `docs/02` (commodities: +1 = price rising; dollar: +1 = weaker
  dollar; rates and credit: +1 = supportive for equities), so for example:
  - Brent → oil producers and services (+), airlines and trucking (−, fuel costs);
  - copper, iron ore, lumber → their miners and producers; China (RatingDog PMI) → industrial metals, luxury goods;
  - building permits → builders, building products and materials, home-improvement retail, mortgage finance (the
    course's housing → XHB idea);
  - UMich sentiment → consumer-discretionary industries;
  - yield curve → banks; real rates → REITs, regulated utilities, homebuilders; credit spreads → lenders;
  - dollar → gold, silver and other precious metals.
  Every link is our reading of how the driver reaches earnings, listed on the page with its reason.
- **ISM industry lists** (`map.yaml`, `ism`): the 18 manufacturing and 18 services industries of the ISM Report On
  Business, from `data/manual/ism_industries.csv`, each mapped to Yahoo industries. Listed as growing = +1,
  contracting = −1, not listed = 0. Names are matched without case or punctuation ("and" = "&"); unknown names are
  shown so the CSV can be corrected. A list older than the latest headline ISM report in `ism_manufacturing.csv` /
  `ism_services.csv` is "awaiting data" and not used (manual data is never used stale). The page shows how many
  months each industry has kept its status.
- **Net** per industry = sum of the available effects. ≥ +1 tailwind, ≤ −1 headwind; ≥ ±2 "strong" (at least two
  drivers agree) *(tune)*. A signal awaiting data adds nothing.

## Macro-driven ideas
The screener's types (`docs/07`) inside the winds: positive outliers and turnarounds in tailwind industries (long
side); negative outliers, post-growth stocks and value traps in headwind industries (short side). Sorted by the
size of the net effect, then the clearest types, then market cap. The macro bias is shown next to them. Every idea
links to its trade-idea template page.

## International listings (ADRs)
- Universe: the screener's stocks headquartered outside the US (Yahoo profile country), grouped into regions
  (`map.yaml`, `regions`); second share classes and stocks without estimates are left out.
- **Currency rules:** EPS growth (EPS1/EPS0, EPS2/EPS1) is a ratio in one currency and is compared across countries.
  When the estimates are in another currency than the US share price (most ADRs), the P/E is not comparable and is
  left blank, and so is sales growth (Yahoo mixes currencies in these sales estimates, seen on Japanese ADRs in
  October 2026). Growth beyond ±300% is left out as a data or currency problem *(tune)*.
- **Leaders / laggards:** EPS growth in the top quarter of these listings in both years (both positive) / falling in
  both years and in the bottom quarter *(tune)*.
- Region medians: EPS growth, sales growth, 90-day EPS revision and 3-month return.

## China check (lesson 14)
Official Chinese data is unreliable; Chinese companies listed in the US report under US rules. The check compares
the official NBS manufacturing PMI's message (≥ 50 = expansion) with the direction of analysts' 90-day revisions to
Chinese listings' current-year EPS (median, at least **5** stocks *(tune)*): official expansion with cuts = "trust the
companies"; official contraction with upgrades = "the companies look better than the data"; else they agree. The
RatingDog − NBS gap and the "potential lie" months come from the Macro Desk's China signal.
