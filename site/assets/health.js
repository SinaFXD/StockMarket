import {
  MANUAL_STATUS,
  REPO,
  SERIES_STATUS,
  badge,
  el,
  fmtDateTime,
  fmtMonth,
  fmtNumber,
  fmtObsDate,
  loadJSON,
  relTime,
  sparkline,
} from "./common.js";

const MAX_ISSUES = 15;
const capitalize = (text) => (text ? text[0].toUpperCase() + text.slice(1) : text);
const fmtDay = (iso) => {
  const d = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
};
const state = { filter: "all", query: "" };

function tile(label, value, of, foot, tone) {
  return el(
    "div",
    { class: "card tile" },
    el("div", { class: "tile-label", text: label }),
    el("div", { class: "tile-value" }, String(value), of ? el("span", { class: "of", text: ` / ${of}` }) : null),
    foot ? el("div", { class: "tile-foot" }, tone ? badge(tone) : null, tone ? " " : null, foot) : null,
  );
}

function renderTiles(health) {
  const s = health.summary.series;
  const m = health.summary.manual;
  const problems = s.stale + s.failed + s.missing;
  document
    .getElementById("tiles")
    .replaceChildren(
      tile("Automatic series up to date", s.ok, s.total, null),
      tile(
        "Series needing attention",
        problems,
        null,
        problems ? `${s.stale} stale, ${s.failed} failed, ${s.missing} missing` : "none",
      ),
      tile("Manual files up to date", m.ok, m.files - (m.empty || 0), m.due ? `${m.due} with a new report out` : null),
      tile(
        "Manual files awaiting data",
        m.awaiting,
        null,
        m.awaiting ? "left out of the scores until entered" : "none",
      ),
      tile("Errors in manual files", m.errors, null, m.errors ? "see the cards below" : "none"),
    );
}

function issueList(issues, cls) {
  const shown = issues.slice(0, MAX_ISSUES).map((i) => el("li", { text: i.text }));
  if (issues.length > MAX_ISSUES)
    shown.push(el("li", { class: "muted", text: `and ${issues.length - MAX_ISSUES} more` }));
  return el("ul", { class: `issues ${cls}` }, shown);
}

function manualCard(m) {
  const status =
    m.optional && m.status === "empty"
      ? { ...MANUAL_STATUS.empty, label: "Optional, no rows yet" }
      : MANUAL_STATUS[m.status];
  const badges = [badge(status)];
  if (m.errors.length) {
    badges.push(
      badge({ label: `${m.errors.length} error${m.errors.length > 1 ? "s" : ""}`, tone: "critical", icon: "×" }),
    );
  }
  const facts = el(
    "p",
    { class: "facts" },
    el("span", {}, "Valid rows ", el("b", { text: String(m.rows) })),
    el("span", {}, "First ", el("b", { text: fmtMonth(m.first_month) })),
    el("span", {}, "Last ", el("b", { text: fmtMonth(m.last_month) })),
  );
  const tracked = m.tracked.length
    ? el(
        "ul",
        { class: "tracked" },
        m.tracked.map((t) =>
          el(
            "li",
            {},
            el(
              "div",
              { class: "t-head" },
              el("span", { class: "t-name", text: t.label }),
              badge(MANUAL_STATUS[t.status]),
            ),
            el("div", { class: "t-reason", text: `${capitalize(t.reason)}.` }),
            el("div", {
              class: "t-next",
              text: `Next: ${fmtMonth(t.next_month)} data, out ~${fmtDay(t.next_due)} (${t.release_rule})`,
            }),
          ),
        ),
      )
    : null;
  return el(
    "article",
    { class: "card manual-card" },
    el(
      "header",
      {},
      el("h3", { text: m.title }),
      el("div", { class: "file mono", text: m.file }),
      el("div", { class: "badges" }, badges),
    ),
    facts,
    tracked,
    m.errors.length ? issueList(m.errors, "errors") : null,
    m.warnings.length
      ? el(
          "details",
          { class: "warnings" },
          el("summary", { text: `${m.warnings.length} warning${m.warnings.length > 1 ? "s" : ""}` }),
          issueList(m.warnings, ""),
        )
      : null,
    el(
      "div",
      { class: "card-actions" },
      el("a", { href: `${REPO}/edit/main/${m.file}`, target: "_blank", rel: "noopener", text: "Edit on GitHub" }),
      el("a", {
        href: `${REPO}/blob/main/data/manual/README.md`,
        target: "_blank",
        rel: "noopener",
        text: "How to enter data",
      }),
      el("span", { class: "muted", text: m.source }),
    ),
  );
}

function renderManual(health) {
  document.getElementById("manual").replaceChildren(...health.manual.map(manualCard));
}

function seriesRow(s) {
  const meta = SERIES_STATUS[s.status];
  const fetch = s.fetch || {};
  let note = null;
  if (s.status === "failed") {
    note = `Fetch failed: ${fetch.error}. Showing the last good copy${fetch.data_fetched_at ? ` from ${fmtDateTime(fetch.data_fetched_at)}` : ""}.`;
  } else if (s.status === "missing") {
    note = `No data: ${fetch.error || "never fetched"}.`;
  } else if (s.status === "stale") {
    note = `Last observation is ${s.age_days} days old (limit ${s.max_age_days}); the source may have stopped updating.`;
  }
  const vint = s.vintages ? ` · ${fmtNumber(s.vintages.rows)} vintage rows` : "";
  return el(
    "tr",
    { class: "row" },
    el(
      "td",
      { class: "c-series" },
      el("div", { class: "s-label", text: s.label }),
      el(
        "div",
        { class: "s-meta" },
        el("a", { href: s.url, target: "_blank", rel: "noopener", text: `${s.source} ${s.id}` }),
        ` · ${s.frequency || "?"}${vint}`,
      ),
      note ? el("div", { class: "s-error", text: note }) : null,
    ),
    el(
      "td",
      { class: "num c-last" },
      el(
        "div",
        {},
        el("strong", { text: fmtNumber(s.last_value) }),
        s.units ? el("span", { class: "unit", text: s.units }) : null,
      ),
      el("div", { class: "s-meta", text: fmtObsDate(s.last_date, s.frequency) }),
    ),
    el("td", { class: "c-spark" }, sparkline(s.spark, { label: s.label, unit: s.units, frequency: s.frequency })),
    el("td", {
      class: "num c-age",
      title: `stale after ${s.max_age_days} days`,
      text: s.age_days === null ? "–" : `${s.age_days} d`,
    }),
    el("td", { class: "c-status" }, badge(meta)),
  );
}

function renderSeries(health) {
  const q = state.query.trim().toLowerCase();
  const rows = health.series.filter((s) => {
    if (state.filter === "problems" && s.status === "ok") return false;
    if (!q) return true;
    return [s.label, s.id, s.title, s.source].some((v) => (v || "").toLowerCase().includes(q));
  });
  const body = document.getElementById("series-body");
  const groups = [];
  for (const [key, title] of Object.entries(health.blocks)) {
    const inBlock = rows.filter((s) => s.block === key);
    if (!inBlock.length) continue;
    groups.push(el("tr", { class: "group" }, el("td", { colspan: 5, text: `${title} (${inBlock.length})` })));
    groups.push(...inBlock.map(seriesRow));
  }
  if (!groups.length) {
    groups.push(
      el(
        "tr",
        {},
        el("td", {
          colspan: 5,
          class: "empty",
          text:
            state.filter === "problems" ? "No problems: every series is up to date." : "No series match your search.",
        }),
      ),
    );
  }
  body.replaceChildren(...groups);
  document.getElementById("series-count").textContent = `Showing ${rows.length} of ${health.series.length} series`;
}

function wireFilters(health) {
  for (const button of document.querySelectorAll("[data-filter]")) {
    button.addEventListener("click", () => {
      state.filter = button.dataset.filter;
      for (const b of document.querySelectorAll("[data-filter]")) b.setAttribute("aria-pressed", String(b === button));
      renderSeries(health);
    });
  }
  document.getElementById("search").addEventListener("input", (ev) => {
    state.query = ev.target.value;
    renderSeries(health);
  });
}

async function main() {
  let health;
  try {
    health = await loadJSON("data/health.json");
  } catch (err) {
    document.getElementById("run-info").textContent = "";
    document
      .getElementById("content")
      .replaceChildren(
        el(
          "div",
          { class: "card notice" },
          el("strong", { text: "No data yet. " }),
          "The update pipeline has not published a health report yet. It runs every day and after every change to data/manual/ on GitHub.",
        ),
      );
    return;
  }
  const info = document.getElementById("run-info");
  info.replaceChildren(
    `Last pipeline run: ${fmtDateTime(health.generated_at)} (${relTime(health.generated_at)})`,
    health.run_url ? " · " : "",
    health.run_url ? el("a", { href: health.run_url, target: "_blank", rel: "noopener", text: "run log" }) : "",
  );
  if (health.macro) {
    const ok = health.macro.status === "ok";
    info.append(
      el("br"),
      "Macro Desk: ",
      badge(
        ok
          ? { label: "Updated", tone: "good", icon: "\u2713" }
          : { label: "Not updated", tone: "critical", icon: "\u00d7" },
      ),
      ok
        ? ` ${health.macro.used} of ${health.macro.total} indicators in the bias`
        : ` ${health.macro.error}. The page shows the previous run.`,
    );
  }
  if (health.calendar) {
    const c = health.calendar;
    const bad = (c.sources || []).filter((s) => !["ok", "cached"].includes(s.status));
    info.append(
      el("br"),
      "Calendar: ",
      badge(
        c.status === "ok"
          ? { label: "Updated", tone: "good", icon: "\u2713" }
          : { label: c.status === "failed" ? "Not updated" : "Partly updated", tone: "warning", icon: "!" },
      ),
      c.status === "failed"
        ? ` ${c.error}. The calendar page shows the previous run.`
        : ` ${c.events} events` +
            (bad.length
              ? `; using the last good copy for ${bad.map((s) => `${s.label} (${s.error || s.status})`).join(", ")}`
              : ""),
    );
  }
  renderTiles(health);
  renderManual(health);
  renderSeries(health);
  wireFilters(health);
}

main();
