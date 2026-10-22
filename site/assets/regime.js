// Regime page: growth vs inflation (map, trail, timeline), what did well in each regime, recession odds,
// Fed funds vs a Taylor rule, and the Treasury curve with a comparison slider. Data: data/regime.json
// (pipeline/regime/build.py). Context only: nothing here feeds the bias.

import { chartSet, redraw, redrawOnResize, renderPanels } from "./charts.js";
import { el, fmtMonth, loadJSON, setChildren } from "./common.js";

const S = { d: null, period: "all", cmp: null };
const recSet = chartSet(null);
const taySet = chartSet(null);
const has = (v) => v !== null && v !== undefined && Number.isFinite(v);
const COLOR = {
  recovery: "var(--s3)",
  overheat: "var(--s2)",
  stagflation: "var(--neg)",
  reflation: "var(--s1)",
};
const ORDER = ["recovery", "overheat", "stagflation", "reflation"];
const signed = (v, d = 1) => {
  if (!has(v)) return "–";
  const r = Number(v.toFixed(d));
  return `${r > 0 ? "+" : r < 0 ? "−" : ""}${Math.abs(r).toFixed(d)}`;
};
const svgEl = (tag, attrs, text) => {
  const n = el(tag, { svg: true, ...attrs });
  if (text !== undefined) n.textContent = text;
  return n;
};

// ---------- tooltip ----------
let tipNode = null;
function showTip(ev, ...children) {
  if (!tipNode) {
    tipNode = el("div", { class: "tooltip", hidden: true });
    document.body.append(tipNode);
  }
  tipNode.replaceChildren(...children);
  tipNode.hidden = false;
  const b = tipNode.getBoundingClientRect();
  tipNode.style.left = `${Math.min(window.innerWidth - b.width - 8, Math.max(8, ev.clientX - b.width / 2))}px`;
  tipNode.style.top = `${Math.max(8, ev.clientY - b.height - 14)}px`;
}
const hideTip = () => tipNode && (tipNode.hidden = true);

function onResize(draw) {
  let t;
  window.addEventListener("resize", () => {
    clearTimeout(t);
    t = setTimeout(draw, 120);
  });
  requestAnimationFrame(draw);
}

// ---------- tiles ----------
function curveNow() {
  const c = S.d.curve;
  if (!c) return null;
  const y = c.yields[c.yields.length - 1];
  const at = (label) => y[c.labels.indexOf(label)];
  return { date: c.dates[c.dates.length - 1], s3m: at("10Y") - at("3M"), s2y: at("10Y") - at("2Y") };
}

function tiles() {
  const { now, recession: rec, taylor: tay } = S.d;
  const tile = (label, value, foot, style = "", cls = "") =>
    el(
      "div",
      { class: "card tile" },
      el("div", { class: "tile-label", text: label }),
      el("div", { class: `tile-value small ${cls}`, style, text: value }),
      el("div", { class: "tile-foot", text: foot }),
    );
  const cv = curveNow();
  const r = rec && rec.latest;
  const t = tay && tay.latest;
  return el(
    "div",
    { class: "tiles" },
    now
      ? tile(
          "Regime now",
          now.label,
          `${S.d.regimes[now.regime].text.toLowerCase()} (data for ${fmtMonth(now.month)})` +
            (now.borderline ? "; close to a line, it can flip with the next release" : ""),
          `color:${COLOR[now.regime]}`,
        )
      : tile("Regime now", "–", "awaiting data"),
    r
      ? tile(
          "Recession odds, 12 months ahead",
          `${r.prob.toFixed(1)}%`,
          `for ${fmtMonth(r.for_month)}, New York Fed model` +
            (has(r.prev) ? `; ${r.prob <= r.prev ? "down" : "up"} from ${r.prev.toFixed(1)}% a month earlier` : ""),
          "",
          r.prob >= 30 ? "down" : "",
        )
      : tile("Recession odds", "–", "awaiting data"),
    t && has(t.fed_funds)
      ? tile(
          "Fed funds vs Taylor rule",
          `${t.fed_funds.toFixed(2)}% vs ${t.taylor.toFixed(2)}%`,
          t.gap_vs_rule < 0
            ? `policy ${Math.abs(t.gap_vs_rule).toFixed(1)} pp looser than the rule`
            : `policy ${t.gap_vs_rule.toFixed(1)} pp tighter than the rule`,
        )
      : tile("Fed funds vs Taylor rule", "–", "awaiting data"),
    cv
      ? tile(
          "Yield curve, 10y − 3m",
          `${signed(cv.s3m, 2)} pp`,
          `${cv.s3m < 0 ? "inverted" : "upward sloping"}; 10y − 2y ${signed(cv.s2y, 2)} pp (${cv.date})`,
          "",
          cv.s3m < 0 ? "down" : "up",
        )
      : tile("Yield curve", "–", "awaiting data"),
  );
}

// ---------- regime map ----------
function regimeMap() {
  const d = S.d;
  const pts = d.trail;
  if (!pts.length) return null;
  const svg = el("svg", { class: "regime-map", role: "img", "aria-label": "Regime map: growth against inflation" });
  const draw = () => {
    const W = svg.clientWidth || 640;
    const H = svg.clientHeight || 420;
    const P = 34;
    const mx = Math.max(0.6, ...pts.map((p) => Math.abs(p[1]))) * 1.2;
    const my = Math.max(0.6, ...pts.map((p) => Math.abs(p[2]))) * 1.2;
    const x = (v) => P + ((v + mx) / (2 * mx)) * (W - 2 * P);
    const y = (v) => H - P - ((v + my) / (2 * my)) * (H - 2 * P);
    const nodes = [];
    const quad = (key, x0, y0, x1, y1, lx, ly, anchor) => {
      nodes.push(
        svgEl("rect", {
          x: Math.min(x0, x1),
          y: Math.min(y0, y1),
          width: Math.abs(x1 - x0),
          height: Math.abs(y1 - y0),
          fill: `color-mix(in srgb, ${COLOR[key]} 11%, var(--surface))`,
        }),
      );
      nodes.push(
        svgEl(
          "text",
          { x: lx, y: ly, "text-anchor": anchor, class: "rrg-quad", fill: COLOR[key] },
          d.regimes[key].label.toUpperCase(),
        ),
      );
    };
    quad("overheat", x(0), y(0), W - P, P, W - P - 8, P + 18, "end");
    quad("recovery", x(0), y(0), W - P, H - P, W - P - 8, H - P - 10, "end");
    quad("reflation", P, y(0), x(0), H - P, P + 8, H - P - 10, "start");
    quad("stagflation", P, y(0), x(0), P, P + 8, P + 18, "start");
    nodes.push(svgEl("line", { x1: x(0), x2: x(0), y1: P, y2: H - P, stroke: "var(--axis)", "stroke-width": 1.5 }));
    nodes.push(svgEl("line", { x1: P, x2: W - P, y1: y(0), y2: y(0), stroke: "var(--axis)", "stroke-width": 1.5 }));
    nodes.push(
      svgEl(
        "text",
        { x: W - P, y: H - 8, "text-anchor": "end" },
        W < 520 ? "→ growth vs trend (CFNAI, 3m avg)" : "→ growth above trend (Chicago Fed index, 3-month avg)",
      ),
    );
    nodes.push(svgEl("text", { x: 8, y: 14 }, "↑ inflation speeding up (core PCE, pp)"));
    const path = pts.map((p, i) => `${i ? "L" : "M"}${x(p[1]).toFixed(1)},${y(p[2]).toFixed(1)}`).join("");
    nodes.push(
      svgEl("path", { d: path, fill: "none", stroke: "var(--ink-2)", "stroke-width": 1.2, "stroke-opacity": 0.45 }),
    );
    pts.forEach((p, i) => {
      const last = i === pts.length - 1;
      const age = (i + 1) / pts.length;
      const dot = svgEl("circle", {
        cx: x(p[1]),
        cy: y(p[2]),
        r: last ? 9 : 3 + 3 * age,
        fill: COLOR[p[3]],
        "fill-opacity": last ? 1 : 0.25 + 0.6 * age,
        stroke: last ? "var(--ink)" : "var(--surface)",
        "stroke-width": last ? 2 : 1,
        class: "rrg-dot",
        tabindex: last ? 0 : -1,
      });
      dot.addEventListener("pointermove", (ev) =>
        showTip(
          ev,
          el("strong", { text: `${fmtMonth(p[0])}: ${d.regimes[p[3]].label}` }),
          el("span", { text: `growth ${signed(p[1], 2)} · inflation momentum ${signed(p[2], 2)} pp` }),
        ),
      );
      dot.addEventListener("pointerleave", hideTip);
      nodes.push(dot);
      if (last || i === 0)
        nodes.push(
          svgEl(
            "text",
            { x: x(p[1]) + (last ? 13 : 7), y: y(p[2]) + 4, class: last ? "map-now" : "" },
            last ? `${fmtMonth(p[0])} (now)` : fmtMonth(p[0]),
          ),
        );
    });
    svg.replaceChildren(...nodes);
  };
  onResize(draw);
  const n = d.now;
  return el(
    "section",
    { class: "card panel sec-block" },
    el("h2", { class: "panel-title", text: "Growth meets inflation: the regime map" }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text:
        `Each dot is a month: across, the Chicago Fed National Activity Index (85 US indicators; 0 = growth at its long-run trend), averaged over 3 months; up, ` +
        `whether core PCE inflation is speeding up (6-month rate, annualised, minus the 12-month rate). The line joins the last ${pts.length} months, the big dot is the latest. ` +
        "Revised data: the map shows today's numbers.",
    }),
    svg,
    n ? el("p", { class: "regime-reason" }, el("b", { text: `${n.label}: ` }), n.reason_en) : null,
  );
}

// ---------- regime timeline ----------
function timeline() {
  const h = S.d.history;
  if (!h.length) return null;
  const svg = el("svg", {
    class: "regime-strip",
    role: "img",
    "aria-label": "The regime at each month-end since 1999",
  });
  const draw = () => {
    const W = svg.clientWidth || 900;
    const H = svg.clientHeight || 64;
    const L = 4;
    const R = 4;
    const bw = (W - L - R) / h.length;
    const nodes = [];
    h.forEach(([m, g, revised], i) => {
      const r = svgEl("rect", {
        x: L + i * bw,
        y: 6,
        width: Math.max(1, bw + 0.3),
        height: 30,
        fill: COLOR[g],
        "fill-opacity": revised ? 0.55 : 0.95,
      });
      r.addEventListener("pointermove", (ev) =>
        showTip(
          ev,
          el("strong", { text: `${fmtMonth(m)}: ${S.d.regimes[g].label}` }),
          el("span", {
            class: "muted",
            text: revised
              ? "read with revised data (before real-time records)"
              : "read with the data published by then",
          }),
        ),
      );
      r.addEventListener("pointerleave", hideTip);
      nodes.push(r);
      const yr = Number(m.slice(0, 4));
      if (m.endsWith("-01") && yr % (W < 520 ? 10 : 5) === 0)
        nodes.push(svgEl("text", { x: L + i * bw, y: 54, "text-anchor": "middle" }, String(yr)));
    });
    const rt = h.findIndex((r) => !r[2]);
    if (rt > 0) {
      const xr = L + rt * bw;
      nodes.push(
        svgEl("line", {
          x1: xr,
          x2: xr,
          y1: 2,
          y2: 40,
          stroke: "var(--ink)",
          "stroke-width": 1.5,
          "stroke-dasharray": "3 2",
        }),
      );
    }
    svg.replaceChildren(...nodes);
  };
  onResize(draw);
  const c = S.d.counts;
  return el(
    "section",
    { class: "card panel sec-block" },
    el("h2", { class: "panel-title", text: "The regime, month by month" }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text: `How the regime could be read at each month-end with the data published by then. Paler months (before ${fmtMonth(S.d.realtime_from)}, the dashed line) had to use revised data. Regimes change often: read the direction of the trail, not one month.`,
    }),
    svg,
    el(
      "div",
      { class: "legend-row" },
      ORDER.map((k) =>
        el(
          "span",
          {},
          el("span", { class: "swatch-dot", style: `background:${COLOR[k]}` }),
          `${S.d.regimes[k].label} (${c[k]} months)`,
        ),
      ),
    ),
  );
}

// ---------- what did well in each regime ----------
function heatmap() {
  const d = S.d;
  const cur = d.now && d.now.regime;
  const cols = [...ORDER, "any"];
  const cell = (st, scale) => {
    if (!st || !st.n) return el("td", { class: "heat muted", text: "–" });
    const a = Math.min(1, Math.abs(st.mean) / scale);
    const bg = `color-mix(in srgb, ${st.mean >= 0 ? "var(--pos)" : "var(--neg)"} ${Math.round(6 + a * 40)}%, var(--surface))`;
    return el(
      "td",
      {
        class: "heat",
        style: `background:${bg}`,
        title: `median ${signed(st.median)}%, ${st.pct_up}% of months positive, worst ${signed(st.worst)}%, best ${signed(st.best)}%; ${st.n} months ≈ ${st.n_independent} independent 3-month windows`,
      },
      el("b", { text: `${signed(st.mean)}%` }),
      el("span", { class: "sub", text: `n=${st.n}` }),
    );
  };
  const rows = (list, scale) =>
    list.map((r) =>
      el(
        "tr",
        {},
        el(
          "td",
          { class: "text-left" },
          el("b", { text: r.label }),
          el("span", { class: "sub", text: `${r.id} · since ${r.first || "–"}` }),
        ),
        cols.map((k) => cell(r[S.period][k], scale)),
      ),
    );
  const groupRow = (text) => el("tr", { class: "group-row" }, el("td", { colspan: cols.length + 1, text }));
  const table = el(
    "table",
    { class: "data heat-table" },
    el(
      "thead",
      {},
      el(
        "tr",
        {},
        el("th", { class: "text-left", text: "" }),
        cols.map((k) =>
          el(
            "th",
            { class: k === cur ? "cur" : "", style: k === "any" ? "" : `box-shadow: inset 0 -3px 0 ${COLOR[k]}` },
            k === "any" ? "All months" : d.regimes[k].label,
            k === cur ? el("span", { class: "sub", text: "now" }) : null,
          ),
        ),
      ),
    ),
    el(
      "tbody",
      {},
      groupRow("Asset classes: average return over the next 3 months"),
      rows(d.assets, 6),
      groupRow("Sectors: average return over the next 3 months minus the S&P 500's (SPY)"),
      rows(d.sectors, 3),
    ),
  );
  const seg = el(
    "div",
    { class: "seg", role: "group", "aria-label": "Months used" },
    [
      ["all", "All months since 1999"],
      ["realtime", `Real-time data only (since ${fmtMonth(d.realtime_from)})`],
    ].map(([k, label]) =>
      el("button", {
        type: "button",
        "aria-pressed": String(S.period === k),
        text: label,
        onclick: () => {
          S.period = k;
          document.getElementById("heat").replaceWith(heatmap());
        },
      }),
    ),
  );
  return el(
    "section",
    { class: "card panel sec-block", id: "heat" },
    el("h2", { class: "panel-title", text: "What did well in each regime" }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text: "After each month-end, the next 3 months' return, grouped by the regime known on that day. Blue = gained (or beat the S&P 500), red = lost. Hover a cell for the median, the share of positive months and the range. Consecutive months overlap, so 60 months are only about 20 independent windows; the ETFs start at different dates. These are past averages, not forecasts.",
    }),
    seg,
    el("div", { class: "scroll-x" }, table),
  );
}

// ---------- recession odds ----------
const monthDate = (m) => `${m}-01`;
const monthEnd = (m) => {
  const [y, mo] = m.split("-").map(Number);
  return new Date(Date.UTC(y, mo, 0)).toISOString().slice(0, 10);
};

function peakText(r) {
  const peaks = r.recessions.map((x) => x[2]).filter(has);
  if (!peaks.length) return "";
  const top = r.series.reduce((a, b) => (b[1] > a[1] ? b : a));
  const inside = r.recessions.some(([a, b]) => top[0] >= a && top[0] <= b);
  return (
    `Before the recessions it covers, the model's highest reading ranged from ${Math.min(...peaks).toFixed(0)}% to ${Math.max(...peaks).toFixed(0)}%. ` +
    (inside
      ? ""
      : `Its highest reading ever, ${top[1].toFixed(0)}% for ${fmtMonth(top[0])}, was not followed by a recession (none declared so far): a false alarm is possible. `)
  );
}

function recessionBlock() {
  const r = S.d.recession;
  if (!r) return null;
  const bands = r.recessions.map(([a, b]) => ({ from: monthDate(a), to: monthEnd(b), tone: "neg" }));
  const panels = [
    {
      title: "Probability of a US recession 12 months ahead",
      unit: "%",
      note: "plotted at the month it is about, so the line runs 12 months into the future; shaded = NBER recessions",
      series: [
        {
          name: "Probability (New York Fed model)",
          dates: r.series.map((x) => monthDate(x[0])),
          values: r.series.map((x) => x[1]),
        },
      ],
      refs: [],
      zones: [],
      bands,
    },
    {
      title: "The input: 10-year minus 3-month Treasury yield, monthly average",
      unit: "pp",
      note: "below zero = inverted curve; plotted at the month it was measured",
      series: [
        {
          name: "10y − 3m",
          dates: r.series.map((x) => {
            const [y, m] = x[0].split("-").map(Number);
            return `${y - 1}-${String(m).padStart(2, "0")}-01`;
          }),
          values: r.series.map((x) => x[2]),
        },
      ],
      refs: [{ y: 0, label: "inverted below" }],
      zones: [],
      bands,
    },
  ];
  const l = r.latest;
  return el(
    "section",
    { class: "sec-block" },
    el("h2", { class: "sec-h2", text: "Recession odds from the yield curve" }),
    el("p", {
      class: "section-note",
      text: `The New York Fed's model turns the monthly average of the 10y − 3m spread into a probability of recession 12 months later: Φ(−0.5333 − 0.6330 × spread). ${fmtMonth(l.spread_month)}: spread ${signed(l.spread, 2)} pp → ${l.prob.toFixed(1)}% for ${fmtMonth(l.for_month)}. We use FRED's constant-maturity yields, so our number can differ from the Fed's by about a point.`,
    }),
    ...renderPanels(recSet, panels),
    el(
      "div",
      { class: "card panel" },
      el("h3", { class: "panel-title", text: "How high did it get before each recession?" }),
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
              el("th", { class: "text-left", text: "NBER recession" }),
              el("th", { text: "Highest probability the model gave it, a year earlier" }),
            ),
          ),
          el(
            "tbody",
            {},
            r.recessions.map(([a, b, peak]) =>
              el(
                "tr",
                {},
                el("td", { class: "text-left", text: `${fmtMonth(a)} – ${fmtMonth(b)}` }),
                el("td", { text: has(peak) ? `${peak.toFixed(0)}%` : "–" }),
              ),
            ),
          ),
        ),
      ),
      el("p", {
        class: "section-note",
        text: `${peakText(r)}What matters is the rise, not a magic level. NBER dates arrive late (latest month covered: ${fmtMonth(r.usrec_last)}).`,
      }),
    ),
  );
}

// ---------- Taylor rule ----------
function taylorBlock() {
  const t = S.d.taylor;
  if (!t) return null;
  const rows = t.rows;
  const ff = rows.filter((r) => has(r[1]));
  const p = S.d.params;
  const l = t.latest;
  const panel = {
    title: "Fed funds rate vs a Taylor-rule rate",
    unit: "%",
    note: "monthly; the rule uses core PCE inflation over 12 months and the output gap (real GDP vs CBO potential)",
    series: [
      { name: "Fed funds (effective)", dates: ff.map((r) => monthDate(r[0])), values: ff.map((r) => r[1]) },
      { name: "Taylor rule", dates: rows.map((r) => monthDate(r[0])), values: rows.map((r) => r[2]) },
    ],
    refs: [],
    zones: [],
  };
  return el(
    "section",
    { class: "sec-block" },
    el("h2", { class: "sec-h2", text: "Is the Fed loose or tight?" }),
    el("p", {
      class: "section-note",
      text: `Taylor (1993): rate = ${p.taylor_r_star} (neutral real rate) + inflation + ${p.taylor_w_inflation} × (inflation − ${p.taylor_target}) + ${p.taylor_w_gap} × output gap. ${fmtMonth(l.month)}: ${p.taylor_r_star} + ${l.inflation.toFixed(2)} + ${p.taylor_w_inflation} × ${signed(l.inflation - p.taylor_target, 2)} + ${p.taylor_w_gap} × ${signed(l.gap, 2)} = ${l.taylor.toFixed(2)}% (output gap from ${l.gap_quarter.slice(0, 4)} Q${Math.floor((Number(l.gap_quarter.slice(5, 7)) - 1) / 3) + 1}). Fed funds below the line = easier policy than the rule suggests. One simple rule among many; the Fed does not follow it mechanically.`,
    }),
    ...renderPanels(taySet, [panel]),
  );
}

// ---------- Treasury curve ----------
function curveBlock() {
  const c = S.d.curve;
  if (!c) return null;
  const n = c.dates.length;
  const back = (weeks) => Math.max(0, n - 1 - weeks);
  if (S.cmp === null) S.cmp = back(52);
  const svg = el("svg", { class: "curve-chart", role: "img", "aria-label": "US Treasury yield curve" });
  const label = el("output", { class: "cmp-date" });
  const table = el("div", { class: "scroll-x" });
  const draw = () => {
    const W = svg.clientWidth || 700;
    const H = svg.clientHeight || 320;
    const L = 44;
    const R = 16;
    const T = 14;
    const B = 30;
    const latest = c.yields[n - 1];
    const cmp = c.yields[S.cmp];
    const vals = [...latest, ...cmp].filter(has);
    let lo = Math.min(...vals);
    let hi = Math.max(...vals);
    const pad = Math.max(0.2, (hi - lo) * 0.12);
    lo = Math.max(0, lo - pad);
    hi += pad;
    const sx = c.years.map(Math.sqrt);
    const x = (i) => L + ((sx[i] - sx[0]) / (sx[sx.length - 1] - sx[0])) * (W - L - R);
    const y = (v) => T + ((hi - v) / (hi - lo)) * (H - T - B);
    const nodes = [];
    const step = hi - lo > 4 ? 1 : hi - lo > 2 ? 0.5 : 0.25;
    for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
      nodes.push(svgEl("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), stroke: "var(--hairline)" }));
      nodes.push(svgEl("text", { x: L - 6, y: y(v) + 4, "text-anchor": "end" }, `${Number(v.toFixed(2))}%`));
    }
    c.labels.forEach((lab, i) => {
      if (W < 480 && ["3Y", "7Y", "20Y"].includes(lab)) return;
      nodes.push(svgEl("text", { x: x(i), y: H - 10, "text-anchor": "middle" }, lab));
    });
    const line = (ys, color, dash, width) => {
      let d = "";
      ys.forEach((v, i) => {
        if (!has(v)) return;
        d += `${d ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
      });
      nodes.push(
        svgEl("path", { d, fill: "none", stroke: color, "stroke-width": width, "stroke-dasharray": dash || null }),
      );
      ys.forEach((v, i) => {
        if (!has(v)) return;
        const dot = svgEl("circle", {
          cx: x(i),
          cy: y(v),
          r: 3.5,
          fill: color,
          stroke: "var(--surface)",
          "stroke-width": 1,
        });
        dot.addEventListener("pointermove", (ev) =>
          showTip(ev, el("strong", { text: `${c.labels[i]}: ${v.toFixed(2)}%` })),
        );
        dot.addEventListener("pointerleave", hideTip);
        nodes.push(dot);
      });
    };
    line(cmp, "var(--s2)", "5 4", 2);
    line(latest, "var(--s1)", null, 2.5);
    svg.replaceChildren(...nodes);
    label.textContent = c.dates[S.cmp];
    const bp = (a, b) => (has(a) && has(b) ? Math.round((a - b) * 100) : null);
    table.replaceChildren(
      el(
        "table",
        { class: "data curve-table" },
        el(
          "thead",
          {},
          el(
            "tr",
            {},
            el("th", { class: "text-left", text: "" }),
            c.labels.map((lab) => el("th", { text: lab })),
          ),
        ),
        el(
          "tbody",
          {},
          el(
            "tr",
            {},
            el(
              "td",
              { class: "text-left" },
              el("span", { class: "swatch-line", style: "background:var(--s1)" }),
              c.dates[n - 1],
            ),
            latest.map((v) => el("td", { text: has(v) ? v.toFixed(2) : "–" })),
          ),
          el(
            "tr",
            {},
            el(
              "td",
              { class: "text-left" },
              el("span", { class: "swatch-line dashed", style: "background:var(--s2)" }),
              c.dates[S.cmp],
            ),
            cmp.map((v) => el("td", { text: has(v) ? v.toFixed(2) : "–" })),
          ),
          el(
            "tr",
            {},
            el("td", { class: "text-left", text: "Change (bp)" }),
            latest.map((v, i) => {
              const ch = bp(v, cmp[i]);
              return el("td", {
                class: ch > 0 ? "up" : ch < 0 ? "down" : "",
                text: ch === null ? "–" : `${ch > 0 ? "+" : ch < 0 ? "−" : ""}${Math.abs(ch)}`,
              });
            }),
          ),
        ),
      ),
    );
  };
  const slider = el("input", {
    type: "range",
    min: 0,
    max: n - 2,
    value: S.cmp,
    "aria-label": "Compare with the curve of",
    oninput: (ev) => {
      S.cmp = Number(ev.target.value);
      draw();
    },
  });
  const quick = [
    ["1 month", 4],
    ["6 months", 26],
    ["1 year", 52],
    ["3 years", 156],
    ["5 years", 260],
    ["10 years", n - 1],
  ].map(([text, w]) =>
    el("button", {
      type: "button",
      class: "btn btn-small",
      text: `${text} ago`,
      onclick: () => {
        S.cmp = back(w);
        slider.value = S.cmp;
        draw();
      },
    }),
  );
  onResize(draw);
  return el(
    "section",
    { class: "card panel sec-block" },
    el("h2", { class: "panel-title", text: "The Treasury yield curve" }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text: "US Treasury yields from 1 month to 30 years (solid = latest). Drag the slider to compare with any week of the last 10 years. A curve sloping up is normal; short yields above long ones (inverted) has come before every US recession since the 1970s, usually by many months.",
    }),
    el(
      "div",
      { class: "curve-controls" },
      el("label", {}, "Compare with ", label),
      slider,
      el("div", { class: "quick" }, quick),
    ),
    svg,
    table,
  );
}

async function main() {
  const d = await loadJSON("data/regime.json").catch(() => null);
  if (!d) {
    setChildren(
      document.getElementById("content"),
      el("div", { class: "card notice", text: "No regime data yet: it is built by the daily update." }),
    );
    return;
  }
  S.d = d;
  setChildren(
    document.getElementById("content"),
    tiles(),
    regimeMap(),
    timeline(),
    heatmap(),
    recessionBlock(),
    taylorBlock(),
    curveBlock(),
    el("p", {
      class: "section-note",
      text: "Sources: FRED (Chicago Fed CFNAI, BEA core PCE, CBO potential GDP, NBER recession dates, Treasury yields, fed funds) and Yahoo Finance (ETFs, adjusted for dividends). Context only: nothing on this page changes the Macro Desk bias.",
    }),
  );
  redraw(recSet);
  redraw(taySet);
  redrawOnResize(recSet);
  redrawOnResize(taySet);
}

main();
