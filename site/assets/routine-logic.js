// Weekly routine (the course's process in order): what each step needs this week, from the published data and
// the ideas / portfolio kept in this browser. Pure functions, tested by tests/js/routine.test.mjs.

const DAY = 86400000;
const OPEN = ["researching", "ready", "active"];

// ISO week label, e.g. "2026-W43" (weeks start on Monday; week 1 holds the year's first Thursday).
export function isoWeek(dateISO) {
  const d = new Date(`${dateISO}T00:00:00Z`);
  const day = (d.getUTCDay() + 6) % 7; // Monday = 0
  d.setUTCDate(d.getUTCDate() - day + 3); // Thursday of this week
  const year = d.getUTCFullYear(); // the Thursday's year is the week's year
  const week = 1 + Math.floor((d - Date.UTC(year, 0, 1)) / DAY / 7);
  return `${year}-W${String(week).padStart(2, "0")}`;
}

export function daysFrom(a, b) {
  return Math.round((Date.parse(b) - Date.parse(a)) / DAY);
}

// Suggested hours per step: our split of the course's 8-12 hours a week for a retail trader.
export const HOURS = { data: 0.5, macro: 1.5, themes: 0.5, screen: 1.5, ideas: 4, review: 1, portfolio: 1 };

const step = (id, title, lesson, page, status, items) => ({ id, title, lesson, page, status, items, hours: HOURS[id] });

export function dataStep(health, calendar, today) {
  const items = [];
  let status = "ok";
  for (const m of (health && health.manual) || []) {
    if (m.status === "due" || m.status === "awaiting" || (m.errors && m.errors.length)) {
      status = "attention";
      const t = (m.tracked || []).find((x) => x.status !== "ok") || {};
      items.push(
        m.errors && m.errors.length
          ? `${m.title}: ${m.errors.length} error(s) in ${m.file}`
          : `${m.title}: ${m.status === "due" ? "a new report is out" : "awaiting data"}${t.expected_month ? ` (${t.expected_month})` : ""}, enter it in ${m.file}`,
      );
    }
  }
  for (const e of (calendar && calendar.events) || []) {
    const d = daysFrom(today, e.date);
    if (e.category === "manual_report" && d >= 0 && d <= 7) items.push(`${e.date}: ${e.title} due (${e.detail})`);
  }
  const series = health && health.summary ? health.summary.series : null;
  if (series && (series.failed || series.stale)) {
    items.push(
      `${series.failed + series.stale} automatic series could not be refreshed and use their last good copy (nothing to enter; see Data health).`,
    );
  }
  if (!items.length) items.push("All hand-entered reports are up to date.");
  return step(
    "data",
    "Enter this week's reports",
    "ISM, NFIB, China PMIs (lessons 7, 8, 11, 14)",
    "health.html",
    status,
    items,
  );
}

export function macroStep(latest) {
  if (!latest)
    return step("macro", "Read the Macro Desk: portfolio bias", "lessons 1–15", "macro.html", "todo", [
      "No Macro Desk data yet.",
    ]);
  const items = [
    `Bias: ${latest.bias.label} (score ${latest.bias.score >= 0 ? "+" : ""}${latest.bias.score.toFixed(2)}, ${latest.bias.used} of ${latest.bias.total} indicators).`,
  ];
  const changes = latest.what_changed || [];
  for (const c of changes)
    items.push(`Changed since ${latest.compared_with}: ${c.name} ${c.from_state} → ${c.to_state}.`);
  for (const a of latest.alerts || []) items.push(a); // includes the data-vs-prices alert
  const biasChanged = changes.some((c) => c.id === "bias");
  return step(
    "macro",
    "Read the Macro Desk: portfolio bias",
    "lessons 1–15",
    "macro.html",
    biasChanged || (latest.alerts || []).length ? "attention" : "todo",
    items,
  );
}

export function themesStep(themes) {
  if (!themes)
    return step("themes", "Macro → industries and regions", "lessons 34–35", "themes.html", "todo", ["No data yet."]);
  const strong = themes.industries.filter((s) => s.net !== null && Math.abs(s.net) >= themes.params.strong);
  const items = strong.length
    ? strong.map((s) => `${s.industry}: ${s.tone} (${s.net > 0 ? "+" : ""}${s.net})`)
    : ["No industry where two or more macro drivers agree."];
  if (themes.china && themes.china.state !== "awaiting") items.push(`China check: ${themes.china.text}`);
  return step(
    "themes",
    "Macro → industries and regions",
    "lessons 34–35",
    "themes.html",
    themes.china && themes.china.state === "disagree" ? "attention" : "todo",
    items,
  );
}

// sectors: data/sectors.json (optional); its rotation says which sectors to screen first
export function screenStep(stocks, rows, sectors = null) {
  if (!stocks)
    return step("screen", "Screen for outliers", "lessons 22–29", "screener.html", "todo", ["No screener data yet."]);
  const count = (cls) => rows.filter((r) => r.cls === cls).length;
  const vol = (cls) => rows.filter((r) => r.cls === cls && r.vol_ok === true).length;
  return step("screen", "Screen for outliers", "lessons 22–29", "screener.html", "todo", [
    `Positive outliers: ${count("positive")} (${vol("positive")} pass the volatility filter).`,
    `Negative outliers: ${count("negative")} (${vol("negative")}); post-growth: ${count("post_growth")} (${vol("post_growth")}).`,
    ...sectorItems(sectors),
    `Estimates as of ${stocks.as_of}.`,
  ]);
}

function sectorItems(sectors) {
  const list = ((sectors && sectors.sectors) || []).filter((s) => s.rotation);
  const pick = (qs) =>
    list
      .filter((s) => qs.includes(s.rotation.quadrant))
      .sort((a, b) => b.rotation.rs - a.rotation.rs)
      .map((s) => s.sector);
  if (!list.length) return [];
  const up = pick(["leading", "improving"]);
  const down = pick(["lagging"]).reverse();
  return [
    `Sectors leading or improving against the S&P 500: ${up.join(", ") || "none"}; lagging: ${down.join(", ") || "none"} (Sectors page).`,
  ];
}

export function ideasStep(ideas, today, p) {
  const open = ideas.filter((i) => OPEN.includes(i.status));
  const fresh = ideas.filter((i) => i.opened && daysFrom(i.opened, today) <= 7).length;
  const items = [
    `${open.length} open ideas (aim for ${p.pipeline_min}–${p.pipeline_max}); ${fresh} new in the last 7 days (aim for about ${p.ideas_per_week} a week, 2–4 hours each).`,
  ];
  const short = open.length < p.pipeline_min || fresh < p.ideas_per_week;
  if (open.length < p.pipeline_min) items.push(`The pipeline needs ${p.pipeline_min - open.length} more idea(s).`);
  return step("ideas", "Work up new trade ideas", "lessons 30–33", "ideas.html", short ? "attention" : "ok", items);
}

// ideas: [{ticker, side, status, updated, ...}], pages: {ticker: stock page or null}, rows: {ticker: screener row}
export function reviewStep(ideas, pages, rows, calendar, today, p) {
  const items = [];
  let status = "ok";
  for (const i of ideas.filter((x) => OPEN.includes(x.status))) {
    const age = i.updated ? daysFrom(i.updated, today) : null;
    if (age !== null && age >= p.review_days) {
      items.push(`${i.ticker}: not reviewed for ${age} days${age >= p.stale_days ? " (stale)" : ""}.`);
      status = "attention";
    }
    const e = pages[i.ticker] && pages[i.ticker].earnings;
    if (e) {
      const d = daysFrom(today, e.date);
      if (d >= 0 && d <= 7) {
        items.push(`${i.ticker}: earnings on ${e.date}, ${e.session}.`);
        status = "attention";
      }
    }
    const r = rows[i.ticker];
    if (r && i.entry_price && Math.abs(r.price / i.entry_price - 1) >= 0.1) {
      const mv = (r.price / i.entry_price - 1) * 100 * (i.side === "short" ? -1 : 1);
      items.push(
        `${i.ticker}: ${mv >= 0 ? "+" : ""}${mv.toFixed(0)}% for the ${i.side} since entry: check it against the targets.`,
      );
    }
  }
  const macro = ((calendar && calendar.events) || []).filter(
    (e) => e.category !== "manual_report" && e.importance === "high",
  );
  for (const e of macro) {
    const d = daysFrom(today, e.date);
    if (d >= 0 && d <= 7) items.push(`${e.date}: ${e.title}${e.region && e.region !== "US" ? ` (${e.region})` : ""}.`);
  }
  if (!items.length)
    items.push("Nothing due: no stale ideas, no earnings or high-importance events in the next 7 days.");
  return step("review", "Review open ideas and this week's catalysts", "lessons 32–33", "ideas.html", status, items);
}

export function portfolioStep(book, guide) {
  if (!book || !book.current || !book.current.length)
    return step("portfolio", "Check the portfolio", "lessons 16–21", "portfolio.html", "todo", [
      "No current book in this browser yet: enter it to check volatility, correlation and beta-adjusted exposure.",
    ]);
  const n = book.current.filter((x) => x.t && x.amount > 0).length;
  const proposed = (book.proposed || []).filter((x) => x.t && x.amount > 0).length;
  const items = [`Current book: ${n} positions (${guide.label}); proposed: ${proposed}.`];
  items.push(
    "Model the proposed book before changing positions; keep volatility in 15–30% and correlations within ±0.3.",
  );
  return step(
    "portfolio",
    "Check the portfolio",
    "lessons 16–21",
    "portfolio.html",
    n < guide.min || n > guide.max ? "attention" : "todo",
    items,
  );
}
