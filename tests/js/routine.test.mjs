// Weekly routine logic (site/assets/routine-logic.js). Run: node --test tests/js/*.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";
import * as R from "../../site/assets/routine-logic.js";

const P = { review_days: 7, stale_days: 14, pipeline_min: 10, pipeline_max: 15, ideas_per_week: 2 };

test("ISO weeks", () => {
  assert.equal(R.isoWeek("2026-10-22"), "2026-W43");
  assert.equal(R.isoWeek("2021-01-03"), "2020-W53"); // a Sunday that belongs to the previous year's last week
  assert.equal(R.isoWeek("2024-12-30"), "2025-W01");
  assert.equal(R.isoWeek("2026-01-01"), "2026-W01");
  assert.equal(R.isoWeek("2026-12-31"), "2026-W53");
});

test("the suggested hours stay inside the course's 8-12 hours a week", () => {
  const h = Object.values(R.HOURS).reduce((a, b) => a + b, 0);
  assert.ok(h >= 8 && h <= 12);
});

test("data step: reports due, errors, upcoming manual reports", () => {
  const health = {
    summary: { series: { failed: 2, stale: 0 } },
    manual: [
      {
        title: "ISM Manufacturing PMI",
        file: "data/manual/ism_manufacturing.csv",
        status: "due",
        errors: [],
        tracked: [{ status: "due", expected_month: "2026-10" }],
      },
      { title: "NFIB", file: "data/manual/nfib_sbet.csv", status: "ok", errors: [], tracked: [] },
    ],
  };
  const cal = {
    events: [{ date: "2026-10-25", category: "manual_report", title: "ISM Services", detail: "2026-09 report" }],
  };
  const s = R.dataStep(health, cal, "2026-10-22");
  assert.equal(s.status, "attention");
  assert.match(s.items[0], /ISM Manufacturing PMI: a new report is out \(2026-10\)/);
  assert.ok(s.items.some((x) => x.startsWith("2026-10-25: ISM Services due")));
  assert.ok(s.items.some((x) => x.startsWith("2 automatic series could not be refreshed")));
  assert.equal(R.dataStep({ manual: [] }, null, "2026-10-22").status, "ok");
});

test("macro step flags a change of bias", () => {
  const latest = {
    bias: { label: "Net long", score: 0.28, used: 19, total: 19 },
    compared_with: "2026-09-22",
    what_changed: [{ id: "bias", name: "Portfolio bias", from_state: "Neutral", to_state: "Net long" }],
    alerts: [],
  };
  const s = R.macroStep(latest);
  assert.equal(s.status, "attention");
  assert.match(s.items[1], /Portfolio bias Neutral → Net long/);
  assert.equal(R.macroStep(null).status, "todo");
});

test("ideas and review steps", () => {
  const ideas = [
    { ticker: "A", side: "long", status: "active", opened: "2026-10-20", updated: "2026-10-01", entry_price: 100 },
    { ticker: "B", side: "short", status: "researching", opened: "2026-09-01", updated: "2026-10-21", entry_price: 50 },
    { ticker: "C", side: "long", status: "closed", opened: "2026-01-01", updated: "2026-01-01" },
  ];
  const s = R.ideasStep(ideas, "2026-10-22", P);
  assert.equal(s.status, "attention");
  assert.match(s.items[0], /^2 open ideas .* 1 new in the last 7 days/);
  const pages = { B: { earnings: { date: "2026-10-27", session: "after the close" } } };
  const rows = { A: { price: 112 }, B: { price: 40 } };
  const cal = {
    events: [
      { date: "2026-10-28", category: "central_bank", importance: "high", title: "FOMC decision", region: "US" },
    ],
  };
  const r = R.reviewStep(ideas, pages, rows, cal, "2026-10-22", P);
  assert.equal(r.status, "attention");
  assert.ok(r.items.includes("A: not reviewed for 21 days (stale)."));
  assert.ok(r.items.includes("B: earnings on 2026-10-27, after the close."));
  assert.ok(r.items.includes("B: +20% for the short since entry: check it against the targets."));
  assert.ok(r.items.includes("2026-10-28: FOMC decision."));
  assert.ok(!r.items.some((x) => x.startsWith("C:")));
});

test("portfolio step", () => {
  const guide = { min: 8, max: 12, label: "8–12 positions" };
  assert.equal(R.portfolioStep(null, guide).status, "todo");
  const book = {
    current: [
      { t: "A", amount: 1 },
      { t: "", amount: 5 },
    ],
    proposed: [],
  };
  const s = R.portfolioStep(book, guide);
  assert.equal(s.status, "attention");
  assert.match(s.items[0], /Current book: 1 positions/);
});

test("screen step: outlier counts and the sectors to screen first", () => {
  const rows = [
    { cls: "positive", vol_ok: true },
    { cls: "positive", vol_ok: false },
    { cls: "negative", vol_ok: true },
  ];
  const rot = (sector, rs, quadrant) => ({ sector, rotation: { rs, change: 0, quadrant } });
  const sectors = {
    sectors: [
      rot("Energy", 10, "leading"),
      rot("Utilities", -13, "lagging"),
      rot("Materials", -2, "improving"),
      rot("Industrials", -12, "lagging"),
      rot("Healthcare", 6, "weakening"),
      { sector: "New", rotation: null },
    ],
  };
  const s = R.screenStep({ as_of: "2026-10-22" }, rows, sectors);
  assert.equal(s.items[0], "Positive outliers: 2 (1 pass the volatility filter).");
  assert.match(s.items[2], /leading or improving .*: Energy, Materials; lagging: Utilities, Industrials/); // weakest first
  assert.equal(R.screenStep({ as_of: "2026-10-22" }, rows).items.length, 3); // no sector file: no line
});
