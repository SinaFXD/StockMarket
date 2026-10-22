// Saved trade ideas. Two places, one format:
// - this browser (localStorage): private, instant, but only on this device (export/import moves them);
// - the repository (data/ideas/<TICKER>.md, published as data/ideas.json): every device, daily refreshed,
//   but public. "Publish to GitHub" opens GitHub's own editor with the file filled in.
// toMarkdown() writes the format pipeline/workbench/ideas.py reads: keep the two in sync.

import { REPO, loadJSON } from "./common.js";

const KEY = "ptm.ideas.v1";
export const SIDES = ["long", "short"];
export const STATUSES = ["researching", "ready", "active", "closed", "dropped"];
export const STATUS_LABEL = {
  researching: "Researching",
  ready: "Ready",
  active: "Active",
  closed: "Closed",
  dropped: "Dropped",
};
export const OPEN_STATUSES = ["researching", "ready", "active"];
export const STRUCTURES = { stock: "Stock", margin: "Stock on margin", cfd: "CFD" };
export const ASSUMPTIONS = ["pe", "ps", "eps1", "eps2", "sales1", "sales2", "shares"];
// key -> heading in the file (the order of the template)
export const SECTIONS = [
  ["business", "Business"],
  ["kpis", "KPIs and management plan"],
  ["drivers", "Industry drivers"],
  ["catalysts", "Catalysts"],
  ["timing", "Timing and technicals"],
  ["structure_why", "Structure"],
  ["notes", "Review notes"],
];
export const TEXT_KEYS = SECTIONS.map(([k]) => k).filter((k) => k !== "catalysts");

export function newIdea(ticker, side, price, horizon) {
  const today = new Date().toISOString().slice(0, 10);
  const idea = {
    ticker,
    side,
    status: "researching",
    opened: today,
    updated: today,
    structure: "stock",
    entry_price: price || null,
    horizon_days: horizon,
    assumptions: {},
    catalysts: [],
  };
  for (const k of TEXT_KEYS) idea[k] = "";
  return idea;
}

// ---- this browser ----
export function loadLocal() {
  try {
    const obj = JSON.parse(localStorage.getItem(KEY) || "{}");
    return obj && typeof obj === "object" ? obj : {};
  } catch {
    return {};
  }
}

function storeLocal(all) {
  try {
    localStorage.setItem(KEY, JSON.stringify(all));
    return true;
  } catch {
    return false;
  }
}

export function saveLocal(idea) {
  const all = loadLocal();
  all[idea.ticker] = idea;
  return storeLocal(all);
}

export function removeLocal(ticker) {
  const all = loadLocal();
  delete all[ticker];
  return storeLocal(all);
}

// ---- the repository ----
export async function loadPublished() {
  try {
    return await loadJSON("data/ideas.json");
  } catch {
    return { ideas: [], problems: [], params: null };
  }
}

// Canonical form for comparing a browser copy with the published one.
function canonical(idea) {
  const out = {};
  for (const k of ["side", "status", "opened", "updated", "structure", "entry_price", "horizon_days"])
    out[k] = idea[k] === undefined || idea[k] === "" ? null : idea[k];
  out.assumptions = Object.fromEntries(
    ASSUMPTIONS.filter((k) => idea.assumptions && idea.assumptions[k] != null).map((k) => [
      k,
      Number(idea.assumptions[k]),
    ]),
  );
  for (const k of TEXT_KEYS) out[k] = (idea[k] || "").trim();
  out.catalysts = (idea.catalysts || [])
    .filter((c) => (c.text || "").trim() || c.date)
    .map((c) => ({ date: c.date || null, text: (c.text || "").trim() }));
  return JSON.stringify(out);
}

// Every idea, from both places: {ticker: {idea, local, published, state}} where state is
// "published" (same in both), "changed" (browser copy differs), "local" (only here) or "repo" (only published).
export function mergeIdeas(published) {
  const local = loadLocal();
  const pub = Object.fromEntries((published.ideas || []).map((i) => [i.ticker, i]));
  const out = {};
  for (const t of new Set([...Object.keys(local), ...Object.keys(pub)])) {
    const l = local[t];
    const p = pub[t];
    let state = "repo";
    if (l && p) state = canonical(l) === canonical(p) ? "published" : "changed";
    else if (l) state = "local";
    out[t] = { idea: l || p, local: l || null, published: p || null, state };
  }
  return out;
}

export const STATE_TEXT = {
  published: ["Published", "Saved in the repository; this browser has the same copy."],
  changed: ["Changed here", "This browser has changes that are not published yet."],
  local: ["Only in this browser", "Not published: other devices cannot see it."],
  repo: ["Published", "Saved in the repository."],
};

// ---- the file ----
function line(s) {
  return String(s ?? "")
    .replace(/[\r\n]+/g, " ")
    .trim();
}

export function toMarkdown(idea) {
  const head = ["---", `side: ${idea.side}`, `status: ${idea.status}`];
  if (idea.opened) head.push(`opened: ${idea.opened}`);
  if (idea.updated) head.push(`updated: ${idea.updated}`);
  if (idea.horizon_days) head.push(`horizon_days: ${Math.round(idea.horizon_days)}`);
  head.push(`structure: ${idea.structure || "stock"}`);
  if (idea.entry_price) head.push(`entry_price: ${Number(idea.entry_price)}`);
  const a = ASSUMPTIONS.filter((k) => idea.assumptions && idea.assumptions[k] != null);
  if (a.length) head.push("assumptions:", ...a.map((k) => `  ${k}: ${Number(idea.assumptions[k])}`));
  head.push("---");
  const body = [];
  for (const [key, heading] of SECTIONS) {
    body.push("", `## ${heading}`);
    if (key === "catalysts") {
      for (const c of idea.catalysts || []) {
        const text = line(c.text);
        if (!text && !c.date) continue;
        body.push(c.date ? `- ${c.date}: ${text}` : `- ${text}`);
      }
    } else {
      const text = (idea[key] || "").replace(/\r\n/g, "\n").trim();
      if (text) body.push(text);
    }
  }
  return `${head.join("\n")}\n${body.join("\n")}\n`;
}

export function fileName(ticker) {
  return `${ticker.toUpperCase().replace(/[^A-Z0-9.-]/g, "")}.md`;
}

// GitHub's "new file" page accepts the file name and its text in the address.
export function githubNewUrl(idea, withText = true) {
  const q = new URLSearchParams({ filename: `data/ideas/${fileName(idea.ticker)}` });
  if (withText) q.set("value", toMarkdown(idea));
  return `${REPO}/new/main?${q.toString()}`;
}

export function githubEditUrl(ticker) {
  return `${REPO}/edit/main/data/ideas/${fileName(ticker)}`;
}

export function githubFileUrl(ticker) {
  return `${REPO}/blob/main/data/ideas/${fileName(ticker)}`;
}

export function download(name, text, type = "text/markdown") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function exportAll() {
  download(
    `ptm-ideas-${new Date().toISOString().slice(0, 10)}.json`,
    JSON.stringify(loadLocal(), null, 1),
    "application/json",
  );
}

// Adds the ideas of an exported file; an idea already here is replaced only by a more recent one.
export async function importFile(file) {
  const obj = JSON.parse(await file.text());
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) throw new Error("not an ideas export file");
  const all = loadLocal();
  let added = 0;
  for (const [t, idea] of Object.entries(obj)) {
    if (!idea || typeof idea !== "object" || idea.ticker !== t || !SIDES.includes(idea.side)) continue;
    if (all[t] && (all[t].updated || "") > (idea.updated || "")) continue;
    all[t] = idea;
    added += 1;
  }
  if (!storeLocal(all)) throw new Error("this browser does not allow saving");
  return added;
}

// The template's own checklist (discipline and consistency, lesson 33): the parts only the user can fill.
export function checklist(idea) {
  const filled = (k) => (idea[k] || "").trim().length > 0;
  return [
    ["business", "Business in 1–2 sentences", filled("business")],
    ["kpis", "KPIs and management's plan", filled("kpis")],
    ["drivers", "Industry drivers for the next 20–60 days", filled("drivers")],
    ["catalysts", "At least one non-earnings catalyst", (idea.catalysts || []).some((c) => (c.text || "").trim())],
    ["timing", "Timing: chart and price action", filled("timing")],
    ["structure_why", "Structure and why", filled("structure_why")],
  ];
}
