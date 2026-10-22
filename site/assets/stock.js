// Trade idea page (lessons 30-33): the template's five sections for one stock, filled from the data where it
// can be, with the user's notes saved in this browser and published to the repository when ready.

import { el, loadJSON, setChildren } from "./common.js";
import { priceChart } from "./pricechart.js";
import * as store from "./ideas-store.js";
import {
  REALISM_TEXT,
  daysBetween,
  excluded,
  fmt,
  median,
  priceTargets,
  realism,
  rowsOf,
  sigmaMove,
  todayISO,
} from "./workbench.js";

// Defaults when data/ideas.json is not there yet (same as config.WORKBENCH)
const DEFAULTS = {
  horizon_days: 40,
  horizon_min: 20,
  horizon_max: 60,
  sigma_ok: 1,
  sigma_stretched: 2,
};
// Sector -> industry drivers to watch over 20-60 days (hints; lesson 33's "industry drivers")
const DRIVERS = {
  "Basic Materials": "Commodity prices (copper, steel, gold, chemicals feedstock), China demand, the US dollar.",
  "Communication Services": "Advertising spend, subscriber numbers, consumer confidence.",
  "Consumer Cyclical":
    "Consumer confidence (UMich), retail sales, jobs, gasoline prices, housing for home-related names.",
  "Consumer Defensive": "Input costs (grains, packaging), pricing power vs volumes, the US dollar.",
  Energy: "Oil (Brent, WTI) and natural gas prices, OPEC+ decisions, inventories, refining margins.",
  "Financial Services": "The yield curve and rates, credit spreads, loan growth, capital-markets activity.",
  Healthcare: "Drug-pricing policy, trial and FDA dates, procedure volumes.",
  Industrials: "ISM new orders and backlogs, freight volumes, capex plans (NFIB), defence budgets.",
  "Real Estate": "10-year Treasury yield, mortgage rates, occupancy and rents.",
  Technology: "Semiconductor pricing (DRAM/NAND), cloud and AI capex, enterprise IT budgets.",
  Utilities: "10-year Treasury yield, power prices, regulation, weather.",
};
const REALISM_TONE = { realistic: "tag-pos", stretched: "", unrealistic: "tag-warn" };

const S = {
  t: "",
  stocks: null,
  rows: [],
  row: null,
  page: null,
  cal: null,
  macro: null,
  p: DEFAULTS,
  entry: null, // merged entry from the ideas store
  idea: null, // the idea being edited (browser copy), or null
  horizon: DEFAULTS.horizon_days,
  work: {}, // target assumptions in use (also when no idea is saved)
  chart: null,
  chartBars: 126,
};

const num = (v) => (v === null || v === undefined || v === "" || Number.isNaN(Number(v)) ? null : Number(v));
const has = (v) => v !== null && v !== undefined;
const pctTone = (v) => (v > 0 ? "up" : v < 0 ? "down" : "");
const tagOf = (text, cls = "", title = null) => el("span", { class: `tag ${cls}`, text, title });

function section(id, title, note, ...children) {
  return el(
    "section",
    { class: "card panel idea-section", id },
    el("h2", { class: "panel-title", text: title }),
    note ? el("p", { class: "section-note", style: "margin-top:0", text: note }) : null,
    ...children,
  );
}

// ---------- saving ----------
let saveTimer = null;
function touch() {
  if (!S.idea) return;
  S.idea.updated = todayISO();
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    const ok = store.saveLocal(S.idea);
    refreshIdeaState(ok);
  }, 300);
}

function refreshIdeaState(ok = true) {
  S.entry = store.mergeIdeas(S.published)[S.t] || null;
  const box = document.getElementById("idea-state");
  if (box) setChildren(box, ...ideaStateNodes(ok));
  const list = document.getElementById("checklist");
  if (list) list.replaceChildren(checklistNode());
}

function noteArea(key, placeholder, rows = 3) {
  if (!S.idea)
    return el("p", { class: "muted small-note", text: "Start a trade idea (top of the page) to write notes here." });
  return el("textarea", {
    class: "note",
    rows,
    placeholder,
    "aria-label": placeholder,
    text: S.idea[key] || "",
    oninput: (ev) => {
      S.idea[key] = ev.target.value;
      touch();
    },
  });
}

// ---------- header ----------
function header() {
  const r = S.row;
  const pg = S.page || {};
  const cats = (S.stocks && S.stocks.categories) || {};
  const c = r && cats[r.cls];
  const tone = c ? { long: "tag-pos", short: "tag-neg" }[c.side] || "" : "";
  const links = [
    ["Yahoo Finance", `https://finance.yahoo.com/quote/${encodeURIComponent(S.t)}`],
    [
      "SEC filings",
      `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${encodeURIComponent(S.t)}&type=10-&dateb=&owner=include&count=40`,
    ],
    pg.profile && pg.profile.website ? ["Company website", pg.profile.website] : null,
  ].filter(Boolean);
  return el(
    "div",
    { class: "ind-head" },
    el(
      "div",
      { class: "ind-title" },
      el("h1", { class: "page-title", text: `${S.t}${r && r.name ? ` · ${r.name}` : ""}` }),
      c ? el("span", { class: `tag ${tone}`, title: c.text, text: c.label }) : null,
    ),
    r
      ? el(
          "p",
          { class: "facts" },
          el("span", { text: [r.sector, r.industry, pg.profile && pg.profile.country].filter(Boolean).join(" · ") }),
          ...links.map(([label, href]) => el("a", { href, target: "_blank", rel: "noopener", text: label })),
        )
      : null,
    r && r.why ? el("p", { class: "reading", text: r.why }) : null,
  );
}

function tiles() {
  const r = S.row;
  const pg = S.page || {};
  const vix = S.stocks.vix;
  const vols = [r.rv, r.iv].filter(has);
  const volx = vix && vols.length ? Math.min(...vols) / vix : null;
  const earn = pg.earnings;
  const days = earn ? daysBetween(todayISO(), earn.date) : null;
  const bias = S.macro && S.macro.bias;
  const tile = (label, value, foot, cls = "") =>
    el(
      "div",
      { class: "card tile" },
      el("div", { class: "tile-label", text: label }),
      el("div", { class: `tile-value small ${cls}`, text: value }),
      foot ? el("div", { class: "tile-foot", text: foot }) : null,
    );
  return el(
    "div",
    { class: "tiles" },
    tile(
      "Price",
      fmt.price(r.price),
      `${S.stocks.as_of}${pg.technicals && pg.technicals.date ? ` · close ${pg.technicals.date}` : ""}`,
    ),
    tile("Market cap", fmt.money(r.mcap), r.analysts ? `${r.analysts} analysts on EPS` : ""),
    tile(
      "Next earnings",
      earn ? earn.date : "–",
      earn ? `${days >= 0 ? `in ${days} days` : `${-days} days ago`} · ${earn.session}` : "no date from Yahoo",
    ),
    tile(
      "Volatility ÷ VIX",
      volx ? `${volx.toFixed(1)}×` : "–",
      `needs ≥ ${S.stocks.params.vol_vs_vix}× (lesson 22–29 filter)`,
      volx === null ? "" : volx >= S.stocks.params.vol_vs_vix ? "up" : "down",
    ),
    bias
      ? el(
          "a",
          { class: "card tile tile-link", href: "macro.html" },
          el("div", { class: "tile-label", text: "Macro bias (Macro Desk)" }),
          el("div", {
            class: `tile-value small ${bias.score > 0 ? "up" : bias.score < 0 ? "down" : ""}`,
            text: bias.label,
          }),
          el("div", { class: "tile-foot", text: `automatic reading, ${S.macro.as_of}` }),
        )
      : null,
  );
}

// ---------- the idea bar ----------
function ideaStateNodes(ok = true) {
  const e = S.entry;
  if (!e) return [];
  const [label, title] = store.STATE_TEXT[e.state];
  const out = [
    el("span", {
      class: `tag ${e.state === "changed" || e.state === "local" ? "tag-warn" : "tag-pos"}`,
      title,
      text: label,
    }),
  ];
  if (!ok) out.push(el("span", { class: "tag tag-warn", text: "This browser refused to save (private mode?)" }));
  if (S.idea) out.push(el("span", { class: "muted", text: ` Updated ${S.idea.updated}` }));
  return out;
}

function checklistNode() {
  if (!S.idea) return el("span");
  const items = store.checklist(S.idea);
  const done = items.filter((i) => i[2]).length;
  return el(
    "details",
    { class: "checklist" },
    el(
      "summary",
      {},
      el("b", { text: `Template ${done} of ${items.length} filled` }),
      " — discipline and consistency (lesson 33)",
    ),
    el(
      "ul",
      { class: "plain-list" },
      items.map(([key, label, ok]) =>
        el(
          "li",
          {},
          el("span", { class: ok ? "up" : "muted", text: ok ? "✓ " : "○ " }),
          el("a", { href: `#note-${key}`, text: label }),
        ),
      ),
    ),
  );
}

function startIdea(side) {
  const pub = S.entry && S.entry.published;
  S.idea = pub ? structuredClone(pub) : store.newIdea(S.t, side, S.row ? S.row.price : null, S.p.horizon_days);
  if (!pub) S.idea.side = side;
  store.saveLocal(S.idea);
  render();
}

function publishBox() {
  const e = S.entry;
  const idea = S.idea;
  const text = store.toMarkdown(idea);
  const isNew = !e || !e.published;
  const newUrl = store.githubNewUrl(idea);
  const tooLong = newUrl.length > 7500;
  const copy = el("button", {
    type: "button",
    class: "btn",
    text: "Copy the file text",
    onclick: async (ev) => {
      try {
        await navigator.clipboard.writeText(text);
        ev.target.textContent = "Copied ✓";
      } catch {
        ev.target.textContent = "Copy failed: use Download";
      }
    },
  });
  return el(
    "details",
    { class: "publish" },
    el(
      "summary",
      {},
      el("b", { text: "Publish to the repository" }),
      " — every device sees it, the daily update refreshes its numbers",
    ),
    el(
      "ol",
      { class: "steps" },
      isNew && !tooLong
        ? el(
            "li",
            {},
            el("a", {
              class: "btn",
              href: newUrl,
              target: "_blank",
              rel: "noopener",
              text: "Open GitHub with the file filled in",
            }),
            " Sign in if asked.",
          )
        : el(
            "li",
            {},
            copy,
            " then ",
            el("a", {
              class: "btn",
              href: isNew ? store.githubNewUrl(idea, false) : store.githubEditUrl(S.t),
              target: "_blank",
              rel: "noopener",
              text: isNew ? "Open GitHub (new file)" : "Open the file on GitHub",
            }),
            isNew ? " and paste the text." : " → select all the text → paste.",
          ),
      el("li", { text: "Click the green “Commit changes…” button, then “Commit changes” again (directly to main)." }),
      el("li", { text: "The site rebuilds in a few minutes; this page then shows “Published”." }),
    ),
    el(
      "p",
      { class: "section-note" },
      "The repository is public: anything published there can be read by anyone. Ideas kept only in this browser stay private to this device (use Export on the Ideas page to move them). ",
      el("button", {
        type: "button",
        class: "btn",
        text: "Download .md",
        onclick: () => store.download(store.fileName(S.t), text),
      }),
    ),
  );
}

function ideaBar() {
  if (!S.idea) {
    const c = S.row && S.stocks.categories[S.row.cls];
    const suggested = c && c.side === "short" ? "short" : "long";
    return el(
      "section",
      { class: "card panel idea-bar" },
      el("h2", { class: "panel-title", text: "Trade idea" }),
      el("p", {
        class: "section-note",
        style: "margin-top:0",
        text: "The sections below are filled from the data. Start an idea to add your own notes (business, KPIs, catalysts, timing, structure) and keep your own target assumptions. It is saved in this browser first.",
      }),
      el(
        "div",
        { class: "toolbar", style: "margin:0" },
        ["long", "short"].map((side) =>
          el("button", {
            type: "button",
            class: `btn ${side === suggested ? "btn-primary" : ""}`,
            text: `Start a ${side} idea`,
            onclick: () => startIdea(side),
          }),
        ),
        S.entry && S.entry.published
          ? el("span", { class: "muted", text: "A published idea exists: it will be loaded." })
          : null,
      ),
    );
  }
  const idea = S.idea;
  const dateInput = (label, key, value) =>
    el(
      "label",
      {},
      `${label} `,
      el("input", {
        class: "select",
        type: "date",
        value: value || "",
        "aria-label": key.replace("_", " "),
        onchange: (ev) => {
          idea[key] = ev.target.value || null;
          touch();
        },
      }),
    );
  const select = (label, value, options, onchange) =>
    el(
      "label",
      {},
      `${label} `,
      el(
        "select",
        { class: "select", onchange: (ev) => onchange(ev.target.value) },
        Object.entries(options).map(([v, text]) => el("option", { value: v, text, selected: v === value })),
      ),
    );
  return el(
    "section",
    { class: "card panel idea-bar" },
    el(
      "div",
      { class: "idea-bar-head" },
      el("h2", { class: "panel-title", style: "margin:0", text: "Trade idea" }),
      el("div", { id: "idea-state", class: "facts" }, ...ideaStateNodes()),
    ),
    el(
      "div",
      { class: "toolbar" },
      el(
        "div",
        { class: "seg", role: "group", "aria-label": "Side" },
        ["long", "short"].map((side) =>
          el("button", {
            type: "button",
            "aria-pressed": String(idea.side === side),
            text: side === "long" ? "Long" : "Short",
            onclick: () => {
              idea.side = side;
              touch();
              render();
            },
          }),
        ),
      ),
      select("Status", idea.status, store.STATUS_LABEL, (v) => {
        idea.status = v;
        if (v === "closed" && !idea.exit_date) idea.exit_date = todayISO();
        if (v === "closed" && !idea.exit_price && S.row) idea.exit_price = S.row.price;
        touch();
        render();
      }),
      el(
        "label",
        {},
        "Horizon ",
        el("input", {
          class: "select num-input",
          type: "number",
          min: 5,
          max: 120,
          step: 1,
          value: idea.horizon_days || S.p.horizon_days,
          onchange: (ev) => {
            idea.horizon_days = Math.max(1, Math.round(Number(ev.target.value) || S.p.horizon_days));
            S.horizon = idea.horizon_days;
            touch();
            render();
          },
        }),
        " days",
      ),
      el(
        "label",
        {},
        "Entry ",
        el("input", {
          class: "select num-input",
          type: "number",
          min: 0,
          step: "any",
          value: idea.entry_price ?? "",
          onchange: (ev) => {
            idea.entry_price = num(ev.target.value);
            touch();
            renderTargets();
          },
        }),
      ),
      dateInput("on", "entry_date", idea.entry_date || idea.opened),
      idea.status === "closed"
        ? el(
            "label",
            {},
            "Exit ",
            el("input", {
              class: "select num-input",
              type: "number",
              min: 0,
              step: "any",
              value: idea.exit_price ?? "",
              onchange: (ev) => {
                idea.exit_price = num(ev.target.value);
                touch();
              },
            }),
          )
        : null,
      idea.status === "closed" ? dateInput("on", "exit_date", idea.exit_date) : null,
      S.entry && S.entry.local
        ? el("button", {
            type: "button",
            class: "btn",
            text: "Delete from this browser",
            onclick: () => {
              if (!confirm(`Delete the ${S.t} idea from this browser? A published copy stays in the repository.`))
                return;
              store.removeLocal(S.t);
              refreshIdeaState();
              S.idea = S.entry ? structuredClone(S.entry.published) : null;
              S.work = {};
              render();
            },
          })
        : null,
    ),
    (idea.horizon_days || 0) < S.p.horizon_min || (idea.horizon_days || 0) > S.p.horizon_max
      ? el("p", { class: "section-note", text: `The course's window is ${S.p.horizon_min}–${S.p.horizon_max} days.` })
      : null,
    sideWarning(),
    idea.status === "closed"
      ? el("p", {
          class: "section-note",
          text: "A closed idea with entry and exit prices and dates counts in the track record on the Ideas page (return for the side, and alpha after the market move at the stock's beta).",
        })
      : null,
    el("div", { id: "checklist" }, checklistNode()),
    publishBox(),
  );
}

function sideWarning() {
  const c = S.row && S.stocks.categories[S.row.cls];
  if (!c || !S.idea || c.side === "either" || !["long", "short"].includes(c.side) || c.side === S.idea.side)
    return null;
  return el("p", {
    class: "callout",
    text: `A ${S.idea.side} on a ${c.label.toLowerCase()} (a ${c.side} candidate type): write down why in the notes.`,
  });
}

// ---------- section 1: quant table and price targets ----------
function quantSection() {
  const r = S.row;
  const pg = S.page;
  if (!pg)
    return section(
      "s1",
      "1 · Quant table",
      "Details for this stock are built by the daily update; check back after the next run.",
    );
  const q = pg.quant;
  const sh = q.shares;
  const labels = [`${q.labels[0] || "FY0"} reported`, `${q.labels[1] || "FY1"}E`, `${q.labels[2] || "FY2"}E`];
  const range = (i, lo, hi, f) => (has(q[lo][i]) && has(q[hi][i]) ? `${f(q[lo][i])}–${f(q[hi][i])}` : "");
  const eps = (v) => (has(v) ? v.toFixed(2) : "–");
  const ni = [
    pg.gaap && has(pg.gaap.net_income) ? pg.gaap.net_income : null,
    ...[1, 2].map((i) => (has(q.eps[i]) && sh ? q.eps[i] * sh : null)),
  ];
  const ps = q.sales.map((s) => (has(s) && s > 0 && r.mcap ? r.mcap / s : null));
  const pe0 = has(q.eps[0]) && q.eps[0] > 0 ? r.price / q.eps[0] : null;
  const line = (label, cells, title) =>
    el(
      "tr",
      {},
      el("td", { title }, label),
      cells.map((c) => (c instanceof Node ? c : el("td", { text: c ?? "–" }))),
    );
  const cell = (v, f, signed = false) =>
    el("td", { class: signed && has(v) ? pctTone(v) : "", text: has(v) ? f(v) : "–" });
  const withSub = (main, sub) => el("td", {}, main, sub ? el("span", { class: "sub", text: sub }) : null);
  const table = el(
    "table",
    { class: "data quant" },
    el(
      "thead",
      {},
      el(
        "tr",
        {},
        el("th", { text: "" }),
        labels.map((l) => el("th", { text: l })),
      ),
    ),
    el(
      "tbody",
      {},
      line(
        "EPS",
        [
          withSub(eps(q.eps[0])),
          withSub(eps(q.eps[1]), range(1, "eps_low", "eps_high", eps)),
          withSub(eps(q.eps[2]), range(2, "eps_low", "eps_high", eps)),
        ],
        "Consensus (adjusted) EPS; the range is the analysts' low–high",
      ),
      line("EPS growth", [el("td", { text: "" }), cell(r.eg1, fmt.pct, true), cell(r.eg2, fmt.pct, true)]),
      line(
        "P/E",
        [cell(pe0, (v) => v.toFixed(1)), cell(r.pe1, (v) => v.toFixed(1)), cell(r.pe2, (v) => v.toFixed(1))],
        "Price / EPS, only when EPS > 0",
      ),
      line(
        "PEG",
        [el("td", { text: "" }), cell(r.peg1, (v) => v.toFixed(2)), cell(r.peg2, (v) => v.toFixed(2))],
        "P/E / EPS growth %, only with positive growth",
      ),
      line("Sales $m", [
        withSub(fmt.millions(q.sales[0])),
        withSub(fmt.millions(q.sales[1]), range(1, "sales_low", "sales_high", fmt.millions)),
        withSub(fmt.millions(q.sales[2]), range(2, "sales_low", "sales_high", fmt.millions)),
      ]),
      line("Sales growth", [el("td", { text: "" }), cell(r.rg1, fmt.pct, true), cell(r.rg2, fmt.pct, true)]),
      line(
        "P/S",
        ps.map((v) => cell(v, (x) => x.toFixed(2))),
        "Market cap / sales",
      ),
      line("Net income $m", [
        withSub(fmt.millions(ni[0]), pg.gaap ? "GAAP (SEC)" : ""),
        withSub(fmt.millions(ni[1]), "EPS × shares"),
        withSub(fmt.millions(ni[2]), "EPS × shares"),
      ]),
      line(
        "Shares (m)",
        [cell(sh, (v) => fmt.millions(v)), el("td", { text: "" }), el("td", { text: "" })],
        "Shares outstanding today",
      ),
    ),
  );
  const rev = (q.revisions || [])[1];
  const comments = [
    ...(pg.story || []),
    pg.gaap && pg.gaap.text ? `GAAP vs adjusted (${q.labels[0]}): ${pg.gaap.text}` : null,
    has(r.eps1_rev90)
      ? `The ${q.labels[1]} EPS consensus moved ${fmt.pct(r.eps1_rev90)} in 90 days${rev && (has(rev.up) || has(rev.down)) ? `; last 30 days ${rev.up ?? 0} raised, ${rev.down ?? 0} cut` : ""}.`
      : null,
  ].filter(Boolean);
  return section(
    "s1",
    "1 · Quant table",
    "E = consensus estimate (Yahoo Finance). Reported EPS is the analysts' adjusted figure; GAAP net income comes from the SEC filing for the same year.",
    el("div", { class: "scroll-x" }, table),
    comments.length
      ? el(
          "ul",
          { class: "notes-list", style: "margin-top:12px" },
          comments.map((c) => el("li", { text: c })),
        )
      : null,
    el("div", { id: "targets" }),
  );
}

function assumptions() {
  const a = (S.idea && S.idea.assumptions) || S.work;
  return a;
}

function computeTargets() {
  const r = S.row;
  const q = S.page.quant;
  const a = assumptions();
  const eps = [q.eps[0], has(a.eps1) ? a.eps1 : q.eps[1], has(a.eps2) ? a.eps2 : q.eps[2]];
  const sales = [q.sales[0], has(a.sales1) ? a.sales1 : q.sales[1], has(a.sales2) ? a.sales2 : q.sales[2]];
  const t = priceTargets(r.price, eps, sales, q.shares, { pe: a.pe, ps: a.ps, sharesFwd: a.shares });
  const vol = r.iv || r.rv;
  const sig = sigmaMove(vol, S.horizon);
  return { t, vol, sig, eps, sales };
}

function setAssumption(key, value) {
  const a = assumptions();
  if (value === null) delete a[key];
  else a[key] = value;
  touch();
  renderTargets();
}

function renderTargets() {
  const box = document.getElementById("targets");
  if (!box || !S.page) return;
  const r = S.row;
  const q = S.page.quant;
  const a = assumptions();
  const { t, vol, sig } = computeTargets();
  const side = S.idea ? S.idea.side : (S.stocks.categories[r.cls] || {}).side === "short" ? "short" : "long";
  const input = (key, label, def, scale = 1, step = "any") =>
    el(
      "label",
      { class: has(a[key]) ? "own" : "" },
      el("span", { text: label }),
      el("input", {
        class: "select num-input",
        type: "number",
        step,
        placeholder: has(def) ? String(+(def / scale).toFixed(scale === 1 ? 2 : 0)) : "–",
        value: has(a[key]) ? +(a[key] / scale).toFixed(scale === 1 ? 4 : 2) : "",
        onchange: (ev) => setAssumption(key, num(ev.target.value) === null ? null : num(ev.target.value) * scale),
      }),
    );
  const defPe = has(q.eps[0]) && q.eps[0] > 0 ? r.price / q.eps[0] : null;
  const defPs = has(q.sales[0]) && q.sales[0] > 0 && q.shares ? r.price / (q.sales[0] / q.shares) : null;
  const preset = (label, which) =>
    el("button", {
      type: "button",
      class: "btn btn-small",
      text: label,
      onclick: () => {
        for (const [k, i] of [
          ["eps1", 1],
          ["eps2", 2],
        ]) {
          const v = which === "avg" ? null : q[`eps_${which}`][i];
          if (which === "avg" || has(v)) {
            if (v === null) delete a[k];
            else a[k] = v;
          }
        }
        touch();
        renderTargets();
      },
    });
  const tcell = (target, mv) => {
    if (!has(target)) return el("td", { class: "muted", text: "–" });
    const rl = realism(mv, sig, S.p);
    const favour = side === "long" ? mv > 0 : mv < 0;
    return el(
      "td",
      {},
      el("b", { text: fmt.price(target) }),
      el("span", { class: `sub ${favour ? "" : "down"}`, text: `${fmt.pct(mv)} from ${fmt.price(r.price)}` }),
      rl
        ? el("span", {
            class: `tag ${REALISM_TONE[rl.state]}`,
            title: REALISM_TEXT[rl.state],
            text: `${rl.z.toFixed(1)}σ`,
          })
        : null,
    );
  };
  const all = t.years.flatMap((y) => [y.eps_target, y.sales_target]).filter(has);
  const near = t.years[0];
  const rng = [near.eps_target, near.sales_target].filter(has).sort((x, y) => x - y);
  const notes = [];
  if (rng.length) {
    const [lo, hi] = [rng[0], rng[rng.length - 1]];
    notes.push(
      side === "long"
        ? `Range for ${q.labels[1]}: conservative ${fmt.price(lo)}, optimistic ${fmt.price(hi)}.`
        : `Range for ${q.labels[1]}: conservative ${fmt.price(hi)}, optimistic ${fmt.price(lo)}.`,
    );
    const against = side === "long" ? all.every((x) => x < r.price) : all.every((x) => x > r.price);
    if (against)
      notes.push(`Every target is on the wrong side of the price for a ${side}: the numbers do not support it.`);
  }
  if (sig) {
    notes.push(
      `A 1σ move over ${S.horizon} days is ±${sig.toFixed(1)}% (${S.page.targets.vol_source === "implied" && r.iv ? "implied" : "realised"} volatility ${vol.toFixed(0)}%). Targets beyond ${S.p.sigma_stretched}σ are unrealistic for the horizon: adjust them or take a partial target.`,
    );
  }
  if (S.idea && S.idea.entry_price)
    notes.push(`Since entry ${fmt.price(S.idea.entry_price)}: ${fmt.pct((r.price / S.idea.entry_price - 1) * 100)}.`);
  const an = S.page.analysts || {};
  if (has(an.target_mean))
    notes.push(
      `Analysts' 12-month targets: ${fmt.price(an.target_low)} – ${fmt.price(an.target_high)} (mean ${fmt.price(an.target_mean)}, ${an.opinions ?? "?"} analysts).`,
    );
  setChildren(
    box,
    el("h3", { class: "sub-title", text: "Price targets" }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text: "Upper / bullish: EPS growth at a constant P/E (price ÷ last reported EPS). Lower / realistic: consensus sales at a constant price-to-sales. Change any number to use your own; blank = consensus.",
    }),
    el(
      "div",
      { class: "assume-grid" },
      input("pe", "P/E", defPe),
      input("eps1", `EPS ${q.labels[1]}`, q.eps[1]),
      input("eps2", `EPS ${q.labels[2]}`, q.eps[2]),
      input("ps", "P/S", defPs),
      input("sales1", `Sales ${q.labels[1]} $m`, q.sales[1], 1e6),
      input("sales2", `Sales ${q.labels[2]} $m`, q.sales[2], 1e6),
      input("shares", "Shares fwd (m)", q.shares, 1e6),
    ),
    el(
      "div",
      { class: "toolbar", style: "margin:8px 0 12px" },
      el("span", { class: "muted", text: "EPS:" }),
      preset("Analysts' low", "low"),
      preset("Consensus", "avg"),
      preset("Analysts' high", "high"),
      el("button", {
        type: "button",
        class: "btn btn-small",
        text: "Reset all",
        onclick: () => {
          for (const k of Object.keys(a)) delete a[k];
          touch();
          renderTargets();
        },
      }),
      S.idea ? null : el("span", { class: "muted", text: "Not saved until you start an idea." }),
    ),
    el(
      "div",
      { class: "scroll-x" },
      el(
        "table",
        { class: "data targets-table" },
        el(
          "thead",
          {},
          el(
            "tr",
            {},
            el("th", { text: "" }),
            el("th", { text: q.labels[1] || "FY1" }),
            el("th", { text: q.labels[2] || "FY2" }),
          ),
        ),
        el(
          "tbody",
          {},
          el(
            "tr",
            {},
            el("td", {}, `EPS-based (P/E ${has(t.pe) ? t.pe.toFixed(1) : "–"})`),
            tcell(t.years[0].eps_target, t.years[0].eps_move),
            tcell(t.years[1].eps_target, t.years[1].eps_move),
          ),
          el(
            "tr",
            {},
            el("td", {}, `Sales-based (P/S ${has(t.ps) ? t.ps.toFixed(2) : "–"})`),
            tcell(t.years[0].sales_target, t.years[0].sales_move),
            tcell(t.years[1].sales_target, t.years[1].sales_move),
          ),
        ),
      ),
    ),
    has(t.pe)
      ? null
      : el("p", {
          class: "section-note",
          text: "No EPS-based target: the last reported EPS is a loss, so there is no constant P/E. Set your own P/E to use one.",
        }),
    el(
      "ul",
      { class: "notes-list", style: "margin-top:12px" },
      notes.map((n) => el("li", { text: n })),
    ),
  );
  if (S.chart) drawChart();
}

// ---------- section 2: sector comparison, drivers, volatility ----------
function sectorSection() {
  const r = S.row;
  const sec = S.stocks.sectors[r.sector] || {};
  const ind = S.rows.filter((x) => x.industry && x.industry === r.industry);
  const indUse = ind.filter((x) => !excluded(x, S.stocks.checks));
  const indMed = (k) => median(indUse.map((x) => x[k]));
  const cols = [
    ["mcap", "Mkt cap", fmt.money],
    ["pe1", "PE1", (v) => v.toFixed(1)],
    ["eg1", "EG1", fmt.pct],
    ["eg2", "EG2", fmt.pct],
    ["peg1", "PEG1", (v) => v.toFixed(2)],
    ["pe2", "PE2", (v) => v.toFixed(1)],
  ];
  const statRow = (label, get) =>
    el(
      "tr",
      {},
      el("td", {}, label),
      cols.map(([k, , f]) => {
        const v = get(k);
        return el("td", { text: has(v) ? f(v) : "–" });
      }),
    );
  const cmp = el(
    "table",
    { class: "data" },
    el(
      "thead",
      {},
      el(
        "tr",
        {},
        el("th", { text: "" }),
        cols.map(([, h]) => el("th", { text: h })),
      ),
    ),
    el(
      "tbody",
      {},
      el(
        "tr",
        { class: "highlight" },
        el("td", {}, el("b", { text: S.t })),
        cols.map(([k, , f]) =>
          el("td", {
            class: ["eg1", "eg2"].includes(k) && has(r[k]) ? pctTone(r[k]) : "",
            text: has(r[k]) ? f(r[k]) : "–",
          }),
        ),
      ),
      statRow(`Industry median (${indUse.length})`, indMed),
      statRow(`Sector average (${sec.n_used ?? "–"})`, (k) => sec[k] && sec[k].mean),
      statRow("Sector median", (k) => sec[k] && sec[k].median),
    ),
  );
  const positions = [
    has(r.eg1_pct) ? `EG1 at the ${r.eg1_pct.toFixed(0)}th percentile of the sector` : null,
    has(r.eg2_pct) ? `EG2 at the ${r.eg2_pct.toFixed(0)}th` : null,
    has(r.pe_prem)
      ? `P/E ${Math.abs(r.pe_prem).toFixed(0)}% ${r.pe_prem >= 0 ? "above" : "below"} the sector median`
      : null,
  ].filter(Boolean);
  const peers = ind
    .filter((x) => x.t !== S.t)
    .sort((x, y) => (y.mcap || 0) - (x.mcap || 0))
    .slice(0, 10);
  const cats = S.stocks.categories;
  const peerTable = el(
    "table",
    { class: "data" },
    el(
      "thead",
      {},
      el(
        "tr",
        {},
        ["Peer", "Mkt cap", "EG1", "EG2", "PE1", "PEG1", "3m return", "Type"].map((h) => el("th", { text: h })),
      ),
    ),
    el(
      "tbody",
      {},
      peers.map((x) =>
        el(
          "tr",
          { class: excluded(x, S.stocks.checks) ? "muted-row" : "" },
          el(
            "td",
            {},
            el("a", { href: `stock.html?t=${encodeURIComponent(x.t)}`, text: x.t }),
            el("span", { class: "sub", text: x.name || "" }),
          ),
          el("td", { text: fmt.money(x.mcap) }),
          el("td", { class: pctTone(x.eg1), text: fmt.pct(x.eg1) }),
          el("td", { class: pctTone(x.eg2), text: fmt.pct(x.eg2) }),
          el("td", { text: has(x.pe1) ? x.pe1.toFixed(1) : "–" }),
          el("td", { text: has(x.peg1) ? x.peg1.toFixed(2) : "–" }),
          el("td", { class: pctTone(x.r3m), text: fmt.pct(x.r3m) }),
          el("td", { class: "text-left" }, cats[x.cls] ? tagOf(cats[x.cls].label) : null),
        ),
      ),
    ),
  );
  return section(
    "s2",
    "2 · Against the sector",
    "Where the numbers sit against the sector and industry (clean stocks only), what drives the industry in the next 20–60 days, and how much the stock can move.",
    el("div", { class: "scroll-x" }, cmp),
    positions.length || (r.notes || []).length
      ? el("p", { class: "reading", style: "margin-top:10px", text: [...positions, ...(r.notes || [])].join(" · ") })
      : null,
    peers.length ? el("h3", { class: "sub-title", text: `${r.industry}: largest peers` }) : null,
    peers.length ? el("div", { class: "scroll-x" }, peerTable) : null,
    el("h3", { class: "sub-title", id: "note-drivers", text: "Industry drivers (20–60 days)" }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text: `Usually watched for ${r.sector}: ${DRIVERS[r.sector] || "–"} Tailwind or headwind for this idea?`,
    }),
    noteArea("drivers", "Industry drivers: tailwinds and headwinds over the next 20–60 days", 3),
    volatilityBlock(),
  );
}

function volatilityBlock() {
  const r = S.row;
  const vix = S.stocks.vix;
  const volOf = (x) => x.iv || x.rv;
  const secRows = S.rows.filter((x) => x.sector === r.sector && !excluded(x, S.stocks.checks));
  const indRows = secRows.filter((x) => x.industry === r.industry);
  const secVol = median(secRows.map(volOf));
  const indVol = median(indRows.map(volOf));
  const mine = volOf(r);
  const months = [1, 2, 3];
  const row = (label, vol) =>
    el(
      "tr",
      {},
      el("td", {}, label),
      el("td", { text: has(vol) ? `${vol.toFixed(0)}%` : "–" }),
      months.map((m) => el("td", { text: has(vol) ? `±${sigmaMove(vol, m * 30).toFixed(1)}%` : "–" })),
    );
  return el(
    "div",
    {},
    el("h3", { class: "sub-title", text: "Volatility and the expected move" }),
    el(
      "p",
      { class: "facts" },
      el("span", {}, "Realised (3m) ", el("b", { text: has(r.rv) ? `${r.rv.toFixed(0)}%` : "–" })),
      el("span", {}, "Implied (~45d options) ", el("b", { text: has(r.iv) ? `${r.iv.toFixed(0)}%` : "–" })),
      el("span", {}, "ATR(14) ", el("b", { text: has(r.atr) ? `${r.atr.toFixed(1)}% a day` : "–" })),
      el("span", {}, "VIX ", el("b", { text: vix ? vix.toFixed(1) : "–" })),
      el(
        "span",
        {},
        "Filter ",
        el("b", {
          class: r.vol_ok ? "up" : r.vol_ok === false ? "down" : "",
          text: r.vol_ok
            ? `passes (≥ ${S.stocks.params.vol_vs_vix}× VIX)`
            : r.vol_ok === false
              ? `below ${S.stocks.params.vol_vs_vix}× VIX`
              : "–",
        }),
      ),
    ),
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
            el("th", { text: "1σ move over" }),
            el("th", { text: "Volatility" }),
            months.map((m) => el("th", { text: `${m} month${m > 1 ? "s" : ""}` })),
          ),
        ),
        el(
          "tbody",
          {},
          row(S.t, mine),
          row(`Industry median (${indRows.length})`, indVol),
          row(`Sector median (${secRows.length})`, secVol),
        ),
      ),
    ),
    el("p", {
      class: "section-note",
      text: "Implied volatility where options were read, otherwise realised. About two moves in three stay within 1σ.",
    }),
    S.page && S.page.prices ? histogram(S.page.prices.c) : null,
  );
}

// Distribution of daily returns over the last year (lesson 33: realised volatility via the distribution).
function histogram(closes) {
  const c = closes.filter(has);
  const rets = [];
  for (let i = 1; i < c.length; i++) rets.push((c[i] / c[i - 1] - 1) * 100);
  if (rets.length < 30) return null;
  const mean = rets.reduce((a, b) => a + b, 0) / rets.length;
  const sd = Math.sqrt(rets.reduce((a, b) => a + (b - mean) ** 2, 0) / (rets.length - 1));
  const lim = Math.max(3, Math.ceil(Math.min(12, sd * 4)));
  const bins = 24;
  const w = (2 * lim) / bins;
  const counts = new Array(bins).fill(0);
  for (const x of rets) counts[Math.min(bins - 1, Math.max(0, Math.floor((x + lim) / w)))] += 1;
  const W = 600;
  const H = 120;
  const max = Math.max(...counts);
  const svg = el("svg", {
    class: "hist",
    viewBox: `0 0 ${W} ${H + 18}`,
    role: "img",
    "aria-label": `Daily returns over the last year: standard deviation ${sd.toFixed(2)}% a day`,
  });
  counts.forEach((n, i) => {
    const h = (n / max) * H;
    const center = -lim + (i + 0.5) * w;
    svg.append(
      el("rect", {
        svg: true,
        x: (i * W) / bins + 1,
        y: H - h,
        width: W / bins - 2,
        height: h,
        rx: 2,
        fill: Math.abs(center) > 2 * sd ? "var(--neg)" : "var(--s1)",
      }),
    );
  });
  for (const v of [-lim, 0, lim]) {
    const t = el("text", {
      svg: true,
      x: ((v + lim) / (2 * lim)) * W,
      y: H + 14,
      "text-anchor": v === -lim ? "start" : v === lim ? "end" : "middle",
    });
    t.textContent = `${v > 0 ? "+" : ""}${v}%`;
    svg.append(t);
  }
  const big = rets.filter((x) => Math.abs(x) > 2 * sd).length;
  return el(
    "div",
    { class: "hist-box" },
    el("p", {
      class: "section-note",
      text: `Daily returns, last ${rets.length} days: σ ${sd.toFixed(2)}% a day (≈ ${(sd * Math.sqrt(252)).toFixed(0)}% a year); ${big} days moved more than 2σ (red bars: fat tails).`,
    }),
    svg,
  );
}

// ---------- section 3: qualitative ----------
function qualitativeSection() {
  const pg = S.page || {};
  const prof = pg.profile || {};
  const own = pg.ownership || {};
  const an = pg.analysts || {};
  const pct = (v) => (has(v) ? `${(v * 100).toFixed(1)}%` : "–");
  return section(
    "s3",
    "3 · Business, KPIs and management",
    "What the company does in one or two sentences, the KPIs that drive its revenue and earnings, and what they tell you about management's operating plan (lessons 30–31).",
    prof.summary
      ? el(
          "details",
          { class: "profile" },
          el(
            "summary",
            {},
            el("b", { text: "Company profile (Yahoo Finance)" }),
            prof.employees ? ` · ${prof.employees.toLocaleString("en-US")} employees` : "",
            prof.city ? ` · ${prof.city}${prof.state ? `, ${prof.state}` : ""}` : "",
          ),
          el("p", { text: prof.summary }),
        )
      : null,
    el("h3", { class: "sub-title", id: "note-business", text: "Business in 1–2 sentences" }),
    noteArea("business", "What does the company do, for whom, and how does it make money?", 2),
    el("h3", { class: "sub-title", id: "note-kpis", text: "KPIs and management's plan" }),
    noteArea(
      "kpis",
      "The 3–5 KPIs behind revenue and earnings (from results and earnings calls), their trend, what management is aiming for, its track record, quality concerns…",
      5,
    ),
    el("h3", { class: "sub-title", text: "Ownership and the analysts" }),
    el(
      "p",
      { class: "facts" },
      el("span", {}, "Insiders ", el("b", { text: pct(own.insiders) })),
      el("span", {}, "Institutions ", el("b", { text: pct(own.institutions) })),
      el("span", {}, "Beta ", el("b", { text: has(own.beta) ? own.beta.toFixed(2) : "–" })),
      el(
        "span",
        {},
        "Rating ",
        el("b", {
          text: has(an.rec_mean) ? `${an.rec_mean.toFixed(2)} (${(an.rec_key || "").replace("_", " ")})` : "–",
        }),
        el("span", { class: "muted", text: " 1 = strong buy … 5 = sell" }),
      ),
      el("span", {}, "Opinions ", el("b", { text: an.opinions ?? "–" })),
    ),
  );
}

// ---------- section 4: earnings and catalysts ----------
function earningsSection() {
  const pg = S.page || {};
  const e = pg.earnings;
  const qtr = pg.quarter;
  const q = pg.quant;
  const today = todayISO();
  const days = e ? daysBetween(today, e.date) : null;
  const facts = e
    ? el(
        "p",
        { class: "reading" },
        el("b", { text: `Next earnings: ${e.date}` }),
        `, ${e.session}, ${days >= 0 ? `in ${days} days` : `${-days} days ago`}. `,
        days !== null && days >= 0
          ? days <= S.horizon
            ? `Inside the ${S.horizon}-day horizon: the report is a catalyst for this trade.`
            : `After the ${S.horizon}-day horizon.`
          : "",
      )
    : el("p", { class: "muted", text: "No earnings date from Yahoo. Check the company's investor-relations page." });
  const est = (o, k) => (o && has(o[k]) ? o[k] : null);
  const qTable = qtr
    ? el(
        "table",
        { class: "data" },
        el(
          "thead",
          {},
          el(
            "tr",
            {},
            ["Quarter to " + (qtr.end || "?"), "Low", "Consensus", "High", "Year ago", "Growth"].map((h) =>
              el("th", { text: h }),
            ),
          ),
        ),
        el(
          "tbody",
          {},
          el(
            "tr",
            {},
            el("td", { text: `EPS${qtr.analysts ? ` (${qtr.analysts} analysts)` : ""}` }),
            ["eps_low", "eps", "eps_high", "eps_year_ago"].map((k) =>
              el("td", { text: has(qtr[k]) ? qtr[k].toFixed(2) : "–" }),
            ),
            el("td", {
              text:
                est(qtr, "eps_year_ago") > 0 && has(qtr.eps) ? fmt.pct((qtr.eps / qtr.eps_year_ago - 1) * 100) : "–",
            }),
          ),
          el(
            "tr",
            {},
            el("td", { text: "Sales $m" }),
            ["rev_low", "rev", "rev_high", "rev_year_ago"].map((k) => el("td", { text: fmt.millions(qtr[k]) })),
            el("td", {
              text:
                est(qtr, "rev_year_ago") > 0 && has(qtr.rev) ? fmt.pct((qtr.rev / qtr.rev_year_ago - 1) * 100) : "–",
            }),
          ),
        ),
      )
    : null;
  const yTable = q
    ? el(
        "table",
        { class: "data" },
        el(
          "thead",
          {},
          el(
            "tr",
            {},
            ["Fiscal year", "EPS low", "EPS consensus", "EPS high", "Analysts", "Raised / cut (30d)"].map((h) =>
              el("th", { text: h }),
            ),
          ),
        ),
        el(
          "tbody",
          {},
          [1, 2].map((i) =>
            el(
              "tr",
              {},
              el("td", { text: `${q.labels[i] || ""}E` }),
              ["eps_low", "eps", "eps_high"].map((k) => el("td", { text: has(q[k][i]) ? q[k][i].toFixed(2) : "–" })),
              el("td", { text: q.analysts[i] ?? "–" }),
              el("td", {
                text: q.revisions && q.revisions[i] ? `${q.revisions[i].up ?? 0} / ${q.revisions[i].down ?? 0}` : "–",
              }),
            ),
          ),
        ),
      )
    : null;
  return section(
    "s4",
    "4 · Earnings and catalysts",
    "Catalysts turn an investment into a trade (lesson 32): the earnings report and, before it, non-earnings events inside the horizon.",
    facts,
    qTable ? el("div", { class: "scroll-x" }, qTable) : null,
    yTable ? el("div", { class: "scroll-x", style: "margin-top:10px" }, yTable) : null,
    el("h3", { class: "sub-title", id: "note-catalysts", text: "Non-earnings catalysts" }),
    catalystEditor(e),
    macroEvents(),
  );
}

function catalystEditor(earn) {
  if (!S.idea)
    return el("p", {
      class: "muted small-note",
      text: "Start a trade idea to list catalysts: product launches, investor days, regulatory decisions, index changes, peers' results…",
    });
  const list = S.idea.catalysts;
  const box = el("div", { class: "catalysts" });
  const draw = () => {
    const rows = list.map((c, i) =>
      el(
        "div",
        { class: "catalyst-row" },
        el("input", {
          class: "select",
          type: "date",
          value: c.date || "",
          "aria-label": "Date",
          onchange: (ev) => {
            c.date = ev.target.value || null;
            touch();
            drawChart();
            draw();
          },
        }),
        el("input", {
          class: "select grow",
          type: "text",
          value: c.text || "",
          placeholder: "What and why it matters",
          "aria-label": "Catalyst",
          oninput: (ev) => {
            c.text = ev.target.value.replace(/[\r\n]+/g, " ");
            touch();
          },
        }),
        el("button", {
          type: "button",
          class: "btn btn-small",
          text: "Remove",
          "aria-label": "Remove this catalyst",
          onclick: () => {
            list.splice(i, 1);
            touch();
            drawChart();
            draw();
          },
        }),
      ),
    );
    const today = todayISO();
    const before =
      earn && earn.date >= today
        ? list.filter((c) => (c.text || "").trim() && (!c.date || (c.date >= today && c.date <= earn.date)))
        : list.filter((c) => (c.text || "").trim());
    const warn =
      earn && earn.date >= today && !before.length
        ? el("p", {
            class: "callout",
            text: `No non-earnings catalyst before the ${earn.date} report: without one this may be an investment, not a trade (lesson 32).`,
          })
        : null;
    setChildren(
      box,
      ...rows,
      el("button", {
        type: "button",
        class: "btn",
        text: "+ Add a catalyst",
        onclick: () => {
          list.push({ date: null, text: "" });
          touch();
          draw();
        },
      }),
      warn,
    );
  };
  draw();
  return box;
}

function macroEvents() {
  if (!S.cal) return null;
  const today = todayISO();
  const end = new Date(Date.now() + S.horizon * 86400000).toISOString().slice(0, 10);
  const ev = S.cal.events.filter((x) => x.date >= today && x.date <= end && x.importance === "high");
  if (!ev.length) return null;
  return el(
    "details",
    { class: "macro-events" },
    el(
      "summary",
      {},
      el("b", { text: `Macro events in the next ${S.horizon} days (${ev.length})` }),
      " — from the Calendar",
    ),
    el(
      "ul",
      { class: "plain-list" },
      ev.map((x) =>
        el(
          "li",
          {},
          el("span", { class: "mono", text: x.date }),
          ` ${x.title}${x.region && x.region !== "US" ? ` (${x.region})` : ""}`,
        ),
      ),
    ),
    el("a", { href: "calendar.html", text: "Full calendar →" }),
  );
}

// ---------- section 5: timing and structure ----------
function timingSection() {
  const pg = S.page || {};
  const tech = pg.technicals || {};
  const sh = pg.short;
  const chartBox = el("div", { id: "chart-box" });
  if (pg.prices && pg.prices.d && pg.prices.d.length > 30) {
    chartBox.append(el("div", { id: "chart-slot" }));
  } else {
    chartBox.append(
      el("p", { class: "muted", text: "No daily prices yet: the chart appears after the next daily update." }),
    );
  }
  const f = (v) => (has(v) ? fmt.price(v) : "–");
  return section(
    "s5",
    "5 · Timing and structure",
    "Price action and the path of least resistance before you commit (lesson 33). The shaded area is the horizon ahead.",
    chartBox,
    tech.last
      ? el(
          "p",
          { class: "facts", style: "margin-top:8px" },
          el("span", {}, "50-day ", el("b", { text: f(tech.ma50) })),
          el("span", {}, "200-day ", el("b", { text: f(tech.ma200) })),
          el("span", {}, "52-week ", el("b", { text: `${f(tech.low52)} – ${f(tech.high52)}` })),
          el("span", {}, "Off the high ", el("b", { text: fmt.pct(tech.off_high) })),
          el(
            "span",
            {},
            "1m / 3m / 6m ",
            el("b", { text: `${fmt.pct(tech.r1m, 0)} / ${fmt.pct(tech.r3m, 0)} / ${fmt.pct(tech.r6m, 0)}` }),
          ),
          has(tech.rs_spy_3m)
            ? el(
                "span",
                {},
                "3m vs S&P 500 ",
                el("b", { class: pctTone(tech.rs_spy_3m), text: fmt.pct(tech.rs_spy_3m, 0) }),
              )
            : null,
          has(tech.rs_sector_3m)
            ? el(
                "span",
                {},
                `3m vs ${tech.sector_etf} `,
                el("b", { class: pctTone(tech.rs_sector_3m), text: fmt.pct(tech.rs_sector_3m, 0) }),
              )
            : null,
        )
      : null,
    tech.reading ? el("p", { class: "reading", text: tech.reading }) : null,
    el("h3", { class: "sub-title", text: "Short interest" }),
    sh
      ? el("p", { class: "reading", text: `${sh.text}${sh.date ? ` (as of ${sh.date})` : ""}` })
      : el("p", { class: "muted", text: "No short-interest data from Yahoo." }),
    el("h3", { class: "sub-title", id: "note-timing", text: "Timing and technicals" }),
    noteArea("timing", "Trend, support and resistance, where you would enter and add, what would prove you wrong…", 3),
    el("h3", { class: "sub-title", id: "note-structure_why", text: "Structure" }),
    S.idea
      ? el(
          "div",
          { class: "toolbar", style: "margin-bottom:8px" },
          el(
            "div",
            { class: "seg", role: "group", "aria-label": "Structure" },
            Object.entries(store.STRUCTURES).map(([k, label]) =>
              el("button", {
                type: "button",
                "aria-pressed": String(S.idea.structure === k),
                text: label,
                onclick: (ev) => {
                  S.idea.structure = k;
                  for (const b of ev.target.parentNode.children)
                    b.setAttribute("aria-pressed", String(b === ev.target));
                  touch();
                },
              }),
            ),
          ),
          el("span", { class: "muted", text: "Options are out of scope here (POTM)." }),
        )
      : null,
    noteArea("structure_why", "Why this structure, position size, how long you expect to hold it…", 2),
    el("h3", { class: "sub-title", id: "note-notes", text: "Review notes" }),
    noteArea("notes", "What changed since you opened the idea: price vs targets, new information, decisions…", 3),
  );
}

function drawChart() {
  const pg = S.page;
  const slot = document.getElementById("chart-slot");
  if (!pg || !pg.prices || !slot) return;
  const { t } = computeTargets();
  const lines = [];
  const y1 = t.years[0];
  if (has(y1.eps_target))
    lines.push({
      y: y1.eps_target,
      label: `EPS target ${S.page.quant.labels[1] || ""}`,
      tone: y1.eps_target >= S.row.price ? "pos" : "neg",
    });
  if (has(y1.sales_target))
    lines.push({
      y: y1.sales_target,
      label: `Sales target ${S.page.quant.labels[1] || ""}`,
      tone: y1.sales_target >= S.row.price ? "pos" : "neg",
    });
  if (S.idea && S.idea.entry_price) lines.push({ y: S.idea.entry_price, label: "Entry", tone: "neu" });
  const marks = [];
  if (pg.earnings) marks.push({ date: pg.earnings.date, label: "Earnings", tone: "earn" });
  for (const c of (S.idea && S.idea.catalysts) || [])
    if (c.date) marks.push({ date: c.date, label: (c.text || "Catalyst").slice(0, 18), tone: "cat" });
  S.chart = priceChart({
    prices: pg.prices,
    lines,
    ahead: { days: S.horizon, marks },
    bars: S.chartBars,
    onRange: (bars) => (S.chartBars = bars),
    label: `${S.t} daily prices with the 50- and 200-day averages`,
  });
  slot.replaceChildren(S.chart.node);
  S.chart.draw();
}

// ---------- page ----------
function render() {
  const content = document.getElementById("content");
  if (S.idea) S.horizon = S.idea.horizon_days || S.p.horizon_days;
  const scroll = window.scrollY;
  setChildren(
    content,
    header(),
    tiles(),
    ideaBar(),
    quantSection(),
    sectorSection(),
    qualitativeSection(),
    earningsSection(),
    timingSection(),
  );
  renderTargets();
  drawChart();
  window.scrollTo(0, scroll);
}

function picker(message) {
  const content = document.getElementById("content");
  const list = el(
    "datalist",
    { id: "tickers" },
    S.rows.map((r) => el("option", { value: r.t, text: r.name || "" })),
  );
  const go = (v) => {
    const t = (v || "").trim().toUpperCase();
    if (t) location.search = `?t=${encodeURIComponent(t)}`;
  };
  setChildren(
    content,
    message ? el("div", { class: "card notice", text: message }) : null,
    el(
      "form",
      {
        class: "toolbar",
        style: "margin-top:12px",
        onsubmit: (ev) => {
          ev.preventDefault();
          go(ev.target.elements.t.value);
        },
      },
      el("input", {
        class: "search",
        name: "t",
        list: "tickers",
        placeholder: "Ticker, e.g. CRWD",
        "aria-label": "Ticker",
        autocomplete: "off",
      }),
      list,
      el("button", { class: "btn", type: "submit", text: "Open" }),
    ),
    el("p", {
      class: "section-note",
      text: "Or pick a stock on the Screener and click its ticker. Your ideas are listed on the Ideas page.",
    }),
  );
}

async function main() {
  const params = new URLSearchParams(location.search);
  S.t = (params.get("t") || "").trim().toUpperCase();
  try {
    S.stocks = await loadJSON("data/screener/stocks.json");
  } catch {
    document
      .getElementById("content")
      .replaceChildren(
        el("div", { class: "card notice", text: "No screener data yet: it is built by the daily update." }),
      );
    return;
  }
  S.rows = rowsOf(S.stocks);
  if (!S.t) {
    picker("");
    return;
  }
  document.title = `${S.t} · Trade idea · PTM Dashboard`;
  S.row = S.rows.find((r) => r.t === S.t) || null;
  const safe = S.t.replace(/[^A-Z0-9.-]/g, "");
  const [page, cal, macro, published] = await Promise.all([
    S.row ? loadJSON(`data/stocks/${safe}.json`).catch(() => null) : null,
    loadJSON("data/calendar.json").catch(() => null),
    loadJSON("data/macro/latest.json").catch(() => null),
    store.loadPublished(),
  ]);
  Object.assign(S, { page, cal, macro, published });
  if (published.params) S.p = { ...DEFAULTS, ...published.params };
  S.horizon = S.p.horizon_days;
  S.entry = store.mergeIdeas(published)[S.t] || null;
  // the browser copy, else the published one (edits then make a browser copy)
  if (S.entry) S.idea = S.entry.local || structuredClone(S.entry.published);
  if (!S.row) {
    picker(
      `${S.t} is not in the screener universe (US-listed stocks above $${S.stocks.params.min_market_cap / 1e9}bn).${S.entry ? " Your saved idea is listed on the Ideas page." : ""}`,
    );
    return;
  }
  render();
}

main();
