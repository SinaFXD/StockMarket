// The Macro Desk as plain text ("Copy brief") and as a CSV file ("Download CSV"). Pure functions, no DOM:
// tested by tests/js/brief.test.mjs.

const signed = (x, d = 2) =>
  x === null || x === undefined ? "–" : `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x).toFixed(d)}`;
const score = (x) => (x === null || x === undefined ? "awaiting" : x > 0 ? "+1" : x < 0 ? "−1" : "0");
const ordinal = (p) => {
  const n = Math.round(p);
  const suffix = n % 100 >= 11 && n % 100 <= 13 ? "th" : { 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th";
  return `${n}${suffix}`;
};

// Extremes against the indicator's own last 10 years (top or bottom tenth).
export function extremes(signals, low = 10, high = 90) {
  return signals.filter(
    (s) => typeof s.percentile_10y === "number" && (s.percentile_10y >= high || s.percentile_10y <= low),
  );
}

// bias: {score, label, used, total, blocks: {key: {label, score}}}; changes: [{name, from, to, from_state, to_state, bias}]
// regime: data/regime.json or null.
export function briefText({ asOf, bias, signals, overrides = {}, changes = [], alerts = [], regime = null, url = "" }) {
  const lines = [`PTM Macro Desk brief, ${asOf}`, ""];
  const n = Object.keys(overrides).length;
  lines.push(
    `Portfolio bias: ${bias.label} (${signed(bias.score)}; ${bias.used} of ${bias.total} indicators` +
      (n ? `; ${n} override${n > 1 ? "s" : ""} of mine` : "") +
      ")",
  );
  lines.push(
    `Blocks: ${Object.values(bias.blocks)
      .map((b) => `${b.label} ${signed(b.score)}`)
      .join(" · ")}`,
  );
  lines.push("", "What changed in the last month:");
  if (!changes.length) lines.push("- No score changed.");
  for (const c of changes)
    lines.push(
      c.bias || c.id === "bias"
        ? `- ${c.name}: ${signed(c.from)} → ${signed(c.to)} (${c.from_state} → ${c.to_state})`
        : `- ${c.name}: ${score(c.from)} → ${score(c.to)}${c.to_state ? ` (${c.to_state})` : ""}`,
    );
  if (alerts.length) {
    lines.push("", "Read together:");
    for (const a of alerts) lines.push(`- ${a}`);
  }
  const ext = extremes(signals);
  if (ext.length) {
    lines.push("", "At extremes against the last 10 years:");
    for (const s of ext) lines.push(`- ${s.name}: ${ordinal(s.percentile_10y)} percentile (${s.state})`);
  }
  if (regime && regime.now) {
    const r = regime.recession && regime.recession.latest;
    const t = regime.taylor && regime.taylor.latest;
    lines.push("", "Bigger picture:");
    lines.push(
      `- Regime: ${regime.now.label} (data for ${regime.now.month})${regime.now.borderline ? ", close to a line" : ""}`,
    );
    if (r) lines.push(`- Recession odds for ${r.for_month} (yield-curve model): ${r.prob.toFixed(1)}%`);
    if (t && t.fed_funds !== null && t.fed_funds !== undefined)
      lines.push(`- Fed funds ${t.fed_funds.toFixed(2)}% vs Taylor rule ${t.taylor.toFixed(2)}%`);
  }
  lines.push("", "Educational tool, not investment advice." + (url ? ` ${url}` : ""));
  return lines.join("\n");
}

export function csvCell(v) {
  if (v === null || v === undefined) return "";
  const s = String(v);
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

const BOM = String.fromCharCode(0xfeff); // lets Excel read the file as UTF-8

export const CSV_COLUMNS = [
  "block",
  "indicator",
  "id",
  "as_of",
  "state",
  "auto_score",
  "your_score",
  "score_used",
  "percentile_10y",
  "reason",
];

// One row per indicator; Excel-friendly (byte-order mark, CRLF).
export function boardCsv({ signals, blocks, overrides = {} }) {
  const rows = [CSV_COLUMNS];
  for (const s of signals) {
    const own = s.id in overrides ? overrides[s.id] : null;
    rows.push([
      blocks[s.block] || s.block,
      s.name,
      s.id,
      s.as_of,
      s.state,
      s.score,
      own,
      own === null ? s.score : own,
      s.percentile_10y,
      s.reason_en,
    ]);
  }
  return BOM + rows.map((r) => r.map(csvCell).join(",")).join("\r\n") + "\r\n";
}
