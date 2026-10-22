// Portfolio Lab (lessons 16-21): a current and a proposed long/short book, modelled on daily prices.
// CEW and non-rebalanced backtests with drawdowns, portfolio volatility, correlations, beta-adjusted exposure,
// position-count guidance and Sharpe framing. The books are kept in this browser (export/import as a file).

import { el, loadJSON, setChildren } from "./common.js";
import { chartSet, redraw, redrawOnResize, renderPanels } from "./charts.js";
import * as pm from "./portfolio-math.js";
import * as store from "./ideas-store.js";
import { fmt, rowsOf } from "./workbench.js";

const KEY = "ptm.portfolio.v1";
// Course targets (lessons 18-20); the alignment threshold is our choice (docs/09-portfolio-method.md)
// Factor exposure: a "style bet" is a loading of at least 20% of capital with |t| >= 2 (our choice, docs/09)
const FT = { loading: 0.2, t: 2 };
const T = { volLo: 15, volHi: 30, volPracLo: 17.5, volPracHi: 22.5, corr: 0.3, rollWindow: 60, neutralBand: 30 };
const LOOKBACKS = [
  [63, "3M"],
  [126, "6M"],
  [252, "1Y"],
  [504, "2Y"],
];
const S = {
  rows: {},
  stocks: null,
  spy: null,
  rf: 0.04,
  macro: null,
  published: { ideas: [] },
  prices: {}, // ticker -> {dates, values} | null (not found)
  ui: { tab: "current", lookback: 252, corrPositions: true },
  data: { capital: 100000, current: [], proposed: [] },
  set: chartSet(null),
};
const has = (v) => v !== null && v !== undefined && Number.isFinite(v);

// ---------- storage ----------
function load() {
  try {
    const obj = JSON.parse(localStorage.getItem(KEY) || "null");
    if (obj && Array.isArray(obj.current) && Array.isArray(obj.proposed)) S.data = { ...S.data, ...obj };
    if (obj && obj.ui) S.ui = { ...S.ui, ...obj.ui };
  } catch {
    /* private mode or bad data: start empty */
  }
}

function save() {
  try {
    localStorage.setItem(KEY, JSON.stringify({ ...S.data, ui: S.ui }));
  } catch {
    /* nothing to do: the page still works for this visit */
  }
}

// ---------- prices ----------
const safe = (t) => t.replace(/[^A-Z0-9.^=-]/g, "");

async function prices(t) {
  if (t in S.prices) return S.prices[t];
  let out = null;
  if (S.rows[t]) {
    const page = await loadJSON(`data/stocks/${safe(t)}.json`).catch(() => null);
    if (page && page.prices) out = { dates: page.prices.d, values: page.prices.c };
  } else {
    // ETFs and indices the pipeline publishes (SPY, sector ETFs, ...)
    const s = await loadJSON(`data/series/yahoo/${safe(t).replace("^", "").replace("=", "_")}.json`).catch(() => null);
    if (s && s.observations) {
      const k = s.columns.indexOf("adj_close") > 0 ? s.columns.indexOf("adj_close") : 1;
      out = { dates: s.observations.map((r) => r[0]), values: s.observations.map((r) => r[k]) };
    }
  }
  S.prices[t] = out;
  return out;
}

function lastPrice(t) {
  if (S.rows[t]) return S.rows[t].price;
  const p = S.prices[t];
  return p && p.values.length ? p.values[p.values.length - 1] : null;
}

// ---------- analysis ----------
function analyse(book) {
  const cap = S.data.capital;
  const all = book.filter((p) => p.t && p.amount > 0);
  const missing = all.filter((p) => !S.prices[p.t]);
  const pos = all.filter((p) => S.prices[p.t]);
  const out = { positions: all, used: pos, missing };
  if (!pos.length || !S.spy) return out;
  const n = S.ui.lookback + 1;
  const dates = S.spy.dates.slice(-n);
  const closes = pm.align(dates, Object.fromEntries(pos.map((p) => [p.t, S.prices[p.t]])));
  const spyC = pm.align(dates, { SPY: S.spy }).SPY;
  const rets = Object.fromEntries(pos.map((p) => [p.t, pm.returns(closes[p.t])]));
  const mret = pm.returns(spyC);
  const betas = Object.fromEntries(pos.map((p) => [p.t, pm.beta(rets[p.t], mret)]));
  const cewR = pm.cew(pos, rets);
  const bh = pm.buyHold(pos, closes, cap);
  const bhCurve = bh.equity.map((v) => (v / cap) * 100);
  const cewCurve = pm.curve(cewR);
  const window = Math.min(T.rollWindow, Math.floor(dates.length / 2));
  const vol = pm.portfolioVol(pos, rets, cap);
  const matrix = pm.correlationMatrix(pos, rets, S.ui.corrPositions);
  return {
    ...out,
    dates,
    closes,
    rets,
    betas,
    spyCurve: spyC.map((v) => (v / spyC[0]) * 100),
    cewCurve,
    bhCurve,
    cewStats: pm.stats(cewR, S.rf),
    bhStats: pm.stats(bh.rets, S.rf),
    cewDD: pm.drawdowns(cewCurve),
    bhDD: pm.drawdowns(bhCurve),
    vol,
    matrix,
    avgCorr: pm.averagePairwise(S.ui.corrPositions ? matrix : pm.correlationMatrix(pos, rets, true)),
    window,
    rollPairs: pm.rollingAveragePairwise(pos, rets, window),
    rollMarket: pm.rollingCorrelation(bh.rets, mret, window),
    marketCorr: pm.correlation(bh.rets, mret),
    exp: pm.exposures(pos, betas, cap),
    vols: Object.fromEntries(pos.map((p) => [p.t, pm.stats(rets[p.t]).vol])),
    factors: factorsFor(pos, rets, dates, cap),
  };
}

// Style-factor loadings of the book (market, size, value, momentum) from the factor ETFs on the same days.
const FACTOR_ETFS = ["SPY", "IWM", "IWD", "IWF", "MTUM"];
function factorsFor(pos, rets, dates, cap) {
  const have = Object.fromEntries(FACTOR_ETFS.filter((t) => S.prices[t]).map((t) => [t, S.prices[t]]));
  if (!have.SPY) return null;
  const fr = pm.factorReturns(pm.align(dates, have));
  const x = pm.factorExposure(pos, rets, fr, cap);
  return x ? { ...x, missing: pm.FACTORS.filter(([id]) => !fr[id]).map(([, label]) => label) } : null;
}

// ---------- editor ----------
function book() {
  return S.data[S.ui.tab];
}

function update(fn) {
  fn();
  save();
  refresh();
}

function editor() {
  const b = book();
  const list = el(
    "datalist",
    { id: "tickers" },
    Object.values(S.rows).map((r) => el("option", { value: r.t, text: r.name || "" })),
  );
  const cap = S.data.capital;
  const rows = b.map((p, i) => {
    const r = S.rows[p.t];
    const price = lastPrice(p.t);
    const notFound = p.t && S.prices[p.t] === null;
    return el(
      "tr",
      {},
      el(
        "td",
        {},
        el("input", {
          class: "select tick-input",
          value: p.t || "",
          list: "tickers",
          "aria-label": "Ticker",
          placeholder: "Ticker",
          onchange: (ev) => update(() => (p.t = ev.target.value.trim().toUpperCase())),
        }),
        el("span", {
          class: `sub ${notFound ? "down" : ""}`,
          text: notFound ? "no daily prices for this ticker" : r ? `${r.name || ""} · ${r.sector || ""}` : "",
        }),
      ),
      el(
        "td",
        { class: "text-left" },
        el(
          "div",
          { class: "seg", role: "group", "aria-label": "Side" },
          ["long", "short"].map((side) =>
            el("button", {
              type: "button",
              "aria-pressed": String(p.side === side),
              text: side === "long" ? "Long" : "Short",
              onclick: () => update(() => (p.side = side)),
            }),
          ),
        ),
      ),
      el(
        "td",
        {},
        el("input", {
          class: "select num-input",
          type: "number",
          min: 0,
          step: 100,
          value: p.amount || "",
          "aria-label": "Position size in dollars",
          onchange: (ev) => update(() => (p.amount = Math.max(0, Number(ev.target.value) || 0))),
        }),
      ),
      el("td", { text: price && p.amount ? Math.round(p.amount / price).toLocaleString("en-US") : "–" }),
      el("td", { text: price ? fmt.price(price) : "–" }),
      el("td", { text: cap ? `${((p.amount / cap) * 100).toFixed(1)}%` : "–" }),
      el(
        "td",
        {},
        el("button", {
          type: "button",
          class: "btn btn-small",
          text: "Remove",
          "aria-label": `Remove ${p.t || "row"}`,
          onclick: () => update(() => b.splice(i, 1)),
        }),
      ),
    );
  });
  return el(
    "div",
    {},
    list,
    el(
      "div",
      { class: "scroll-x" },
      el(
        "table",
        { class: "data editor" },
        el(
          "thead",
          {},
          el(
            "tr",
            {},
            ["Stock or ETF", "Side", "Size $", "Shares", "Price", "% of capital", ""].map((h) => el("th", { text: h })),
          ),
        ),
        el("tbody", {}, rows),
      ),
    ),
    el(
      "div",
      { class: "toolbar", style: "margin:10px 0 0" },
      el("button", {
        type: "button",
        class: "btn",
        text: "+ Add a position",
        onclick: () => update(() => b.push({ t: "", side: "long", amount: Math.round(cap / 10) })),
      }),
      el("button", {
        type: "button",
        class: "btn",
        text: S.ui.tab === "current" ? "Add my active ideas" : "Add my open ideas",
        title: "From the Ideas page: side from the idea, size = capital ÷ 10",
        onclick: () => update(addIdeas),
      }),
      S.ui.tab === "proposed"
        ? el("button", {
            type: "button",
            class: "btn",
            text: "Start from the current book",
            onclick: () => {
              if (!book().length || confirm("Replace the proposed book with a copy of the current one?"))
                update(() => (S.data.proposed = structuredClone(S.data.current)));
            },
          })
        : null,
    ),
  );
}

function addIdeas() {
  const statuses = S.ui.tab === "current" ? ["active"] : store.OPEN_STATUSES;
  const merged = Object.values(store.mergeIdeas(S.published));
  const b = book();
  for (const e of merged) {
    if (!statuses.includes(e.idea.status) || b.some((p) => p.t === e.idea.ticker)) continue;
    b.push({ t: e.idea.ticker, side: e.idea.side, amount: Math.round(S.data.capital / 10) });
  }
}

function controls() {
  return el(
    "div",
    { class: "toolbar" },
    el(
      "div",
      { class: "seg", role: "group", "aria-label": "Book" },
      [
        ["current", `Current (${S.data.current.length})`],
        ["proposed", `Proposed (${S.data.proposed.length})`],
      ].map(([k, label]) =>
        el("button", {
          type: "button",
          "aria-pressed": String(S.ui.tab === k),
          text: label,
          onclick: () => update(() => (S.ui.tab = k)),
        }),
      ),
    ),
    el(
      "label",
      {},
      "Account $ ",
      el("input", {
        class: "select num-input",
        type: "number",
        min: 1000,
        step: 1000,
        value: S.data.capital,
        onchange: (ev) => update(() => (S.data.capital = Math.max(1000, Number(ev.target.value) || 100000))),
      }),
    ),
    el(
      "div",
      { class: "seg", role: "group", "aria-label": "History" },
      LOOKBACKS.map(([d, label]) =>
        el("button", {
          type: "button",
          "aria-pressed": String(S.ui.lookback === d),
          text: label,
          onclick: () => update(() => (S.ui.lookback = d)),
        }),
      ),
    ),
    el("button", {
      type: "button",
      class: "btn",
      text: "Export",
      onclick: () =>
        store.download(
          `ptm-portfolio-${new Date().toISOString().slice(0, 10)}.json`,
          JSON.stringify(S.data, null, 1),
          "application/json",
        ),
    }),
    el("button", {
      type: "button",
      class: "btn",
      text: "Import",
      onclick: () => document.getElementById("pf-file").click(),
    }),
    el("input", {
      id: "pf-file",
      type: "file",
      accept: "application/json,.json",
      hidden: true,
      onchange: async (ev) => {
        try {
          const obj = JSON.parse(await ev.target.files[0].text());
          if (!Array.isArray(obj.current) || !Array.isArray(obj.proposed)) throw new Error("not a portfolio file");
          update(
            () => (S.data = { capital: Number(obj.capital) || 100000, current: obj.current, proposed: obj.proposed }),
          );
        } catch (err) {
          alert(`Import failed: ${err.message}`);
        }
      },
    }),
  );
}

// ---------- results ----------
const pct = (v, d = 1) => (has(v) ? `${v.toFixed(d)}%` : "–");

function checks(a) {
  const guide = pm.positionGuide(S.data.capital);
  const n = a.positions.length;
  const vol = a.vol && a.vol.vol;
  const bias = S.macro && S.macro.bias;
  let align = null;
  if (bias && a.exp) {
    const net = a.exp.betaNet;
    if (bias.state === "net_long") align = net > 0 ? "good" : "bad";
    else if (bias.state === "net_short") align = net < 0 ? "good" : "bad";
    else align = Math.abs(net) <= T.neutralBand ? "good" : "bad";
  }
  return {
    count: { ok: n >= guide.min && n <= guide.max, text: `${n} (${guide.min}–${guide.max})` },
    vol: { ok: has(vol) && vol >= T.volLo && vol <= T.volHi, text: pct(vol) },
    corr: { ok: has(a.avgCorr) && Math.abs(a.avgCorr) <= T.corr, text: has(a.avgCorr) ? a.avgCorr.toFixed(2) : "–" },
    align,
    guide,
    bias,
  };
}

function tiles(a) {
  const c = checks(a);
  const tile = (label, value, foot, tone) =>
    el(
      "div",
      { class: "card tile" },
      el("div", { class: "tile-label", text: label }),
      el("div", { class: `tile-value small ${tone === true ? "up" : tone === false ? "down" : ""}`, text: value }),
      el("div", { class: "tile-foot", text: foot }),
    );
  const e = a.exp || {};
  return el(
    "div",
    { class: "tiles" },
    tile("Positions", c.count.text, c.guide.label, a.positions.length ? c.count.ok : null),
    tile(
      "Portfolio volatility",
      c.vol.text,
      `target ${T.volLo}–${T.volHi}% a year (aim ${T.volPracLo}–${T.volPracHi}%)`,
      has(a.vol && a.vol.vol) ? c.vol.ok : null,
    ),
    tile(
      "Average correlation",
      c.corr.text,
      `between positions; target −${T.corr} to +${T.corr}`,
      has(a.avgCorr) ? c.corr.ok : null,
    ),
    tile(
      "Net / beta-adjusted",
      has(e.net) ? `${fmt.pct(e.net, 0)} / ${fmt.pct(e.betaNet, 0)}` : "–",
      c.bias
        ? `Macro bias: ${c.bias.label}${c.align === "bad" ? " — the book leans the other way" : ""}`
        : "of capital",
      c.align === null ? null : c.align === "good",
    ),
    tile(
      "Gross exposure",
      has(e.gross) ? `${e.gross.toFixed(0)}%` : "–",
      has(e.long) ? `long ${e.long.toFixed(0)}% · short ${e.short.toFixed(0)}%` : "",
    ),
    tile(
      "Max drawdown",
      has(a.bhDD && a.bhDD.max) ? `${a.bhDD.max.toFixed(1)}%` : "–",
      a.dates ? `non-rebalanced, ${LOOKBACKS.find((l) => l[0] === S.ui.lookback)[1]} of history` : "",
    ),
  );
}

function compareTable(cur, pro) {
  const line = (label, f, target = "") =>
    el(
      "tr",
      {},
      el("td", { text: label }),
      el("td", { text: f(cur) }),
      el("td", { text: f(pro) }),
      el("td", { class: "muted", text: target }),
    );
  const s = (k, kk) => (a) => (a[k] && has(a[k][kk]) ? `${a[k][kk].toFixed(1)}${kk === "sharpe" ? "" : "%"}` : "–");
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
          ["", "Current", "Proposed", "Target"].map((h) => el("th", { text: h })),
        ),
      ),
      el(
        "tbody",
        {},
        line(
          "Positions",
          (a) => String(a.positions.length),
          `${pm.positionGuide(S.data.capital).min}–${pm.positionGuide(S.data.capital).max}`,
        ),
        line("Portfolio volatility", (a) => pct(a.vol && a.vol.vol), `${T.volLo}–${T.volHi}%`),
        line("Average correlation", (a) => (has(a.avgCorr) ? a.avgCorr.toFixed(2) : "–"), `−${T.corr} to +${T.corr}`),
        line("Correlation with the S&P 500", (a) => (has(a.marketCorr) ? a.marketCorr.toFixed(2) : "–")),
        line("Net exposure", (a) => (a.exp ? fmt.pct(a.exp.net, 0) : "–")),
        line("Beta-adjusted net", (a) => (a.exp ? fmt.pct(a.exp.betaNet, 0) : "–"), "in line with the macro bias"),
        line("Gross exposure", (a) => (a.exp ? `${a.exp.gross.toFixed(0)}%` : "–")),
        line("Return a year, non-rebalanced", s("bhStats", "ret")),
        line("Volatility, non-rebalanced", s("bhStats", "vol")),
        line("Sharpe, non-rebalanced", s("bhStats", "sharpe"), "≥ 1.5–2"),
        line("Max drawdown, non-rebalanced", (a) => (a.bhDD ? `${a.bhDD.max.toFixed(1)}%` : "–")),
        line("Return a year, CEW", s("cewStats", "ret")),
        line("Max drawdown, CEW", (a) => (a.cewDD ? `${a.cewDD.max.toFixed(1)}%` : "–")),
      ),
    ),
  );
}

function charts(a) {
  const dates = a.dates;
  const lb = LOOKBACKS.find((l) => l[0] === S.ui.lookback)[1];
  const roll = (vals) => {
    const i = vals.findIndex(has);
    return i < 0 ? { dates: [], values: [] } : { dates: dates.slice(i), values: vals.slice(i) };
  };
  const panels = [
    {
      title: `Backtest: the ${S.ui.tab} book over the last ${lb}`,
      unit: "index, start = 100",
      note: "non-rebalanced = your dollar sizes left to drift; CEW = equal weights rebalanced daily; S&P 500 for reference",
      series: [
        { name: "Non-rebalanced", dates, values: a.bhCurve },
        { name: "CEW", dates, values: a.cewCurve },
        { name: "S&P 500 (SPY)", dates, values: a.spyCurve },
      ],
      refs: [{ y: 100, label: "start" }],
      zones: [],
    },
    {
      title: "Drawdowns",
      unit: "% below the previous peak",
      series: [
        { name: "Non-rebalanced", dates, values: a.bhDD.dd },
        { name: "CEW", dates, values: a.cewDD.dd },
      ],
      refs: [{ y: 0, label: "" }],
      zones: [],
    },
  ];
  const r1 = roll(a.rollPairs);
  const r2 = roll(a.rollMarket);
  const rs = [];
  if (r1.dates.length > 1) rs.push({ name: "Average between positions", ...r1 });
  if (r2.dates.length > 1) rs.push({ name: "Book vs S&P 500", ...r2 });
  if (rs.length)
    panels.push({
      title: `Rolling correlation (${a.window} days)`,
      unit: "correlation",
      note: `shaded: the −${T.corr} to +${T.corr} target band`,
      series: rs,
      refs: [{ y: 0, label: "" }],
      zones: [{ from: -T.corr, to: T.corr, tone: "pos" }],
    });
  return renderPanels(S.set, panels);
}

function matrixCard(a) {
  const pos = a.used;
  if (pos.length < 2) return null;
  const cell = (v, i, j) => {
    if (i === j) return el("td", { class: "muted", text: "1" });
    if (!has(v)) return el("td", { text: "–" });
    const strength = Math.round(Math.min(1, Math.abs(v)) * 55);
    const color = v > 0 ? "var(--neg)" : "var(--pos)";
    return el("td", {
      class: Math.abs(v) > T.corr ? "corr-out" : "",
      style: `background: color-mix(in srgb, ${color} ${strength}%, transparent)`,
      title: `${pos[i].t} / ${pos[j].t}: ${v.toFixed(2)}`,
      text: v.toFixed(2),
    });
  };
  return el(
    "section",
    { class: "card panel", style: "margin-top:12px" },
    el("h2", { class: "panel-title", text: "Correlation matrix" }),
    el(
      "div",
      { class: "toolbar" },
      el(
        "div",
        { class: "seg", role: "group", "aria-label": "Correlation of" },
        [
          [true, "Positions (shorts flipped)"],
          [false, "Stock prices"],
        ].map(([v, label]) =>
          el("button", {
            type: "button",
            "aria-pressed": String(S.ui.corrPositions === v),
            text: label,
            onclick: () => update(() => (S.ui.corrPositions = v)),
          }),
        ),
      ),
    ),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text: "Daily returns over the selected history. As positions, a long and a short in two stocks that move together show a negative number: the pair offsets. Red = the positions add risk together, blue = they offset; bold = outside the ±0.3 target.",
    }),
    el(
      "div",
      { class: "scroll-x" },
      el(
        "table",
        { class: "data corr" },
        el(
          "thead",
          {},
          el(
            "tr",
            {},
            el("th", { text: "" }),
            pos.map((p) => el("th", { text: p.t })),
          ),
        ),
        el(
          "tbody",
          {},
          pos.map((p, i) =>
            el(
              "tr",
              {},
              el("td", {}, el("b", { text: p.t }), el("span", { class: "sub", text: p.side })),
              a.matrix[i].map((v, j) => cell(v, i, j)),
            ),
          ),
        ),
      ),
    ),
  );
}

function factorCard(a) {
  const f = a.factors;
  if (!f) return null;
  const sig = (b, t) => Math.abs(b) >= FT.loading && t !== null && Math.abs(t) >= FT.t;
  const pctCap = (b) => `${b > 0 ? "+" : b < 0 ? "−" : ""}${Math.abs(b * 100).toFixed(0)}%`;
  const etf = (id) => {
    const row = pm.FACTORS.find((x) => x[0] === id);
    return row[3] ? `${row[2]} − ${row[3]}` : row[2];
  };
  const hedgeText = (id, b) => {
    const usd = `$${Math.round(Math.abs(b) * S.data.capital).toLocaleString("en-US")}`;
    const row = pm.FACTORS.find((x) => x[0] === id);
    const [long, short] = [row[2], row[3]];
    if (!short) return b > 0 ? `short ${usd} ${long}` : `buy ${usd} ${long}`;
    return b > 0 ? `short ${usd} ${long}, buy ${usd} ${short}` : `buy ${usd} ${long}, short ${usd} ${short}`;
  };
  const ids = Object.keys(f.betas);
  const tilts = ids.filter((id) => id !== "market" && sig(f.betas[id], f.t[id]));
  const label = (id) => pm.FACTORS.find((x) => x[0] === id)[1];
  const reading =
    f.r2 === null
      ? ""
      : `The factors explain ${(f.r2 * 100).toFixed(0)}% of the book's daily moves; ${(f.specific * 100).toFixed(0)}% is stock-specific (what your stock picking adds or loses). ` +
        (tilts.length
          ? `Style bets to be aware of: ${tilts.map((id) => `${label(id).toLowerCase()} ${pctCap(f.betas[id])} of capital`).join(", ")}. If those styles turn, the book can lose even when every thesis is right.`
          : "No significant style bet beyond the market: the result depends on the stocks themselves.");
  const cols = ["", ...ids.map(label)];
  return el(
    "section",
    { class: "card panel", style: "margin-top:12px" },
    el("h2", { class: "panel-title", text: "Factor exposure: stock picking or a style bet?" }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text: "The book's daily returns at today's weights, regressed on four style factors built from ETFs: market (SPY), size (IWM − SPY), value (IWD − IWF) and momentum (MTUM − SPY). A loading of +30% on momentum means the book moves like 30% of capital long MTUM and short SPY. Long positive outliers and short negative ones often adds up to long growth and momentum, short value.",
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
            ["Factor", "ETFs", "Loading (% of capital)", "t-stat", "Reading", "Hedge to neutralise"].map((h) =>
              el("th", { text: h }),
            ),
          ),
        ),
        el(
          "tbody",
          {},
          ids.map((id) => {
            const b = f.betas[id];
            const t = f.t[id];
            const strong = sig(b, t);
            return el(
              "tr",
              {},
              el("td", {}, el("b", { text: label(id) })),
              el("td", { text: etf(id) }),
              el("td", { class: strong ? (b > 0 ? "up" : "down") : "", text: pctCap(b) }),
              el("td", { text: t === null ? "–" : t.toFixed(1) }),
              el(
                "td",
                {},
                el("span", {
                  class: `tag ${strong ? "tag-neg" : ""}`,
                  text: strong ? (id === "market" ? "net market exposure" : "style bet") : "small / not significant",
                }),
              ),
              el("td", { text: strong ? hedgeText(id, b) : "–" }),
            );
          }),
        ),
      ),
    ),
    el("p", { class: "reading", style: "margin-top:10px", text: reading }),
    el(
      "p",
      { class: "section-note" },
      `Daily data, ${f.n} days (the "History" setting). Alpha (the part no factor explains): ${f.alphaAnnual >= 0 ? "+" : "−"}${Math.abs(f.alphaAnnual).toFixed(1)}% a year, t = ${f.alphaT === null ? "–" : f.alphaT.toFixed(1)}: a backtest of today's book, not a track record. "Style bet" = loading at least ${FT.loading * 100}% of capital with |t| ≥ ${FT.t}.` +
        (f.missing.length ? ` Not available yet: ${f.missing.join(", ")}.` : ""),
    ),
    el(
      "details",
      { class: "factor-detail" },
      el("summary", { text: "Loadings of each position" }),
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
              cols.map((h) => el("th", { text: h })),
            ),
          ),
          el(
            "tbody",
            {},
            a.used.map((p) => {
              const pl = f.perPosition[p.t];
              return el(
                "tr",
                {},
                el("td", {}, el("b", { text: p.t }), el("span", { class: "sub", text: p.side })),
                ids.map((id) => el("td", { text: pl && pl[id] !== undefined ? pl[id].toFixed(2) : "–" })),
              );
            }),
          ),
        ),
      ),
      el("p", {
        class: "section-note",
        text: "Stock loadings before sizing: a short position flips its sign in the book.",
      }),
    ),
  );
}

function riskCard(a) {
  const pos = a.used;
  return el(
    "section",
    { class: "card panel", style: "margin-top:12px" },
    el("h2", { class: "panel-title", text: "Positions: beta, volatility and risk" }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text: "Beta against the S&P 500 and volatility over the selected history. Risk share = how much of the portfolio's variance each position brings (a hedge can be negative).",
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
            ["Position", "Size", "Beta", "Beta-adjusted $", "Volatility", "Risk share", "Mkt cap"].map((h) =>
              el("th", { text: h }),
            ),
          ),
        ),
        el(
          "tbody",
          {},
          pos.map((p, i) => {
            const b = a.betas[p.t];
            const sign = p.side === "short" ? -1 : 1;
            const r = S.rows[p.t];
            return el(
              "tr",
              {},
              el(
                "td",
                {},
                S.rows[p.t]
                  ? el("a", { href: `stock.html?t=${encodeURIComponent(p.t)}`, text: p.t })
                  : el("b", { text: p.t }),
                el("span", { class: "sub", text: p.side }),
              ),
              el("td", { text: fmt.money(sign * p.amount) }),
              el("td", { text: has(b) ? b.toFixed(2) : "–" }),
              el("td", { text: has(b) ? fmt.money(sign * p.amount * b) : "–" }),
              el("td", { text: pct(a.vols[p.t], 0) }),
              el("td", { text: pct(a.vol.contrib[i], 0) }),
              el("td", { text: r ? fmt.money(r.mcap) : "–" }),
            );
          }),
        ),
      ),
    ),
    tiltNote(pos),
  );
}

// Lesson 21: in GDP-growth regimes mid-cap longs vs large-cap shorts tended to beat large vs large.
function tiltNote(pos) {
  const caps = (side) => pos.filter((p) => p.side === side && S.rows[p.t]).map((p) => S.rows[p.t].mcap);
  const med = (v) => (v.length ? v.sort((x, y) => x - y)[Math.floor(v.length / 2)] : null);
  const l = med(caps("long"));
  const s = med(caps("short"));
  if (!l || !s) return null;
  return el("p", {
    class: "reading",
    style: "margin-top:10px",
    text: `Median market cap: longs ${fmt.money(l)}, shorts ${fmt.money(s)}. In GDP-growth regimes, mid-cap longs against large-cap shorts tended to do better than large against large (earnings more sensitive to the cycle).`,
  });
}

function framingCard(a) {
  const vol = a.vol && a.vol.vol;
  const base = has(vol) ? vol : null;
  return el(
    "section",
    { class: "card panel", style: "margin-top:12px" },
    el("h2", { class: "panel-title", text: "Sharpe framing: the return each structure needs" }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text: "Absolute-return mandate: required return = minimum Sharpe ratio × portfolio volatility. With the course's 15–30% volatility band, CFDs need 22.5–45% a year, US stocks long/short 30–60%, options 50–100%.",
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
            [
              "Structure",
              "Minimum Sharpe",
              "At 15% vol",
              "At 30% vol",
              base ? `At this book's ${base.toFixed(0)}%` : "This book",
            ].map((h) => el("th", { text: h })),
          ),
        ),
        el(
          "tbody",
          {},
          pm.SHARPE_FRAMES.map((f) =>
            el(
              "tr",
              {},
              el("td", { text: f.structure }),
              el("td", { text: f.sharpe.toFixed(1) }),
              el("td", { text: pct(pm.requiredReturn(f.sharpe, 15), 1) }),
              el("td", { text: pct(pm.requiredReturn(f.sharpe, 30), 1) }),
              el("td", { text: base ? pct(pm.requiredReturn(f.sharpe, base), 1) : "–" }),
            ),
          ),
        ),
      ),
    ),
    a.bhStats && has(a.bhStats.sharpe)
      ? el("p", {
          class: "section-note",
          text: `Backtest Sharpe of this book (non-rebalanced, ${a.bhStats.days} days, risk-free ${(S.rf * 100).toFixed(1)}%): ${a.bhStats.sharpe.toFixed(2)}. One short sample: a description of the past, not a forecast.`,
        })
      : null,
  );
}

async function refresh() {
  const b = book();
  setChildren(document.getElementById("controls"), controls());
  setChildren(document.getElementById("editor"), editor());
  const tickers = [
    ...new Set(
      [...S.data.current, ...S.data.proposed]
        .map((p) => p.t)
        .filter(Boolean)
        .concat(FACTOR_ETFS),
    ),
  ];
  await Promise.all(tickers.map(prices));
  setChildren(document.getElementById("editor"), editor());
  const cur = analyse(S.data.current);
  const pro = analyse(S.data.proposed);
  const a = S.ui.tab === "current" ? cur : pro;
  const results = document.getElementById("results");
  if (!b.length || !a.dates) {
    setChildren(
      results,
      el("div", {
        class: "card notice",
        style: "margin-top:12px",
        text: b.length
          ? "No daily prices for these tickers yet: stocks need to be in the screener universe (or be an ETF the site tracks)."
          : "Add positions (or your ideas) to model the book. Sizes are in dollars; the account size sets the weights.",
      }),
      framingCard(a),
    );
    return;
  }
  setChildren(
    results,
    a.missing.length
      ? el("div", {
          class: "card notice",
          style: "margin-top:12px",
          text: `Left out (no daily prices): ${a.missing.map((p) => p.t).join(", ")}.`,
        })
      : null,
    el("div", { style: "margin-top:12px" }, tiles(a)),
    el(
      "section",
      { class: "card panel", style: "margin-top:12px" },
      el("h2", { class: "panel-title", text: "Current vs proposed" }),
      el("p", {
        class: "section-note",
        style: "margin-top:0",
        text: "Model the proposed book before adding, removing or resizing positions (lesson 16). Same history and account size for both.",
      }),
      compareTable(cur, pro),
    ),
    el("div", { style: "margin-top:12px" }, ...charts(a)),
    matrixCard(a),
    riskCard(a),
    factorCard(a),
    framingCard(a),
  );
  redraw(S.set);
}

async function main() {
  load();
  const [stocks, spy, macro, rate, published] = await Promise.all([
    loadJSON("data/screener/stocks.json").catch(() => null),
    loadJSON("data/series/yahoo/SPY.json").catch(() => null),
    loadJSON("data/macro/latest.json").catch(() => null),
    loadJSON("data/series/fred/DGS3MO.json").catch(() => null),
    store.loadPublished(),
  ]);
  S.stocks = stocks;
  S.rows = stocks ? Object.fromEntries(rowsOf(stocks).map((r) => [r.t, r])) : {};
  if (spy) {
    const k = spy.columns.indexOf("adj_close") > 0 ? spy.columns.indexOf("adj_close") : 1;
    S.spy = { dates: spy.observations.map((r) => r[0]), values: spy.observations.map((r) => r[k]) };
    S.prices.SPY = S.spy;
  }
  if (rate && rate.observations && rate.observations.length) {
    const v = rate.observations.filter((r) => r[1] !== null).pop();
    if (v) S.rf = v[1] / 100;
  }
  S.macro = macro;
  S.published = published;
  setChildren(
    document.getElementById("content"),
    el("div", { id: "controls" }),
    el("section", { class: "card panel" }, el("div", { id: "editor" })),
    el("div", { id: "results" }),
    el("p", {
      class: "section-note",
      text: "The books are saved in this browser only; Export moves them to another device. History: daily closes (dividend-adjusted) of stocks in the screener and the ETFs the site tracks.",
    }),
  );
  redrawOnResize(S.set);
  await refresh();
}

main();
