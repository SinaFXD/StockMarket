// How to use: table of contents, the live teaching tools and the glossary. The tools reuse the site's own
// arithmetic (workbench.js for targets and the expected move) so the numbers match the real pages.

import { el, loadJSON } from "./common.js";
import { REALISM_TEXT, priceTargets, realism, sigmaMove } from "./workbench.js";

const has = (v) => v !== null && v !== undefined && Number.isFinite(v);
const pct = (v, d = 1) => (has(v) ? `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(d)}%` : "–");
const num = (v, d = 2) => (has(v) ? v.toLocaleString("en-US", { maximumFractionDigits: d }) : "–");

function field(label, value, onInput, attrs = {}) {
  return el(
    "label",
    { class: "w-field" },
    el("span", { text: label }),
    el("input", {
      class: "select",
      type: "number",
      step: "any",
      value,
      ...attrs,
      oninput: (ev) => onInput(Number(ev.target.value)),
    }),
  );
}

function slider(label, min, max, step, value, fmt, onInput) {
  const out = el("b", { text: fmt(value) });
  return el(
    "label",
    { class: "w-slider" },
    el("span", {}, `${label} `, out),
    el("input", {
      type: "range",
      min,
      max,
      step,
      value,
      "aria-label": label,
      oninput: (ev) => {
        out.textContent = fmt(Number(ev.target.value));
        onInput(Number(ev.target.value));
      },
    }),
  );
}

function scorePill(v) {
  return el(
    "span",
    { class: `score ${v > 0 ? "pos" : v < 0 ? "neg" : ""}` },
    `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(2)}`,
  );
}

// ---------- table of contents ----------
function toc() {
  const items = [...document.querySelectorAll(".guide-sec")].map((s) => [s.id, s.querySelector("h2").textContent]);
  for (const box of document.querySelectorAll("[data-toc]")) {
    box.replaceChildren(
      el(
        "ol",
        { class: "toc-list" },
        items.map(([id, t]) => el("li", {}, el("a", { href: `#${id}`, text: t.replace(/^\d+\.\s*/, "") }))),
      ),
    );
  }
  const links = [...document.querySelectorAll(".guide-toc a")];
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries)
        if (e.isIntersecting)
          for (const a of links) a.classList.toggle("active", a.getAttribute("href") === `#${e.target.id}`);
    },
    { rootMargin: "-20% 0px -70% 0px" },
  );
  for (const s of document.querySelectorAll(".guide-sec")) io.observe(s);
}

// ---------- 1. bias playground ----------
const BLOCKS = {
  money_markets: "US money markets",
  surveys: "US surveys",
  prices_fx_equities: "Cyclical prices, FX & equities",
  international: "International",
};

async function biasWidget(box) {
  let latest = null;
  try {
    latest = await loadJSON("data/macro/latest.json");
  } catch {
    /* demo values below */
  }
  const threshold = (latest && latest.bias && latest.bias.threshold) || 0.25;
  const signals = latest
    ? latest.signals.map((s) => ({ id: s.id, name: s.name, block: s.block, auto: s.score, score: s.score }))
    : [];
  if (!signals.length) {
    box.replaceChildren(el("p", { class: "muted", text: "The Macro Desk data is not available yet." }));
    return;
  }
  const result = el("div", { class: "w-result" });
  const draw = () => {
    const blocks = Object.entries(BLOCKS).map(([k, label]) => {
      const used = signals.filter((s) => s.block === k && s.score !== null);
      const v = used.length ? used.reduce((a, s) => a + s.score, 0) / used.length : null;
      return { label, v, n: used.length };
    });
    const vals = blocks.filter((b) => b.v !== null).map((b) => b.v);
    const bias = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
    const state =
      bias === null
        ? "No reading"
        : bias >= threshold
          ? "Net long"
          : bias <= -threshold
            ? "Net short"
            : "Neutral (balanced)";
    result.replaceChildren(
      el(
        "div",
        { class: "w-blocks" },
        blocks.map((b) =>
          el(
            "div",
            { class: "w-block" },
            el("span", { text: b.label }),
            b.v === null ? el("span", { class: "muted", text: "awaiting" }) : scorePill(b.v),
          ),
        ),
      ),
      el(
        "p",
        { class: "w-big" },
        "Bias = average of the four blocks = ",
        bias === null ? "–" : scorePill(bias),
        " → ",
        el("b", { class: bias >= threshold ? "up" : bias <= -threshold ? "down" : "", text: state }),
        el("span", { class: "muted", text: `  (net long ≥ +${threshold}, net short ≤ −${threshold})` }),
      ),
      el("div", { class: "meter-mini" }, el("span", { style: `left:${bias === null ? 50 : ((bias + 1) / 2) * 100}%` })),
    );
  };
  const rows = Object.entries(BLOCKS).map(([k, label]) =>
    el(
      "div",
      { class: "w-group" },
      el("h4", { text: label }),
      signals
        .filter((s) => s.block === k)
        .map((s) =>
          el(
            "div",
            { class: "w-sig" },
            el("span", { class: "w-sig-name", text: s.name }),
            el(
              "div",
              { class: "seg seg-small", role: "group", "aria-label": s.name },
              [-1, 0, 1, null].map((v) =>
                el("button", {
                  type: "button",
                  "aria-pressed": String(s.score === v),
                  title: v === null ? "Treat as awaiting data (left out)" : "",
                  text: v === null ? "n/a" : v > 0 ? "+1" : v < 0 ? "−1" : "0",
                  onclick: (ev) => {
                    s.score = v;
                    for (const b of ev.target.parentNode.children)
                      b.setAttribute("aria-pressed", String(b === ev.target));
                    draw();
                  },
                }),
              ),
            ),
          ),
        ),
    ),
  );
  box.replaceChildren(
    el("div", { class: "w-groups" }, rows),
    result,
    el("button", {
      type: "button",
      class: "btn btn-small",
      text: "Back to today's automatic scores",
      onclick: () => {
        for (const s of signals) s.score = s.auto;
        biasWidget(box);
      },
    }),
  );
  draw();
}

// ---------- 2. the 11 numbers ----------
function elevenWidget(box) {
  const v = { price: 100, eps0: 4, eps1: 5, eps2: 6 };
  const out = el("div", { class: "w-result" });
  const draw = () => {
    const g = (a, b) => (b > 0 && has(a) ? (a / b - 1) * 100 : null);
    const pe = (e) => (e > 0 ? v.price / e : null);
    const peg = (p, gr) => (has(p) && gr > 0 ? p / gr : null);
    const eg1 = g(v.eps1, v.eps0);
    const eg2 = g(v.eps2, v.eps1);
    const pe1 = pe(v.eps1);
    const pe2 = pe(v.eps2);
    const cell = (label, value, why) =>
      el("div", { class: "w-cell" }, el("span", { text: label }), el("b", { text: value }), el("small", { text: why }));
    out.replaceChildren(
      el(
        "div",
        { class: "w-cells" },
        cell("EG1", has(eg1) ? pct(eg1) : "–", has(eg1) ? "EPS1 ÷ EPS0 − 1" : "EPS0 ≤ 0: a turnaround, not a rate"),
        cell("EG2", has(eg2) ? pct(eg2) : "–", has(eg2) ? "EPS2 ÷ EPS1 − 1" : "EPS1 ≤ 0: not a rate"),
        cell("PE1", num(pe1, 1), has(pe1) ? "price ÷ EPS1" : "EPS1 ≤ 0: no P/E"),
        cell("PE2", num(pe2, 1), has(pe2) ? "price ÷ EPS2" : "EPS2 ≤ 0: no P/E"),
        cell("PEG1", num(peg(pe1, eg1), 2), has(peg(pe1, eg1)) ? "PE1 ÷ EG1" : "needs P/E and positive growth"),
        cell("PEG2", num(peg(pe2, eg2), 2), has(peg(pe2, eg2)) ? "PE2 ÷ EG2" : "needs P/E and positive growth"),
      ),
      el("p", {
        class: "section-note",
        text: "Try EPS0 = −1 (a loss last year): growth is not a rate any more and the stock is a turnaround candidate. Try EPS2 below EPS1: growth turns negative and the PEG disappears.",
      }),
    );
  };
  const set = (k) => (x) => {
    v[k] = x;
    draw();
  };
  box.replaceChildren(
    el(
      "div",
      { class: "w-inputs" },
      field("Price", v.price, set("price")),
      field("EPS0 (last year, reported)", v.eps0, set("eps0")),
      field("EPS1 (this year, estimate)", v.eps1, set("eps1")),
      field("EPS2 (next year, estimate)", v.eps2, set("eps2")),
    ),
    out,
  );
  draw();
}

// ---------- 3. type finder (same order of rules as pipeline/screener/outliers.py) ----------
const TYPES = {
  positive: ["Positive outlier", "tag-pos", "Top-quarter EPS growth in both years: a long candidate (lesson 25)."],
  negative: [
    "Negative outlier",
    "tag-neg",
    "EPS falling in both years and in the bottom quarter: a short candidate (lesson 26).",
  ],
  post_growth: [
    "Post-growth",
    "tag-neg",
    "Fast growth this year, bottom-quarter next year: the growth phase is ending (short side).",
  ],
  turnaround: [
    "Turnaround",
    "",
    "Out of losses, or falling this year and recovering above the sector median next year (lesson 27).",
  ],
  loss: ["Loss-making", "", "Losses in both years: growth and P/E are not meaningful."],
  value_trap: ["Value trap", "", "Cheap P/E while EPS is falling: cheap for a reason (lesson 27)."],
  boring: ["Boring", "", "Growth in the middle half of the sector in both years."],
  mixed: ["In between", "", "None of the patterns above."],
};

function classify(s) {
  const top = 75;
  const bottom = 25;
  const eg1 = s.loss0 ? null : s.eg1; // growth out of a loss is not a rate
  const eg2 = s.eps2 <= 0 ? null : s.eg2;
  if (s.eps1 > 0 && s.eps2 <= 0) return "negative";
  if (eg1 > 0 && eg2 > 0 && s.p1 >= top && s.p2 >= top) return "positive";
  if (eg1 < 0 && eg2 < 0 && s.p1 <= bottom && s.p2 <= bottom) return "negative";
  if (eg1 > 0 && s.p1 >= top && s.p2 <= bottom) return "post_growth";
  if (s.loss0 && s.eps1 > 0) return "turnaround";
  if (s.eps1 <= 0 && s.eps2 <= 0) return "loss";
  if (eg1 < 0 && eg2 > 0 && s.p2 >= 50) return "turnaround";
  if (s.pePct <= bottom && (eg1 < 0 || eg2 < 0)) return "value_trap";
  if (s.p1 > bottom && s.p1 < top && s.p2 > bottom && s.p2 < top) return "boring";
  return "mixed";
}

function typesWidget(box) {
  const s = { eg1: 30, eg2: 25, p1: 85, p2: 80, pePct: 50, eps1: 1, eps2: 1, loss0: false };
  const out = el("div", { class: "w-result" });
  const draw = () => {
    const [label, cls, text] = TYPES[classify(s)];
    out.replaceChildren(
      el("p", { class: "w-big" }, "Type: ", el("span", { class: `tag ${cls}`, text: label })),
      el("p", { text }),
    );
  };
  const set = (k) => (x) => {
    s[k] = x;
    draw();
  };
  box.replaceChildren(
    el(
      "div",
      { class: "w-sliders" },
      slider("EG1 (this year)", -60, 120, 1, s.eg1, (x) => pct(x, 0), set("eg1")),
      slider("EG1 percentile in the sector", 0, 100, 1, s.p1, (x) => `${x}th`, set("p1")),
      slider("EG2 (next year)", -60, 120, 1, s.eg2, (x) => pct(x, 0), set("eg2")),
      slider("EG2 percentile in the sector", 0, 100, 1, s.p2, (x) => `${x}th`, set("p2")),
      slider("PE1 percentile (low = cheap)", 0, 100, 1, s.pePct, (x) => `${x}th`, set("pePct")),
    ),
    el(
      "div",
      { class: "toolbar", style: "margin:10px 0 0" },
      el(
        "label",
        { class: "check" },
        el("input", { type: "checkbox", onchange: (ev) => set("loss0")(ev.target.checked) }),
        " Loss last year (EPS0 ≤ 0)",
      ),
      el(
        "label",
        { class: "check" },
        el("input", { type: "checkbox", onchange: (ev) => set("eps2")(ev.target.checked ? -1 : 1) }),
        " Loss expected next year (EPS2 ≤ 0)",
      ),
    ),
    out,
    el("p", {
      class: "section-note",
      text: "Percentile = the share of the sector's clean stocks with lower growth. The rules are tried in a fixed order and the first that matches wins, exactly as on the Screener.",
    }),
  );
  draw();
}

// ---------- 4. price targets (the course's Zendesk example) ----------
function targetsWidget(box) {
  const v = { price: 76, eps0: 1, eps1: 1.8, sales0: 100, sales1: 135, side: "long" };
  const out = el("div", { class: "w-result" });
  const draw = () => {
    const t = priceTargets(v.price, [v.eps0, v.eps1, null], [v.sales0, v.sales1, null], 1);
    const y = t.years[0];
    const line = (label, how, target, mv) =>
      el(
        "div",
        { class: "w-target" },
        el("span", {}, el("b", { text: label }), el("small", { text: how })),
        el("b", { class: "w-target-v", text: has(target) ? target.toFixed(2) : "–" }),
        el("span", { class: has(mv) ? (mv >= 0 ? "up" : "down") : "", text: has(mv) ? pct(mv) : "" }),
      );
    out.replaceChildren(
      line(
        "EPS-based (upper)",
        has(t.pe) ? `constant P/E ${t.pe.toFixed(1)} × EPS1 ${v.eps1}` : "no P/E: last year was a loss",
        y.eps_target,
        y.eps_move,
      ),
      line(
        "Sales-based (lower)",
        has(t.ps) ? `price × sales growth ${pct((v.sales1 / v.sales0 - 1) * 100, 0)}` : "needs last year's sales",
        y.sales_target,
        y.sales_move,
      ),
      el("p", {
        class: "section-note",
        text: "With the course's numbers (price 76, EPS +80%, sales +35%) the targets are 136.80 and 102.60, exactly as in the lesson. On a stock page the same formulas use the analysts' consensus, and you can replace any input with your own view.",
      }),
    );
  };
  const set = (k) => (x) => {
    v[k] = x;
    draw();
  };
  box.replaceChildren(
    el(
      "div",
      { class: "w-inputs" },
      field("Price today", v.price, set("price")),
      field("EPS last year (EPS0)", v.eps0, set("eps0")),
      field("EPS this year (EPS1)", v.eps1, set("eps1")),
      field("Sales last year", v.sales0, set("sales0")),
      field("Sales this year (estimate)", v.sales1, set("sales1")),
    ),
    out,
  );
  draw();
}

// ---------- 5. expected move ----------
function moveWidget(box) {
  const v = { vol: 40, days: 40, target: 15 };
  const out = el("div", { class: "w-result" });
  const p = { sigma_ok: 1, sigma_stretched: 2 };
  const draw = () => {
    const sig = sigmaMove(v.vol, v.days);
    const r = realism(v.target, sig, p);
    out.replaceChildren(
      el(
        "p",
        { class: "w-big" },
        "1σ move over ",
        el("b", { text: `${v.days} days` }),
        ": ±",
        el("b", { text: sig.toFixed(1) + "%" }),
      ),
      el(
        "div",
        { class: "w-band" },
        ...[-2, -1, 0, 1, 2].map((k) =>
          el("span", {
            class: `band-${Math.abs(k)}`,
            text: k === 0 ? "today" : `${k > 0 ? "+" : "−"}${(Math.abs(k) * sig).toFixed(0)}%`,
          }),
        ),
      ),
      r
        ? el(
            "p",
            {},
            `A target ${pct(v.target, 0)} away is `,
            el("b", { text: `${r.z.toFixed(1)}σ` }),
            ": ",
            el("span", {
              class: `tag ${r.state === "realistic" ? "tag-pos" : r.state === "unrealistic" ? "tag-warn" : ""}`,
              text: REALISM_TEXT[r.state],
            }),
          )
        : null,
    );
  };
  const set = (k) => (x) => {
    v[k] = x;
    draw();
  };
  box.replaceChildren(
    el(
      "div",
      { class: "w-sliders" },
      slider("Annual volatility", 10, 120, 1, v.vol, (x) => `${x}%`, set("vol")),
      slider("Horizon", 10, 90, 1, v.days, (x) => `${x} days`, set("days")),
      slider("Move the target needs", -60, 80, 1, v.target, (x) => pct(x, 0), set("target")),
    ),
    out,
    el("p", {
      class: "section-note",
      text: "1σ = annual volatility × √(days ÷ 365). About two moves in three stay within 1σ, about 19 in 20 within 2σ.",
    }),
  );
  draw();
}

// ---------- 6. correlation and portfolio volatility ----------
function corrWidget(box) {
  const v = { volA: 30, volB: 30, rho: 0.6, sideB: "short" };
  const out = el("div", { class: "w-result" });
  const draw = () => {
    const wA = 0.5;
    const wB = v.sideB === "short" ? -0.5 : 0.5;
    const a = wA * v.volA;
    const b = wB * v.volB;
    const vol = Math.sqrt(a * a + b * b + 2 * a * b * v.rho);
    const asPositions = v.rho * (v.sideB === "short" ? -1 : 1);
    out.replaceChildren(
      el(
        "p",
        { class: "w-big" },
        "Portfolio volatility: ",
        el("b", { text: `${vol.toFixed(1)}%` }),
        el("span", {
          class: "muted",
          text: ` (each position alone: ${(0.5 * v.volA).toFixed(1)}% and ${(0.5 * v.volB).toFixed(1)}%)`,
        }),
      ),
      el(
        "p",
        {},
        "Correlation of the two ",
        el("i", { text: "positions" }),
        ` (shorts flipped): ${asPositions >= 0 ? "+" : "−"}${Math.abs(asPositions).toFixed(2)} `,
        el("span", {
          class: `tag ${Math.abs(asPositions) <= 0.3 ? "tag-pos" : "tag-warn"}`,
          text:
            Math.abs(asPositions) <= 0.3
              ? "inside the ±0.3 target"
              : asPositions > 0
                ? "they add risk together"
                : "a strong hedge: little net exposure",
        }),
      ),
    );
  };
  const set = (k) => (x) => {
    v[k] = x;
    draw();
  };
  box.replaceChildren(
    el(
      "div",
      { class: "w-sliders" },
      slider("Volatility of stock A (long)", 10, 80, 1, v.volA, (x) => `${x}%`, set("volA")),
      slider("Volatility of stock B", 10, 80, 1, v.volB, (x) => `${x}%`, set("volB")),
      slider("Correlation of the two stocks' prices", -1, 1, 0.05, v.rho, (x) => x.toFixed(2), set("rho")),
    ),
    el(
      "div",
      { class: "seg", role: "group", "aria-label": "Side of stock B", style: "margin-top:8px" },
      ["long", "short"].map((side) =>
        el("button", {
          type: "button",
          "aria-pressed": String(v.sideB === side),
          text: `Stock B ${side}`,
          onclick: (ev) => {
            v.sideB = side;
            for (const btn of ev.target.parentNode.children)
              btn.setAttribute("aria-pressed", String(btn === ev.target));
            draw();
          },
        }),
      ),
    ),
    out,
    el("p", {
      class: "section-note",
      text: "Each position is half the account. Volatility² = a² + b² + 2·a·b·correlation, with a and b the signed position volatilities.",
    }),
  );
  draw();
}

// ---------- 7. glossary ----------
// [term, where on the site, definition]
const GLOSSARY = [
  [
    "20–60 day horizon",
    "everywhere",
    "The course's holding period for a trade (1–3 months of volatility). 60–120 days is a grey zone; beyond 120 days it is an investment.",
  ],
  [
    "ADR",
    "Macro ideas",
    "American Depositary Receipt: a US listing of a foreign company. Used for international ideas, e.g. Chinese companies reporting under US rules.",
  ],
  [
    "Analysts' range",
    "Trade idea",
    "The lowest and highest analyst estimate behind a consensus number. A wide range means more uncertainty and room for surprises.",
  ],
  [
    "ATR",
    "Screener, Trade idea",
    "Average True Range: the average daily high-to-low move over 14 days, in % of the price.",
  ],
  [
    "Awaiting data",
    "Macro Desk, Data health",
    "No recent data for an indicator. It is left out of every calculation until the data arrives; nothing is guessed.",
  ],
  ["Beta", "Portfolio", "How much a stock moves with the S&P 500. Beta 1.5 = 1.5% for each 1% of the index."],
  [
    "Beta-adjusted net exposure",
    "Portfolio",
    "Sum of long minus short positions, each multiplied by its beta, as % of the account: how long or short the book really is against the market.",
  ],
  [
    "Bias (portfolio bias)",
    "Macro Desk",
    "The macro reading for the whole book: Net long (score ≥ +0.25), Neutral, or Net short (≤ −0.25). Average of the four block scores.",
  ],
  [
    "Block",
    "Macro Desk",
    "A group of indicators: US money markets, US surveys, cyclical prices/FX/equities, international. Block score = average of its indicators.",
  ],
  [
    "Building permits",
    "Macro Desk",
    "New housing permits (Census). They lead housing starts and completions; the course reads them together with consumer sentiment.",
  ],
  [
    "Catalyst",
    "Trade idea, Calendar",
    "An event that can move the stock within the horizon: earnings, investor days, product launches, regulatory decisions. It turns an investment into a trade.",
  ],
  ["CEW", "Portfolio", "Constant equal weight: a backtest where every position has the same weight again each day."],
  [
    "CFNAI (Chicago Fed activity index)",
    "Regime",
    "A monthly average of 85 US indicators of production, jobs, spending and sales. 0 = growth at its long-run trend; the 3-month average is the growth axis of the regime map.",
  ],
  [
    "China PMI (NBS / RatingDog)",
    "Macro Desk",
    "Purchasing managers' indices for China. NBS is official; RatingDog (formerly Caixin) is private and preferred by the course. Private minus official is the 'potential lie' gap.",
  ],
  [
    "Confirmers",
    "Macro Desk",
    "Coincident and lagging data (CPI, payrolls, claims, industrial production, GDP). They confirm the leading indicators; never scored.",
  ],
  ["Consensus", "Screener, Trade idea", "The average of the analysts' estimates (EPS, sales)."],
  [
    "Core PCE inflation",
    "Regime",
    "Inflation of the prices consumers pay, without food and energy: the Fed's preferred measure.",
  ],
  [
    "Correlation",
    "Portfolio",
    "How two return series move together, from −1 (opposite) to +1 (together). The course aims for −0.3 to +0.3 between positions.",
  ],
  [
    "Credit spreads",
    "Macro Desk",
    "The extra yield of corporate bonds (AA, BBB, CCC) over Treasuries. Widening = stress; junk (CCC) usually moves first.",
  ],
  [
    "Cyclical / sensitive / defensive",
    "Sectors",
    "Morningstar's three groups of sectors. Cyclicals and sensitives follow the economy; defensives (staples, healthcare, utilities) hold up when it slows.",
  ],
  [
    "Data checks",
    "Screener",
    "Tags that warn about unreliable numbers (other currency, feeds disagree, extreme P/E, few analysts…). Red ones keep the stock out of averages.",
  ],
  [
    "Days to cover",
    "Trade idea",
    "Shares sold short ÷ average daily volume: how many days the shorts would need to buy back.",
  ],
  ["Drawdown", "Portfolio", "How far the book is below its previous peak, in %. The deepest is the maximum drawdown."],
  [
    "EG1, EG2",
    "Screener",
    "EPS growth this year (EPS1 vs EPS0) and next year (EPS2 vs EPS1), in %. Only from a positive base.",
  ],
  [
    "EPS0, EPS1, EPS2",
    "Screener",
    "Earnings per share: last reported fiscal year, and the consensus for the current and the next fiscal year.",
  ],
  [
    "ESI",
    "Macro Desk, Global",
    "The euro area's Economic Sentiment Indicator (Eurostat). Long-run average 100; above 100 = better than average.",
  ],
  [
    "Estimate revisions",
    "Evidence (forward test)",
    "The change in analysts' consensus EPS over the last 90 days. Rising estimates tend to matter more than a high growth forecast.",
  ],
  [
    "EV/EBIT, EV/EBITDA",
    "Screener (Evidence)",
    "Enterprise value (market cap + debt − cash) divided by operating profit (EBIT) or by operating profit before depreciation (EBITDA).",
  ],
  [
    "Evidence (page)",
    "Evidence",
    "How past bias readings were followed by the S&P 500, with sample sizes and real-time data. A check of the method, not a forecast.",
  ],
  [
    "Expected move (1σ)",
    "Trade idea",
    "Annual volatility × √(days ÷ 365): the size of a normal move over the horizon.",
  ],
  [
    "Factor exposure (style bet)",
    "Portfolio",
    "How much the book moves with a style (market, small vs large, value vs growth, momentum), in % of capital. A big one means the book is partly a bet on that style, not on its stocks.",
  ],
  [
    "First reading",
    "everywhere",
    "An automatic application of the course's rule. Always shown with its reason; you decide and can override.",
  ],
  [
    "GAAP vs adjusted",
    "Trade idea",
    "GAAP = the official accounts. Analysts' EPS is usually 'adjusted' (excluding items such as stock pay or one-offs). A big gap deserves a look.",
  ],
  ["Gross exposure", "Portfolio", "Longs plus shorts, as % of the account."],
  [
    "Implied volatility",
    "Screener, Trade idea",
    "The volatility the option market prices in (here: at-the-money options about 45 days out).",
  ],
  [
    "ISM Manufacturing / Services",
    "Macro Desk",
    "Monthly surveys of US purchasing managers. Above 50 = expanding. Sub-indices (new orders, production, employment…) and the industry lists matter too. Entered by hand.",
  ],
  [
    "ISM industry lists",
    "Macro ideas",
    "The industries ISM reports as growing or contracting each month; they feed the macro → industry map.",
  ],
  [
    "Leading / coincident / lagging",
    "Macro Desk",
    "Leading indicators move before the economy (money markets, surveys, prices); coincident with it (CPI, payrolls); lagging after it (earnings, GDP).",
  ],
  [
    "Long-short spread",
    "Evidence (forward test)",
    "Average return of the positive outliers minus that of the negative outliers in the same weekly cohort. Positive = the types separate winners from losers.",
  ],
  ["M2", "Macro Desk", "US money supply; its growth confirms what the Fed is doing with liquidity."],
  ["Net exposure", "Portfolio", "Longs minus shorts, as % of the account."],
  [
    "NFIB",
    "Macro Desk",
    "The US small-business optimism survey, with the course's own leading index built from its components. Entered by hand.",
  ],
  [
    "Non-rebalanced",
    "Portfolio",
    "A backtest where your dollar positions are set once and left to drift: what an account really does.",
  ],
  [
    "Outlier (positive / negative)",
    "Screener",
    "A stock whose EPS growth is in the top (positive) or bottom (negative) quarter of its sector in both forward years: long and short candidates.",
  ],
  [
    "Output gap",
    "Regime",
    "Real GDP minus the economy's potential (CBO estimate), in % of potential. Positive = running hot.",
  ],
  [
    "Override",
    "Macro Desk",
    "Your own score for an indicator (−1 / 0 / +1). The bias recalculates; saved only in your browser.",
  ],
  [
    "Payoff ratio",
    "Ideas (track record)",
    "Average winning trade ÷ average losing trade. With a hit rate below 50% you need a payoff well above 1.",
  ],
  ["P/E (PE1, PE2)", "Screener", "Price ÷ EPS. Only meaningful when EPS is positive."],
  ["P/S", "Trade idea", "Price-to-sales: market cap ÷ sales. Used for the sales-based target."],
  ["PEG", "Screener", "P/E ÷ EPS growth in %. Below 1 = cheap for its growth; meaningless with negative growth."],
  [
    "Percentile",
    "Screener, Macro Desk",
    "The share of comparable values below this one. 90th = higher than 90% of them.",
  ],
  ["Pipeline (ideas)", "Ideas", "Your list of open ideas; the course aims for 10–15, about two new a week."],
  [
    "Post-growth",
    "Screener",
    "Fast growth this year but bottom-quarter growth next year: the growth phase is ending (a short-side type).",
  ],
  [
    "Pre-registered test",
    "Evidence",
    "A hypothesis written down before the data exists, so the result cannot be bent to fit afterwards.",
  ],
  [
    "Price targets (EPS / sales)",
    "Trade idea",
    "Upper: EPS growth at a constant P/E. Lower: sales growth at a constant P/S. Always a range.",
  ],
  [
    "Real interest rate",
    "Macro Desk",
    "The 10-year Treasury yield minus inflation. Low vs history = cheap money, supportive for stocks.",
  ],
  [
    "Realised volatility",
    "Screener",
    "The annualised standard deviation of the stock's daily returns over the last ~3 months.",
  ],
  [
    "Recession probability (yield-curve model)",
    "Regime",
    "The New York Fed's estimate of a US recession 12 months later, from the 10-year minus 3-month Treasury spread. Watch the rise, not a level.",
  ],
  [
    "Regime (Recovery, Overheat, Stagflation, Reflation)",
    "Regime",
    "Growth above or below trend crossed with inflation speeding up or easing. Context for the bias, not a signal.",
  ],
  [
    "Relative strength",
    "Trade idea, Sectors",
    "A stock's or sector ETF's return minus the S&P 500's (or its sector ETF's) over the same period, in percentage points.",
  ],
  [
    "Revision breadth",
    "Sectors",
    "The share of a sector's stocks whose EPS consensus analysts raised (or cut) by 1% or more in 90 days. More raised than cut = earnings momentum.",
  ],
  [
    "Rotation map",
    "Sectors",
    "Each sector's 3-month strength against the S&P 500 (across) and its change over the last month (up): leading, weakening, lagging or improving.",
  ],
  ["Risk share", "Portfolio", "The part of the portfolio's variance a position brings; a hedge has a negative share."],
  [
    "Sharpe ratio",
    "Portfolio",
    "Return above the risk-free rate ÷ volatility. The course's minimums: 1.5 (CFDs), 2 (stocks long/short), ≈3.3 (options).",
  ],
  [
    "Short interest",
    "Trade idea",
    "Shares sold short, as % of the float. Above ~10% (or 5+ days to cover) is a crowded short.",
  ],
  ["Structure", "Trade idea", "How you hold the trade: stock, stock on margin, or CFD. Options are out of scope here."],
  [
    "Tailwind / headwind",
    "Macro ideas",
    "Macro drivers that help (tailwind) or hurt (headwind) an industry's earnings in the next 20–60 days.",
  ],
  [
    "t-statistic",
    "Evidence",
    "How many standard errors an average is away from zero. Above about 2 (in absolute value), the result is unlikely to be luck; it needs enough independent observations.",
  ],
  [
    "Taylor rule",
    "Regime",
    "A simple formula for where the policy rate 'should' be: 2 + inflation + 0.5 × (inflation − 2) + 0.5 × output gap.",
  ],
  ["Turnaround", "Screener", "A company coming back to profit, or falling this year and recovering next year."],
  [
    "UMich sentiment",
    "Macro Desk",
    "The University of Michigan consumer survey; the expectations part leads spending. The course's zones: 55–70 trough, 70–95 middle, 95–110 peak.",
  ],
  ["Value trap", "Screener", "A cheap P/E while earnings fall: cheap for a reason."],
  [
    "Vintage (real-time data)",
    "Evidence",
    "The value of a data series as it was first published. Backtests use vintages so the past is not judged with later revisions.",
  ],
  [
    "VIX",
    "Macro Desk, Screener",
    "The S&P 500's implied volatility. The screener wants stocks moving at least 1.5× the VIX.",
  ],
  [
    "Volatility filter",
    "Screener",
    "Keep only stocks whose realised and implied volatility are ≥ 1.5× the VIX, so they can move enough in 20–60 days.",
  ],
  [
    "Yield curve",
    "Macro Desk",
    "The 10-year minus the 2-year Treasury yield. Inverted (negative) = contraction expected; steepening out of flat = supportive.",
  ],
];

function glossaryWidget(box) {
  const list = el("dl", { class: "glossary" });
  const count = el("span", { class: "muted" });
  const draw = (q = "") => {
    const t = q.trim().toLowerCase();
    const hits = GLOSSARY.filter(([term, where, def]) => !t || `${term} ${where} ${def}`.toLowerCase().includes(t));
    count.textContent = `${hits.length} of ${GLOSSARY.length} terms`;
    list.replaceChildren(
      ...hits.flatMap(([term, where, def]) => [
        el("dt", {}, el("b", { text: term }), el("span", { class: "tag", text: where })),
        el("dd", { text: def }),
      ]),
    );
  };
  box.replaceChildren(
    el(
      "div",
      { class: "toolbar" },
      el("input", {
        class: "search",
        type: "search",
        placeholder: "Search a term, e.g. PEG or beta",
        "aria-label": "Search the glossary",
        oninput: (ev) => draw(ev.target.value),
      }),
      count,
    ),
    list,
  );
  draw();
}

const WIDGETS = {
  bias: biasWidget,
  eleven: elevenWidget,
  types: typesWidget,
  targets: targetsWidget,
  move: moveWidget,
  corr: corrWidget,
  glossary: glossaryWidget,
};

toc();
for (const box of document.querySelectorAll("[data-widget]")) WIDGETS[box.dataset.widget](box);
