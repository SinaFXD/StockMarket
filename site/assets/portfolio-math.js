// Portfolio Lab arithmetic (lessons 16-21), with no page code so it can be tested (tests/js/portfolio.test.mjs).
// Positions: {t, side: "long"|"short", amount: dollars}. Prices: aligned daily closes per ticker on one date list.

export const TRADING_DAYS = 252;

const ok = (x) => typeof x === "number" && Number.isFinite(x);
const sideSign = (p) => (p.side === "short" ? -1 : 1);

// Closes per ticker on the benchmark's dates: a missing day repeats the previous close (holidays, halts);
// days before a ticker's first close stay null.
export function align(dates, series) {
  const out = {};
  for (const [t, s] of Object.entries(series)) {
    const map = new Map(s.dates.map((d, i) => [d, s.values[i]]));
    let last = null;
    out[t] = dates.map((d) => {
      const v = map.get(d);
      if (ok(v) && v > 0) last = v;
      return last;
    });
  }
  return out;
}

export function returns(closes) {
  return closes.map((c, i) => (i && ok(c) && ok(closes[i - 1]) && closes[i - 1] > 0 ? c / closes[i - 1] - 1 : null));
}

// CEW: constant equal weight, rebalanced daily. Each day's return is the average of the positions' returns
// (a short earns minus the stock's return); positions without a price that day are left out.
export function cew(positions, rets) {
  const n = rets[positions[0].t].length;
  const out = new Array(n).fill(null);
  for (let i = 1; i < n; i++) {
    const vals = positions.map((p) => rets[p.t][i]).map((r, k) => (ok(r) ? sideSign(positions[k]) * r : null));
    const have = vals.filter(ok);
    out[i] = have.length ? have.reduce((a, b) => a + b, 0) / have.length : 0;
  }
  return out;
}

// Non-rebalanced: each position's dollars are invested on the first day and left to drift (a short's P&L is
// minus the long's). Equity = capital + total P&L; returns are on the equity. A position whose history starts
// later enters on its first close.
export function buyHold(positions, closes, capital) {
  const n = closes[positions[0].t].length;
  const equity = new Array(n).fill(capital);
  for (const p of positions) {
    const c = closes[p.t];
    const start = c.findIndex(ok);
    if (start < 0) continue;
    for (let i = start; i < n; i++) equity[i] += sideSign(p) * p.amount * (c[i] / c[start] - 1);
  }
  const rets = equity.map((v, i) => (i && equity[i - 1] > 0 ? v / equity[i - 1] - 1 : null));
  return { equity, rets };
}

export function curve(rets, start = 100) {
  let v = start;
  return rets.map((r) => (v *= 1 + (ok(r) ? r : 0)));
}

export function drawdowns(values) {
  let peak = -Infinity;
  let max = 0;
  let at = 0;
  const dd = values.map((v, i) => {
    peak = Math.max(peak, v);
    const d = peak > 0 ? (v / peak - 1) * 100 : 0;
    if (d < max) [max, at] = [d, i];
    return d;
  });
  return { dd, max, at };
}

export function mean(xs) {
  const v = xs.filter(ok);
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
}

export function stdev(xs) {
  const v = xs.filter(ok);
  if (v.length < 2) return null;
  const m = mean(v);
  return Math.sqrt(v.reduce((a, b) => a + (b - m) ** 2, 0) / (v.length - 1));
}

// Annualised return (compounded), volatility and Sharpe ratio (rf: annual risk-free rate, e.g. 0.04) of daily returns.
export function stats(rets, rf = 0) {
  const v = rets.filter(ok);
  if (v.length < 10) return { ret: null, vol: null, sharpe: null, days: v.length };
  const growth = v.reduce((a, r) => a * (1 + r), 1);
  const ret = (growth ** (TRADING_DAYS / v.length) - 1) * 100;
  const vol = stdev(v) * Math.sqrt(TRADING_DAYS) * 100;
  const excess = mean(v) * TRADING_DAYS - rf;
  return { ret, vol, sharpe: vol ? (excess * 100) / vol : null, days: v.length };
}

// Covariance and correlation over the days both series have a return.
function pairs(a, b) {
  const x = [];
  const y = [];
  for (let i = 0; i < a.length; i++)
    if (ok(a[i]) && ok(b[i])) {
      x.push(a[i]);
      y.push(b[i]);
    }
  return [x, y];
}

export function covariance(a, b) {
  const [x, y] = pairs(a, b);
  if (x.length < 10) return null;
  const mx = mean(x);
  const my = mean(y);
  let s = 0;
  for (let i = 0; i < x.length; i++) s += (x[i] - mx) * (y[i] - my);
  return s / (x.length - 1);
}

export function correlation(a, b) {
  const [x, y] = pairs(a, b);
  if (x.length < 10) return null;
  const c = covariance(x, y);
  const sx = stdev(x);
  const sy = stdev(y);
  return c !== null && sx && sy ? c / (sx * sy) : null;
}

export function beta(r, market) {
  const [x, m] = pairs(r, market);
  const v = stdev(m);
  const c = covariance(x, m);
  return c !== null && v ? c / (v * v) : null;
}

// Portfolio volatility from the variance/covariance of the holdings: weights are signed dollars / capital.
// Also each position's share of the portfolio variance (risk contribution, sums to 100%).
export function portfolioVol(positions, rets, capital) {
  const w = positions.map((p) => (sideSign(p) * p.amount) / capital);
  const n = positions.length;
  const cov = positions.map((p) => positions.map((q) => covariance(rets[p.t], rets[q.t]) ?? 0));
  const sw = cov.map((row) => row.reduce((a, c, j) => a + c * w[j], 0));
  const variance = w.reduce((a, wi, i) => a + wi * sw[i], 0);
  if (!(variance > 0) || !n) return { vol: null, contrib: positions.map(() => null) };
  return {
    vol: Math.sqrt(variance * TRADING_DAYS) * 100,
    contrib: w.map((wi, i) => ((wi * sw[i]) / variance) * 100),
  };
}

// Correlation matrix; asPositions flips shorts so the number says how two positions' P&L move together.
export function correlationMatrix(positions, rets, asPositions = true) {
  return positions.map((p) =>
    positions.map((q) => {
      if (p === q) return 1;
      const c = correlation(rets[p.t], rets[q.t]);
      return c === null ? null : asPositions ? c * sideSign(p) * sideSign(q) : c;
    }),
  );
}

export function averagePairwise(matrix) {
  const vals = [];
  for (let i = 0; i < matrix.length; i++)
    for (let j = i + 1; j < matrix.length; j++) if (ok(matrix[i][j])) vals.push(matrix[i][j]);
  return vals.length ? mean(vals) : null;
}

export function rollingCorrelation(a, b, window) {
  return a.map((_, i) =>
    i + 1 < window ? null : correlation(a.slice(i + 1 - window, i + 1), b.slice(i + 1 - window, i + 1)),
  );
}

// Rolling average pairwise correlation of the positions (shorts flipped).
export function rollingAveragePairwise(positions, rets, window) {
  const n = rets[positions[0].t].length;
  const out = new Array(n).fill(null);
  if (positions.length < 2) return out;
  for (let i = window - 1; i < n; i++) {
    const sl = {};
    for (const p of positions) sl[p.t] = rets[p.t].slice(i + 1 - window, i + 1);
    out[i] = averagePairwise(correlationMatrix(positions, sl, true));
  }
  return out;
}

// Long, short, gross and net exposure, and net exposure weighted by each stock's beta, in % of capital.
export function exposures(positions, betas, capital) {
  let long = 0;
  let short = 0;
  let betaNet = 0;
  for (const p of positions) {
    if (p.side === "short") short += p.amount;
    else long += p.amount;
    betaNet += sideSign(p) * p.amount * (ok(betas[p.t]) ? betas[p.t] : 1);
  }
  const pct = (x) => (capital > 0 ? (x / capital) * 100 : null);
  return {
    long: pct(long),
    short: pct(short),
    gross: pct(long + short),
    net: pct(long - short),
    betaNet: pct(betaNet),
  };
}

// Diversification by account size (lesson 20): number of positions.
export function positionGuide(capital) {
  if (capital >= 2e6)
    return { min: 12, max: 16, label: "$2m and above: 12–16 positions; more is over-diversification" };
  if (capital >= 250e3) return { min: 10, max: 14, label: "$250k–$2m: 10–14 positions" };
  return { min: 8, max: 12, label: "Up to $250k (retail margin account): 8–12 positions" };
}

// Sharpe framing (lesson 21): return a structure needs = minimum Sharpe x portfolio volatility.
export const SHARPE_FRAMES = [
  { structure: "CFDs (about 4× leverage)", sharpe: 1.5 },
  { structure: "US stocks long/short (2× margin)", sharpe: 2 },
  { structure: "Options (3–10× implied leverage)", sharpe: 10 / 3 },
];

export function requiredReturn(sharpe, volPct) {
  return ok(volPct) ? sharpe * volPct : null;
}

// ---------- factor exposure ----------
// Style factors as long-short ETF pairs (free data). Each entry: [id, label, long ETF, short ETF or null].
export const FACTORS = [
  ["market", "Market", "SPY", null],
  ["size", "Size (small minus large)", "IWM", "SPY"],
  ["value", "Value (value minus growth)", "IWD", "IWF"],
  ["momentum", "Momentum", "MTUM", "SPY"],
];

// Daily factor returns from aligned closes {SPY, IWM, IWD, IWF, MTUM}: long ETF minus short ETF.
export function factorReturns(closes) {
  const r = Object.fromEntries(Object.entries(closes).map(([k, v]) => [k, returns(v)]));
  const out = {};
  for (const [id, , long, short] of FACTORS) {
    if (!r[long] || (short && !r[short])) continue;
    out[id] = r[long].map((x, i) => {
      const y = short ? r[short][i] : 0;
      return ok(x) && ok(y) ? x - y : null;
    });
  }
  return out;
}

// Solve A x = b (small, symmetric positive definite) by Gaussian elimination with partial pivoting.
function solve(A, b) {
  const n = b.length;
  const M = A.map((row, i) => [...row, b[i]]);
  for (let c = 0; c < n; c++) {
    let p = c;
    for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r;
    if (Math.abs(M[p][c]) < 1e-14) return null;
    [M[c], M[p]] = [M[p], M[c]];
    for (let r = 0; r < n; r++) {
      if (r === c) continue;
      const f = M[r][c] / M[c][c];
      for (let k = c; k <= n; k++) M[r][k] -= f * M[c][k];
    }
  }
  return M.map((row, i) => row[n] / row[i]);
}

function inverse(A) {
  const n = A.length;
  const cols = [];
  for (let j = 0; j < n; j++) {
    const e = new Array(n).fill(0);
    e[j] = 1;
    const x = solve(A, e);
    if (!x) return null;
    cols.push(x);
  }
  return A.map((_, i) => cols.map((c) => c[i]));
}

// Ordinary least squares with an intercept: y = a + Σ b_k x_k. xs: {name: array}. Only days where y and every
// x are numbers count. Returns the coefficients, their t-statistics, R² and the number of days.
export function ols(y, xs) {
  const names = Object.keys(xs);
  const rows = [];
  for (let i = 0; i < y.length; i++) {
    const v = names.map((k) => xs[k][i]);
    if (ok(y[i]) && v.every(ok)) rows.push([1, ...v, y[i]]);
  }
  const k = names.length + 1;
  const n = rows.length;
  if (n <= k + 2) return null;
  const XtX = Array.from({ length: k }, (_, a) =>
    Array.from({ length: k }, (_, b) => rows.reduce((s, r) => s + r[a] * r[b], 0)),
  );
  const Xty = Array.from({ length: k }, (_, a) => rows.reduce((s, r) => s + r[a] * r[k], 0));
  const inv = inverse(XtX);
  if (!inv) return null;
  const coef = inv.map((row) => row.reduce((s, v, j) => s + v * Xty[j], 0));
  const fitted = rows.map((r) => coef.reduce((s, c, j) => s + c * r[j], 0));
  const ys = rows.map((r) => r[k]);
  const my = mean(ys);
  const ssr = ys.reduce((s, v, i) => s + (v - fitted[i]) ** 2, 0);
  const sst = ys.reduce((s, v) => s + (v - my) ** 2, 0);
  const s2 = ssr / (n - k);
  const t = coef.map((c, j) => (inv[j][j] > 0 && s2 > 0 ? c / Math.sqrt(s2 * inv[j][j]) : null));
  return {
    alpha: coef[0],
    alphaT: t[0],
    betas: Object.fromEntries(names.map((nm, j) => [nm, coef[j + 1]])),
    t: Object.fromEntries(names.map((nm, j) => [nm, t[j + 1]])),
    r2: sst > 0 ? 1 - ssr / sst : null,
    n,
  };
}

// The book's factor loadings: its daily return at today's weights (signed dollars / capital), regressed on the
// factor returns. A loading of 0.4 on momentum moves the book like 40% of capital long MTUM and short SPY.
// Also each position's own loadings, and the hedge in dollars that would bring a loading to zero.
export function factorExposure(positions, rets, factors, capital) {
  const w = positions.map((p) => (sideSign(p) * p.amount) / capital);
  const n = rets[positions[0].t].length;
  const book = new Array(n).fill(null);
  for (let i = 1; i < n; i++) {
    let s = 0;
    positions.forEach((p, k) => {
      const r = rets[p.t][i];
      if (ok(r)) s += w[k] * r;
    });
    book[i] = s;
  }
  const fit = ols(book, factors);
  if (!fit) return null;
  const perPosition = Object.fromEntries(
    positions.map((p) => {
      const f = ols(rets[p.t], factors);
      return [p.t, f ? f.betas : null];
    }),
  );
  const hedge = Object.fromEntries(Object.entries(fit.betas).map(([k, b]) => [k, -b * capital]));
  return {
    ...fit,
    perPosition,
    hedge,
    // the share of the book's daily variance the factors explain; the rest is stock-specific
    specific: fit.r2 === null ? null : 1 - fit.r2,
    alphaAnnual: fit.alpha * TRADING_DAYS * 100,
  };
}
