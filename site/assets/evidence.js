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

function priceAlert() {
  const a = state.ev.price_alert;
  if (!a) return null;
  const val = (s) =>
    s.n
      ? el("td", { class: tone(s.mean) }, pct(s.mean), el("span", { class: "sub", text: `up ${s.pct_up.toFixed(0)}%` }))
      : el("td", { text: "–" });
  return el(
    "section",
    { class: "card panel", style: "margin-top:12px" },
    el("h2", { class: "panel-title", text: "The data-vs-prices alert" }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text:
        "Shown on the Macro Desk when the bias and the S&P 500's own trend point opposite ways (it never changes the " +
        `score). It would have fired in ${a.fired} of ${state.ev.months} month-ends. ${a.note}`,
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
            ["S&P 500 after", "Months", "1 month", "3 months", "6 months"].map((h) => el("th", { text: h })),
          ),
        ),
        el(
          "tbody",
          {},
          a.rows.map((r) =>
            el(
              "tr",
              {},
              el("td", {}, r.alert ? el("b", { text: r.label }) : r.label),
              el("td", { text: `${r["3m"].n || 0}` }),
              val(r["1m"]),
              val(r["3m"]),
              val(r["6m"]),
            ),
          ),
        ),
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

// Forward test of the Screener's types (pipeline/forward/outliers.py): a live record that only grows.
const TYPE_LABEL = {
  positive: ["Positive outlier", "long side: higher is better"],
  negative: ["Negative outlier", "short side: lower is better"],
  post_growth: ["Post-growth", "short side: lower is better"],
  turnaround: ["Turnaround", "either side"],
  value_trap: ["Value trap", "either side"],
};

function forwardCard(fw) {
  const box = el("section", { class: "card panel", style: "margin-top:12px", id: "forward" });
  const pct = (v) =>
    v === null || v === undefined ? "–" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}%`;
  const head = [
    el("h2", { class: "panel-title", text: "Forward test: the Screener's types (live record)" }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text: "Analysts' past estimates are not available for free, so the outlier types cannot be backtested honestly. Instead, once a week every stock of a candidate type is written down with its price, and its return over the next 20, 40 and 60 trading days is filled in as the days pass: against SPY and against its sector ETF. The long-short spread is positive outliers minus negative outliers within each weekly cohort. Weekly cohorts overlap, so the t-statistic uses the number of independent windows; |t| above about 2 starts to mean something. Rules are never tuned to this record.",
    }),
  ];
  if (!fw) {
    box.append(...head, el("p", { class: "muted", text: "The record starts with the next daily update." }));
    return box;
  }
  const state = { h: "20", vol: false };
  const body = el("div");
  const draw = () => {
    const s = (state.vol ? fw.vol_only : fw.all).horizons[state.h];
    const sp = s.spread;
    const rows = Object.entries(TYPE_LABEL).map(([k, [label, note]]) => {
      const t = s.types[k];
      return el(
        "tr",
        {},
        el("td", {}, el("b", { text: label }), el("span", { class: "sub", text: note })),
        el("td", { text: t.return.n }),
        el("td", { text: t.cohorts }),
        el("td", { text: pct(t.return.mean) }),
        el("td", { text: pct(t.vs_spy.mean) }),
        el("td", { text: t.vs_spy.pct_pos === null ? "–" : `${t.vs_spy.pct_pos.toFixed(0)}%` }),
        el("td", { text: pct(t.vs_sector.mean) }),
      );
    });
    const spreadText = (x) =>
      x && x.n_cohorts
        ? `${pct(x.mean)} on average across ${x.n_cohorts} cohort${x.n_cohorts > 1 ? "s" : ""} (${x.n_independent} independent window${x.n_independent === 1 ? "" : "s"}), positive in ${x.pct_pos}% of cohorts${x.t === null ? "; too few for a t-statistic" : `, t = ${x.t}`}.`
        : "no cohort has reached this horizon yet.";
    const rv = s.revisions;
    const revRow = (k, label, note) => {
      const t = rv && rv[k];
      if (!t) return null;
      return el(
        "tr",
        {},
        el("td", {}, el("b", { text: label }), el("span", { class: "sub", text: note })),
        el("td", { text: t.return.n }),
        el("td", { text: t.cohorts }),
        el("td", { text: pct(t.return.mean) }),
        el("td", { text: pct(t.vs_spy.mean) }),
        el("td", { text: t.vs_spy.pct_pos === null ? "–" : `${t.vs_spy.pct_pos.toFixed(0)}%` }),
        el("td", { text: pct(t.vs_sector.mean) }),
      );
    };
    const head7 = () =>
      el(
        "thead",
        {},
        el(
          "tr",
          {},
          ["Group", "Stocks", "Cohorts", "Return", "vs S&P 500", "Beat S&P 500", "vs sector ETF"].map((h) =>
            el("th", { text: h }),
          ),
        ),
      );
    const revisionPart = rv
      ? [
          el("h3", { class: "sub-title", text: "Pre-registered test: estimate revisions vs forecast growth" }),
          el("p", {
            class: "section-note",
            text: "Fixed on 22 Oct 2026, before the first cohort. Research finds that rising analysts' estimates tend to be followed by better returns, while the highest forecast growth is often already in the price. Each week the top and bottom quarter of every sector's 90-day EPS revisions are recorded too. H1: rising beats falling. H2: positive outliers whose estimates are rising beat the other positive outliers. Compare H1 with the types' spread above.",
          }),
          el(
            "p",
            { class: "reading" },
            el("b", { text: `H1, rising minus falling estimates (${state.h} days): ` }),
            spreadText(s.rev_spread),
          ),
          el(
            "p",
            { class: "reading" },
            el("b", { text: `H2, positive outliers with rising estimates minus the others: ` }),
            spreadText(s.positive_rev_spread),
          ),
          el(
            "div",
            { class: "scroll-x" },
            el(
              "table",
              { class: "data" },
              head7(),
              el(
                "tbody",
                {},
                revRow("up", "Estimates rising", "top quarter of the sector's 90-day EPS1 revisions"),
                revRow("down", "Estimates falling", "bottom quarter"),
              ),
            ),
          ),
        ]
      : [];
    body.replaceChildren(
      el("p", { class: "reading" }, el("b", { text: `Long-short spread over ${state.h} days: ` }), spreadText(sp)),
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
              ["Type", "Stocks", "Cohorts", "Return", "vs S&P 500", "Beat S&P 500", "vs sector ETF"].map((h) =>
                el("th", { text: h }),
              ),
            ),
          ),
          el("tbody", {}, rows),
        ),
      ),
      ...revisionPart,
    );
  };
  const segBtns = (opts, key) =>
    el(
      "div",
      { class: "seg", role: "group" },
      opts.map(([v, label]) =>
        el("button", {
          type: "button",
          "aria-pressed": String(state[key] === v),
          text: label,
          onclick: (ev) => {
            state[key] = v;
            for (const b of ev.target.parentNode.children) b.setAttribute("aria-pressed", String(b === ev.target));
            draw();
          },
        }),
      ),
    );
  box.append(
    ...head,
    el(
      "p",
      { class: "facts" },
      el("span", {}, "Started ", el("b", { text: fw.first_cohort || "–" })),
      el("span", {}, "Latest cohort ", el("b", { text: fw.last_cohort || "–" })),
      el("span", {}, "Cohorts ", el("b", { text: String(fw.all.cohorts) })),
      el("span", {}, "Stocks recorded ", el("b", { text: String(fw.all.rows) })),
    ),
    el(
      "div",
      { class: "toolbar" },
      segBtns(
        fw.horizons.map((h) => [String(h), `${h} days`]),
        "h",
      ),
      segBtns(
        [
          [false, "All stocks"],
          [true, "Volatility filter passed"],
        ],
        "vol",
      ),
    ),
    body,
    el(
      "p",
      { class: "section-note" },
      "The full record: ",
      el("a", { href: "data/forward/outliers.csv", text: "outliers.csv" }),
      ". Costs and borrow fees are not included.",
    ),
  );
  draw();
  return box;
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
      priceAlert(),
      el("div", { style: "margin-top:24px" }),
      rangeButtons(charts),
      ...renderPanels(charts, state.ev.panels),
      signalTable(),
      forwardCard(await loadJSON("data/forward/summary.json").catch(() => null)),
    );
  renderTables();
  redraw(charts);
  redrawOnResize(charts);
}

main();
