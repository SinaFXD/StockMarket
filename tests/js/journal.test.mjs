// Track record arithmetic (site/assets/journal-math.js). Run: node --test tests/js/*.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";
import * as J from "../../site/assets/journal-math.js";

const close = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);

function series(start, n, f) {
  const dates = [];
  const values = [];
  const d0 = Date.parse(start);
  for (let i = 0; i < n; i++) {
    dates.push(new Date(d0 + i * 86400000).toISOString().slice(0, 10));
    values.push(f(i));
  }
  return { dates, values };
}

test("closeOn uses the last close up to 5 days back", () => {
  const s = { dates: ["2026-01-01", "2026-01-05"], values: [10, 11] };
  assert.equal(J.closeOn(s, "2026-01-07"), 11);
  assert.equal(J.closeOn(s, "2026-01-20"), null);
  assert.equal(J.closeOn(s, "2025-12-31"), null);
});

test("a short that falls is a win; alpha removes the market at the stock's beta", () => {
  // market +10% over the trade; the stock moved exactly 2x the market every day for a year before the entry
  const spy = series("2025-01-01", 500, (i) => 100 * (1 + 0.001 * Math.sin(i)) ** i);
  const stock = { dates: spy.dates, values: spy.values.map((v, i) => (i ? null : 50)) };
  // build the stock from 2x the market's daily returns
  for (let i = 1; i < spy.values.length; i++)
    stock.values[i] = stock.values[i - 1] * (1 + 2 * (spy.values[i] / spy.values[i - 1] - 1));
  const idea = {
    ticker: "X",
    side: "short",
    entry_price: 100,
    exit_price: 90,
    entry_date: spy.dates[400],
    exit_date: spy.dates[430],
  };
  const r = J.tradeResult(idea, spy, stock);
  close(r.ret, 10);
  close(r.beta, 2, 1e-6);
  assert.ok(r.beta_estimated);
  const m = (J.closeOn(spy, idea.exit_date) / J.closeOn(spy, idea.entry_date) - 1) * 100;
  close(r.market, m);
  close(r.alpha, 10 + 2 * m, 1e-6);
  assert.equal(r.days, 30);
  assert.equal(J.tradeResult({ ...idea, exit_price: null }, spy, stock), null);
  assert.equal(J.betaBefore(null, spy, idea.entry_date).beta, 1);
});

test("stats: hit rate, payoff, alpha", () => {
  const s = J.stats([
    { ret: 10, alpha: 5, side: "long", days: 30 },
    { ret: -5, alpha: -2, side: "short", days: 20 },
    { ret: 4, alpha: null, side: "long", days: 40 },
  ]);
  assert.equal(s.n, 3);
  close(s.hit_rate, (2 / 3) * 100);
  close(s.avg_win, 7);
  close(s.avg_loss, -5);
  close(s.payoff, 7 / 5);
  close(s.mean_alpha, 1.5);
  close(s.alpha_hit_rate, 50);
  assert.deepEqual([s.longs, s.shorts, s.best, s.worst, s.avg_days], [2, 1, 10, -5, 30]);
  assert.deepEqual(J.stats([]), { n: 0 });
});
