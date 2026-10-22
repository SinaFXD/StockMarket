// Global page: money markets by country (the US template applied abroad) and regional equity dispersion.

import { chartSet, rangeButtons, redraw, redrawOnResize, renderPanels } from "./charts.js";
import { el, loadJSON, scorePill } from "./common.js";

const charts = chartSet(5);

const num = (v, digits = 2) =>
  v === null || v === undefined
    ? "–"
    : v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const signed = (v, digits = 2) =>
  v === null || v === undefined ? "–" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${num(Math.abs(v), digits)}`;
const score = (x) => (x > 0 ? "+1" : x < 0 ? "−1" : "0");
const ord = (p) => {
  if (p === null || p === undefined) return "–";
  const n = Math.round(p);
  const suffix = n % 100 >= 10 && n % 100 <= 20 ? "th" : { 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th";
  return `${n}${suffix}`;
};
const tone = (v) => (!v ? "" : v > 0 ? "up" : "down");
const pct = (v) => el("td", { class: tone(v), text: v === null || v === undefined ? "–" : `${signed(v, 1)}%` });
const head = (cols) =>
  el(
    "thead",
    {},
    el(
      "tr",
      {},
      cols.map((h) => el("th", { text: h })),
    ),
  );
const table = (cols, rows) =>
  el("div", { class: "scroll-x" }, el("table", { class: "data" }, head(cols), el("tbody", {}, rows)));

function card(title, note, ...body) {
  return el(
    "section",
    { class: "card panel", style: "margin-top:12px" },
    el("h2", { class: "panel-title", text: title }),
    note ? el("p", { class: "section-note", style: "margin-top:0", text: note }) : null,
    ...body,
  );
}

function scoreCell(c) {
  if (c.code === "US") return el("td", {}, el("a", { href: "macro.html", text: "US block" }));
  if (!c.scored) return el("td", { class: "muted", text: "not scored" });
  return el("td", {}, scorePill(c.score));
}

function countryRow(c) {
  const name = el("td", {}, el("b", { text: c.name }), c.as_of ? el("span", { class: "sub", text: c.as_of }) : null);
  if (c.status !== "ok")
    return el("tr", {}, name, el("td", { colspan: 7, class: "text", text: `Awaiting data: ${c.why}` }));
  const cv = c.curve;
  const rr = c.real;
  const reading =
    c.code === "US"
      ? "Scored on the Macro Desk (10y-2y curve and real rate)."
      : `Curve ${cv.state.toLowerCase()} (${score(cv.score)}); real rate ${rr.state.toLowerCase()} (${score(rr.score)}).`;
  return el(
    "tr",
    {},
    name,
    el("td", { text: `${num(c.yield_10y)}%` }),
    el("td", {}, `${num(c.short_rate)}%`, el("span", { class: "sub", text: c.short_label })),
    el(
      "td",
      { class: cv.value < 0 ? "down" : "" },
      `${signed(cv.value)}pp`,
      el("span", { class: "sub", text: `${signed(cv.change_3m)} in 3m, ${cv.direction}` }),
    ),
    el("td", {}, `${num(c.cpi_yoy, 1)}%`, el("span", { class: "sub", text: c.cpi_month })),
    el("td", {}, `${signed(rr.value)}%`, el("span", { class: "sub", text: `${ord(rr.percentile)} pct, 10y` })),
    scoreCell(c),
    el("td", { class: "text", text: reading }),
  );
}

function moneyMarkets(countries) {
  return card(
    "Money markets by country",
    "Curve = 10y yield − short rate; real rate = 10y yield − latest CPI YoY, ranked against the country's last 10 years. " +
      "Monthly averages from the OECD (the US row uses daily Treasury yields). Japan, the UK, Germany and Italy make up " +
      "the international money-markets signal; China is context only (its bonds are mostly held at home).",
    table(
      ["Country", "10y yield", "Short rate", "Curve", "CPI YoY", "Real 10y", "Score", "Reading"],
      countries.map(countryRow),
    ),
    el(
      "p",
      { class: "muted", style: "margin:10px 0 0;font-size:13px" },
      el("a", { href: "indicator.html?id=intl_money_markets", text: "Signal page: charts, rule and reading guide →" }),
    ),
  );
}

function regionName(r, label) {
  return el("td", {}, el("b", { text: r.name }), el("span", { class: "sub", text: label }));
}

function equities(d) {
  const awaiting = (n) => [el("td", { colspan: n, class: "text", text: "Awaiting data" })];
  const local = d.regions.map((r) =>
    el(
      "tr",
      {},
      regionName(r, r.local_label),
      ...(r.local
        ? ["r1m", "r3m", "r6m", "r12m", "ytd", "vs_ma200", "from_high"].map((k) => pct(r.local[k]))
        : awaiting(7)),
    ),
  );
  const usd = d.regions.map((r) =>
    el(
      "tr",
      {},
      regionName(r, r.usd_label),
      ...(r.usd
        ? [pct(r.usd.r3m), pct(r.usd.r12m), pct(r.vs_us ? r.vs_us["3m"] : null), pct(r.vs_us ? r.vs_us["12m"] : null)]
        : awaiting(4)),
    ),
  );
  return card(
    "Regional equity dispersion",
    "Is a move global or local? Context for reading the regions' own indicators, not part of the bias. " +
      "Local indices are in their own currency; the ETFs are in US dollars so the regions compare like for like. " +
      "Price returns.",
    el("p", { class: "reading", text: d.dispersion.reading }),
    el("p", { class: "reading muted", text: d.dispersion_12m.reading }),
    el("h3", { text: "Local indices" }),
    table(["Region", "1m", "3m", "6m", "12m", "YTD", "vs 200-day avg", "From 12m high"], local),
    el("h3", { text: "In US dollars (ETFs)" }),
    table(["Region", "3m", "12m", "vs US, 3m", "vs US, 12m"], usd),
  );
}

async function main() {
  const content = document.getElementById("content");
  let d;
  try {
    d = await loadJSON("data/macro/global.json");
  } catch {
    content.replaceChildren(
      el("div", { class: "card notice", text: "No Global data yet: it is built by the daily update." }),
    );
    return;
  }
  content.replaceChildren(
    moneyMarkets(d.countries),
    equities(d),
    rangeButtons(charts),
    ...renderPanels(charts, d.panels),
    el("p", {
      class: "muted",
      style: "font-size:13px",
      text: `Built ${d.as_of}. Rebased charts start at 100 on the first day of the selected range.`,
    }),
  );
  redraw(charts);
  redrawOnResize(charts);
}

main();
