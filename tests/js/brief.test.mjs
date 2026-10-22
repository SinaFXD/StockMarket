// Macro Desk brief and CSV (site/assets/brief.js). Run: node --test tests/js/*.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";
import { boardCsv, briefText, csvCell, extremes } from "../../site/assets/brief.js";

const SIGNALS = [
  {
    id: "curve",
    name: "Yield curve",
    block: "mm",
    score: 0,
    state: "Flat",
    percentile_10y: 46.8,
    as_of: "2026-10-21",
    reason_en: "flat, wait",
  },
  {
    id: "vix",
    name: "VIX",
    block: "mm",
    score: 1,
    state: "Low",
    percentile_10y: 8,
    as_of: "2026-10-21",
    reason_en: 'calm, "low"',
  },
  {
    id: "ism",
    name: "ISM",
    block: "sv",
    score: null,
    state: "Awaiting data",
    percentile_10y: null,
    as_of: null,
    reason_en: "",
  },
];
const BIAS = {
  label: "Net long",
  score: 0.284,
  used: 2,
  total: 3,
  blocks: { mm: { label: "US money markets", score: 0.5 }, sv: { label: "US surveys", score: null } },
};

test("extremes are the top and bottom tenth", () => {
  assert.deepEqual(
    extremes(SIGNALS).map((s) => s.id),
    ["vix"],
  );
});

test("the brief lists bias, blocks, changes, alerts, extremes and the bigger picture", () => {
  const text = briefText({
    asOf: "2026-10-21",
    bias: BIAS,
    signals: SIGNALS,
    overrides: { curve: 1 },
    changes: [
      { id: "bias", name: "Portfolio bias", from: 0.167, to: 0.284, from_state: "Neutral", to_state: "Net long" },
      { name: "Credit", from: 0, to: -1, to_state: "Widening" },
    ],
    alerts: ["Blocks disagree."],
    regime: {
      now: { label: "Recovery", month: "2026-08", borderline: true },
      levels: { verdict: "hot", hot: 2, items: [1, 2, 3] },
      cpi_check: { month: "2026-09", rising: true, agrees: false },
      recession: { latest: { for_month: "2027-09", prob: 13.55 } },
      taylor: { latest: { fed_funds: 3.75, taylor: 6.21 } },
    },
    url: "https://example.org/macro.html",
  });
  assert.match(text, /^PTM Macro Desk brief, 2026-10-21\n/);
  assert.match(text, /Portfolio bias: Net long \(\+0\.28; 2 of 3 indicators; 1 override of mine\)/);
  assert.match(text, /Blocks: US money markets \+0\.50 · US surveys –/);
  assert.match(text, /- Portfolio bias: \+0\.17 → \+0\.28 \(Neutral → Net long\)/);
  assert.match(text, /- Credit: 0 → −1 \(Widening\)/);
  assert.match(text, /- Blocks disagree\./);
  assert.match(text, /- VIX: 8th percentile \(Low\)/);
  assert.match(text, /- Regime: Recovery \(data for 2026-08\), close to a line/);
  assert.match(text, /- Recession odds for 2027-09 \(yield-curve model\): 13\.6%/);
  assert.match(text, /- Levels: running hot \(2 of 3 hot\)/);
  assert.match(text, /- Check: core CPI for 2026-09 points to rising inflation; the regime may flip/);
  assert.match(text, /Educational tool, not investment advice\. https:\/\/example\.org\/macro\.html$/);
});

test("the brief without changes or regime", () => {
  const text = briefText({ asOf: "2026-10-21", bias: BIAS, signals: [] });
  assert.match(text, /No score changed\./);
  assert.doesNotMatch(text, /Bigger picture|Read together|extremes/);
});

test("CSV cells are quoted when needed", () => {
  assert.equal(csvCell(null), "");
  assert.equal(csvCell(1), "1");
  assert.equal(csvCell("a,b"), '"a,b"');
  assert.equal(csvCell('say "hi"'), '"say ""hi"""');
});

test("the board CSV has one row per indicator with my override", () => {
  const csv = boardCsv({
    signals: SIGNALS,
    blocks: { mm: "US money markets", sv: "US surveys" },
    overrides: { vix: -1 },
  });
  assert.equal(csv.charCodeAt(0), 0xfeff);
  assert.ok(csv.slice(1).startsWith("block,indicator,id,"));
  const lines = csv.trim().split("\r\n");
  assert.equal(lines.length, 4);
  assert.equal(lines[1], 'US money markets,Yield curve,curve,2026-10-21,Flat,0,,0,46.8,"flat, wait"');
  assert.equal(lines[2], 'US money markets,VIX,vix,2026-10-21,Low,1,-1,-1,8,"calm, ""low"""');
  assert.equal(lines[3], "US surveys,ISM,ism,,Awaiting data,,,,,");
});
