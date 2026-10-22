// Shared helpers for every page. All text goes in through textContent (data is never trusted as HTML).

export const REPO = "https://github.com/SinaFXD/StockMarket";

export function el(tag, attrs = {}, ...children) {
  const node = document.createElementNS(
    tag === "svg" || attrs.svg ? "http://www.w3.org/2000/svg" : "http://www.w3.org/1999/xhtml",
    tag,
  );
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "svg" || value === null || value === undefined || value === false) continue;
    if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

// replaceChildren that skips null / false / undefined (optional parts of a page)
export function setChildren(node, ...children) {
  node.replaceChildren(...children.flat().filter((c) => c !== null && c !== undefined && c !== false));
}

export async function loadJSON(path) {
  const resp = await fetch(path, { cache: "no-cache" });
  if (!resp.ok) throw new Error(`${path}: HTTP ${resp.status}`);
  return resp.json();
}

// A signal score as a pill: ▲ +1 (blue), ● 0, ▼ −1 (red), or "awaiting".
export function scorePill(score) {
  if (score === null || score === undefined) return el("span", { class: "score none", text: "awaiting" });
  const cls = score > 0 ? "pos" : score < 0 ? "neg" : "";
  return el(
    "span",
    { class: `score ${cls}` },
    el("span", { "aria-hidden": "true", text: score > 0 ? "▲" : score < 0 ? "▼" : "●" }),
    score > 0 ? "+1" : score < 0 ? "−1" : "0",
  );
}

export const SERIES_STATUS = {
  ok: { label: "OK", tone: "good", icon: "✓" },
  stale: { label: "Stale", tone: "warning", icon: "!" },
  failed: { label: "Fetch failed", tone: "serious", icon: "!" },
  missing: { label: "No data", tone: "critical", icon: "×" },
};

export const MANUAL_STATUS = {
  ok: { label: "Up to date", tone: "good", icon: "✓" },
  due: { label: "New report out", tone: "warning", icon: "!" },
  awaiting: { label: "Awaiting data", tone: "critical", icon: "…" },
  empty: { label: "No rows yet", tone: "neutral", icon: "–" },
};

export function badge(meta, title) {
  return el(
    "span",
    { class: `badge ${meta.tone}`, title },
    el("span", { class: "dot", "aria-hidden": "true", text: meta.icon }),
    meta.label,
  );
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function fmtNumber(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  const abs = Math.abs(value);
  const digits = abs >= 100000 ? 0 : abs >= 1000 ? 1 : abs >= 10 ? 2 : 3;
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(value);
}

export function fmtObsDate(iso, frequency) {
  if (!iso) return "–";
  const [y, m] = iso.split("-").map(Number);
  if (frequency === "monthly") return `${MONTHS[m - 1]} ${y}`;
  if (frequency === "quarterly") return `${y} Q${Math.floor((m - 1) / 3) + 1}`;
  if (frequency === "annual") return String(y);
  return iso;
}

export function fmtMonth(month) {
  if (!month) return "–";
  const [y, m] = month.split("-").map(Number);
  return `${MONTHS[m - 1]} ${y}`;
}

export function fmtDateTime(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso || "–";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}, ${pad(d.getUTCHours())}:${pad(
    d.getUTCMinutes(),
  )} UTC`;
}

export function relTime(iso, now = Date.now()) {
  const seconds = Math.round((now - new Date(iso).getTime()) / 1000);
  if (!Number.isFinite(seconds)) return "";
  if (seconds < 90) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 90) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 36) return `${hours} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

// ---- sparkline: one series, 2px line, end dot with a surface ring, crosshair tooltip on hover/focus ----

let tooltipNode = null;

function tooltip() {
  if (!tooltipNode) {
    tooltipNode = el("div", { class: "tooltip", role: "status", hidden: true });
    document.body.append(tooltipNode);
  }
  return tooltipNode;
}

export function sparkline(points, { label = "", unit = "", frequency = "" } = {}) {
  const W = 120;
  const H = 32;
  const PAD = 4;
  if (!points || points.length < 2) return el("span", { class: "muted", text: "–" });
  const values = points.map((p) => p[1]);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const x = (i) => PAD + (i * (W - 2 * PAD)) / (points.length - 1);
  const y = (v) => (max === min ? H / 2 : H - PAD - ((v - min) * (H - 2 * PAD)) / (max - min));
  const d = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join("");
  const last = points.length - 1;
  const first = points[0];
  const end = points[last];
  const summary = `${label}: trend over the last two years, from ${fmtNumber(first[1])} (${first[0]}) to ${fmtNumber(
    end[1],
  )} (${end[0]})`;

  const svg = el("svg", {
    class: "spark",
    viewBox: `0 0 ${W} ${H}`,
    role: "img",
    "aria-label": summary,
    tabindex: "0",
  });
  const cross = el("line", { svg: true, y1: 0, y2: H, stroke: "var(--axis)", "stroke-width": 1, visibility: "hidden" });
  const path = el("path", {
    svg: true,
    d,
    fill: "none",
    stroke: "var(--spark)",
    "stroke-width": 2,
    "stroke-linejoin": "round",
    "stroke-linecap": "round",
    "vector-effect": "non-scaling-stroke",
  });
  const dot = el("circle", {
    svg: true,
    cx: x(last),
    cy: y(end[1]),
    r: 3.5,
    fill: "var(--spark)",
    stroke: "var(--surface)",
    "stroke-width": 2,
  });
  const hit = el("rect", { svg: true, x: 0, y: -6, width: W, height: H + 12, fill: "transparent" });
  svg.append(cross, path, dot, hit);

  const show = (i, clientX, clientY) => {
    const p = points[i];
    cross.setAttribute("x1", x(i));
    cross.setAttribute("x2", x(i));
    cross.setAttribute("visibility", "visible");
    dot.setAttribute("cx", x(i));
    dot.setAttribute("cy", y(p[1]));
    const tip = tooltip();
    tip.replaceChildren(
      el("strong", { text: `${fmtNumber(p[1])}${unit ? " " + unit : ""}` }),
      el("span", { class: "muted", text: fmtObsDate(p[0], frequency === "daily" ? "" : frequency) }),
    );
    tip.hidden = false;
    const box = tip.getBoundingClientRect();
    const left = Math.min(window.innerWidth - box.width - 8, Math.max(8, clientX - box.width / 2));
    tip.style.left = `${left}px`;
    tip.style.top = `${Math.max(8, clientY - box.height - 12)}px`;
  };
  const hide = () => {
    cross.setAttribute("visibility", "hidden");
    dot.setAttribute("cx", x(last));
    dot.setAttribute("cy", y(end[1]));
    if (tooltipNode) tooltipNode.hidden = true;
  };
  svg.addEventListener("pointermove", (ev) => {
    const rect = svg.getBoundingClientRect();
    const rel = ((ev.clientX - rect.left) / rect.width) * W;
    const i = Math.max(0, Math.min(last, Math.round(((rel - PAD) / (W - 2 * PAD)) * last)));
    show(i, ev.clientX, rect.top);
  });
  svg.addEventListener("pointerleave", hide);
  svg.addEventListener("focus", () => {
    const rect = svg.getBoundingClientRect();
    show(last, rect.right, rect.top);
  });
  svg.addEventListener("blur", hide);
  return svg;
}

export function setFooterYear() {
  for (const node of document.querySelectorAll("[data-year]")) node.textContent = new Date().getFullYear();
}
