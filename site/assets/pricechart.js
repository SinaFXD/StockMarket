// Daily price chart for the trade-idea page (template section 5): candles (or a line for long ranges), the
// 50- and 200-day averages, price-target lines, and the horizon ahead with the earnings date and catalysts.

import { el } from "./common.js";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const RANGES = [
  ["3M", 63],
  ["6M", 126],
  ["1Y", 260],
  ["2Y", 520],
];
const DAY = 86400000;

function sma(values, n) {
  const out = new Array(values.length).fill(null);
  let sum = 0;
  let count = 0;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (v !== null) {
      sum += v;
      count += 1;
    }
    if (i >= n) {
      const old = values[i - n];
      if (old !== null) {
        sum -= old;
        count -= 1;
      }
    }
    if (i >= n - 1 && count === n) out[i] = sum / n;
  }
  return out;
}

let tip = null;
function tooltip() {
  if (!tip) {
    tip = el("div", { class: "tooltip", hidden: true });
    document.body.append(tip);
  }
  return tip;
}

const f2 = (v) => (v === null || v === undefined ? "–" : v.toLocaleString("en-US", { maximumFractionDigits: 2 }));
const dayLabel = (d) => `${Number(d.slice(8, 10))} ${MONTHS[Number(d.slice(5, 7)) - 1]} ${d.slice(0, 4)}`;

// spec: {prices: {d,o,h,l,c}, lines: [{y, label, tone}], ahead: {days, marks: [{date, label, tone}]}}
export function priceChart(spec) {
  const state = { bars: spec.bars || 126 };
  const svg = el("svg", { class: "chart price-chart", role: "img", "aria-label": spec.label || "Daily price chart" });
  const p = spec.prices;
  const ma50 = sma(p.c, 50);
  const ma200 = sma(p.c, 200);

  function draw() {
    const n = p.d.length;
    const i0 = Math.max(0, n - state.bars);
    const idx = [];
    for (let i = i0; i < n; i++) if (p.c[i] !== null) idx.push(i);
    if (idx.length < 2) {
      svg.replaceChildren();
      return;
    }
    const W = svg.clientWidth || 640;
    const H = svg.clientHeight || 300;
    const L = 52;
    const R = 10;
    const T = 10;
    const B = 22;
    const t0 = Date.parse(p.d[idx[0]]);
    const tLast = Date.parse(p.d[idx[idx.length - 1]]);
    const ahead = spec.ahead && spec.ahead.days ? spec.ahead.days : 0;
    // the axis reaches past the horizon when a mark (e.g. the earnings date) falls just after it
    const markDays = ((spec.ahead && spec.ahead.marks) || [])
      .map((mk) => (Date.parse(mk.date) - tLast) / DAY)
      .filter((d) => d > 0 && d <= ahead + 30);
    const t1 = tLast + Math.max(ahead, ...markDays.map((d) => d + 3)) * DAY;
    let lo = Infinity;
    let hi = -Infinity;
    for (const i of idx) {
      lo = Math.min(lo, p.l[i] ?? p.c[i]);
      hi = Math.max(hi, p.h[i] ?? p.c[i]);
    }
    const span = hi - lo || hi || 1;
    const lines = (spec.lines || []).filter((l) => l.y !== null && l.y !== undefined && l.y > 0);
    for (const l of lines)
      if (l.y >= lo - span * 0.6 && l.y <= hi + span * 0.6) [lo, hi] = [Math.min(lo, l.y), Math.max(hi, l.y)];
    const pad = (hi - lo || 1) * 0.05;
    lo -= pad;
    hi += pad;
    const x = (t) => L + ((t - t0) / Math.max(1, t1 - t0)) * (W - L - R);
    const y = (v) => T + ((hi - v) / (hi - lo)) * (H - T - B);
    const s = (tag, attrs) => el(tag, { svg: true, ...attrs });
    const nodes = [];
    if (ahead) {
      nodes.push(
        s("rect", {
          x: x(tLast),
          y: T,
          width: Math.max(0, x(tLast + ahead * DAY) - x(tLast)),
          height: H - T - B,
          fill: "var(--neu-wash)",
        }),
      );
      const t = s("text", { x: x(tLast) + 4, y: H - B - 20 });
      t.textContent = `${ahead}d`;
      nodes.push(t);
    }
    // y grid
    const raw = (hi - lo) / 4;
    const mag = 10 ** Math.floor(Math.log10(raw || 1));
    const m = raw / mag;
    const step = (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * mag;
    for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
      nodes.push(s("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), stroke: "var(--hairline)", "stroke-width": 1 }));
      const t = s("text", { x: L - 6, y: y(v) + 4, "text-anchor": "end" });
      t.textContent = f2(Math.round(v / step) * step);
      nodes.push(t);
    }
    // x ticks: month starts
    let lastMonth = "";
    const every = Math.max(1, Math.ceil((t1 - t0) / DAY / 30 / Math.max(2, Math.floor((W - L - R) / 60))));
    let k = 0;
    for (let t = t0; t <= t1; t += DAY) {
      const d = new Date(t).toISOString().slice(0, 7);
      if (d === lastMonth) continue;
      lastMonth = d;
      if (k++ % every) continue;
      const tx = x(Date.UTC(Number(d.slice(0, 4)), Number(d.slice(5, 7)) - 1, 1));
      if (tx < L + 12 || tx > W - R - 12) continue;
      const label = s("text", { x: tx, y: H - 6, "text-anchor": "middle" });
      label.textContent = d.slice(5, 7) === "01" ? d.slice(0, 4) : MONTHS[Number(d.slice(5, 7)) - 1];
      nodes.push(label);
    }
    // price
    const barW = Math.max(1, ((W - L - R) / ((t1 - t0) / DAY)) * 0.9);
    const candles = idx.length <= 140 && barW >= 2;
    if (candles) {
      for (const i of idx) {
        const tx = x(Date.parse(p.d[i]));
        const o = p.o[i] ?? p.c[i];
        const up = p.c[i] >= o;
        const color = up ? "var(--pos)" : "var(--neg)";
        nodes.push(
          s("line", {
            x1: tx,
            x2: tx,
            y1: y(p.h[i] ?? p.c[i]),
            y2: y(p.l[i] ?? p.c[i]),
            stroke: color,
            "stroke-width": 1,
          }),
        );
        const top = y(Math.max(o, p.c[i]));
        nodes.push(
          s("rect", {
            x: tx - Math.min(barW, 8) / 2,
            y: top,
            width: Math.min(barW, 8),
            height: Math.max(1, y(Math.min(o, p.c[i])) - top),
            fill: up ? "var(--surface)" : color,
            stroke: color,
            "stroke-width": 1,
          }),
        );
      }
    } else {
      nodes.push(
        path(
          idx.map((i) => [x(Date.parse(p.d[i])), y(p.c[i])]),
          "var(--ink-2)",
          1.5,
        ),
      );
    }
    const maPath = (ma, color) => {
      const pts = idx.filter((i) => ma[i] !== null).map((i) => [x(Date.parse(p.d[i])), y(ma[i])]);
      if (pts.length > 1) nodes.push(path(pts, color, 2));
    };
    maPath(ma50, "var(--s2)");
    maPath(ma200, "var(--s4)");
    // target and entry lines
    for (const l of lines) {
      if (l.y < lo || l.y > hi) continue;
      const color = l.tone === "pos" ? "var(--pos)" : l.tone === "neg" ? "var(--neg)" : "var(--axis)";
      nodes.push(
        s("line", {
          x1: L,
          x2: W - R,
          y1: y(l.y),
          y2: y(l.y),
          stroke: color,
          "stroke-width": 1.5,
          "stroke-dasharray": "5 4",
        }),
      );
      const t = s("text", { x: L + 4, y: y(l.y) - 4 });
      t.textContent = `${l.label} ${f2(l.y)}`;
      nodes.push(t);
    }
    // marks ahead (earnings, catalysts)
    let shown = 0;
    for (const mk of (spec.ahead && spec.ahead.marks) || []) {
      const t = Date.parse(mk.date);
      if (!(t > tLast && t <= t1)) continue;
      const color = mk.tone === "earn" ? "var(--warning-ink)" : "var(--accent)";
      nodes.push(s("line", { x1: x(t), x2: x(t), y1: T, y2: H - B, stroke: color, "stroke-width": 1.5 }));
      const label = s("text", { x: x(t) - 3, y: T + 12 + (shown++ % 3) * 13, "text-anchor": "end" });
      label.textContent = mk.label;
      nodes.push(label);
    }
    const cross = s("line", { y1: T, y2: H - B, stroke: "var(--axis)", "stroke-width": 1, visibility: "hidden" });
    const hit = s("rect", { x: L, y: 0, width: W - L - R, height: H, fill: "transparent" });
    nodes.push(cross, hit);
    svg.replaceChildren(...nodes);
    const show = (clientX) => {
      const r = svg.getBoundingClientRect();
      const t = t0 + ((clientX - r.left - L) / (W - L - R)) * (t1 - t0);
      let best = idx[0];
      for (const i of idx) if (Math.abs(Date.parse(p.d[i]) - t) < Math.abs(Date.parse(p.d[best]) - t)) best = i;
      const bx = x(Date.parse(p.d[best]));
      cross.setAttribute("x1", bx);
      cross.setAttribute("x2", bx);
      cross.setAttribute("visibility", "visible");
      const box = tooltip();
      box.replaceChildren(
        el("span", { class: "muted", text: dayLabel(p.d[best]) }),
        el("strong", { text: f2(p.c[best]) }),
        el("span", { text: `O ${f2(p.o[best])} · H ${f2(p.h[best])} · L ${f2(p.l[best])}` }),
        el("span", { class: "muted", text: `50d ${f2(ma50[best])} · 200d ${f2(ma200[best])}` }),
      );
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

  function path(points, color, width) {
    const d = points.map(([px, py], i) => `${i ? "L" : "M"}${px.toFixed(1)},${py.toFixed(1)}`).join("");
    return el("path", { svg: true, d, fill: "none", stroke: color, "stroke-width": width, "stroke-linejoin": "round" });
  }

  const buttons = el(
    "div",
    { class: "seg", role: "group", "aria-label": "Chart range" },
    RANGES.map(([label, bars]) =>
      el("button", {
        type: "button",
        "aria-pressed": String(state.bars === bars),
        text: label,
        onclick: (ev) => {
          state.bars = bars;
          if (spec.onRange) spec.onRange(bars);
          for (const b of ev.target.parentNode.children) b.setAttribute("aria-pressed", String(b === ev.target));
          draw();
        },
      }),
    ),
  );
  const legend = el(
    "div",
    { class: "legend-row" },
    el("span", {}, el("span", { class: "swatch-line", style: "background:var(--s2)" }), "50-day average"),
    el("span", {}, el("span", { class: "swatch-line", style: "background:var(--s4)" }), "200-day average"),
    el("span", {}, el("span", { class: "swatch-line dashed", style: "background:var(--pos)" }), "targets / entry"),
  );
  let timer;
  window.addEventListener("resize", () => {
    clearTimeout(timer);
    timer = setTimeout(draw, 150);
  });
  return { node: el("div", {}, el("div", { class: "toolbar" }, buttons), legend, svg), draw };
}
