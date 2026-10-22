// Evidence page: forward index returns after each point-in-time bias reading, with sample sizes.

import { chartSet, rangeButtons, redraw, redrawOnResize, renderPanels } from "./charts.js";
import { el, loadJSON } from "./common.js";

const state = { ev: null, asset: "sp500", period: "all", horizon: "3m" };
const charts = chartSet(null);
const HORIZON = { "1m": "1 month", "3m": "3 months", "6m": "6 months" };

const pct = (v, digits = 1) =>
  v === null || v === undefined ? "–" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(digits)}%`;
const tone = (v) => (!v ? "" : v > 0 ? "up" : "down");
const cell = (v, fmt = pct) => el("td", { class: tone(v), text: fmt(v) });

function seg(label, options, key) {
  return el(
    "div",
    { class: "seg", role: "group", "aria-label": label },
    options.map(([id, text]) =>
      el("button", {
        type: "button",
        "aria-pressed": String(state[key] === id),
        text,
        onclick: () => {
          state[key] = id;
          renderTables();
        },
      }),
    ),
  );
}

function honesty() {
  const e = state.ev;
  return el(
    "section",
    { class: "card panel" },
    el("h2", { class: "panel-title", text: "How to read this page" }),
    el(
      "ul",
      { class: "plain-list" },
      el(
        "li",
        {},
        `${e.months} month-ends (${e.first_month} to ${e.last_month}), each recomputed with only the data published by that day.`,
      ),
      el(
        "li",
        {},
        `${e.revised_months} of them needed revised data for at least one input (no real-time vintage exists that far back). "Real-time inputs only" leaves them out.`,
      ),
      el(
        "li",
        {},
        "The rules come from the lessons (docs/02) and were not fitted to these results. A rule that looks bad here stays as it is: changing it to fit this sample would make the next sample look worse.",
      ),
      el(
        "li",
        {},
        "Windows overlap: a 6-month return starts every month, so neighbouring months share most of their path. “Independent” is roughly how many non-overlapping windows the sample holds.",
      ),
      el(
        "li",
        {},
        "The bias is meant to set the net exposure of a book of stock ideas, not to time an index. These numbers test only one part of the process.",
      ),
      e.live_log_start
        ? el(
            "li",
            {},
            `The live record starts on ${e.live_log_start}: `,
            el("a", { href: "data/macro/log.csv", text: "daily log (CSV)" }),
            ", one row per day with what the system said.",
          )
        : null,
    ),
  );
}

function stateTable(asset) {
  const rows = asset.by_state[state.period][state.horizon];
  const line = (label, s, strong) =>
    el(
      "tr",
      {},
      el("td", {}, strong ? el("b", { text: label }) : label),
      ...(s.n
        ? [
            cell(s.mean),
            cell(s.median),
            el("td", { text: `${s.pct_up.toFixed(0)}%` }),
            cell(s.worst),
            cell(s.best),
            el("td", { text: `${s.n}` }),
            el("td", { text: `~${s.n_independent}` }),
          ]
        : [el("td", { colspan: 7, class: "text", text: "No months in this sample." })]),
    );
  return el(
    "div",
    { class: "scroll-x" },
    el(
      "table",
      { class: "data" },
      el(
        "thead",
        {},
        el(
          "tr",
          {},
          ["After a reading of", "Mean", "Median", "Up", "Worst", "Best", "Months", "Independent"].map((h) =>
            el("th", { text: h }),
          ),
        ),
      ),
      el(
        "tbody",
        {},
        line("Any (all months)", rows.all, true),
        ...state.ev.states.map((s) => line(s.label, rows[s.id])),
      ),
    ),
  );
}

function headline(asset) {
  const r = asset.by_state[state.period][state.horizon];
  const L = r.net_long;
  const S = r.net_short;
  if (!L.n || !S.n) return "Not enough net long and net short months in this sample to compare.";
  const better = L.mean > S.mean;
  return (
    `${asset.name}, next ${HORIZON[state.horizon]}: after net long readings ${pct(L.mean)} on average ` +
    `(${L.n} months, up ${L.pct_up.toFixed(0)}% of the time); after net short readings ${pct(S.mean)} ` +
    `(${S.n} months). ` +
    (better
      ? "Net long readings were followed by better returns than net short ones, as the bias intends."
      : "Net short readings were followed by better returns than net long ones: in this sample the bias was early or wrong-footed at turning points (markets often bottom while the data is still weak).")
  );
}

function signalTable() {
  const rows = state.ev.signals.map((s) => {
    const part = (x) =>
      x.n
        ? el(
            "td",
            { class: tone(x.mean) },
            pct(x.mean),
            el("span", { class: "sub", text: `${x.n} months${x.n < 24 ? " · small sample" : ""}` }),
          )
        : el("td", { text: "–" });
    return el(
      "tr",
      {},
      el(
        "td",
        {},
        el("a", { href: `indicator.html?id=${encodeURIComponent(s.id)}`, text: s.name }),
        el("span", { class: "sub", text: s.first_month ? `from ${s.first_month}` : "no history yet" }),
      ),
      part(s.plus),
      part(s.zero),
      part(s.minus),
      cell(s.spread, (v) =>
        v === null || v === undefined ? "–" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}pp`,
      ),
    );
  });
  return el(
    "section",
    { class: "card panel", style: "margin-top:12px" },
    el("h2", { class: "panel-title", text: "Each indicator on its own: S&P 500 over the next 3 months" }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text: "Mean 3-month return after each score, with the number of months. Spread = after +1 minus after −1; a positive spread means the indicator pointed the right way on average. Manual-data indicators (ISM, NFIB, China) have only the months you have entered.",
    }),
    el(
      "div",
      { class: "scroll-x" },
      el(
        "table",
        { class: "data" },
        el(
          "thead",
          {},
          el(
            "tr",
            {},
            ["Indicator", "After +1", "After 0", "After −1", "Spread"].map((h) => el("th", { text: h })),
          ),
        ),
        el("tbody", {}, rows),
      ),
    ),
  );
}

function exposure() {
  const x = state.ev.exposure;
  if (!x) return null;
  const row = (label, s) =>
    el(
      "tr",
      {},
      el("td", { text: label }),
      cell(s.cagr),
      el("td", { text: `${s.vol.toFixed(1)}%` }),
      cell(s.max_drawdown),
    );
  return el(
    "section",
    { class: "card panel", style: "margin-top:12px" },
    el("h2", { class: "panel-title", text: "Illustration: the S&P 500 held with the bias's exposure" }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text: `+1 after a net long reading, 0 after neutral, −1 after net short, rebalanced at each month-end over ${x.months} months; no costs, no dividends. The real use of the bias is the net exposure of a book of stock ideas.`,
    }),
    el(
      "div",
      { class: "scroll-x" },
      el(
        "table",
        { class: "data" },
        el(
          "thead",
          {},
          el(
            "tr",
            {},
            ["", "Annual return", "Volatility", "Worst drawdown"].map((h) => el("th", { text: h })),
          ),
        ),
        el("tbody", {}, row("Buy and hold", x.buy_and_hold), row("Exposure set by the bias", x.bias_scaled)),
      ),
    ),
  );
}

function renderTables() {
  const asset = state.ev.assets.find((a) => a.id === state.asset) || state.ev.assets[0];
  document.getElementById("tables").replaceChildren(
    el(
      "div",
      { class: "toolbar" },
      el(
        "label",
        {},
        "Market ",
        el(
          "select",
          {
            class: "select",
            onchange: (ev) => {
              state.asset = ev.target.value;
              renderTables();
            },
          },
          state.ev.assets.map((a) =>
            el("option", { value: a.id, text: `${a.name} (from ${a.first.slice(0, 4)})`, selected: a.id === asset.id }),
          ),
        ),
      ),
      seg("Horizon", Object.entries(HORIZON), "horizon"),
      seg(
        "Sample",
        state.ev.periods.map((p) => [p.id, p.label]),
        "period",
      ),
    ),
    el("p", { class: "reading", text: headline(asset) }),
    stateTable(asset),
  );
}

async function main() {
  try {
    state.ev = await loadJSON("data/macro/evidence.json");
  } catch {
    document
      .getElementById("content")
      .replaceChildren(
        el("div", { class: "card notice", text: "No evidence data yet: it is built by the daily update." }),
      );
    return;
  }
  document
    .getElementById("content")
    .replaceChildren(
      honesty(),
      el(
        "section",
        { class: "card panel", style: "margin-top:12px" },
        el("h2", { class: "panel-title", text: "Forward returns after each bias reading" }),
        el("div", { id: "tables" }),
      ),
      exposure(),
      el("div", { style: "margin-top:24px" }),
      rangeButtons(charts),
      ...renderPanels(charts, state.ev.panels),
      signalTable(),
    );
  renderTables();
  redraw(charts);
  redrawOnResize(charts);
}

main();
