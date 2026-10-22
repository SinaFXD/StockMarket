// Sector Screener: the 11 numbers per stock, sector averages and data checks (lessons 22-29).

import { el, loadJSON } from "./common.js";

const state = {
  data: null,
  rows: [],
  sector: "Technology",
  industry: "",
  query: "",
  minCap: 2e9,
  hideExcluded: false,
  cls: "all",
  volOnly: false,
  columns: "forward",
  sort: { key: "mcap", dir: -1 },
  limit: 150,
};
const STATS = ["pe1", "pe2", "eg1", "eg2", "peg1", "peg2", "mcap"];
const CAPS = [
  [2e9, "$2bn+"],
  [10e9, "$10bn+"],
  [50e9, "$50bn+"],
  [200e9, "$200bn+"],
];

const fmt = {
  price: (v) => v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  mcap: (v) => `${(v / 1e9).toLocaleString("en-US", { maximumFractionDigits: v >= 1e11 ? 0 : 1 })}`,
  eps: (v) => v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  pct: (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}%`,
  pe: (v) => v.toFixed(1),
  peg: (v) => v.toFixed(2),
};
// key, header, formatter, tone by sign, title
const COLS = [
  ["price", "Price", fmt.price, false, "Last price"],
  ["mcap", "Mkt cap $bn", fmt.mcap, false, "Market capitalisation, $ billions"],
  ["eps0", "EPS0", fmt.eps, false, "EPS of the last reported fiscal year"],
  ["eps1", "EPS1", fmt.eps, false, "Consensus EPS, current fiscal year"],
  ["eps2", "EPS2", fmt.eps, false, "Consensus EPS, next fiscal year"],
  ["eg1", "EG1", fmt.pct, true, "EPS growth EPS0 → EPS1"],
  ["eg2", "EG2", fmt.pct, true, "EPS growth EPS1 → EPS2"],
  ["pe1", "PE1", fmt.pe, false, "Price / EPS1 (only when EPS1 > 0)"],
  ["pe2", "PE2", fmt.pe, false, "Price / EPS2 (only when EPS2 > 0)"],
  ["peg1", "PEG1", fmt.peg, false, "PE1 / EG1 (only with positive growth)"],
  ["peg2", "PEG2", fmt.peg, false, "PE2 / EG2 (only with positive growth)"],
  ["rg1", "Sales g1", fmt.pct, true, "Revenue growth, current fiscal year (consensus)"],
  ["eps1_rev90", "EPS1 rev. 90d", fmt.pct, true, "Change in the EPS1 consensus over the last 90 days"],
  ["pe_prem", "P/E vs sector", fmt.pct, false, "PE1 against the sector median PE1 (premium = money likes it)"],
  ["rv", "Realised vol", (v) => `${v.toFixed(0)}%`, false, "Annualised volatility of daily returns, last ~3 months"],
  ["iv", "Implied vol", (v) => `${v.toFixed(0)}%`, false, "At-the-money options, expiry closest to 45 days"],
  ["volx", "Vol ÷ VIX", (v) => `${v.toFixed(1)}×`, false, "Lower of realised and implied volatility divided by VIX"],
];
// Category tag tone: long candidates blue, short candidates red
const SIDE_TONE = { long: "tag-pos", short: "tag-neg" };

function excluded(r) {
  return r.flags.some((f) => state.data.checks[f] && state.data.checks[f].excluded);
}

// Stocks in the chosen sector / industry / size / search, before the category filter.
function base() {
  const q = state.query.trim().toLowerCase();
  return state.rows.filter(
    (r) =>
      (state.sector === "All" || r.sector === state.sector) &&
      (!state.industry || r.industry === state.industry) &&
      (r.mcap || 0) >= state.minCap &&
      (!state.hideExcluded || !excluded(r)) &&
      (!q || r.t.toLowerCase().includes(q) || (r.name || "").toLowerCase().includes(q)),
  );
}

function view(rows) {
  return rows.filter((r) => (state.cls === "all" || r.cls === state.cls) && (!state.volOnly || r.vol_ok === true));
}

function typeTag(r) {
  const c = state.data.categories && state.data.categories[r.cls];
  if (!c) return null;
  return el("span", { class: `tag ${SIDE_TONE[c.side] || ""}`, title: c.text, text: c.label });
}

function categoryBar(rows) {
  const cats = state.data.categories || {};
  const order = ["all", "positive", "negative", "post_growth", "turnaround", "value_trap", "boring", "mixed", "loss"];
  return el(
    "div",
    { class: "toolbar" },
    el(
      "div",
      { class: "seg wrap-seg", role: "group", "aria-label": "Stock type" },
      order
        .filter((k) => k === "all" || cats[k])
        .map((k) => {
          const n = k === "all" ? rows.length : rows.filter((r) => r.cls === k).length;
          return el("button", {
            type: "button",
            "aria-pressed": String(state.cls === k),
            title: k === "all" ? "" : cats[k].text,
            text: `${k === "all" ? "All types" : cats[k].label} ${n}`,
            onclick: () => {
              state.cls = k;
              state.limit = 150;
              renderTable();
            },
          });
        }),
    ),
    el(
      "label",
      { class: "check" },
      el("input", {
        type: "checkbox",
        checked: state.volOnly,
        onchange: (ev) => {
          state.volOnly = ev.target.checked;
          renderTable();
        },
      }),
      ` Volatility ≥ ${state.data.params.vol_vs_vix}× VIX only${state.data.vix ? ` (VIX ${state.data.vix.toFixed(1)})` : ""}`,
    ),
  );
}

// Same rule as pipeline/screener/numbers.py group_stats: averages over stocks without an excluding check.
function stats(rows) {
  const use = rows.filter((r) => !excluded(r));
  const out = { n: rows.length, used: use.length };
  for (const m of STATS) {
    const v = use
      .map((r) => r[m])
      .filter((x) => x !== null && x !== undefined)
      .sort((a, b) => a - b);
    const mid = Math.floor(v.length / 2);
    out[m] = {
      n: v.length,
      mean: v.length ? v.reduce((a, b) => a + b, 0) / v.length : null,
      median: v.length ? (v.length % 2 ? v[mid] : (v[mid - 1] + v[mid]) / 2) : null,
    };
  }
  return out;
}

// Evidence columns (lesson 29) from the SEC accounts: formats from each metric's unit.
function evidenceCols() {
  const metrics = (state.data.evidence && state.data.evidence.metrics) || {};
  return [
    ["acc_fy", "FY end", (v) => v.slice(0, 7), false, "End of the latest fiscal year in the SEC filings"],
    ...Object.entries(metrics).map(([k, m]) => [
      k,
      m.label,
      m.unit === "%" ? fmt.pct : (v) => `${v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}×`,
      ["rev_growth", "fcf_margin", "fcf_yield", "roe", "roa", "net_margin", "op_margin", "pretax_margin"].includes(k),
      m.text,
    ]),
  ];
}

function cols() {
  return state.columns === "evidence" ? evidenceCols() : COLS;
}

function evidenceMedians(rows) {
  const use = rows.filter((r) => !excluded(r));
  const out = {};
  for (const [k] of evidenceCols().slice(1)) {
    const v = use
      .map((r) => r[k])
      .filter((x) => x !== null && x !== undefined)
      .sort((a, b) => a - b);
    const mid = Math.floor(v.length / 2);
    out[k] = v.length ? (v.length % 2 ? v[mid] : (v[mid - 1] + v[mid]) / 2) : null;
  }
  return out;
}

function evidenceCard(rows) {
  const med = evidenceMedians(rows);
  const label = state.industry || (state.sector === "All" ? "All sectors" : state.sector);
  const c = evidenceCols().slice(1);
  const withAcc = rows.filter((r) => r.acc_fy).length;
  return el(
    "section",
    { class: "card panel" },
    el("h2", { class: "panel-title", text: `${label}: Evidence medians (latest annual accounts)` }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text:
        `${withAcc} of ${rows.length} stocks have SEC accounts (foreign filers reporting under IFRS have none). ` +
        "Evidence is backward-looking: it explains why money likes or dislikes a stock, it does not forecast (lesson 29).",
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
            el("th", { text: "" }),
            c.map(([, label, , , title]) => el("th", { title, text: label })),
          ),
        ),
        el(
          "tbody",
          {},
          el(
            "tr",
            {},
            el("td", {}, el("b", { text: "Median" })),
            c.map(([k, , f]) => el("td", { text: med[k] === null ? "–" : f(med[k]) })),
          ),
        ),
      ),
    ),
  );
}

function averagesCard(rows) {
  const s = stats(rows);
  const label = state.industry || (state.sector === "All" ? "All sectors" : state.sector);
  const cell = (m, f, kind) => {
    const v = s[m][kind];
    return el("td", { text: v === null ? "–" : f(v) });
  };
  const line = (kind) =>
    el(
      "tr",
      {},
      el("td", {}, el("b", { text: kind === "mean" ? "Average" : "Median" })),
      cell("mcap", fmt.mcap, kind),
      cell("eg1", fmt.pct, kind),
      cell("eg2", fmt.pct, kind),
      cell("pe1", fmt.pe, kind),
      cell("pe2", fmt.pe, kind),
      cell("peg1", fmt.peg, kind),
      cell("peg2", fmt.peg, kind),
    );
  return el(
    "section",
    { class: "card panel" },
    el("h2", { class: "panel-title", text: `${label}: averages` }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text:
        `${s.used} of ${s.n} stocks count toward the averages (the others carry a data check that makes their ` +
        "numbers unreliable). A P/E is averaged only where EPS > 0 and a PEG only where growth is positive.",
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
            ["", "Mkt cap $bn", "EG1", "EG2", "PE1", "PE2", "PEG1", "PEG2"].map((h) => el("th", { text: h })),
          ),
        ),
        el("tbody", {}, line("mean"), line("median")),
      ),
    ),
  );
}

function flagTags(r) {
  return r.flags.map((f) => {
    const c = state.data.checks[f];
    return el("span", {
      class: `tag ${c && c.excluded ? "tag-warn" : ""}`,
      title: c
        ? c.text + (r.t in state.data.duplicates && f === "duplicate" ? ` Kept: ${state.data.duplicates[r.t]}.` : "")
        : f,
      text: c ? c.label : f,
    });
  });
}

function stockTable(rows) {
  const { key, dir } = state.sort;
  const sorted = rows.slice().sort((a, b) => {
    const x = key === "t" ? a.t : a[key];
    const y = key === "t" ? b.t : b[key];
    if (x === null || x === undefined) return 1;
    if (y === null || y === undefined) return -1;
    return (x < y ? -1 : x > y ? 1 : 0) * dir;
  });
  const shown = sorted.slice(0, state.limit);
  const head = el(
    "tr",
    {},
    [
      ["t", "Stock", null, false, "Ticker, name and industry"],
      ["cls", "Type", null, false, "Outlier type against the sector (first reading)"],
      ...cols(),
      ["flags", "Why · checks", null, false, ""],
    ].map(([k, label, , , title]) => {
      const sortable = k !== "flags" && k !== "cls";
      const active = state.sort.key === k;
      return el(
        "th",
        {
          title,
          class: sortable ? "sortable" : "",
          "aria-sort": active ? (dir > 0 ? "ascending" : "descending") : null,
          style: k === "flags" ? "text-align:left" : null,
          onclick: sortable
            ? () => {
                state.sort = { key: k, dir: active ? -dir : k === "t" ? 1 : -1 };
                render();
              }
            : null,
        },
        label,
        active ? (dir > 0 ? " ▲" : " ▼") : "",
      );
    }),
  );
  const body = shown.map((r) =>
    el(
      "tr",
      { class: excluded(r) ? "muted-row" : "" },
      el(
        "td",
        {},
        el(
          "a",
          { href: `stock.html?t=${encodeURIComponent(r.t)}`, title: "Open the trade-idea template" },
          el("b", { text: r.t }),
        ),
        el("span", { class: "sub", text: `${r.name || ""}${r.industry ? ` · ${r.industry}` : ""}` }),
      ),
      el("td", { class: "text-left" }, typeTag(r)),
      ...cols().map(([k, , f, signed]) => {
        const v = r[k];
        if (v === null || v === undefined) return el("td", { class: "muted", text: "–" });
        return el("td", { class: signed ? (v > 0 ? "up" : v < 0 ? "down" : "") : "", text: f(v) });
      }),
      el(
        "td",
        { class: "text" },
        r.why ? el("div", { text: r.why }) : null,
        r.notes && r.notes.length ? el("div", { class: "sub", text: r.notes.join(" · ") }) : null,
        ...flagTags(r),
      ),
    ),
  );
  return el(
    "section",
    { class: "card panel", style: "margin-top:12px" },
    el("h2", { class: "panel-title", text: `${rows.length} stocks` }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text:
        "Click a column to sort, a ticker to open its trade-idea template. Types are a first reading against the sector (top / bottom quarter of EPS growth); " +
        "grey rows are left out of the averages.",
    }),
    el(
      "div",
      { class: "scroll-x" },
      el("table", { class: "data screener-table" }, el("thead", {}, head), el("tbody", {}, body)),
    ),
    rows.length > state.limit
      ? el("button", {
          type: "button",
          class: "btn",
          style: "margin-top:10px",
          text: `Show all ${rows.length}`,
          onclick: () => {
            state.limit = Infinity;
            render();
          },
        })
      : null,
  );
}

function controls() {
  const sectors = ["All", ...Object.keys(state.data.sectors).filter((s) => s !== "all")];
  const industries = [
    ...new Set(state.rows.filter((r) => state.sector === "All" || r.sector === state.sector).map((r) => r.industry)),
  ]
    .filter(Boolean)
    .sort();
  const select = (label, value, options, onchange) =>
    el(
      "label",
      {},
      `${label} `,
      el(
        "select",
        { class: "select", onchange: (ev) => onchange(ev.target.value) },
        options.map(([v, text]) => el("option", { value: v, text, selected: String(v) === String(value) })),
      ),
    );
  return el(
    "div",
    { class: "toolbar" },
    select(
      "Sector",
      state.sector,
      sectors.map((s) => [s, s === "All" ? "All sectors" : `${s} (${state.data.sectors[s].n})`]),
      (v) => {
        state.sector = v;
        state.industry = "";
        state.limit = 150;
        render();
      },
    ),
    select("Industry", state.industry, [["", "All industries"], ...industries.map((i) => [i, i])], (v) => {
      state.industry = v;
      render();
    }),
    select("Size", state.minCap, CAPS, (v) => {
      state.minCap = Number(v);
      render();
    }),
    el("input", {
      class: "select",
      type: "search",
      placeholder: "Ticker or name",
      value: state.query,
      "aria-label": "Search by ticker or name",
      oninput: (ev) => {
        state.query = ev.target.value;
        renderTable();
      },
    }),
    el(
      "div",
      { class: "seg", role: "group", "aria-label": "Columns" },
      [
        ["forward", "Forward: 11 numbers"],
        ["evidence", "Evidence: accounts"],
      ].map(([k, label]) =>
        el("button", {
          type: "button",
          "aria-pressed": String(state.columns === k),
          text: label,
          onclick: () => {
            state.columns = k;
            if (!cols().some(([c]) => c === state.sort.key) && !["t", "mcap"].includes(state.sort.key))
              state.sort = { key: "mcap", dir: -1 };
            render();
          },
        }),
      ),
    ),
    el(
      "label",
      { class: "check" },
      el("input", {
        type: "checkbox",
        checked: state.hideExcluded,
        onchange: (ev) => {
          state.hideExcluded = ev.target.checked;
          render();
        },
      }),
      " Hide rows left out of the averages",
    ),
  );
}

function checksCard() {
  const d = state.data;
  return el(
    "section",
    { class: "card panel", style: "margin-top:12px" },
    el("h2", { class: "panel-title", text: "Data checks (lesson 28)" }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text:
        `Universe: ${d.rows.length} US-listed common stocks above $${d.params.min_market_cap / 1e9}bn (Yahoo Finance screener); ` +
        `estimates as of ${d.as_of}. Checks marked "left out" keep a stock out of the averages; the others only blank the numbers that are not meaningful.`,
    }),
    el(
      "ul",
      { class: "plain-list" },
      Object.values(d.checks).map((c) =>
        el(
          "li",
          {},
          el("span", { class: `tag ${c.excluded ? "tag-warn" : ""}`, text: c.label }),
          ` ${c.text} `,
          el("span", { class: "muted", text: `${c.count} stocks${c.excluded ? ", left out" : ""}.` }),
        ),
      ),
    ),
  );
}

function renderTable() {
  const rows = base();
  document
    .getElementById("averages")
    .replaceChildren(state.columns === "evidence" ? evidenceCard(rows) : averagesCard(rows));
  document.getElementById("types").replaceChildren(categoryBar(rows));
  document.getElementById("table").replaceChildren(stockTable(view(rows)));
}

function render() {
  document.getElementById("controls").replaceChildren(controls());
  renderTable();
}

async function main() {
  const content = document.getElementById("content");
  try {
    state.data = await loadJSON("data/screener/stocks.json");
  } catch {
    content.replaceChildren(
      el("div", { class: "card notice", text: "No screener data yet: it is built by the daily update." }),
    );
    return;
  }
  const cols = state.data.columns;
  state.rows = state.data.rows.map((r) => Object.fromEntries(cols.map((c, i) => [c, r[i]])));
  const vix = state.data.vix;
  for (const r of state.rows) {
    const vols = [r.rv, r.iv].filter((x) => x !== null && x !== undefined);
    r.volx = vix && vols.length ? Math.min(...vols) / vix : null;
  }
  const params = new URLSearchParams(location.search);
  if (params.get("sector")) state.sector = params.get("sector");
  if (params.get("type")) state.cls = params.get("type");
  if (params.get("industry")) {
    const hit = state.rows.find((r) => r.industry === params.get("industry"));
    if (hit) [state.sector, state.industry] = [hit.sector, hit.industry];
  }
  if (params.get("columns") === "evidence") state.columns = "evidence";
  content.replaceChildren(
    el("div", { id: "controls" }),
    el("div", { id: "averages" }),
    el("div", { id: "types", style: "margin-top:12px" }),
    el("div", { id: "table" }),
    checksCard(),
  );
  render();
}

main();
