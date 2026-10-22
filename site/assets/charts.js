// Shared SVG line charts: panels of same-unit series, reference lines, shaded zones, range buttons, tooltip.
// Used by the indicator pages and the Global page. A "set" holds the selected range and the drawn charts.

import { el } from "./common.js";

export const RANGES = [
  ["1Y", 1],
  ["3Y", 3],
  ["5Y", 5],
  ["10Y", 10],
  ["Max", null],
];
export const COLORS = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export const fmtNum = (v) =>
  v === null || v === undefined || Number.isNaN(v)
    ? "–"
    : Math.abs(v) >= 1000
      ? v.toLocaleString("en-US", { maximumFractionDigits: 0 })
      : v.toLocaleString("en-US", { maximumFractionDigits: 2 });
const dayLabel = (d) => `${Number(d.slice(8, 10))} ${MONTHS[Number(d.slice(5, 7)) - 1]} ${d.slice(0, 4)}`;

export function chartSet(range = 10) {
  return { range, charts: [] };
}

// Redraw every chart of a set when the window is resized.
export function redrawOnResize(set) {
  let timer;
  window.addEventListener("resize", () => {
    clearTimeout(timer);
    timer = setTimeout(() => redraw(set), 150);
  });
}

// Rebased series start at 100 on the first day of the selected range (relative performance).
function rebased(s) {
  const base = s.values[0];
  return base ? { ...s, values: s.values.map((v) => (v / base) * 100) } : s;
}

let tip = null;
function tooltip() {
  if (!tip) {
    tip = el("div", { class: "tooltip", hidden: true });
    document.body.append(tip);
  }
  return tip;
}

function sliceRange(series, years) {
  if (!years) return series;
  const lastDates = series.map((s) => s.dates[s.dates.length - 1]).sort();
  const end = new Date(lastDates[lastDates.length - 1]);
  const start = new Date(end);
  start.setFullYear(end.getFullYear() - years);
  const cut = start.toISOString().slice(0, 10);
  return series.map((s) => {
    const i = s.dates.findIndex((d) => d >= cut);
    return { ...s, dates: i < 0 ? [] : s.dates.slice(i), values: i < 0 ? [] : s.values.slice(i) };
  });
}

function drawChart(svg, spec, range) {
  let series = sliceRange(spec.series, range).filter((s) => s.dates.length);
  if (spec.rebase) series = series.map(rebased);
  const small = svg.classList.contains("small");
  const W = svg.clientWidth || 600;
  const H = svg.clientHeight || 220;
  const L = 52;
  const R = 10;
  const T = 8;
  const B = 22;
  if (!series.length) {
    svg.replaceChildren();
    return;
  }
  const t0 = Math.min(...series.map((s) => Date.parse(s.dates[0])));
  const t1 = Math.max(...series.map((s) => Date.parse(s.dates[s.dates.length - 1])));
  let lo = Math.min(...series.flatMap((s) => s.values));
  let hi = Math.max(...series.flatMap((s) => s.values));
  const span0 = hi - lo || Math.abs(hi) || 1;
  for (const r of spec.refs)
    if (r.y >= lo - span0 * 0.35 && r.y <= hi + span0 * 0.35) [lo, hi] = [Math.min(lo, r.y), Math.max(hi, r.y)];
  const pad = (hi - lo || 1) * 0.06;
  lo -= pad;
  hi += pad;
  const x = (t) => L + ((t - t0) / Math.max(1, t1 - t0)) * (W - L - R);
  const y = (v) => T + ((hi - v) / (hi - lo)) * (H - T - B);
  const s = (tag, attrs) => el(tag, { svg: true, ...attrs });
  const nodes = [];
  for (const z of spec.zones) {
    const a = Math.max(lo, Math.min(z.from, z.to));
    const b = Math.min(hi, Math.max(z.from, z.to));
    if (b <= a) continue;
    const fill = z.tone === "pos" ? "var(--pos-wash)" : z.tone === "neg" ? "var(--neg-wash)" : "var(--neu-wash)";
    nodes.push(s("rect", { x: L, width: W - L - R, y: y(b), height: y(a) - y(b), fill }));
  }
  // x bands: shaded periods (e.g. the month after each bias reading)
  for (const band of spec.bands || []) {
    const a = Math.max(t0, Date.parse(band.from));
    const b = Math.min(t1, Date.parse(band.to));
    if (b <= a) continue;
    const fill = band.tone === "pos" ? "var(--pos-wash)" : band.tone === "neg" ? "var(--neg-wash)" : "var(--neu-wash)";
    nodes.push(s("rect", { x: x(a), width: Math.max(1, x(b) - x(a)), y: T, height: H - T - B, fill }));
  }
  // y ticks: 4-5 clean numbers
  const step = niceStep((hi - lo) / 4);
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
    nodes.push(s("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), stroke: "var(--hairline)", "stroke-width": 1 }));
    const t = s("text", { x: L - 6, y: y(v) + 4, "text-anchor": "end" });
    t.textContent = fmtNum(Math.round(v / step) * step + 0); // + 0 turns -0 into 0
    nodes.push(t);
  }
  for (const r of spec.refs) {
    if (r.y < lo || r.y > hi) continue;
    nodes.push(s("line", { x1: L, x2: W - R, y1: y(r.y), y2: y(r.y), stroke: "var(--axis)", "stroke-width": 1.5 }));
    if (small) continue; // small multiples: the panel title names the lines, labels would collide
    const t = s("text", { x: W - R - 4, y: y(r.y) - 4, "text-anchor": "end" });
    t.textContent = r.label;
    nodes.push(t);
  }
  // x ticks: years
  const y0 = new Date(t0).getUTCFullYear();
  const y1 = new Date(t1).getUTCFullYear();
  const every = Math.max(1, Math.ceil((y1 - y0 + 1) / Math.max(2, Math.floor((W - L - R) / 70))));
  for (let yr = y0 + 1; yr <= y1; yr++) {
    if ((yr - y0) % every) continue;
    const tx = x(Date.UTC(yr, 0, 1));
    if (tx < L + 10 || tx > W - R - 10) continue;
    const t = s("text", { x: tx, y: H - 6, "text-anchor": "middle" });
    t.textContent = String(yr);
    nodes.push(t);
  }
  series.forEach((ser, k) => {
    let d = "";
    ser.dates.forEach((dt, i) => {
      d += `${i ? "L" : "M"}${x(Date.parse(dt)).toFixed(1)},${y(ser.values[i]).toFixed(1)}`;
    });
    nodes.push(
      s("path", {
        d,
        fill: "none",
        stroke: COLORS[k % COLORS.length],
        "stroke-width": 2,
        "stroke-linejoin": "round",
        "stroke-linecap": "round",
      }),
    );
    const li = ser.values.length - 1;
    nodes.push(
      s("circle", {
        cx: x(Date.parse(ser.dates[li])),
        cy: y(ser.values[li]),
        r: 4,
        fill: COLORS[k % COLORS.length],
        stroke: "var(--surface)",
        "stroke-width": 2,
      }),
    );
  });
  const cross = s("line", { y1: T, y2: H - B, stroke: "var(--axis)", "stroke-width": 1, visibility: "hidden" });
  const hit = s("rect", { x: L, y: 0, width: W - L - R, height: H, fill: "transparent" });
  nodes.push(cross, hit);
  svg.replaceChildren(...nodes);

  const show = (clientX) => {
    const r = svg.getBoundingClientRect();
    const t = t0 + ((clientX - r.left - L) / (W - L - R)) * (t1 - t0);
    const rows = [];
    let at = null;
    series.forEach((ser, k) => {
      let i = ser.dates.findIndex((d) => Date.parse(d) > t) - 1;
      if (i === -2) i = ser.dates.length - 1;
      if (i < 0) return;
      at = at && at > ser.dates[i] ? at : ser.dates[i];
      rows.push(
        el(
          "div",
          {},
          el("span", { class: "swatch-line", style: `background:${COLORS[k % COLORS.length]}` }),
          el("strong", { style: "display:inline", text: fmtNum(ser.values[i]) }),
          ` ${series.length > 1 ? ser.name : ""}`,
        ),
      );
    });
    if (!at) return;
    cross.setAttribute("x1", x(Date.parse(at)));
    cross.setAttribute("x2", x(Date.parse(at)));
    cross.setAttribute("visibility", "visible");
    const box = tooltip();
    box.replaceChildren(el("span", { class: "muted", text: dayLabel(at) }), ...rows);
    box.hidden = false;
    const b = box.getBoundingClientRect();
    box.style.left = `${Math.min(window.innerWidth - b.width - 8, Math.max(8, clientX - b.width / 2))}px`;
    box.style.top = `${Math.max(8, r.top - b.height - 8)}px`;
  };
  hit.addEventListener("pointermove", (ev) => show(ev.clientX));
  hit.addEventListener("pointerleave", () => {
    cross.setAttribute("visibility", "hidden");
    if (tip) tip.hidden = true;
  });
}

function niceStep(raw) {
  const p = 10 ** Math.floor(Math.log10(raw || 1));
  const m = raw / p;
  return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p;
}

function legend(series) {
  if (series.length < 2) return null;
  return el(
    "div",
    { class: "legend-row" },
    series.map((s, k) =>
      el("span", {}, el("span", { class: "swatch-line", style: `background:${COLORS[k % COLORS.length]}` }), s.name),
    ),
  );
}

function chartBlock(set, spec, small) {
  const svg = el("svg", {
    class: `chart ${small ? "small" : ""}`,
    role: "img",
    "aria-label": `${spec.title}: ${spec.series.map((s) => `${s.name} latest ${fmtNum(s.values[s.values.length - 1])}`).join(", ")}`,
  });
  set.charts.push([svg, spec]);
  return svg;
}

export function renderPanels(set, list) {
  set.charts = [];
  const out = [];
  for (const p of list) {
    if (p.kind === "grid") {
      out.push(
        el(
          "section",
          { class: "card panel-chart" },
          el("h3", { text: p.title }),
          el("p", { class: "sub", text: `Unit: ${p.unit}. Same time range as above.` }),
          el(
            "div",
            { class: "mini-grid" },
            p.charts.map((c) =>
              el(
                "div",
                {},
                el("h4", { text: `${c.title} · ${fmtNum(c.series[0].values[c.series[0].values.length - 1])}` }),
                chartBlock(set, c, true),
              ),
            ),
          ),
        ),
      );
    } else {
      out.push(
        el(
          "section",
          { class: "card panel-chart" },
          el("h3", { text: p.title }),
          el("p", { class: "sub", text: `Unit: ${p.unit}${p.note ? ` · ${p.note}` : ""}` }),
          legend(p.series),
          chartBlock(set, p, false),
        ),
      );
    }
  }
  if (!out.length)
    out.push(el("div", { class: "card notice", text: "No chart data for this indicator yet (awaiting data)." }));
  return out;
}

export function redraw(set) {
  for (const [svg, spec] of set.charts) drawChart(svg, spec, set.range);
}

export function rangeButtons(set) {
  return el(
    "div",
    { class: "toolbar ranges" },
    el("strong", { text: "Charts" }),
    el(
      "div",
      { class: "seg", role: "group", "aria-label": "Time range" },
      RANGES.map(([label, years]) =>
        el("button", {
          type: "button",
          "aria-pressed": String(set.range === years),
          text: label,
          onclick: () => {
            set.range = years;
            for (const b of document.querySelectorAll(".ranges button"))
              b.setAttribute("aria-pressed", String(b.textContent === label));
            redraw(set);
          },
        }),
      ),
    ),
  );
}
