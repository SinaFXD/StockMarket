// Sectors side by side: rotation map, sector cards (heatmap), growth vs valuation, cyclicals vs defensives, the
// full table and each sector's candidates. Data: data/sectors.json (pipeline/sectors/build.py).

import { chartSet, redraw, redrawOnResize, renderPanels } from "./charts.js";
import { el, loadJSON, setChildren, sparkline } from "./common.js";
import { fmt } from "./workbench.js";

const S = { data: null, cats: {}, growth: "eg1", sort: { key: "rs3m", dir: -1 }, set: chartSet(null) };
const has = (v) => v !== null && v !== undefined && Number.isFinite(v);
const GROUP = {
  cyclical: ["Cyclical", "var(--s2)"],
  sensitive: ["Sensitive", "var(--s1)"],
  defensive: ["Defensive", "var(--s3)"],
};
const QUAD = {
  leading: ["Leading", "tag-pos", "Beating the S&P 500 and gaining"],
  weakening: ["Weakening", "", "Beating the S&P 500 but losing momentum"],
  lagging: ["Lagging", "tag-neg", "Behind the S&P 500 and still losing"],
  improving: ["Improving", "", "Behind the S&P 500 but catching up"],
};
// signed percentage points, never "−0.0"
const pp = (v, d = 1) => {
  if (!has(v)) return "–";
  const r = Number(v.toFixed(d));
  return `${r > 0 ? "+" : r < 0 ? "−" : ""}${Math.abs(r).toFixed(d)}`;
};
const tone = (v) => (has(v) ? (v > 0 ? "up" : v < 0 ? "down" : "") : "");

// bubbles shrink on a phone; a bubble too small for its ticker gets the label beside it
const shrink = (W) => Math.max(0.55, Math.min(1, W / 800));
function etfLabel(etf, cx, cy, r) {
  const inside = r >= 13;
  const t = el("text", {
    svg: true,
    x: inside ? cx : cx + r + 3,
    y: cy + 4,
    "text-anchor": inside ? "middle" : "start",
    class: inside ? "rrg-label" : "rrg-label out",
  });
  t.textContent = etf;
  return t;
}

let tipNode = null;
function tip() {
  if (!tipNode) {
    tipNode = el("div", { class: "tooltip", hidden: true });
    document.body.append(tipNode);
  }
  return tipNode;
}
function showTip(ev, ...children) {
  const t = tip();
  t.replaceChildren(...children);
  t.hidden = false;
  const b = t.getBoundingClientRect();
  t.style.left = `${Math.min(window.innerWidth - b.width - 8, Math.max(8, ev.clientX - b.width / 2))}px`;
  t.style.top = `${Math.max(8, ev.clientY - b.height - 14)}px`;
}
const hideTip = () => tipNode && (tipNode.hidden = true);

// ---------- tiles ----------
function tiles() {
  const d = S.data;
  const g = d.groups || {};
  const a = d.agreement;
  const ranked = d.sectors.filter((s) => has(s.price.rs3m)).sort((x, y) => y.price.rs3m - x.price.rs3m);
  const tile = (label, value, foot, cls = "") =>
    el(
      "div",
      { class: "card tile" },
      el("div", { class: "tile-label", text: label }),
      el("div", { class: `tile-value small ${cls}`, text: value }),
      el("div", { class: "tile-foot", text: foot }),
    );
  const market = a ? { cyclical: "Cyclicals", defensive: "Defensives", mixed: "No clear preference" }[a.market] : "–";
  return el(
    "div",
    { class: "tiles" },
    tile(
      "The market prefers",
      market,
      has(g.spread_3m) ? `cyclicals vs defensives over 3 months: ${pp(g.spread_3m)} pp` : "",
      a && a.market === "cyclical" ? "up" : a && a.market === "defensive" ? "down" : "",
    ),
    tile(
      "Macro bias",
      d.bias.label || "–",
      a
        ? {
            agree: "the market agrees with the macro bias",
            disagree: "the market disagrees: read both (lesson 1)",
            mixed: "no clear signal from the rotation",
            "no bias": "",
          }[a.verdict]
        : "",
      d.bias.score > 0 ? "up" : d.bias.score < 0 ? "down" : "",
    ),
    tile(
      "Strongest over 3 months",
      ranked
        .slice(0, 2)
        .map((s) => s.etf)
        .join(" · ") || "–",
      ranked
        .slice(0, 2)
        .map((s) => `${s.sector} ${pp(s.price.rs3m)} pp`)
        .join(", "),
      "up",
    ),
    tile(
      "Weakest over 3 months",
      ranked
        .slice(-2)
        .reverse()
        .map((s) => s.etf)
        .join(" · ") || "–",
      ranked
        .slice(-2)
        .reverse()
        .map((s) => `${s.sector} ${pp(s.price.rs3m)} pp`)
        .join(", "),
      "down",
    ),
  );
}

// ---------- rotation map ----------
function rotationMap() {
  const pts = S.data.sectors.filter((s) => s.rotation);
  const svg = el("svg", {
    class: "rrg",
    role: "img",
    "aria-label": "Rotation map: relative strength against its change",
  });
  const draw = () => {
    const W = svg.clientWidth || 700;
    const H = svg.clientHeight || 420;
    const P = 36;
    const mx = Math.max(4, ...pts.map((s) => Math.abs(s.rotation.rs))) * 1.15;
    const my = Math.max(2, ...pts.map((s) => Math.abs(s.rotation.change))) * 1.2;
    const x = (v) => P + ((v + mx) / (2 * mx)) * (W - 2 * P);
    const y = (v) => H - P - ((v + my) / (2 * my)) * (H - 2 * P);
    const s = (tag, attrs) => el(tag, { svg: true, ...attrs });
    const nodes = [];
    const quad = (x0, y0, x1, y1, fill, label, lx, ly, anchor) => {
      nodes.push(
        s("rect", {
          x: Math.min(x0, x1),
          y: Math.min(y0, y1),
          width: Math.abs(x1 - x0),
          height: Math.abs(y1 - y0),
          fill,
        }),
      );
      const t = s("text", { x: lx, y: ly, "text-anchor": anchor, class: "rrg-quad" });
      t.textContent = label;
      nodes.push(t);
    };
    quad(x(0), y(0), W - P, P, "var(--pos-wash)", "LEADING", W - P - 8, P + 18, "end");
    quad(x(0), y(0), W - P, H - P, "var(--neu-wash)", "WEAKENING", W - P - 8, H - P - 10, "end");
    quad(P, y(0), x(0), H - P, "var(--neg-wash)", "LAGGING", P + 8, H - P - 10, "start");
    quad(P, y(0), x(0), P, "var(--neu-wash)", "IMPROVING", P + 8, P + 18, "start");
    nodes.push(s("line", { x1: x(0), x2: x(0), y1: P, y2: H - P, stroke: "var(--axis)", "stroke-width": 1.5 }));
    nodes.push(s("line", { x1: P, x2: W - P, y1: y(0), y2: y(0), stroke: "var(--axis)", "stroke-width": 1.5 }));
    const ax = s("text", { x: W - P, y: H - 8, "text-anchor": "end" });
    ax.textContent = "→ relative strength vs S&P 500, 3 months (pp)";
    const ay = s("text", { x: 8, y: 14 });
    ay.textContent = "↑ change over the last month (pp)";
    nodes.push(ax, ay);
    const caps = pts.map((p) => p.fundamentals.mcap || 1);
    const cmax = Math.max(...caps);
    for (const p of pts) {
      const r = (14 + 12 * Math.sqrt((p.fundamentals.mcap || 1) / cmax)) * shrink(W);
      const cx = x(p.rotation.rs);
      const cy = y(p.rotation.change);
      const dot = s("circle", {
        cx,
        cy,
        r,
        fill: GROUP[p.group][1],
        "fill-opacity": 0.85,
        stroke: "var(--surface)",
        "stroke-width": 2,
        class: "rrg-dot",
        tabindex: 0,
      });
      const label = etfLabel(p.etf, cx, cy, r);
      const info = (ev) =>
        showTip(
          ev,
          el("strong", { text: `${p.sector} (${p.etf})` }),
          el("span", { text: `${QUAD[p.rotation.quadrant][0]}: ${QUAD[p.rotation.quadrant][2].toLowerCase()}` }),
          el("span", {
            class: "muted",
            text: `3m vs S&P ${pp(p.rotation.rs)} pp · last month ${pp(p.rotation.change)} pp`,
          }),
        );
      dot.addEventListener("pointermove", info);
      dot.addEventListener("pointerleave", hideTip);
      dot.addEventListener("click", () =>
        document.getElementById(`sec-${p.etf}`).scrollIntoView({ behavior: "smooth", block: "center" }),
      );
      nodes.push(dot, label);
    }
    svg.replaceChildren(...nodes);
  };
  window.addEventListener("resize", draw);
  requestAnimationFrame(draw);
  return el(
    "section",
    { class: "card panel sec-block" },
    el("h2", { class: "panel-title", text: "Rotation map: where is the money going?" }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text: "Each sector ETF against the S&P 500: across, how far it is ahead or behind over 3 months; up, whether that gap grew or shrank in the last month. Sectors usually travel clockwise: improving → leading → weakening → lagging. Bubble size = market cap of the sector's stocks; colour = group. Click a bubble to jump to its card.",
    }),
    svg,
    el(
      "div",
      { class: "legend-row" },
      Object.values(GROUP).map(([label, color]) =>
        el("span", {}, el("span", { class: "swatch-dot", style: `background:${color}` }), label),
      ),
    ),
  );
}

// ---------- sector cards ----------
function breadth(f) {
  if (!has(f.rev_up)) return el("span", { class: "muted", text: "–" });
  const flat = Math.max(0, 100 - f.rev_up - f.rev_down);
  return el(
    "div",
    {
      class: "breadth",
      title: `${f.rev_up}% raised, ${f.rev_down}% cut, ${flat.toFixed(0)}% unchanged (EPS1 consensus, 90 days)`,
    },
    el("span", { class: "b-up", style: `width:${f.rev_up}%` }),
    el("span", { class: "b-flat", style: `width:${flat}%` }),
    el("span", { class: "b-down", style: `width:${f.rev_down}%` }),
  );
}

function card(s) {
  const f = s.fundamentals;
  const pr = s.price;
  const rs = pr.rs3m;
  const strength = has(rs) ? Math.min(1, Math.abs(rs) / 12) : 0;
  const wash = has(rs)
    ? `color-mix(in srgb, ${rs >= 0 ? "var(--pos)" : "var(--neg)"} ${Math.round(4 + strength * 18)}%, var(--surface))`
    : "var(--surface)";
  const q = s.rotation && QUAD[s.rotation.quadrant];
  const t = f.types || {};
  const macro = s.macro;
  return el(
    "article",
    { class: "card sec-card", id: `sec-${s.etf}`, style: `background:${wash}` },
    el(
      "header",
      { class: "sec-card-head" },
      el(
        "div",
        {},
        el("h3", { text: s.sector }),
        el("span", { class: "sec-etf", text: s.etf }),
        el(
          "span",
          { class: "tag" },
          el("span", { class: "swatch-dot", style: `background:${GROUP[s.group][1]}` }),
          GROUP[s.group][0],
        ),
      ),
      q ? el("span", { class: `tag ${q[1]}`, title: q[2], text: q[0] }) : null,
    ),
    el(
      "div",
      { class: "sec-rs" },
      el(
        "div",
        {},
        el("b", { class: `sec-big ${tone(rs)}`, text: `${pp(rs)} pp` }),
        el("span", { class: "sub", text: "vs S&P 500, 3 months" }),
      ),
      s.relative_line.length > 1
        ? sparkline(s.relative_line, { label: `${s.etf} relative to SPY`, frequency: "daily" })
        : null,
    ),
    el(
      "p",
      { class: "facts" },
      el("span", {}, "1m ", el("b", { class: tone(pr.rs1m), text: pp(pr.rs1m) })),
      el("span", {}, "6m ", el("b", { class: tone(pr.rs6m), text: pp(pr.rs6m) })),
      el("span", {}, "ETF 3m ", el("b", { text: fmt.pct(pr.r3m) })),
    ),
    el(
      "div",
      { class: "sec-grid" },
      el(
        "div",
        {},
        el("span", { class: "sub", text: "EPS growth (EG1 / EG2)" }),
        el("b", { text: `${fmt.pct(f.eg1, 0)} / ${fmt.pct(f.eg2, 0)}` }),
      ),
      el(
        "div",
        {},
        el("span", { class: "sub", text: "P/E · PEG" }),
        el("b", { text: `${has(f.pe1) ? f.pe1.toFixed(1) : "–"} · ${has(f.peg1) ? f.peg1.toFixed(2) : "–"}` }),
      ),
      el(
        "div",
        {},
        el("span", { class: "sub", text: "Outliers + / −" }),
        el(
          "b",
          {},
          el("span", { class: "up", text: String(t.positive || 0) }),
          " / ",
          el("span", { class: "down", text: String((t.negative || 0) + (t.post_growth || 0)) }),
        ),
      ),
      el(
        "div",
        {},
        el("span", { class: "sub", text: "Macro wind" }),
        macro
          ? el("b", { class: tone(macro.score), title: macroTitle(macro), text: pp(macro.score, 2) })
          : el("b", { class: "muted", text: "–" }),
      ),
    ),
    el(
      "div",
      { class: "sec-breadth" },
      el("span", { class: "sub", text: "Estimate revisions, 90 days (raised · unchanged · cut)" }),
      breadth(f),
    ),
    el(
      "footer",
      { class: "sec-card-foot" },
      el("a", {
        class: "btn btn-small",
        href: `screener.html?sector=${encodeURIComponent(s.sector)}`,
        text: `Screener: ${f.n} stocks →`,
      }),
      el("a", {
        class: "btn btn-small",
        href: `#cand-${s.etf}`,
        text: "Candidates",
        onclick: () => (document.getElementById(`cand-${s.etf}`).open = true),
      }),
    ),
  );
}

function macroTitle(m) {
  const fmtList = (xs) => xs.map(([i, n]) => `${i} (${n > 0 ? "+" : ""}${n})`).join(", ");
  return `Stock-weighted net of the macro drivers on its industries. Tailwinds: ${fmtList(m.tailwinds) || "none"}. Headwinds: ${fmtList(m.headwinds) || "none"}.`;
}

const byStrength = () => S.data.sectors.slice().sort((a, b) => (b.price.rs3m ?? -99) - (a.price.rs3m ?? -99));

function cards() {
  const list = byStrength();
  return el(
    "section",
    { class: "sec-block" },
    el("h2", { class: "sec-h2", text: "The eleven sectors, strongest first" }),
    el("p", {
      class: "section-note",
      text: "Card colour = how far the sector ETF is ahead (blue) or behind (red) the S&P 500 over 3 months. The line is the ETF divided by the S&P 500 over 6 months (rising = beating the market). Fundamentals are medians of the sector's clean stocks; revisions show how many had their EPS estimate raised or cut by 1% or more in 90 days.",
    }),
    el("div", { class: "sec-cards" }, list.map(card)),
  );
}

// ---------- growth vs valuation ----------
function bubbles() {
  const svg = el("svg", { class: "bubbles", role: "img", "aria-label": "Sectors: EPS growth against P/E" });
  const pts = () => S.data.sectors.filter((s) => has(s.fundamentals[S.growth]) && has(s.fundamentals.pe1));
  const draw = () => {
    const list = pts();
    if (!list.length) return svg.replaceChildren();
    const W = svg.clientWidth || 700;
    const H = svg.clientHeight || 380;
    const L = 46;
    const R = 20;
    const T = 16;
    const B = 34;
    const xs = list.map((s) => s.fundamentals[S.growth]);
    const ys = list.map((s) => s.fundamentals.pe1);
    const [x0, x1] = [Math.min(0, ...xs) - 2, Math.max(...xs) + 3];
    const [y0, y1] = [Math.max(0, Math.min(...ys) - 3), Math.max(...ys) + 3];
    const x = (v) => L + ((v - x0) / (x1 - x0)) * (W - L - R);
    const y = (v) => H - B - ((v - y0) / (y1 - y0)) * (H - T - B);
    const s = (tag, attrs) => el(tag, { svg: true, ...attrs });
    const nodes = [];
    const mx = list.reduce((a, b) => a + b.fundamentals[S.growth], 0) / list.length;
    const my = list.reduce((a, b) => a + b.fundamentals.pe1, 0) / list.length;
    nodes.push(s("line", { x1: x(mx), x2: x(mx), y1: T, y2: H - B, stroke: "var(--axis)", "stroke-dasharray": "4 4" }));
    nodes.push(s("line", { x1: L, x2: W - R, y1: y(my), y2: y(my), stroke: "var(--axis)", "stroke-dasharray": "4 4" }));
    const corner = (tx, ty, text, anchor) => {
      const t = s("text", { x: tx, y: ty, "text-anchor": anchor, class: "rrg-quad" });
      t.textContent = text;
      nodes.push(t);
    };
    corner(W - R - 4, H - B - 8, "FAST GROWTH, CHEAP", "end");
    corner(L + 4, T + 12, "SLOW GROWTH, EXPENSIVE", "start");
    for (let v = Math.ceil(y0 / 5) * 5; v <= y1; v += 5) {
      const t = s("text", { x: L - 6, y: y(v) + 4, "text-anchor": "end" });
      t.textContent = String(v);
      nodes.push(t);
    }
    for (let v = Math.ceil(x0 / 5) * 5; v <= x1; v += 5) {
      const t = s("text", { x: x(v), y: H - B + 16, "text-anchor": "middle" });
      t.textContent = `${v}%`;
      nodes.push(t);
    }
    const ax = s("text", { x: W - R, y: H - 4, "text-anchor": "end" });
    ax.textContent = `median ${S.growth === "eg1" ? "EPS growth this year (EG1)" : "EPS growth next year (EG2)"} →`;
    const ay = s("text", { x: 4, y: 12 });
    ay.textContent = "↑ median P/E (PE1)";
    nodes.push(ax, ay);
    const cmax = Math.max(...list.map((p) => p.fundamentals.mcap || 1));
    for (const p of list) {
      const f = p.fundamentals;
      const r = (14 + 18 * Math.sqrt((f.mcap || 1) / cmax)) * shrink(W);
      const cx = x(f[S.growth]);
      const cy = y(f.pe1);
      const dot = s("circle", {
        cx,
        cy,
        r,
        fill: GROUP[p.group][1],
        "fill-opacity": 0.75,
        stroke: "var(--surface)",
        "stroke-width": 2,
        class: "rrg-dot",
      });
      const label = etfLabel(p.etf, cx, cy, r);
      dot.addEventListener("pointermove", (ev) =>
        showTip(
          ev,
          el("strong", { text: p.sector }),
          el("span", { text: `EG1 ${fmt.pct(f.eg1)} · EG2 ${fmt.pct(f.eg2)}` }),
          el("span", {
            text: `P/E ${has(f.pe1) ? f.pe1.toFixed(1) : "–"} · PEG ${has(f.peg1) ? f.peg1.toFixed(2) : "–"}`,
          }),
          el("span", { class: "muted", text: `market cap ${fmt.money(f.mcap)} · ${f.n_clean} clean stocks` }),
        ),
      );
      dot.addEventListener("pointerleave", hideTip);
      nodes.push(dot, label);
    }
    svg.replaceChildren(...nodes);
  };
  window.addEventListener("resize", draw);
  requestAnimationFrame(draw);
  return el(
    "section",
    { class: "card panel sec-block" },
    el("h2", { class: "panel-title", text: "Growth vs valuation" }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text: "Where each sector sits on expected EPS growth and P/E (medians of its clean stocks). Bottom-right = growth on sale; top-left = paying a lot for little growth. The dashed lines are the averages of the sectors.",
    }),
    el(
      "div",
      { class: "seg", role: "group", "aria-label": "Growth year" },
      [
        ["eg1", "This year (EG1)"],
        ["eg2", "Next year (EG2)"],
      ].map(([k, label]) =>
        el("button", {
          type: "button",
          "aria-pressed": String(S.growth === k),
          text: label,
          onclick: (ev) => {
            S.growth = k;
            for (const b of ev.target.parentNode.children) b.setAttribute("aria-pressed", String(b === ev.target));
            draw();
          },
        }),
      ),
    ),
    svg,
  );
}

// ---------- cyclicals vs defensives ----------
function groupsChart() {
  const g = S.data.groups;
  if (!g || !g.ratio || g.ratio.length < 2) return null;
  const panel = {
    title: "Cyclicals and sensitives vs defensives (start = 100)",
    unit: "index",
    note: "equal-weight sector ETFs, each relative to the S&P 500; rising = the market is buying risk",
    series: [
      { name: "Cyclical + sensitive ÷ defensive", dates: g.ratio.map((r) => r[0]), values: g.ratio.map((r) => r[1]) },
    ],
    refs: [{ y: 100, label: "start" }],
    zones: [],
  };
  const grp = (k) =>
    el(
      "span",
      {},
      el("span", { class: "swatch-dot", style: `background:${GROUP[k][1]}` }),
      `${GROUP[k][0]} `,
      el("b", { class: tone(g[`${k}_3m`]), text: `${pp(g[`${k}_3m`])} pp` }),
    );
  return el(
    "section",
    { class: "sec-block" },
    el("h2", { class: "sec-h2", text: "Risk appetite: cyclicals vs defensives" }),
    el(
      "p",
      { class: "facts" },
      el("span", { class: "muted", text: "3 months vs the S&P 500:" }),
      grp("cyclical"),
      grp("sensitive"),
      grp("defensive"),
    ),
    ...renderPanels(S.set, [panel]),
  );
}

// ---------- table ----------
const COLS = [
  ["sector", "Sector", (s) => s.sector, (v) => v],
  ["rs1m", "1m vs S&P", (s) => s.price.rs1m, (v) => pp(v)],
  ["rs3m", "3m vs S&P", (s) => s.price.rs3m, (v) => pp(v)],
  ["rs6m", "6m vs S&P", (s) => s.price.rs6m, (v) => pp(v)],
  ["eg1", "EG1", (s) => s.fundamentals.eg1, (v) => fmt.pct(v)],
  ["eg2", "EG2", (s) => s.fundamentals.eg2, (v) => fmt.pct(v)],
  ["pe1", "PE1", (s) => s.fundamentals.pe1, (v) => (has(v) ? v.toFixed(1) : "–")],
  ["peg1", "PEG1", (s) => s.fundamentals.peg1, (v) => (has(v) ? v.toFixed(2) : "–")],
  ["rg1", "Sales g1", (s) => s.fundamentals.rg1, (v) => fmt.pct(v)],
  [
    "rev",
    "Revisions ↑−↓",
    (s) => (has(s.fundamentals.rev_up) ? s.fundamentals.rev_up - s.fundamentals.rev_down : null),
    (v) => pp(v, 0),
  ],
  ["pos", "Pos. outliers", (s) => (s.fundamentals.types || {}).positive || 0, (v) => String(v)],
  [
    "neg",
    "Neg. + post-growth",
    (s) => ((s.fundamentals.types || {}).negative || 0) + ((s.fundamentals.types || {}).post_growth || 0),
    (v) => String(v),
  ],
  ["macro", "Macro wind", (s) => (s.macro ? s.macro.score : null), (v) => pp(v, 2)],
  ["rv", "Volatility", (s) => s.fundamentals.rv, (v) => (has(v) ? `${v.toFixed(0)}%` : "–")],
];

function table() {
  const { key, dir } = S.sort;
  const col = COLS.find((c) => c[0] === key);
  const rows = S.data.sectors.slice().sort((a, b) => {
    const x = col[2](a);
    const y = col[2](b);
    if (x === null || x === undefined) return 1;
    if (y === null || y === undefined) return -1;
    return (x < y ? -1 : x > y ? 1 : 0) * dir;
  });
  return el(
    "section",
    { class: "card panel sec-block", id: "sec-table" },
    el("h2", { class: "panel-title", text: "All the numbers" }),
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
            COLS.map(([k, label]) =>
              el(
                "th",
                {
                  class: "sortable",
                  "aria-sort": k === key ? (dir > 0 ? "ascending" : "descending") : null,
                  onclick: () => {
                    S.sort = { key: k, dir: k === key ? -dir : k === "sector" ? 1 : -1 };
                    document.getElementById("sec-table").replaceWith(table());
                  },
                },
                label,
                k === key ? (dir > 0 ? " ▲" : " ▼") : "",
              ),
            ),
          ),
        ),
        el(
          "tbody",
          {},
          rows.map((s) =>
            el(
              "tr",
              {},
              COLS.map(([k, , get, f], i) => {
                const v = get(s);
                if (i === 0)
                  return el(
                    "td",
                    {},
                    el("a", { href: `#sec-${s.etf}`, text: v }),
                    el("span", { class: "sub", text: `${s.etf} · ${GROUP[s.group][0]}` }),
                  );
                const signed = ["rs1m", "rs3m", "rs6m", "eg1", "eg2", "rg1", "rev", "macro"].includes(k);
                return el("td", { class: signed ? tone(v) : "", text: f(v) });
              }),
            ),
          ),
        ),
      ),
    ),
  );
}

// ---------- candidates ----------
function candidates() {
  const list = (items, side) =>
    items.length
      ? el(
          "ul",
          { class: "cand-list" },
          items.map((c) =>
            el(
              "li",
              {},
              el("a", { href: `stock.html?t=${encodeURIComponent(c.t)}` }, el("b", { text: c.t })),
              el("span", { class: "muted", text: ` ${c.name || ""}` }),
              el("span", {
                class: `tag ${side === "long" ? "tag-pos" : "tag-neg"}`,
                text: (S.cats[c.cls] || {}).label || c.cls,
              }),
              el("span", {
                class: "sub",
                text: `EG1 ${fmt.pct(c.eg1, 0)} · EG2 ${fmt.pct(c.eg2, 0)} · ${fmt.money(c.mcap)}${c.vol_ok ? " · vol ✓" : ""}`,
              }),
            ),
          ),
        )
      : el("p", { class: "muted", text: "none" });
  return el(
    "section",
    { class: "sec-block" },
    el("h2", { class: "sec-h2", text: "Candidates by sector" }),
    el("p", {
      class: "section-note",
      text: "The largest long candidates (positive outliers) and short candidates (negative outliers and post-growth) of each sector, those passing the volatility filter first. Open one to work it through the trade-idea template.",
    }),
    el(
      "div",
      { class: "cand-grid" },
      byStrength().map((s) =>
        el(
          "details",
          { class: "card cand-card", id: `cand-${s.etf}` },
          el("summary", {}, el("b", { text: s.sector }), el("span", { class: "muted", text: ` ${s.etf}` })),
          el("h4", { text: "Long side" }),
          list(s.long, "long"),
          el("h4", { text: "Short side" }),
          list(s.short, "short"),
        ),
      ),
    ),
  );
}

async function main() {
  const [data, stocks] = await Promise.all([
    loadJSON("data/sectors.json").catch(() => null),
    loadJSON("data/screener/stocks.json").catch(() => null),
  ]);
  if (!data) {
    setChildren(
      document.getElementById("content"),
      el("div", { class: "card notice", text: "No sector data yet: it is built by the daily update." }),
    );
    return;
  }
  S.data = data;
  S.cats = (stocks && stocks.categories) || {};
  setChildren(
    document.getElementById("content"),
    tiles(),
    rotationMap(),
    cards(),
    bubbles(),
    groupsChart(),
    table(),
    candidates(),
    el("p", {
      class: "section-note",
      text: `Fundamentals as of ${data.as_of}; prices to ${data.prices_as_of}. Groups follow Morningstar's super-sectors (cyclical, sensitive, defensive). Context only: nothing here changes the bias or the types.`,
    }),
  );
  redraw(S.set);
  redrawOnResize(S.set);
}

main();
