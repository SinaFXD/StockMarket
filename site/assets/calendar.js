// Calendar page: upcoming catalysts with the 20-60 day holding window of a new trade highlighted.

import { badge, el, loadJSON } from "./common.js";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const REGIONS = ["All", "US", "Euro area", "Japan", "UK", "China"];
const CATEGORY = { central_bank: "Central bank", us_data: "US data", manual_report: "You enter this" };
const state = { cal: null, region: "All", weekly: false, highOnly: false, signals: {} };

const parse = (d) => new Date(`${d}T00:00:00Z`);
const dayLabel = (d) => {
  const x = parse(d);
  return `${DAYS[x.getUTCDay()]} ${x.getUTCDate()} ${MONTHS[x.getUTCMonth()]}`;
};
const monthLabel = (d) => `${MONTHS[parse(d).getUTCMonth()]} ${parse(d).getUTCFullYear()}`;
const relative = (n) => (n === 0 ? "today" : n === 1 ? "tomorrow" : n > 0 ? `in ${n} days` : `${-n} days ago`);

function visible(e) {
  if (state.region !== "All" && e.region !== state.region) return false;
  if (!state.weekly && e.importance === "low") return false;
  if (state.highOnly && e.importance !== "high") return false;
  return true;
}

function windowCard() {
  const c = state.cal;
  const inside = c.events.filter((e) => e.in_window && visible(e));
  const banks = inside.filter((e) => e.category === "central_bank");
  const high = inside.filter((e) => e.importance === "high" && e.category !== "central_bank");
  return el(
    "section",
    { class: "card panel window-card" },
    el("h2", {
      class: "panel-title",
      text: `Your window: ${dayLabel(c.window.from)} – ${dayLabel(c.window.to)} ${parse(c.window.to).getUTCFullYear()}`,
    }),
    el("p", {
      class: "reading",
      text:
        `A trade opened today and held ${c.window.days[0]}–${c.window.days[1]} days lives through ` +
        `${banks.length} central-bank decision${banks.length === 1 ? "" : "s"} and ${high.length} other ` +
        "high-importance release" +
        (high.length === 1 ? "" : "s") +
        ". Check each one against your idea's catalysts and timing.",
    }),
    banks.length
      ? el(
          "ul",
          { class: "plain-list" },
          banks.map((e) =>
            el("li", {}, el("b", { text: dayLabel(e.date) }), ` ${e.title}${e.detail ? ` · ${e.detail}` : ""}`),
          ),
        )
      : null,
  );
}

function eventRow(e) {
  const links = e.signals.map((id) =>
    el("a", { href: `indicator.html?id=${encodeURIComponent(id)}`, text: state.signals[id] || id }),
  );
  return el(
    "li",
    { class: `cal-row ${e.in_window ? "in-window" : ""} ${e.days < 0 ? "past" : ""} imp-${e.importance}` },
    el(
      "div",
      { class: "cal-date" },
      el("b", { text: dayLabel(e.date) }),
      el("span", { class: "sub", text: relative(e.days) }),
    ),
    el(
      "div",
      { class: "cal-body" },
      el(
        "div",
        { class: "cal-title" },
        el("span", {
          class: "imp-dot",
          title: `${e.importance} importance`,
          "aria-label": `${e.importance} importance`,
        }),
        el("b", { text: e.title }),
        el("span", { class: "tag", text: e.region }),
        el("span", { class: "tag", text: CATEGORY[e.category] || e.category }),
      ),
      e.detail ? el("div", { class: "sub", text: e.detail }) : null,
      links.length || e.url
        ? el(
            "div",
            { class: "cal-links" },
            ...links.flatMap((a) => [a, " "]),
            e.url ? el("a", { href: e.url, target: "_blank", rel: "noopener", class: "muted", text: e.source }) : null,
          )
        : null,
    ),
  );
}

function timeline() {
  const events = state.cal.events.filter(visible);
  const out = [];
  let month = null;
  let list = null;
  let markedStart = false;
  let markedEnd = false;
  for (const e of events) {
    if (monthLabel(e.date) !== month) {
      month = monthLabel(e.date);
      list = el("ul", { class: "cal-list" });
      out.push(el("h3", { class: "cal-month", text: month }), list);
    }
    if (!markedStart && e.days >= state.cal.window.days[0]) {
      list.append(
        el("li", { class: "cal-marker", text: `Day ${state.cal.window.days[0]}: your 20–60 day window starts` }),
      );
      markedStart = true;
    }
    if (!markedEnd && e.days > state.cal.window.days[1]) {
      list.append(el("li", { class: "cal-marker", text: `Day ${state.cal.window.days[1]}: window ends` }));
      markedEnd = true;
    }
    list.append(eventRow(e));
  }
  if (!out.length) out.push(el("p", { class: "muted", text: "No events match these filters." }));
  return el("section", { class: "card panel" }, ...out);
}

function sources() {
  const tone = {
    ok: { label: "Updated", tone: "good", icon: "✓" },
    cached: { label: "Last copy", tone: "good", icon: "✓" },
    failed: { label: "Last good copy", tone: "warning", icon: "!" },
    missing: { label: "Missing", tone: "critical", icon: "×" },
  };
  return el(
    "section",
    { class: "card panel", style: "margin-top:12px" },
    el("h2", { class: "panel-title", text: "Sources" }),
    el(
      "ul",
      { class: "plain-list" },
      state.cal.sources.map((s) =>
        el(
          "li",
          {},
          badge(tone[s.status] || tone.missing),
          ` ${s.label}: ${s.events} events`,
          s.error ? el("span", { class: "muted", text: ` (${s.error})` }) : null,
        ),
      ),
    ),
    el("p", {
      class: "muted",
      style: "font-size:13px;margin:8px 0 0",
      text:
        "Release times are not shown; US data is usually out at 8:30 New York time. Dates for the reports you enter " +
        "by hand follow each report's usual release rule and can move by a day around holidays.",
    }),
  );
}

function controls() {
  const seg = el(
    "div",
    { class: "seg", role: "group", "aria-label": "Region" },
    REGIONS.map((r) =>
      el("button", {
        type: "button",
        "aria-pressed": String(state.region === r),
        text: r,
        onclick: () => {
          state.region = r;
          render();
        },
      }),
    ),
  );
  const check = (label, key) =>
    el(
      "label",
      { class: "check" },
      el("input", {
        type: "checkbox",
        checked: state[key],
        onchange: (ev) => {
          state[key] = ev.target.checked;
          render();
        },
      }),
      ` ${label}`,
    );
  return el(
    "div",
    { class: "toolbar" },
    seg,
    check("Weekly jobless claims", "weekly"),
    check("High importance only", "highOnly"),
  );
}

function render() {
  document.getElementById("content").replaceChildren(controls(), windowCard(), timeline(), sources());
}

async function main() {
  try {
    state.cal = await loadJSON("data/calendar.json");
  } catch {
    document
      .getElementById("content")
      .replaceChildren(el("div", { class: "card notice", text: "No calendar yet: it is built by the daily update." }));
    return;
  }
  try {
    const latest = await loadJSON("data/macro/latest.json");
    for (const s of latest.signals) state.signals[s.id] = s.name;
  } catch {
    // indicator names are a nicety; the ids still link
  }
  render();
}

main();
