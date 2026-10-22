// Trade Idea Workbench arithmetic shared by the stock page and the Ideas page.
// Repeats pipeline/workbench/targets.py (price_targets, sigma_move, realism) so the user's own assumptions
// give the same numbers as the pipeline's defaults: keep the two in sync.

const pos = (x) => typeof x === "number" && Number.isFinite(x) && x > 0;

// eps, sales: [last reported year, current year E, next year E]. Options: pe / ps override the constant
// multiples; sharesFwd is the share count expected in the forward years (buybacks, dilution), default today's.
export function priceTargets(price, eps, sales, shares, { pe = null, ps = null, sharesFwd = null } = {}) {
  const peUsed = pos(pe) ? pe : pos(price) && pos(eps[0]) ? price / eps[0] : null;
  const psUsed = pos(ps) ? ps : pos(price) && pos(sales[0]) && pos(shares) ? price / (sales[0] / shares) : null;
  const sh = pos(sharesFwd) ? sharesFwd : shares;
  const years = [1, 2].map((i) => {
    const epsT = peUsed !== null && pos(eps[i]) ? peUsed * eps[i] : null;
    const salesT = psUsed !== null && pos(sales[i]) && pos(sh) ? (psUsed * sales[i]) / sh : null;
    return { eps_target: epsT, sales_target: salesT, eps_move: move(price, epsT), sales_move: move(price, salesT) };
  });
  return { pe: peUsed, ps: psUsed, years };
}

export function move(price, target) {
  return pos(price) && target !== null && target !== undefined ? (target / price - 1) * 100 : null;
}

// One standard deviation of the move over `days` calendar days, in %, from an annualised volatility in %.
export function sigmaMove(volPct, days) {
  return pos(volPct) && days > 0 ? volPct * Math.sqrt(days / 365) : null;
}

export function realism(movePct, sigmaPct, p) {
  if (movePct === null || movePct === undefined || !pos(sigmaPct)) return null;
  const z = Math.abs(movePct) / sigmaPct;
  return { z, state: z <= p.sigma_ok ? "realistic" : z <= p.sigma_stretched ? "stretched" : "unrealistic" };
}

export const REALISM_TEXT = {
  realistic: "within a normal 1σ move",
  stretched: "stretched: 1–2σ",
  unrealistic: "unrealistic for the horizon: adjust",
};

// Same rule as pipeline/screener/numbers.py: a row counts toward averages unless a "left out" check applies.
export function excluded(row, checks) {
  return row.flags.some((f) => checks[f] && checks[f].excluded);
}

export function median(values) {
  const v = values.filter((x) => x !== null && x !== undefined && Number.isFinite(x)).sort((a, b) => a - b);
  if (!v.length) return null;
  const mid = Math.floor(v.length / 2);
  return v.length % 2 ? v[mid] : (v[mid - 1] + v[mid]) / 2;
}

export function rowsOf(stocks) {
  const cols = stocks.columns;
  return stocks.rows.map((r) => Object.fromEntries(cols.map((c, i) => [c, r[i]])));
}

// ---- formatting ----
export const fmt = {
  price: (v) =>
    v === null || v === undefined
      ? "–"
      : v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  pct: (v, d = 1) => {
    if (v === null || v === undefined) return "–";
    const r = Number(v.toFixed(d)); // no "−0.0%" for a tiny negative
    return `${r > 0 ? "+" : r < 0 ? "−" : ""}${Math.abs(r).toFixed(d)}%`;
  },
  plain: (v, d = 1) => (v === null || v === undefined ? "–" : `${v.toFixed(d)}%`),
  x: (v, d = 1) => (v === null || v === undefined ? "–" : `${v.toFixed(d)}×`),
  num: (v, d = 2) => (v === null || v === undefined ? "–" : v.toLocaleString("en-US", { maximumFractionDigits: d })),
  money: (v) => {
    if (v === null || v === undefined) return "–";
    const a = Math.abs(v);
    const s =
      a >= 1e12
        ? `${(a / 1e12).toFixed(2)}T`
        : a >= 1e9
          ? `${(a / 1e9).toFixed(a >= 1e11 ? 0 : 1)}B`
          : a >= 1e6
            ? `${(a / 1e6).toFixed(0)}M`
            : a.toFixed(0);
    return `${v < 0 ? "−" : ""}$${s}`;
  },
  millions: (v) =>
    v === null || v === undefined
      ? "–"
      : `${v < 0 ? "−" : ""}${Math.abs(v / 1e6).toLocaleString("en-US", { maximumFractionDigits: 0 })}`,
};

export function daysBetween(a, b) {
  return Math.round((Date.parse(b) - Date.parse(a)) / 86400000);
}

export function todayISO() {
  return new Date().toISOString().slice(0, 10);
}
