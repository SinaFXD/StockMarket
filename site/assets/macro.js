// Macro Desk: bias card, block tiles, signal board with overrides, "as of" picker and the bias history chart.
// The bias arithmetic mirrors pipeline/signals/bias.py so overrides recalculate in the browser.

import { boardCsv, briefText } from "./brief.js";
import { el, loadJSON } from "./common.js";

const STORE = "ptm.overrides.v1";
const STATES = { net_long: "Net long", neutral: "Neutral (balanced)", net_short: "Net short" };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const STRIP_MONTHS = 36;

const state = {
  latest: null,
  history: null,
  years: {},
  current: null,
  isLatest: true,
  overrides: {},
  regime: null,
  view: null, // what is on screen: {bias, alerts, overrides}
};

// ---------- overrides (this browser only) ----------
function loadOverrides() {
  try {
    return JSON.parse(localStorage.getItem(STORE) || "{}") || {};
  } catch {
    return {};
  }
}

function saveOverrides() {
  try {
    localStorage.setItem(STORE, JSON.stringify(state.overrides));
  } catch {
    /* storage unavailable: overrides last for this visit only */
  }
}

// ---------- arithmetic (same as bias.py) ----------
function combine(signals, threshold, overrides) {
  const blocks = {};
  for (const [key, label] of Object.entries(state.latest.blocks)) {
    const members = signals.filter((s) => s.block === key);
    const used = members.map((s) => (s.id in overrides ? overrides[s.id] : s.score)).filter((x) => x !== null);
    blocks[key] = {
      label,
      score: used.length ? used.reduce((a, b) => a + b, 0) / used.length : null,
      used: used.length,
      total: members.length,
    };
  }
  const scores = Object.values(blocks)
    .map((b) => b.score)
    .filter((x) => x !== null);
  const score = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null;
  const st = score === null ? null : score >= threshold ? "net_long" : score <= -threshold ? "net_short" : "neutral";
  return {
    score,
    state: st,
    label: STATES[st] || "No reading",
    blocks,
    used: Object.values(blocks).reduce((a, b) => a + b.used, 0),
    total: signals.length,
  };
}

// Data vs prices (bias.py price_alert): redone here so it follows the user's overrides.
function alertsWith(snap, bias, overrides) {
  const pa = state.latest.price_alerts;
  const list = snap.alerts || [];
  if (!pa) return list;
  const sp = snap.signals.find((s) => s.id === "sp500");
  const spScore = sp ? (sp.id in overrides ? overrides[sp.id] : sp.score) : null;
  const kind =
    bias.state === "net_short" && spScore === 1
      ? "data_weak_price_up"
      : bias.state === "net_long" && spScore === -1
        ? "data_strong_price_down"
        : null;
  const rest = list.filter((a) => !a.startsWith(pa.prefix));
  return kind ? [pa.texts[kind], ...rest] : rest;
}

// ---------- formatting ----------
const tone = (x) => (x === null || x === undefined ? "none" : x > 0 ? "pos" : x < 0 ? "neg" : "zero");
const fmtScore = (x) =>
  x === null || x === undefined ? "–" : `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x).toFixed(2)}`;
const monthLabel = (m) => `${MONTHS[Number(m.slice(5, 7)) - 1]} ${m.slice(0, 4)}`;

function scorePill(score) {
  if (score === null || score === undefined) return el("span", { class: "score none", text: "awaiting" });
  const icon = score > 0 ? "▲" : score < 0 ? "▼" : "●";
  const text = score > 0 ? "+1" : score < 0 ? "−1" : "0";
  return el("span", { class: `score ${tone(score)}` }, el("span", { "aria-hidden": "true", text: icon }), text);
}

// ---------- rendering ----------
function renderBias(bias) {
  const pos = bias.score === null ? 50 : ((bias.score + 1) / 2) * 100;
  const cls = bias.state === "net_long" ? "pos" : bias.state === "net_short" ? "neg" : "";
  const thr = state.latest.params.bias_threshold;
  const tick = (v, label) => {
    const shift = v <= -1 ? "0" : v >= 1 ? "-100%" : "-50%"; // keep the end labels inside the card
    return el("span", { style: `left:${((v + 1) / 2) * 100}%;transform:translateX(${shift})`, text: label });
  };
  document.getElementById("bias").replaceChildren(
    el(
      "div",
      {},
      el("div", { class: "bias-label", text: "Portfolio bias" }),
      el("div", { class: `bias-state ${cls}`, text: bias.label }),
      el("div", {
        class: "bias-sub",
        text: `Score ${fmtScore(bias.score)} from ${bias.used} of ${bias.total} indicators · net long ≥ +${thr}, net short ≤ −${thr}`,
      }),
    ),
    el(
      "div",
      { class: "meter", role: "img", "aria-label": `Bias score ${fmtScore(bias.score)} on a scale from −1 to +1` },
      el("div", { class: "meter-track" }),
      bias.score === null ? null : el("div", { class: "meter-mark", style: `left:${pos}%` }),
      el(
        "div",
        { class: "meter-ticks" },
        tick(-1, "−1 short"),
        tick(-thr, `−${thr}`),
        tick(0, "0"),
        tick(thr, `+${thr}`),
        tick(1, "+1 long"),
      ),
    ),
  );
  document
    .getElementById("blocks")
    .replaceChildren(
      ...Object.values(bias.blocks).map((b) =>
        el(
          "div",
          { class: "card tile block-tile" },
          el("div", { class: "tile-label", text: b.label }),
          el("div", { class: "tile-value" }, el("span", { class: `score ${tone(b.score)}`, text: fmtScore(b.score) })),
          el("div", { class: "tile-foot muted", text: `${b.used} of ${b.total} indicators` }),
        ),
      ),
    );
}

function renderNotes(id, items, empty, cls = "") {
  const box = document.getElementById(id);
  box.replaceChildren(
    items.length ? el("ul", { class: `notes-list ${cls}` }, items) : el("p", { class: "muted", text: empty }),
  );
}

function changesFor(index) {
  // compare a history month with the month before it (used for past "as of" views)
  const h = state.history;
  if (index < 1) return [];
  const out = [];
  if (h.bias[index] !== h.bias[index - 1]) {
    out.push({
      name: "Portfolio bias",
      from: h.bias[index - 1],
      to: h.bias[index],
      from_state: STATES[h.state[index - 1]] || "–",
      to_state: STATES[h.state[index]] || "–",
      bias: true,
    });
  }
  for (const s of state.current.signals) {
    const arr = h.signals[s.id] || [];
    if (arr[index] !== arr[index - 1]) out.push({ name: s.name, from: arr[index - 1], to: arr[index] });
  }
  return out;
}

function changeItems() {
  return state.isLatest
    ? state.latest.what_changed
    : changesFor(state.history.months.indexOf(state.current.as_of.slice(0, 7)));
}

function renderChanges() {
  renderNotes(
    "changes",
    changeItems().map((c) =>
      el(
        "li",
        {},
        el("strong", { text: c.name }),
        c.id === "bias" || c.bias
          ? el("span", { text: `${fmtScore(c.from)} → ${fmtScore(c.to)} (${c.from_state} → ${c.to_state})` })
          : el("span", {}, scorePill(c.from), " → ", scorePill(c.to)),
        c.to_state && !(c.id === "bias" || c.bias) ? el("span", { class: "muted", text: c.to_state }) : null,
      ),
    ),
    "No score changed in the last month.",
    "changes",
  );
}

function strip(id, asOfMonth) {
  const h = state.history;
  const end = asOfMonth ? h.months.indexOf(asOfMonth) : h.months.length - 1;
  const start = Math.max(0, end - STRIP_MONTHS + 1);
  const scores = (h.signals[id] || []).slice(start, end + 1);
  const months = h.months.slice(start, end + 1);
  if (!scores.length) return null;
  return el(
    "div",
    {},
    el(
      "div",
      { class: "strip", role: "img", "aria-label": `Monthly score for the last ${scores.length} months` },
      scores.map((x, i) =>
        el("span", {
          class: x === null ? "none" : x > 0 ? "pos" : x < 0 ? "neg" : "zero",
          title: `${monthLabel(months[i])}: ${x === null ? "awaiting data" : x > 0 ? "+1" : x < 0 ? "−1" : "0"}`,
        }),
      ),
    ),
    el(
      "div",
      { class: "strip-caption" },
      el("span", { text: monthLabel(months[0]) }),
      el("span", { text: monthLabel(months[months.length - 1]) }),
    ),
  );
}

function overrideControl(s) {
  const current = s.id in state.overrides ? String(state.overrides[s.id]) : "auto";
  const options = [
    ["auto", "Auto"],
    ["1", "+1"],
    ["0", "0"],
    ["-1", "−1"],
  ];
  return el(
    "div",
    { class: "override" },
    el("span", { text: "Your reading:" }),
    el(
      "div",
      { class: "seg", role: "group", "aria-label": `Override ${s.name}` },
      options.map(([value, label]) =>
        el("button", {
          type: "button",
          "aria-pressed": String(current === value),
          text: label,
          onclick: () => {
            if (value === "auto") delete state.overrides[s.id];
            else state.overrides[s.id] = Number(value);
            saveOverrides();
            render();
          },
        }),
      ),
    ),
  );
}

function signalCard(s) {
  const overridden = state.isLatest && s.id in state.overrides;
  const meta = [];
  if (s.as_of) meta.push(`Data: ${s.as_of}`);
  if (s.percentile_10y !== null && s.percentile_10y !== undefined)
    meta.push(`10y percentile: ${Math.round(s.percentile_10y)}`);
  if (s.revised) meta.push("revised data (no real-time vintage for this date)");
  return el(
    "article",
    { class: `card signal ${s.status === "awaiting" ? "awaiting" : ""} ${overridden ? "overridden" : ""}` },
    el(
      "div",
      { class: "signal-head" },
      el(
        "div",
        {},
        el("div", { class: "signal-name", text: s.name }),
        el("div", { class: "signal-state", text: s.state }),
      ),
      el(
        "div",
        { style: "display:grid;gap:4px;justify-items:end" },
        scorePill(overridden ? state.overrides[s.id] : s.score),
        overridden
          ? el("span", {
              class: "muted",
              style: "font-size:11.5px",
              text: `auto ${s.score === null ? "–" : s.score > 0 ? "+1" : s.score}`,
            })
          : null,
      ),
    ),
    el("p", { class: "signal-reason", text: s.reason_en }),
    s.flags && s.flags.length
      ? el(
          "ul",
          { class: "signal-flags" },
          s.flags.map((f) => el("li", { text: f })),
        )
      : null,
    strip(s.id, state.isLatest ? null : state.current.as_of.slice(0, 7)),
    el(
      "div",
      { class: "signal-meta" },
      meta.map((x) => el("span", { text: x })),
    ),
    el(
      "details",
      {},
      el("summary", { class: "muted", style: "font-size:12.5px;cursor:pointer", text: "Rule" }),
      el("p", { class: "muted", style: "font-size:12.5px;margin:6px 0 0", text: s.rule }),
    ),
    el("a", {
      class: "detail-link",
      href: `indicator.html?id=${encodeURIComponent(s.id)}`,
      text: "Chart, components & reading guide →",
    }),
    state.isLatest ? overrideControl(s) : null,
  );
}

function renderBoard() {
  const sections = Object.entries(state.latest.blocks).map(([key, label]) => {
    const members = state.current.signals.filter((s) => s.block === key);
    return el(
      "section",
      { "aria-label": label },
      el("h2", { text: label }),
      el("div", { class: "signal-grid" }, members.map(signalCard)),
    );
  });
  document.getElementById("board").replaceChildren(...sections);
}

function render() {
  const snap = state.current;
  const overrides = state.isLatest ? state.overrides : {};
  const bias = combine(snap.signals, state.latest.params.bias_threshold, overrides);
  const alerts = alertsWith(snap, bias, overrides);
  state.view = { bias, alerts, overrides };
  renderBias(bias);
  renderChanges();
  renderNotes(
    "alerts",
    alerts.map((a) => el("li", { text: a })),
    "No disagreements between blocks.",
  );
  renderBoard();
  const n = Object.keys(state.overrides).length;
  document.getElementById("reset").disabled = !n;
  document.getElementById("override-note").textContent = !state.isLatest
    ? "Past months show the automatic reading (overrides apply to today only)."
    : n
      ? `${n} override${n > 1 ? "s" : ""} active, saved in this browser.`
      : "";
  drawChart();
}

// ---------- confirmers (coincident & lagging, not scored) ----------
async function renderConfirmers() {
  const box = document.getElementById("confirmers");
  let c;
  try {
    c = await loadJSON("data/macro/confirmers.json");
  } catch {
    box.replaceChildren(el("p", { class: "muted", text: "No confirmer data yet." }));
    return;
  }
  const toneLabel = { 1: ["Supportive", "up"], 0: ["Neutral", ""], "-1": ["Weak", "down"] };
  const num = (v) => (v === null || v === undefined ? "–" : v.toLocaleString("en-US", { maximumFractionDigits: 1 }));
  const row = (i) => {
    const [label, cls] = i.tone === null ? [i.direction, ""] : toneLabel[i.tone];
    return el(
      "tr",
      {},
      el("td", {}, el("b", { text: i.name }), el("span", { class: "sub", text: `${i.kind} · ${i.as_of || "–"}` })),
      el("td", {}, num(i.value), el("span", { class: "sub", text: i.unit })),
      el("td", { class: cls, text: label }),
      el("td", { class: "text", text: i.text }),
    );
  };
  const table = (title, items) =>
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
            [title, "Latest", "Reading", "Detail"].map((h, k) =>
              el("th", { text: h, style: k === 3 ? "text-align:left" : null }),
            ),
          ),
        ),
        el("tbody", {}, items.map(row)),
      ),
    );
  box.replaceChildren(
    el("p", { class: "reading", text: c.summary.text }),
    table("Growth", c.growth),
    el("h3", { text: "Inflation (context for the central bank)" }),
    table("Inflation", c.inflation),
  );
}

// ---------- history chart ----------
let tip = null;

function tooltip() {
  if (!tip) {
    tip = el("div", { class: "tooltip", hidden: true });
    document.body.append(tip);
  }
  return tip;
}

function drawChart() {
  const svg = document.getElementById("chart");
  const h = state.history;
  const W = svg.clientWidth || 800;
  const H = svg.clientHeight || 240;
  const sp = h.sp500 || [];
  const spVals = sp.filter((v) => v > 0);
  const L = 44;
  const R = spVals.length ? 50 : 8;
  const T = 8;
  const B = 22;
  const n = h.months.length;
  const x = (i) => L + (i * (W - L - R)) / Math.max(1, n - 1);
  const y = (v) => T + ((1 - v) * (H - T - B)) / 2;
  const thr = state.latest.params.bias_threshold;
  const nodes = [];
  const svgEl = (tag, attrs) => el(tag, { svg: true, ...attrs });
  nodes.push(svgEl("rect", { x: L, y: y(1), width: W - L - R, height: y(thr) - y(1), fill: "var(--pos-wash)" }));
  nodes.push(svgEl("rect", { x: L, y: y(-thr), width: W - L - R, height: y(-1) - y(-thr), fill: "var(--neg-wash)" }));
  for (const v of [-1, -thr, 0, thr, 1]) {
    nodes.push(
      svgEl("line", {
        x1: L,
        x2: W - R,
        y1: y(v),
        y2: y(v),
        stroke: v === 0 ? "var(--axis)" : "var(--hairline)",
        "stroke-width": 1,
      }),
    );
    const t = svgEl("text", { x: L - 6, y: y(v) + 4, "text-anchor": "end" });
    t.textContent = v === 0 ? "0" : `${v > 0 ? "+" : "−"}${Math.abs(v)}`;
    nodes.push(t);
  }
  const step = W < 500 ? 10 : 5;
  h.months.forEach((m, i) => {
    if (m.endsWith("-01") && Number(m.slice(0, 4)) % step === 0) {
      const t = svgEl("text", { x: x(i), y: H - 6, "text-anchor": "middle" });
      t.textContent = m.slice(0, 4);
      nodes.push(t);
    }
  });
  if (spVals.length) {
    // the S&P 500 on its own log scale (right axis), under the bias line
    const lo = Math.log(Math.min(...spVals));
    const hi = Math.log(Math.max(...spVals));
    const ys = (v) => T + (1 - (Math.log(v) - lo) / Math.max(1e-9, hi - lo)) * (H - T - B);
    let p = "";
    sp.forEach((v, i) => {
      if (!(v > 0)) return;
      p += `${p && sp[i - 1] > 0 ? "L" : "M"}${x(i).toFixed(1)},${ys(v).toFixed(1)}`;
    });
    nodes.push(
      svgEl("path", { d: p, fill: "none", stroke: "var(--ink-2)", "stroke-width": 1.3, "stroke-opacity": 0.55 }),
    );
    // round ticks that double: ..., 500, 1k, 2k, 4k, 8k
    for (let tick = 1000 * 2 ** Math.ceil(Math.log2(Math.exp(lo) / 1000)); tick <= Math.exp(hi); tick *= 2) {
      const t = svgEl("text", { x: W - R + 6, y: ys(tick) + 4, "text-anchor": "start" });
      t.textContent = tick >= 1000 ? `${tick / 1000}k` : String(Math.round(tick));
      nodes.push(t);
    }
  }
  let d = "";
  h.bias.forEach((v, i) => {
    if (v === null) return;
    d += `${d && h.bias[i - 1] !== null ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
  });
  nodes.push(
    svgEl("path", { d, fill: "none", stroke: "var(--accent)", "stroke-width": 2, "stroke-linejoin": "round" }),
  );
  const selected = state.isLatest ? n - 1 : h.months.indexOf(state.current.as_of.slice(0, 7));
  if (selected >= 0 && h.bias[selected] !== null) {
    nodes.push(
      svgEl("circle", {
        cx: x(selected),
        cy: y(h.bias[selected]),
        r: 4.5,
        fill: "var(--accent)",
        stroke: "var(--surface)",
        "stroke-width": 2,
      }),
    );
  }
  const cross = svgEl("line", { y1: T, y2: H - B, stroke: "var(--axis)", "stroke-width": 1, visibility: "hidden" });
  const hit = svgEl("rect", { x: L, y: 0, width: W - L - R, height: H, fill: "transparent", style: "cursor:pointer" });
  nodes.push(cross, hit);
  svg.replaceChildren(...nodes);

  const indexAt = (clientX) => {
    const r = svg.getBoundingClientRect();
    return Math.max(0, Math.min(n - 1, Math.round(((clientX - r.left - L) / (W - L - R)) * (n - 1))));
  };
  hit.addEventListener("pointermove", (ev) => {
    const i = indexAt(ev.clientX);
    cross.setAttribute("x1", x(i));
    cross.setAttribute("x2", x(i));
    cross.setAttribute("visibility", "visible");
    const t = tooltip();
    t.replaceChildren(
      el("strong", { text: fmtScore(h.bias[i]) }),
      el("span", { text: `${STATES[h.state[i]] || "No reading"} · ${monthLabel(h.months[i])}` }),
      el("span", {
        class: "muted",
        style: "display:block",
        text: `${h.used[i]} indicators${h.revised[i] ? " · some revised data" : ""}`,
      }),
      sp[i] > 0
        ? el("span", {
            style: "display:block",
            text: `S&P 500 ${sp[i].toLocaleString("en-US", { maximumFractionDigits: 0 })}`,
          })
        : null,
    );
    t.hidden = false;
    const box = t.getBoundingClientRect();
    t.style.left = `${Math.min(window.innerWidth - box.width - 8, Math.max(8, ev.clientX - box.width / 2))}px`;
    t.style.top = `${Math.max(8, svg.getBoundingClientRect().top - box.height - 8)}px`;
  });
  hit.addEventListener("pointerleave", () => {
    cross.setAttribute("visibility", "hidden");
    if (tip) tip.hidden = true;
  });
  hit.addEventListener("click", (ev) => {
    const i = indexAt(ev.clientX);
    const select = document.getElementById("asof");
    select.value = h.months[i];
    select.dispatchEvent(new Event("change"));
  });
  const firstVintage = h.revised.indexOf(false);
  document.getElementById("chart-legend").replaceChildren(
    el("span", {}, el("span", { class: "key", style: "background:var(--pos-wash)" }), `Net long zone (≥ +${thr})`),
    el("span", {}, el("span", { class: "key", style: "background:var(--neg-wash)" }), `Net short zone (≤ −${thr})`),
    spVals.length
      ? el(
          "span",
          {},
          el("span", { class: "swatch-line", style: "background:var(--ink-2);opacity:.55" }),
          "S&P 500 at each month-end (right axis, log scale)",
        )
      : null,
    firstVintage > 0
      ? el("span", {
          class: "muted",
          text: `Before ${monthLabel(h.months[firstVintage])} some inputs use revised data.`,
        })
      : null,
    el("span", { class: "muted", text: "Hand-entered surveys exist only from the dates you entered them." }),
  );
}

// ---------- copy brief / download CSV ----------
async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = el("textarea", { style: "position:fixed;opacity:0", "aria-hidden": "true" });
    area.value = text;
    document.body.append(area);
    area.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch {
      ok = false;
    }
    area.remove();
    return ok;
  }
}

function flash(button, text) {
  const old = button.dataset.label || button.textContent.trim();
  button.dataset.label = old;
  button.textContent = text;
  setTimeout(() => (button.textContent = old), 2200);
}

function wireExports() {
  const copy = document.getElementById("copy-brief");
  copy.addEventListener("click", async () => {
    const { bias, alerts, overrides } = state.view;
    const text = briefText({
      asOf: state.current.as_of,
      bias,
      signals: state.current.signals,
      overrides,
      changes: changeItems(),
      alerts,
      regime: state.isLatest ? state.regime : null,
      url: location.href.split("#")[0],
    });
    flash(copy, (await copyText(text)) ? "Copied ✓" : "Copy failed");
  });
  document.getElementById("download-csv").addEventListener("click", () => {
    const csv = boardCsv({
      signals: state.current.signals,
      blocks: state.latest.blocks,
      overrides: state.view.overrides,
    });
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const a = el("a", { href: url, download: `ptm-signal-board-${state.current.as_of}.csv` });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
}

// ---------- as of ----------
async function showMonth(month) {
  if (month === "latest") {
    state.current = state.latest;
    state.isLatest = true;
  } else {
    const year = month.slice(0, 4);
    if (!state.years[year]) state.years[year] = await loadJSON(`data/macro/snapshots/${year}.json`);
    state.current = state.years[year].find((s) => s.as_of.startsWith(month));
    state.isLatest = false;
  }
  render();
}

async function main() {
  state.overrides = loadOverrides();
  try {
    [state.latest, state.history] = await Promise.all([
      loadJSON("data/macro/latest.json"),
      loadJSON("data/macro/history.json"),
    ]);
  } catch {
    document
      .getElementById("content")
      .replaceChildren(
        el(
          "div",
          { class: "card notice" },
          el("strong", { text: "No Macro Desk data yet. " }),
          "It appears after the next pipeline run.",
        ),
      );
    return;
  }
  const known = new Set(state.latest.signals.map((s) => s.id));
  for (const id of Object.keys(state.overrides)) if (!known.has(id)) delete state.overrides[id];
  const select = document.getElementById("asof");
  select.replaceChildren(
    el("option", { value: "latest", text: `Today (${state.latest.as_of})` }),
    ...state.history.months
      .slice()
      .reverse()
      .map((m) => el("option", { value: m, text: `${monthLabel(m)} month-end` })),
  );
  select.addEventListener("change", () => showMonth(select.value));
  document.getElementById("reset").addEventListener("click", () => {
    state.overrides = {};
    saveOverrides();
    render();
  });
  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(drawChart, 150);
  });
  state.current = state.latest;
  render();
  wireExports();
  renderConfirmers();
  loadJSON("data/regime.json")
    .then((r) => (state.regime = r))
    .catch(() => null);
  document.title = `Macro Desk · ${state.latest.bias.label} · PTM Dashboard`;
}

main();
