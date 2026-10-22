// "This week": the course's weekly process in order, with what each step needs from the live data and a
// checklist kept in this browser per ISO week.

import { el, loadJSON, setChildren } from "./common.js";
import * as store from "./ideas-store.js";
import { positionGuide } from "./portfolio-math.js";
import * as R from "./routine-logic.js";
import { rowsOf, todayISO } from "./workbench.js";

const KEY = "ptm.routine.v1";
const DEFAULTS = { review_days: 7, stale_days: 14, pipeline_min: 10, pipeline_max: 15, ideas_per_week: 2 };
const STATUS = {
  ok: { label: "Up to date", cls: "tag-pos" },
  attention: { label: "Needs attention", cls: "tag-warn" },
  todo: { label: "Weekly step", cls: "" },
};

function loadChecks() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "{}") || {};
  } catch {
    return {};
  }
}

function saveChecks(all) {
  try {
    localStorage.setItem(KEY, JSON.stringify(all));
  } catch {
    /* private mode: the checklist lasts for this visit only */
  }
}

function loadBook() {
  try {
    return JSON.parse(localStorage.getItem("ptm.portfolio.v1") || "null");
  } catch {
    return null;
  }
}

function render(steps, week) {
  const all = loadChecks();
  const done = all[week] || {};
  const n = steps.filter((s) => done[s.id]).length;
  const hours = steps.reduce((a, s) => a + s.hours, 0);
  const progress = el(
    "div",
    { class: "card panel routine-head" },
    el(
      "div",
      {},
      el("b", { text: `Week ${week.split("-W")[1]}, ${week.slice(0, 4)}` }),
      el("span", { class: "muted", text: ` · ${n} of ${steps.length} steps done` }),
    ),
    el(
      "div",
      {
        class: "routine-meter",
        role: "progressbar",
        "aria-valuemin": 0,
        "aria-valuemax": steps.length,
        "aria-valuenow": n,
      },
      el("span", { style: `width:${(n / steps.length) * 100}%` }),
    ),
    el("p", {
      class: "section-note",
      style: "margin:0",
      text: `About ${hours} hours in all (the course's retail routine is 8–12 hours a week; the split per step is our suggestion). Ticks are kept in this browser and start fresh each week.`,
    }),
  );
  const cards = steps.map((s, i) =>
    el(
      "section",
      { class: `card panel routine-step ${done[s.id] ? "is-done" : ""}` },
      el(
        "div",
        { class: "routine-step-head" },
        el(
          "label",
          { class: "check" },
          el("input", {
            type: "checkbox",
            checked: !!done[s.id],
            "aria-label": `Mark step ${i + 1} done`,
            onchange: (ev) => {
              const cur = loadChecks();
              cur[week] = { ...(cur[week] || {}), [s.id]: ev.target.checked };
              saveChecks(cur);
              render(steps, week);
            },
          }),
          el("h2", { class: "panel-title", style: "margin:0", text: `${i + 1}. ${s.title}` }),
        ),
        el("span", { class: `tag ${STATUS[s.status].cls}`, text: STATUS[s.status].label }),
      ),
      el("p", { class: "section-note", style: "margin:4px 0 8px", text: `${s.lesson} · about ${s.hours} h` }),
      el(
        "ul",
        { class: "plain-list routine-items" },
        s.items.map((t) => el("li", { text: t })),
      ),
      el("a", { class: "btn", href: s.page, text: "Open →" }),
    ),
  );
  setChildren(document.getElementById("content"), progress, ...cards);
}

async function main() {
  const today = todayISO();
  const week = R.isoWeek(today);
  const [health, calendar, latest, themes, stocks, sectors, published] = await Promise.all([
    loadJSON("data/health.json").catch(() => null),
    loadJSON("data/calendar.json").catch(() => null),
    loadJSON("data/macro/latest.json").catch(() => null),
    loadJSON("data/themes.json").catch(() => null),
    loadJSON("data/screener/stocks.json").catch(() => null),
    loadJSON("data/sectors.json").catch(() => null),
    store.loadPublished(),
  ]);
  const p = { ...DEFAULTS, ...(published.params || {}) };
  const rows = stocks ? rowsOf(stocks) : [];
  const byT = Object.fromEntries(rows.map((r) => [r.t, r]));
  const ideas = Object.values(store.mergeIdeas(published)).map((e) => e.idea);
  const book = loadBook();
  const steps = () => [
    R.dataStep(health, calendar, today),
    R.macroStep(latest),
    R.themesStep(themes),
    R.screenStep(stocks, rows, sectors),
    R.ideasStep(ideas, today, p),
    R.reviewStep(ideas, pages, byT, calendar, today, p),
    R.portfolioStep(book, positionGuide((book && book.capital) || 100000)),
  ];
  const pages = {};
  render(steps(), week);
  // earnings dates of the open ideas come from their stock pages
  const open = ideas.filter((i) => store.OPEN_STATUSES.includes(i.status) && byT[i.ticker]).map((i) => i.ticker);
  const got = await Promise.all(
    open.map((t) => loadJSON(`data/stocks/${t.replace(/[^A-Z0-9.-]/g, "")}.json`).catch(() => null)),
  );
  open.forEach((t, i) => (pages[t] = got[i]));
  if (open.length) render(steps(), week);
}

main();
