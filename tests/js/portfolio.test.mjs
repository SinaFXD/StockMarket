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
