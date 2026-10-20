import { MANUAL_STATUS, badge, el, fmtDateTime, loadJSON, relTime } from "./common.js";

function row(label, value) {
  return [el("dt", { text: label }), el("dd", {}, value)];
}

async function main() {
  const list = document.getElementById("pipeline");
  let health;
  try {
    health = await loadJSON("data/health.json");
  } catch {
    list.replaceChildren(...row("Last update", "not run yet"));
    return;
  }
  const s = health.summary.series;
  const m = health.summary.manual;
  const manualTone = m.errors ? "critical" : m.awaiting ? "awaiting" : m.due ? "due" : "ok";
  const manualBadge =
    manualTone === "critical"
      ? badge({ label: `${m.errors} error${m.errors > 1 ? "s" : ""}`, tone: "critical", icon: "×" })
      : badge(MANUAL_STATUS[manualTone]);
  list.replaceChildren(
    ...row("Last update", `${fmtDateTime(health.generated_at)} (${relTime(health.generated_at)})`),
    ...row("Automatic series up to date", `${s.ok} of ${s.total}`),
    ...row("Series needing attention", String(s.stale + s.failed + s.missing)),
    ...row("Manual files awaiting data", String(m.awaiting)),
    ...row("Manual data", manualBadge),
  );
}

main();
