// Ideas pipeline (lesson 33): every saved trade idea with its status, how far the price is from the targets,
// the next earnings date, how complete the template is, and which ideas are due for a review.

import { el, loadJSON, setChildren } from "./common.js";
import * as store from "./ideas-store.js";
import { daysBetween, fmt, priceTargets, rowsOf, todayISO } from "./workbench.js";

const DEFAULTS = { review_days: 7, stale_days: 14, pipeline_min: 10, pipeline_max: 15, ideas_per_week: 2 };
const state = { filter: "open", stocks: null, rows: {}, pages: {}, published: null, p: DEFAULTS };
const has = (v) => v !== null && v !== undefined;

function targetsFor(idea, row, page) {
  if (!row || !page || !page.quant) return null;
  const q = page.quant;
  const a = idea.assumptions || {};
  const eps = [q.eps[0], has(a.eps1) ? a.eps1 : q.eps[1], has(a.eps2) ? a.eps2 : q.eps[2]];
  const sales = [q.sales[0], has(a.sales1) ? a.sales1 : q.sales[1], has(a.sales2) ? a.sales2 : q.sales[2]];
  const t = priceTargets(row.price, eps, sales, q.shares, { pe: a.pe, ps: a.ps, sharesFwd: a.shares });
  const y = t.years[0];
  const vals = [y.eps_target, y.sales_target].filter(has).sort((x, z) => x - z);
  if (!vals.length) return null;
  const [lo, hi] = [vals[0], vals[vals.length - 1]];
  // conservative = the target nearer the trade's direction
  return idea.side === "long" ? { cons: lo, opt: hi } : { cons: hi, opt: lo };
}

function flagsFor(idea, row, page, tg) {
  const out = [];
  const today = todayISO();
  const age = idea.updated ? daysBetween(idea.updated, today) : null;
  if (store.OPEN_STATUSES.includes(idea.status)) {
    if (age !== null && age >= state.p.stale_days) out.push(["Stale", "tag-warn", `Not updated for ${age} days`]);
    else if (age !== null && age >= state.p.review_days) out.push(["Review", "", `Not updated for ${age} days`]);
    if (row && tg) {
      const reached = idea.side === "long" ? row.price >= tg.cons : row.price <= tg.cons;
      if (reached)
        out.push([
          "Target reached",
          "tag-pos",
          "The price is at or beyond the conservative target: be active (lesson 33)",
        ]);
      const wrong = idea.side === "long" ? tg.opt < row.price : tg.opt > row.price;
      if (wrong) out.push(["Targets against you", "tag-warn", "The targets are on the wrong side of today's price"]);
    }
    const e = page && page.earnings;
    if (e) {
      const d = daysBetween(today, e.date);
      if (d >= 0 && d <= 7) out.push([`Earnings in ${d}d`, "", `${e.date}, ${e.session}`]);
    }
    if (!row) out.push(["Not in screener", "", "Not in the screener universe: no live numbers"]);
  }
  return out;
}

function summary(entries) {
  const open = entries.filter((e) => store.OPEN_STATUSES.includes(e.idea.status));
  const longs = open.filter((e) => e.idea.side === "long").length;
  const today = todayISO();
  const week = entries.filter((e) => e.idea.opened && daysBetween(e.idea.opened, today) <= 7).length;
  const due = open.filter((e) => e.idea.updated && daysBetween(e.idea.updated, today) >= state.p.review_days).length;
  const tile = (label, value, foot, cls = "") =>
    el(
      "div",
      { class: "card tile" },
      el("div", { class: "tile-label", text: label }),
      el("div", { class: `tile-value small ${cls}`, text: value }),
      el("div", { class: "tile-foot", text: foot }),
    );
  const n = open.length;
  return el(
    "div",
    { class: "tiles" },
    tile(
      "Open ideas",
      String(n),
      `aim for a pipeline of ${state.p.pipeline_min}–${state.p.pipeline_max}`,
      n >= state.p.pipeline_min && n <= state.p.pipeline_max ? "up" : "",
    ),
    tile("Long / short", `${longs} / ${n - longs}`, "open ideas by side"),
    tile("New this week", String(week), `about ${state.p.ideas_per_week} a week keeps the pipeline fresh`),
    tile("Due for review", String(due), `not updated for ${state.p.review_days}+ days`, due ? "down" : ""),
  );
}

function table(entries) {
  const today = todayISO();
  const rowsHtml = entries.map((e) => {
    const idea = e.idea;
    const row = state.rows[idea.ticker];
    const page = state.pages[idea.ticker];
    const tg = targetsFor(idea, row, page);
    const sign = idea.side === "long" ? 1 : -1;
    const pnl = row && idea.entry_price ? sign * (row.price / idea.entry_price - 1) * 100 : null;
    const toCons = row && tg ? (tg.cons / row.price - 1) * 100 : null;
    const items = store.checklist(idea);
    const done = items.filter((i) => i[2]).length;
    const age = idea.updated ? daysBetween(idea.updated, today) : null;
    const earn = page && page.earnings;
    const [label, title] = store.STATE_TEXT[e.state];
    return el(
      "tr",
      { class: store.OPEN_STATUSES.includes(idea.status) ? "" : "muted-row" },
      el(
        "td",
        {},
        el("a", { href: `stock.html?t=${encodeURIComponent(idea.ticker)}` }, el("b", { text: idea.ticker })),
        el("span", { class: "sub", text: row ? row.name || "" : "" }),
      ),
      el(
        "td",
        { class: "text-left" },
        el("span", {
          class: `tag ${idea.side === "long" ? "tag-pos" : "tag-neg"}`,
          text: idea.side === "long" ? "Long" : "Short",
        }),
      ),
      el("td", { class: "text-left", text: store.STATUS_LABEL[idea.status] || idea.status }),
      el("td", { text: row ? fmt.price(row.price) : "–" }),
      el(
        "td",
        {},
        idea.entry_price ? fmt.price(idea.entry_price) : "–",
        has(pnl)
          ? el("span", {
              class: `sub ${pnl > 0 ? "up" : pnl < 0 ? "down" : ""}`,
              text: `${fmt.pct(pnl)} for the ${idea.side}`,
            })
          : null,
      ),
      el(
        "td",
        {},
        tg ? `${fmt.price(tg.cons)} / ${fmt.price(tg.opt)}` : "–",
        has(toCons) ? el("span", { class: "sub", text: `${fmt.pct(toCons)} to the conservative` }) : null,
      ),
      el("td", {}, earn ? earn.date : "–", earn ? el("span", { class: "sub", text: earn.session }) : null),
      el("td", { text: `${done}/${items.length}` }),
      el(
        "td",
        {},
        idea.updated || "–",
        has(age) ? el("span", { class: "sub", text: age === 0 ? "today" : `${age} days ago` }) : null,
      ),
      el(
        "td",
        { class: "text" },
        el("span", {
          class: `tag ${e.state === "changed" || e.state === "local" ? "tag-warn" : ""}`,
          title,
          text: label,
        }),
        ...flagsFor(idea, row, page, tg).map(([text, cls, t]) => el("span", { class: `tag ${cls}`, title: t, text })),
      ),
    );
  });
  return el(
    "div",
    { class: "scroll-x" },
    el(
      "table",
      { class: "data screener-table" },
      el(
        "thead",
        {},
        el(
          "tr",
          {},
          [
            ["Stock", ""],
            ["Side", ""],
            ["Status", ""],
            ["Price", "Last price"],
            ["Entry", "Your entry price and the result so far for the side"],
            ["Targets", "Current fiscal year: conservative / optimistic (your assumptions)"],
            ["Earnings", "Next report"],
            ["Template", "Notes filled of the template's six"],
            ["Updated", ""],
            ["Flags", ""],
          ].map(([h, t]) => el("th", { title: t || null, text: h, style: h === "Flags" ? "text-align:left" : null })),
        ),
      ),
      el("tbody", {}, rowsHtml),
    ),
  );
}

function problems() {
  const list = (state.published && state.published.problems) || [];
  if (!list.length) return null;
  return el(
    "section",
    { class: "card panel", style: "margin-top:12px" },
    el("h2", { class: "panel-title", text: "Problems in data/ideas/" }),
    el(
      "ul",
      { class: "plain-list" },
      list.flatMap((p) => [
        ...p.errors.map((e) => el("li", {}, el("span", { class: "tag tag-warn", text: "Error" }), ` ${p.file}: ${e}`)),
        ...p.warnings.map((w) => el("li", {}, el("span", { class: "tag", text: "Warning" }), ` ${p.file}: ${w}`)),
      ]),
    ),
  );
}

function tools() {
  const file = el("input", {
    type: "file",
    accept: "application/json,.json",
    hidden: true,
    onchange: async (ev) => {
      const f = ev.target.files[0];
      if (!f) return;
      try {
        const n = await store.importFile(f);
        alert(`${n} idea(s) imported.`);
        render();
      } catch (err) {
        alert(`Import failed: ${err.message}`);
      }
    },
  });
  return el(
    "div",
    { class: "toolbar" },
    el(
      "div",
      { class: "seg", role: "group", "aria-label": "Show" },
      [
        ["open", "Open"],
        ["all", "All"],
        ["done", "Closed & dropped"],
      ].map(([k, label]) =>
        el("button", {
          type: "button",
          "aria-pressed": String(state.filter === k),
          text: label,
          onclick: () => {
            state.filter = k;
            render();
          },
        }),
      ),
    ),
    el("a", { class: "btn", href: "stock.html", text: "+ New idea" }),
    el("button", {
      type: "button",
      class: "btn",
      text: "Export this browser's ideas",
      onclick: () => store.exportAll(),
    }),
    el("button", { type: "button", class: "btn", text: "Import", onclick: () => file.click() }),
    file,
  );
}

function render() {
  const merged = Object.values(store.mergeIdeas(state.published));
  const shown = merged
    .filter((e) =>
      state.filter === "open"
        ? store.OPEN_STATUSES.includes(e.idea.status)
        : state.filter === "done"
          ? !store.OPEN_STATUSES.includes(e.idea.status)
          : true,
    )
    .sort(
      (a, b) =>
        store.STATUSES.indexOf(a.idea.status) - store.STATUSES.indexOf(b.idea.status) ||
        a.idea.ticker.localeCompare(b.idea.ticker),
    );
  setChildren(
    document.getElementById("content"),
    summary(merged),
    el(
      "section",
      { class: "card panel", style: "margin-top:12px" },
      el("h2", { class: "panel-title", text: `${shown.length} idea${shown.length === 1 ? "" : "s"}` }),
      tools(),
      shown.length
        ? table(shown)
        : el("p", {
            class: "muted",
            text: "No ideas here yet. Open a stock from the Screener (click its ticker) and start a trade idea.",
          }),
      el(
        "p",
        { class: "section-note" },
        "Ideas live in this browser until you publish them to the repository (data/ideas/, public). Export moves this browser's ideas to another device. Targets use each idea's own assumptions and today's consensus.",
      ),
    ),
    problems(),
  );
}

async function main() {
  try {
    state.stocks = await loadJSON("data/screener/stocks.json");
  } catch {
    state.stocks = null;
  }
  state.rows = state.stocks ? Object.fromEntries(rowsOf(state.stocks).map((r) => [r.t, r])) : {};
  state.published = await store.loadPublished();
  if (state.published.params) state.p = { ...DEFAULTS, ...state.published.params };
  render();
  const tickers = Object.keys(store.mergeIdeas(state.published)).filter((t) => state.rows[t]);
  const pages = await Promise.all(
    tickers.map((t) => loadJSON(`data/stocks/${t.replace(/[^A-Z0-9.-]/g, "")}.json`).catch(() => null)),
  );
  tickers.forEach((t, i) => (state.pages[t] = pages[i]));
  render();
}

main();
