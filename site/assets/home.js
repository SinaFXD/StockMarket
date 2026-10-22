// Home page: today's bias with its 24-month trail, the four blocks, what changed, the next reports, the regime, the
// four process steps with live counts, and the data status. Everything comes from the published files; the week's
// ticks, ideas and book come from this browser.

import { MANUAL_STATUS, badge, el, fmtDateTime, fmtMonth, loadJSON, relTime, setChildren, tooltip } from "./common.js";
import * as store from "./ideas-store.js";
import { HOURS, daysFrom, isoWeek } from "./routine-logic.js";
import { todayISO } from "./workbench.js";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const TRAIL_MONTHS = 24;
const AHEAD_DAYS = 14;
const MAX_EVENTS = 6;

const tone = (x) => (x === null || x === undefined ? "none" : x > 0 ? "pos" : x < 0 ? "neg" : "zero");
const signed = (x, d = 2) =>
  x === null || x === undefined ? "–" : `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x).toFixed(d)}`;
const fmtDay = (iso) => {
  const d = new Date(`${iso}T00:00:00Z`);
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
};
const STATE_OF = { net_long: "Net long", net_short: "Net short", neutral: "Neutral" };

function readJSONStorage(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key) || "null") ?? fallback;
  } catch {
    return fallback;
  }
}

// ---------- hero: bias, meter, trail ----------

function meter(score, thr) {
  const at = (v) => `${((v + 1) / 2) * 100}%`;
  const zone = score === null ? "" : score >= thr ? "long" : score <= -thr ? "short" : "neutral";
  return el(
    "div",
    { class: "bh-meter", role: "img", "aria-label": `Score ${signed(score)} on a scale from −1 (short) to +1 (long)` },
    el(
      "div",
      { class: "bh-track" },
      el("span", { class: `z-short ${zone === "short" ? "on" : ""}`, style: `width:${at(-thr)}` }),
      el("span", { class: `z-neutral ${zone === "neutral" ? "on" : ""}`, style: `left:${at(-thr)};right:${at(-thr)}` }),
      el("span", { class: `z-long ${zone === "long" ? "on" : ""}`, style: `width:${at(-thr)}` }),
      score === null ? null : el("span", { class: "bh-mark", style: `left:${at(Math.max(-1, Math.min(1, score)))}` }),
    ),
    el(
      "div",
      { class: "bh-ticks", "aria-hidden": "true" },
      el("span", { style: "left:0", text: "−1 short" }),
      el("span", { style: `left:${at(-thr)}`, text: signed(-thr) }),
      el("span", { style: `left:${at(thr)}`, text: signed(thr) }),
      el("span", { style: "left:100%", text: "+1 long" }),
    ),
  );
}

// Month-end bias over the last two years plus today's reading; the neutral zone is shaded.
function trail(history, latest, thr) {
  const n = history ? history.months.length : 0;
  const pts = [];
  for (let i = Math.max(0, n - TRAIL_MONTHS); i < n; i++)
    if (history.bias[i] !== null) pts.push([fmtMonth(history.months[i]), history.bias[i], history.state[i]]);
  if (latest.bias.score !== null) pts.push([`Today (${fmtDay(latest.as_of)})`, latest.bias.score, latest.bias.state]);
  if (pts.length < 3) return null;

  const W = 320;
  const H = 96;
  const PX = 4;
  const PT = 8;
  const PB = 8;
  const top = Math.max(0.5, Math.ceil(Math.max(...pts.map((p) => Math.abs(p[1]))) * 4) / 4);
  const x = (i) => PX + (i * (W - 2 * PX)) / (pts.length - 1);
  const y = (v) => PT + ((top - v) * (H - PT - PB)) / (2 * top);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join("");
  const last = pts.length - 1;

  const svg = el("svg", {
    class: "bh-trail",
    viewBox: `0 0 ${W} ${H}`,
    role: "img",
    tabindex: "0",
    "aria-label": `Bias over the last ${TRAIL_MONTHS} months: from ${signed(pts[0][1])} (${pts[0][0]}) to ${signed(pts[last][1])} today`,
  });
  const band = el("rect", {
    svg: true,
    x: 0,
    width: W,
    y: y(thr),
    height: y(-thr) - y(thr),
    fill: "var(--neu-wash)",
  });
  const zero = el("line", { svg: true, x1: 0, x2: W, y1: y(0), y2: y(0), stroke: "var(--axis)", "stroke-width": 1 });
  const cross = el("line", { svg: true, y1: 0, y2: H, stroke: "var(--axis)", "stroke-width": 1, visibility: "hidden" });
  const line = el("path", {
    svg: true,
    d,
    fill: "none",
    stroke: "var(--spark)",
    "stroke-width": 2,
    "stroke-linejoin": "round",
    "stroke-linecap": "round",
  });
  const dot = el("circle", {
    svg: true,
    cx: x(last),
    cy: y(pts[last][1]),
    r: 4,
    fill: "var(--spark)",
    stroke: "var(--surface)",
    "stroke-width": 2,
  });
  const hit = el("rect", { svg: true, x: 0, y: 0, width: W, height: H, fill: "transparent" });
  svg.append(band, zero, cross, line, dot, hit);

  const show = (i, clientX, clientY) => {
    const p = pts[i];
    cross.setAttribute("x1", x(i));
    cross.setAttribute("x2", x(i));
    cross.setAttribute("visibility", "visible");
    dot.setAttribute("cx", x(i));
    dot.setAttribute("cy", y(p[1]));
    const tip = tooltip();
    tip.replaceChildren(
      el("strong", { text: `${signed(p[1])} · ${STATE_OF[p[2]] || "–"}` }),
      el("span", { class: "muted", text: p[0] }),
    );
    tip.hidden = false;
    const box = tip.getBoundingClientRect();
    tip.style.left = `${Math.min(window.innerWidth - box.width - 8, Math.max(8, clientX - box.width / 2))}px`;
    tip.style.top = `${Math.max(8, clientY - box.height - 10)}px`;
  };
  const hide = () => {
    cross.setAttribute("visibility", "hidden");
    dot.setAttribute("cx", x(last));
    dot.setAttribute("cy", y(pts[last][1]));
    tooltip().hidden = true;
  };
  svg.addEventListener("pointermove", (ev) => {
    const r = svg.getBoundingClientRect();
    const rel = ((ev.clientX - r.left) / r.width) * W;
    const i = Math.max(0, Math.min(last, Math.round(((rel - PX) / (W - 2 * PX)) * last)));
    show(i, r.left + (x(i) / W) * r.width, r.top);
  });
  svg.addEventListener("pointerleave", hide);
  svg.addEventListener("focus", () => {
    const r = svg.getBoundingClientRect();
    show(last, r.right, r.top);
  });
  svg.addEventListener("blur", hide);

  return el(
    "figure",
    { class: "bh-fig" },
    svg,
    el(
      "figcaption",
      {},
      el("span", { text: pts[0][0] }),
      el("span", { class: "muted", text: `month-end bias · shaded: neutral (±${thr})` }),
      el("span", { text: "today" }),
    ),
  );
}

function renderBias(latest, history) {
  const b = latest.bias;
  const thr = b.threshold ?? 0.25;
  const change = (latest.what_changed || []).find((c) => c.id === "bias");
  const since = latest.compared_with ? fmtDay(latest.compared_with) : null;
  let delta = null;
  if (change && change.from !== null && b.score !== null) {
    const d = b.score - change.from;
    const dir = d > 0 ? "up" : d < 0 ? "down" : "flat";
    delta = el(
      "span",
      { class: `delta ${dir}` },
      el("span", { "aria-hidden": "true", text: d > 0 ? "▲" : d < 0 ? "▼" : "●" }),
      ` ${signed(d)} since ${since}`,
      change.from_state !== change.to_state
        ? el("span", { class: "muted", text: ` · was ${change.from_state}` })
        : null,
    );
  } else if (since) delta = el("span", { class: "delta flat", text: `unchanged since ${since}` });

  document.getElementById("bias-asof").textContent = `as of ${fmtDay(latest.as_of)}`;
  setChildren(
    document.getElementById("bias-body"),
    el("p", { class: `bh-state ${tone(b.score)}`, text: b.label }),
    el("p", { class: "bh-score" }, el("b", { text: signed(b.score) }), delta),
    meter(b.score, thr),
    trail(history, latest, thr),
    el("p", {
      class: "bh-foot",
      text: `${b.used} of ${b.total} indicators · net long at ${signed(thr)} or more, net short at ${signed(-thr)} or less. A first reading: the Macro Desk lets you override every signal.`,
    }),
  );
  document.querySelector(".bias-hero").removeAttribute("aria-busy");
}

// ---------- blocks and alerts ----------

function renderBlocks(latest) {
  const signals = latest.signals || [];
  const tiles = Object.entries(latest.bias.blocks).map(([id, blk]) => {
    const mine = signals.filter((s) => s.block === id);
    const count = (f) => mine.filter((s) => s.score !== null && f(s.score)).length;
    const up = count((v) => v > 0);
    const flat = count((v) => v === 0);
    const down = count((v) => v < 0);
    const v = blk.score;
    const half = v === null ? 0 : Math.min(1, Math.abs(v)) * 50;
    return el(
      "a",
      { class: "card block-card", href: "macro.html" },
      el("span", { class: "bc-label", text: blk.label }),
      el("span", { class: `bc-score ${tone(v)}`, text: signed(v) }),
      el(
        "span",
        { class: "bc-bar", "aria-hidden": "true" },
        el("span", {
          class: `bc-fill ${tone(v)}`,
          style: v === null ? "width:0" : v >= 0 ? `left:50%;width:${half}%` : `left:${50 - half}%;width:${half}%`,
        }),
      ),
      el(
        "span",
        { class: "bc-dots" },
        mine.map((s) =>
          el("span", {
            class: `bc-dot ${tone(s.score)}`,
            title: `${s.name}: ${s.state}`,
            text: s.score === null ? "–" : s.score > 0 ? "▲" : s.score < 0 ? "▼" : "●",
          }),
        ),
      ),
      el("span", {
        class: "bc-foot",
        text: `${up} up · ${flat} flat · ${down} down${blk.used < blk.total ? ` · ${blk.total - blk.used} awaiting` : ""}`,
      }),
    );
  });
  setChildren(document.getElementById("blocks"), tiles);
  setChildren(
    document.getElementById("alerts"),
    (latest.alerts || []).map((a) =>
      el(
        "p",
        { class: "home-alert" },
        el("span", { class: "ha-icon", "aria-hidden": "true", text: "!" }),
        el("span", { text: a }),
      ),
    ),
  );
}

// ---------- what changed, coming up, regime ----------

function renderChanged(latest) {
  const since = latest.compared_with ? `since ${fmtDay(latest.compared_with)}` : "";
  document.getElementById("changed-since").textContent = since;
  const list = (latest.what_changed || []).filter((c) => c.id !== "bias");
  const items = list.map((c) => {
    const d = (c.to ?? 0) - (c.from ?? 0);
    return el(
      "li",
      {},
      el("span", {
        class: `hc-icon ${d > 0 ? "pos" : d < 0 ? "neg" : "zero"}`,
        "aria-hidden": "true",
        text: d > 0 ? "▲" : d < 0 ? "▼" : "●",
      }),
      el(
        "span",
        { class: "hc-main" },
        el("a", { href: `indicator.html?id=${encodeURIComponent(c.id)}`, text: c.name }),
        el("span", { class: "hc-sub", text: `${c.from_state} → ${c.to_state}` }),
      ),
    );
  });
  setChildren(
    document.getElementById("changed"),
    items.length ? items : el("li", { class: "hc-empty", text: `No indicator changed its reading ${since}.` }),
  );
}

function renderComing(calendar, latest, today) {
  const names = Object.fromEntries((latest ? latest.signals : []).map((s) => [s.id, s.name.replace(/ \(.*\)$/, "")]));
  const events = (calendar ? calendar.events : [])
    .map((e) => ({ ...e, d: daysFrom(today, e.date) }))
    .filter((e) => e.d >= 0 && e.d <= AHEAD_DAYS && (e.importance === "high" || (e.signals || []).length))
    .slice(0, MAX_EVENTS);
  const items = events.map((e) => {
    const day = new Date(`${e.date}T00:00:00Z`);
    const when = e.d === 0 ? "today" : e.d === 1 ? "tomorrow" : `in ${e.d} days`;
    const feeds = (e.signals || []).map((id) => names[id] || id);
    return el(
      "li",
      {},
      el(
        "span",
        { class: "hc-date" },
        el("b", { text: String(day.getUTCDate()) }),
        el("span", { text: `${DAYS[day.getUTCDay()]} ${MONTHS[day.getUTCMonth()]}` }),
      ),
      el(
        "span",
        { class: "hc-main" },
        el("span", { class: "hc-title", text: e.title }),
        el(
          "span",
          { class: "hc-sub" },
          `${e.region} · ${when}`,
          feeds.length
            ? el("span", { class: "hc-feeds", title: `Feeds ${[...new Set(feeds)].join(", ")}`, text: "bias input" })
            : null,
          e.category === "manual_report" ? el("span", { class: "hc-feeds manual", text: "enter by hand" }) : null,
        ),
      ),
    );
  });
  setChildren(
    document.getElementById("coming"),
    items.length
      ? items
      : el("li", {
          class: "hc-empty",
          text: calendar ? "No major report in the next two weeks." : "Calendar not built yet.",
        }),
  );
}

const QUADRANTS = [
  ["recovery", "Recovery"],
  ["overheat", "Overheat"],
  ["reflation", "Reflation"],
  ["stagflation", "Stagflation"],
];
const LEVELS = {
  hot: "Running hot: inflation, the output gap or jobs above normal.",
  cold: "Running cold: inflation, the output gap or jobs below normal.",
  balanced: "Levels balanced: inflation, the output gap and jobs near normal.",
};

function renderRegime(health) {
  const box = document.getElementById("regime");
  const r = health && health.regime;
  if (!r || r.status !== "ok") {
    setChildren(box, el("p", { class: "hc-empty", text: "The regime is not computed yet." }));
    return;
  }
  document.getElementById("regime-month").textContent = r.month ? `data for ${fmtMonth(r.month)}` : "";
  const now = (QUADRANTS.find(([, label]) => label === r.regime) || [])[0];
  const prob = typeof r.recession_prob === "number" ? r.recession_prob : null;
  setChildren(
    box,
    el(
      "div",
      { class: "rg-row" },
      el(
        "div",
        { class: "rg-map", role: "img", "aria-label": `Current regime: ${r.regime}` },
        QUADRANTS.map(([id, label]) => el("span", { class: id === now ? "on" : "", text: label })),
        el("span", { class: "rg-y", "aria-hidden": "true", text: "growth ↑" }),
        el("span", { class: "rg-x", "aria-hidden": "true", text: "inflation →" }),
      ),
      el(
        "div",
        { class: "rg-now" },
        el("span", { class: "muted", text: "Growth vs inflation" }),
        el("b", { text: r.regime || "–" }),
        r.levels ? el("span", { class: "rg-level", text: LEVELS[r.levels] || r.levels }) : null,
      ),
    ),
    prob === null
      ? null
      : el(
          "div",
          { class: "rg-odds" },
          el(
            "div",
            { class: "rg-odds-head" },
            el("span", { text: "US recession odds, next 12 months" }),
            el("b", { text: `${prob.toFixed(1)}%` }),
          ),
          el(
            "div",
            {
              class: "rg-meter",
              role: "meter",
              "aria-valuemin": 0,
              "aria-valuemax": 100,
              "aria-valuenow": prob,
              "aria-label": "US recession odds over the next 12 months, New York Fed yield-curve model",
            },
            el("span", { style: `width:${Math.min(100, prob)}%` }),
          ),
          el("span", { class: "hc-sub", text: "New York Fed yield-curve model · context, not part of the bias" }),
        ),
  );
}

// ---------- process stats, hero facts, status ----------

function renderSteps(latest, health, ideasOpen, book) {
  const set = (key, text) => {
    const node = document.querySelector(`[data-stat="${key}"]`);
    if (node && text) node.textContent = text;
  };
  if (latest) set("bias", `${latest.bias.label} · ${latest.bias.used} of ${latest.bias.total} indicators`);
  const th = health && health.themes;
  if (th && th.status === "ok")
    set("themes", `${th.tailwinds} industries with a macro tailwind, ${th.headwinds} with a headwind`);
  const sc = health && health.screener;
  const stocks = sc && sc.stocks ? `${sc.stocks.toLocaleString("en-US")} stocks screened` : null;
  set("ideas", [stocks, `${ideasOpen} open idea${ideasOpen === 1 ? "" : "s"}`].filter(Boolean).join(" · "));
  const n = book && book.current ? book.current.filter((x) => x.t && x.amount > 0).length : 0;
  set("book", n ? `${n} position${n === 1 ? "" : "s"} in your book` : "No book in this browser yet");
}

function renderFacts(latest, health) {
  const facts = [];
  if (latest) facts.push([String(latest.bias.total), "leading indicators"]);
  if (health && health.screener && health.screener.stocks)
    facts.push([health.screener.stocks.toLocaleString("en-US"), "stocks screened"]);
  if (health) facts.push([String(health.summary.series.total), "data series"]);
  setChildren(
    document.getElementById("hero-facts"),
    facts.map(([v, label]) => el("div", {}, el("dt", { text: label }), el("dd", { text: v }))),
  );
}

function renderStatus(health, calendar, today) {
  const box = document.getElementById("status");
  if (!health) {
    setChildren(box, el("div", {}, el("dt", { text: "Pipeline" }), el("dd", { text: "not run yet" })));
    return;
  }
  document.getElementById("updated").textContent = `Updated ${relTime(health.generated_at)} · ${fmtDateTime(
    health.generated_at,
  )}`;
  const s = health.summary.series;
  const m = health.summary.manual;
  const issues = s.stale + s.failed + s.missing;
  const manualTone = m.errors ? "critical" : m.awaiting ? "awaiting" : m.due ? "due" : "ok";
  const next = (calendar ? calendar.events : []).find(
    (e) => e.category === "manual_report" && daysFrom(today, e.date) >= 0,
  );
  const item = (label, ...value) => el("div", {}, el("dt", { text: label }), el("dd", {}, ...value));
  setChildren(
    box,
    item("Last update", `${fmtDateTime(health.generated_at)}`),
    item(
      "Automatic series",
      issues
        ? badge({ label: `${issues} need attention`, tone: "warning", icon: "!" })
        : badge({ label: `${s.ok} of ${s.total} fresh`, tone: "good", icon: "✓" }),
    ),
    item(
      "Hand-entered reports",
      manualTone === "critical"
        ? badge({ label: `${m.errors} error${m.errors > 1 ? "s" : ""}`, tone: "critical", icon: "×" })
        : badge(MANUAL_STATUS[manualTone]),
    ),
    next ? item("Next report to enter", `${next.title} · ${fmtDay(next.date)}`) : null,
  );
}

function renderWeek(today) {
  const week = isoWeek(today);
  const done = readJSONStorage("ptm.routine.v1", {})[week] || {};
  const steps = Object.keys(HOURS);
  const n = steps.filter((id) => done[id]).length;
  document.getElementById("week-note").textContent = n
    ? `· ${n} of ${steps.length} done`
    : `· week ${Number(week.split("-W")[1])}`;
}

async function main() {
  const today = todayISO();
  renderWeek(today);
  const [latest, history, health, calendar, published] = await Promise.all([
    loadJSON("data/macro/latest.json").catch(() => null),
    loadJSON("data/macro/history.json").catch(() => null),
    loadJSON("data/health.json").catch(() => null),
    loadJSON("data/calendar.json").catch(() => null),
    store.loadPublished(),
  ]);

  if (latest) {
    renderBias(latest, history);
    renderBlocks(latest);
    renderChanged(latest);
  } else {
    setChildren(document.getElementById("bias-body"), el("p", { class: "bh-state", text: "Not computed yet" }));
    setChildren(document.getElementById("blocks"));
    setChildren(document.getElementById("changed"), el("li", { class: "hc-empty", text: "No Macro Desk data yet." }));
  }
  renderComing(calendar, latest, today);
  renderRegime(health);
  const ideas = Object.values(store.mergeIdeas(published)).map((e) => e.idea);
  renderSteps(
    latest,
    health,
    ideas.filter((i) => store.OPEN_STATUSES.includes(i.status)).length,
    readJSONStorage("ptm.portfolio.v1", null),
  );
  renderFacts(latest, health);
  renderStatus(health, calendar, today);
}

main();
