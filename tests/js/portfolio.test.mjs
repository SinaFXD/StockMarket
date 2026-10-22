// Portfolio Lab arithmetic (site/assets/portfolio-math.js). Run: node --test tests/js
import assert from "node:assert/strict";
import { test } from "node:test";
import * as m from "../../site/assets/portfolio-math.js";

const close = (a, b) => assert.ok(Math.abs(a - b) < 1e-9, `${a} != ${b}`);

test("align repeats the last close and keeps days before the first close empty", () => {
  const out = m.align(["d1", "d2", "d3", "d4"], { A: { dates: ["d2", "d4"], values: [10, 12] } });
  assert.deepEqual(out.A, [null, 10, 10, 12]);
});

test("CEW averages the positions' daily returns, shorts earn minus the stock", () => {
  const rets = { A: [null, 0.02, -0.01], B: [null, 0.04, 0.03] };
  const out = m.cew(
    [
      { t: "A", side: "long" },
      { t: "B", side: "short" },
    ],
    rets,
  );
  close(out[1], (0.02 - 0.04) / 2);
  close(out[2], (-0.01 - 0.03) / 2);
});

test("non-rebalanced: dollar P&L on capital, a later listing enters on its first close", () => {
  const closes = { A: [100, 110, 121], B: [null, 50, 40] };
  const { equity, rets } = m.buyHold(
    [
      { t: "A", side: "long", amount: 1000 },
      { t: "B", side: "short", amount: 500 },
    ],
    closes,
    10000,
  );
  assert.deepEqual(equity, [10000, 10100, 10210 + 100]);
  close(rets[1], 0.01);
});

test("drawdowns and stats", () => {
  const d = m.drawdowns([100, 120, 90, 130]);
  close(d.max, -25);
  assert.equal(d.at, 2);
  const s = m.stats(new Array(252).fill(0.001));
  close(s.ret, (1.001 ** 252 - 1) * 100);
  assert.ok(s.vol < 1e-9);
});

test("correlation, beta and portfolio volatility", () => {
  const mkt = Array.from({ length: 60 }, (_, i) => Math.sin(i) / 100);
  const twice = mkt.map((x) => 2 * x);
  close(m.correlation(mkt, twice), 1);
  close(m.beta(twice, mkt), 2);
  const rets = { A: mkt, B: twice };
  // long A and short half as much of 2x A: a perfect hedge
  const hedge = m.portfolioVol(
    [
      { t: "A", side: "long", amount: 100 },
      { t: "B", side: "short", amount: 50 },
    ],
    rets,
    100,
  );
  assert.equal(hedge.vol, null);
  const one = m.portfolioVol([{ t: "A", side: "long", amount: 100 }], rets, 100);
  close(one.vol, m.stdev(mkt) * Math.sqrt(252) * 100);
  close(one.contrib[0], 100);
  const mat = m.correlationMatrix(
    [
      { t: "A", side: "long" },
      { t: "B", side: "short" },
    ],
    rets,
    true,
  );
  close(mat[0][1], -1);
  close(m.averagePairwise(mat), -1);
});

test("exposures, position guide and Sharpe framing", () => {
  const e = m.exposures(
    [
      { t: "A", side: "long", amount: 60 },
      { t: "B", side: "short", amount: 40 },
    ],
    { A: 1.5, B: 0.5 },
    100,
  );
  assert.deepEqual([e.long, e.short, e.gross, e.net], [60, 40, 100, 20]);
  close(e.betaNet, 90 - 20);
  assert.deepEqual([m.positionGuide(50e3).min, m.positionGuide(500e3).max, m.positionGuide(3e6).min], [8, 14, 12]);
  // the course: CFD Sharpe 1.5 x 15-30% vol = 22.5-45%; stocks Sharpe 2 -> 30-60%; options -> 50-100%
  close(m.requiredReturn(1.5, 15), 22.5);
  close(m.requiredReturn(2, 30), 60);
  close(m.requiredReturn(m.SHARPE_FRAMES[2].sharpe, 30), 100);
});

// ---------- factor exposure ----------
function rng(seed) {
  let s = seed;
  return () => {
    s = (s * 1103515245 + 12345) % 2147483648;
    return s / 2147483648 - 0.5;
  };
}

test("OLS recovers known coefficients and t-statistics", () => {
  const r = rng(7);
  const x1 = Array.from({ length: 300 }, () => r() * 0.02);
  const x2 = Array.from({ length: 300 }, () => r() * 0.02);
  const y = x1.map((v, i) => 0.001 + 0.8 * v - 0.3 * x2[i] + r() * 0.002);
  y[0] = null; // gaps are skipped
  const f = m.ols(y, { a: x1, b: x2 });
  assert.equal(f.n, 299);
  assert.ok(Math.abs(f.betas.a - 0.8) < 0.03 && Math.abs(f.betas.b + 0.3) < 0.03);
  assert.ok(Math.abs(f.alpha - 0.001) < 0.0002 && f.r2 > 0.95 && f.t.a > 20 && f.t.b < -8);
  assert.equal(m.ols([1, 2], { a: [1, 2] }), null); // too few days
});

test("factor returns are long ETF minus short ETF", () => {
  const closes = {
    SPY: [100, 101, 102],
    IWM: [50, 51, 51],
    IWD: [20, 20, 20.2],
    IWF: [30, 30.3, 30.3],
    MTUM: [10, 10, 10],
  };
  const f = m.factorReturns(closes);
  assert.deepEqual(Object.keys(f), ["market", "size", "value", "momentum"]);
  assert.equal(f.market[0], null);
  assert.ok(Math.abs(f.size[1] - (0.02 - 0.01)) < 1e-12);
  assert.ok(Math.abs(f.value[1] - (0 - 0.01)) < 1e-12);
  assert.ok(Math.abs(f.momentum[1] + 0.01) < 1e-12);
  assert.deepEqual(Object.keys(m.factorReturns({ SPY: [1, 2] })), ["market"]); // missing ETFs: factor left out
});

test("a book's factor loadings are its weighted stock loadings, with the hedge that cancels them", () => {
  const r = rng(11);
  const n = 260;
  const fac = { market: [], value: [], momentum: [] };
  for (let i = 0; i < n; i++) for (const k of Object.keys(fac)) fac[k].push(i ? r() * 0.02 : null);
  // A: a market + momentum stock; B: a value stock; shorting B gives the book negative value exposure
  const A = fac.market.map((m, i) => (i ? 1.0 * m + 0.6 * fac.momentum[i] + r() * 0.004 : null));
  const B = fac.market.map((m, i) => (i ? 0.9 * m + 0.8 * fac.value[i] + r() * 0.004 : null));
  const positions = [
    { t: "A", side: "long", amount: 50000 },
    { t: "B", side: "short", amount: 50000 },
  ];
  const x = m.factorExposure(positions, { A, B }, fac, 100000);
  // book = 0.5 A - 0.5 B: market 0.5*1.0 - 0.5*0.9 = 0.05, value -0.4, momentum +0.3
  assert.ok(Math.abs(x.betas.market - 0.05) < 0.03, `market ${x.betas.market}`);
  assert.ok(Math.abs(x.betas.value + 0.4) < 0.03, `value ${x.betas.value}`);
  assert.ok(Math.abs(x.betas.momentum - 0.3) < 0.03, `momentum ${x.betas.momentum}`);
  assert.ok(Math.abs(x.hedge.value - 40000) < 3000 && Math.abs(x.hedge.momentum + 30000) < 3000);
  assert.ok(x.r2 > 0.9 && Math.abs(x.specific - (1 - x.r2)) < 1e-12);
  assert.ok(Math.abs(x.perPosition.A.momentum - 0.6) < 0.05 && Math.abs(x.perPosition.B.value - 0.8) < 0.05);
});
