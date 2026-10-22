// Track record of closed trade ideas (lesson 33: be judged on results). Pure functions, tested by
// tests/js/journal.test.mjs. A trade counts when it has an entry and an exit price and dates.

import { beta } from "./portfolio-math.js";

const ok = (x) => typeof x === "number" && Number.isFinite(x);

// Close on `day`, or the last close up to 5 days before it. series: {dates: [...], values: [...]} sorted.
export function closeOn(series, day) {
  if (!series) return null;
  let found = null;
  for (let i = 0; i < series.dates.length && series.dates[i] <= day; i++) found = i;
  if (found === null) return null;
  const gap = (Date.parse(day) - Date.parse(series.dates[found])) / 86400000;
  return gap <= 5 && ok(series.values[found]) ? series.values[found] : null;
}

function dailyReturns(series, from, to) {
  const out = new Map();
  for (let i = 1; i < series.dates.length; i++) {
    const d = series.dates[i];
    if (d < from || d > to) continue;
    const a = series.values[i - 1];
    const b = series.values[i];
    if (ok(a) && ok(b) && a > 0) out.set(d, b / a - 1);
  }
  return out;
}

// Beta of the stock against SPY over the 252 trading days before the entry (falls back to 1 without history).
export function betaBefore(stock, spy, entryDate) {
  if (!stock || !spy) return { beta: 1, estimated: false };
  const start = new Date(Date.parse(entryDate) - 370 * 86400000).toISOString().slice(0, 10);
  const s = dailyReturns(stock, start, entryDate);
  const m = dailyReturns(spy, start, entryDate);
  const days = [...s.keys()].filter((d) => m.has(d));
  if (days.length < 60) return { beta: 1, estimated: false };
  const b = beta(
    days.map((d) => s.get(d)),
    days.map((d) => m.get(d)),
  );
  return ok(b) ? { beta: b, estimated: true } : { beta: 1, estimated: false };
}

// One closed trade. Return for the side (a short gains when the price falls); alpha = return minus what the
// market move would have given the same side at the stock's beta.
export function tradeResult(idea, spy, stock) {
  const entry = idea.entry_price;
  const exit = idea.exit_price;
  const d0 = idea.entry_date || idea.opened;
  const d1 = idea.exit_date;
  if (!ok(entry) || !ok(exit) || !d0 || !d1 || entry <= 0) return null;
  const sign = idea.side === "short" ? -1 : 1;
  const ret = sign * (exit / entry - 1) * 100;
  const s0 = closeOn(spy, d0);
  const s1 = closeOn(spy, d1);
  const market = ok(s0) && ok(s1) ? (s1 / s0 - 1) * 100 : null;
  const { beta: b, estimated } = betaBefore(stock, spy, d0);
  return {
    ticker: idea.ticker,
    side: idea.side,
    entry_date: d0,
    exit_date: d1,
    days: Math.round((Date.parse(d1) - Date.parse(d0)) / 86400000),
    ret,
    market,
    beta: b,
    beta_estimated: estimated,
    alpha: market === null ? null : ret - sign * b * market,
  };
}

// Summary of a list of trade results.
export function stats(trades) {
  const t = trades.filter((x) => x && ok(x.ret));
  if (!t.length) return { n: 0 };
  const wins = t.filter((x) => x.ret > 0);
  const losses = t.filter((x) => x.ret <= 0);
  const avg = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);
  const avgWin = avg(wins.map((x) => x.ret));
  const avgLoss = avg(losses.map((x) => x.ret));
  const alphas = t.map((x) => x.alpha).filter(ok);
  return {
    n: t.length,
    longs: t.filter((x) => x.side === "long").length,
    shorts: t.filter((x) => x.side === "short").length,
    hit_rate: (wins.length / t.length) * 100,
    avg_win: avgWin,
    avg_loss: avgLoss,
    payoff: avgWin !== null && avgLoss !== null && avgLoss < 0 ? avgWin / -avgLoss : null,
    mean: avg(t.map((x) => x.ret)),
    mean_alpha: alphas.length ? avg(alphas) : null,
    alpha_hit_rate: alphas.length ? (alphas.filter((a) => a > 0).length / alphas.length) * 100 : null,
    best: Math.max(...t.map((x) => x.ret)),
    worst: Math.min(...t.map((x) => x.ret)),
    avg_days: avg(t.map((x) => x.days)),
  };
}
