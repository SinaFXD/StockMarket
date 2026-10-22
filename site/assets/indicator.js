// Indicator page: score and reason, reading guide, rule, chart panels with ranges, components, score history.

import { chartSet, fmtNum, rangeButtons, redraw, redrawOnResize, renderPanels } from "./charts.js";
import { el, loadJSON, scorePill } from "./common.js";

const state = { latest: null, data: null, signal: null };
const charts = chartSet(10);

function override() {
  try {
    const o = JSON.parse(localStorage.getItem("ptm.overrides.v1") || "{}");
    return state.signal.id in o ? o[state.signal.id] : undefined;
  } catch {
    return undefined;
  }
}

// ---------- header, guide ----------
function metricItems(metrics) {
  const out = [];
  for (const [k, v] of Object.entries(metrics || {})) {
    if (v === null || typeof v === "object") continue;
    const label = k.replace(/_/g, " ");
    out.push(el("li", {}, `${label}: `, el("b", { text: typeof v === "number" ? fmtNum(v) : String(v) })));
  }
  return out;
}

function header() {
  const s = state.signal;
  const ov = override();
  const facts = [];
  if (s.as_of) facts.push(`Data: ${s.as_of}`);
  if (s.percentile_10y !== null && s.percentile_10y !== undefined)
    facts.push(`10y percentile: ${Math.round(s.percentile_10y)}`);
  if (s.revised) facts.push("revised data");
  return el(
    "section",
    { class: "card ind-head" },
    el(
      "div",
      { class: "ind-title" },
      el("h1", { text: s.name }),
      scorePill(s.score),
      el("span", { class: "signal-state", text: s.state }),
    ),
    el("p", { class: "signal-reason", style: "font-size:15px", text: s.reason_en }),
    ov !== undefined
      ? el("p", {
          class: "muted",
          style: "margin:0",
          text: `Your override on the Macro Desk: ${ov > 0 ? "+1" : ov < 0 ? "−1" : "0"}.`,
        })
      : null,
    s.flags && s.flags.length
      ? el(
          "ul",
          { class: "signal-flags" },
          s.flags.map((f) => el("li", { text: f })),
        )
      : null,
    el("ul", { class: "metrics" }, metricItems(s.metrics)),
    el(
      "div",
      { class: "signal-meta" },
      facts.map((f) => el("span", { text: f })),
    ),
  );
}

function guide() {
  const g = state.data.guide || {};
  const list = (items) =>
    el(
      "ul",
      {},
      (items || []).map((t) => el("li", { text: t })),
    );
  return el(
    "div",
    { class: "two-col", style: "margin-top:12px" },
    el(
      "section",
      { class: "card panel guide" },
      el("h3", { text: "What it is" }),
      el("p", { style: "margin:0;font-size:14px", text: g.what || "" }),
      el("h3", { text: "How to read it (course method)" }),
      list(g.read),
      g.watch ? el("h3", { text: "Watch for" }) : null,
      g.watch ? list(g.watch) : null,
    ),
    el(
      "section",
      { class: "card panel guide" },
      el("h3", { text: "First-reading rule" }),
      el("p", { style: "margin:0;font-size:14px", text: state.signal.rule }),
      el("h3", { text: "Score history (month-ends, point in time)" }),
      scoreHistory(),
      el("p", {
        class: "muted",
        style: "font-size:12.5px;margin:8px 0 0",
        text: "Blue +1, grey 0, red −1, blank = awaiting data. A rule is a starting point: read it with the other indicators.",
      }),
    ),
  );
}

function scoreHistory() {
  const all = state.signal.history || [];
  const first = all.findIndex(([, x]) => x !== null);
  const h = first < 0 ? [] : all.slice(first); // start at the first month with data
  if (!h.length) return el("p", { class: "muted", text: "No history yet: awaiting data." });
  return el(
    "div",
    {},
    el(
      "div",
      {
        class: "score-strip",
        style: h.length > 120 ? "gap:0" : "",
        role: "img",
        "aria-label": `Monthly score from ${h[0][0]} to ${h[h.length - 1][0]}`,
      },
      h.map(([m, x]) =>
        el("span", {
          class: x === null ? "none" : x > 0 ? "pos" : x < 0 ? "neg" : "zero",
          title: `${m}: ${x === null ? "awaiting" : x}`,
        }),
      ),
    ),
    el("div", { class: "strip-caption" }, el("span", { text: h[0][0] }), el("span", { text: h[h.length - 1][0] })),
  );
}

async function show(id) {
  state.signal = state.latest.signals.find((s) => s.id === id) || state.latest.signals[0];
  try {
    state.data = await loadJSON(`data/macro/indicators/${state.signal.id}.json`);
  } catch {
    state.data = { guide: {}, panels: [] };
  }
  document.title = `${state.signal.name} · PTM Dashboard`;
  document
    .getElementById("content")
    .replaceChildren(header(), guide(), rangeButtons(charts), ...renderPanels(charts, state.data.panels));
  redraw(charts);
}

async function main() {
  try {
    state.latest = await loadJSON("data/macro/latest.json");
  } catch {
    document
      .getElementById("content")
      .replaceChildren(el("div", { class: "card notice", text: "No Macro Desk data yet." }));
    return;
  }
  const params = new URLSearchParams(location.search);
  const picker = document.getElementById("picker");
  picker.replaceChildren(
    ...Object.entries(state.latest.blocks).map(([key, label]) =>
      el(
        "optgroup",
        { label },
        state.latest.signals.filter((s) => s.block === key).map((s) => el("option", { value: s.id, text: s.name })),
      ),
    ),
  );
  const id = params.get("id") || state.latest.signals[0].id;
  picker.value = id;
  picker.addEventListener("change", () => {
    history.replaceState(null, "", `?id=${encodeURIComponent(picker.value)}`);
    show(picker.value);
  });
  redrawOnResize(charts);
  await show(id);
}

main();
