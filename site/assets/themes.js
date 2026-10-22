// Macro ideas (lessons 34-35): which industries the macro readings and the ISM industry lists favour, the
// screener's outliers inside them, and international listings (ADRs) with the China check.

import { el, loadJSON, setChildren } from "./common.js";
import { fmt } from "./workbench.js";

const S = { data: null, cats: {}, filter: "strong", intlRegion: "China", intlRank: "all" };
const has = (v) => v !== null && v !== undefined;
const TONE_CLASS = {
  "strong tailwind": "tag-pos",
  tailwind: "tag-pos",
  neutral: "",
  headwind: "tag-neg",
  "strong headwind": "tag-neg",
};

function net(v) {
  if (!has(v)) return el("span", { class: "score none", text: "awaiting" });
  return el(
    "span",
    { class: `score ${v > 0 ? "pos" : v < 0 ? "neg" : ""}` },
    el("span", { "aria-hidden": "true", text: v > 0 ? "▲" : v < 0 ? "▼" : "●" }),
    v > 0 ? `+${v}` : v < 0 ? `−${-v}` : "0",
  );
}

function tiles() {
  const d = S.data;
  const ind = d.industries.filter((s) => has(s.net));
  const tile = (label, value, foot, cls = "", href = null) =>
    el(
      href ? "a" : "div",
      { class: `card tile ${href ? "tile-link" : ""}`, href },
      el("div", { class: "tile-label", text: label }),
      el("div", { class: `tile-value small ${cls}`, text: value }),
      el("div", { class: "tile-foot", text: foot }),
    );
  const ism = (k) => {
    const x = d.ism[k];
    return x && x.status === "ok"
      ? `${x.growth.length} growing, ${x.contraction.length} contracting (${x.month})`
      : "awaiting data";
  };
  return el(
    "div",
    { class: "tiles" },
    d.bias
      ? tile(
          "Macro bias",
          d.bias.label,
          `Macro Desk, ${d.macro_as_of}`,
          d.bias.score > 0 ? "up" : d.bias.score < 0 ? "down" : "",
          "macro.html",
        )
      : null,
    tile(
      "Tailwinds",
      String(ind.filter((s) => s.net > 0).length),
      `industries; ${ind.filter((s) => s.net >= d.params.strong).length} strong`,
      "up",
    ),
    tile(
      "Headwinds",
      String(ind.filter((s) => s.net < 0).length),
      `industries; ${ind.filter((s) => s.net <= -d.params.strong).length} strong`,
      "down",
    ),
    tile(
      "ISM manufacturing industries",
      d.ism.manufacturing ? d.ism.manufacturing.growth.length + " / " + d.ism.manufacturing.contraction.length : "–",
      ism("manufacturing"),
    ),
    tile(
      "ISM services industries",
      d.ism.services ? d.ism.services.growth.length + " / " + d.ism.services.contraction.length : "–",
      ism("services"),
    ),
  );
}

function drivers(items) {
  return items
    .filter((e) => e.effect !== 0 || e.source === "macro")
    .map((e) =>
      el("span", {
        class: `tag ${e.effect > 0 ? "tag-pos" : e.effect < 0 ? "tag-neg" : ""}`,
        title: `${e.reading}${e.as_of ? ` (${e.as_of})` : ""}. ${e.why}`,
        text: `${e.effect > 0 ? "▲ " : e.effect < 0 ? "▼ " : ""}${e.label}: ${e.reading}`,
      }),
    );
}

function industriesCard() {
  const d = S.data;
  const list = d.industries.filter((s) =>
    S.filter === "strong"
      ? has(s.net) && Math.abs(s.net) >= d.params.strong
      : S.filter === "wind"
        ? has(s.net) && s.net !== 0
        : S.filter === "all"
          ? true
          : s.tone && s.tone.endsWith(S.filter),
  );
  return el(
    "section",
    { class: "card panel", style: "margin-top:12px" },
    el("h2", { class: "panel-title", text: "Industries: macro tailwinds and headwinds" }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text: "Each industry adds up the Macro Desk signals that reach it (oil, metals, housing, consumer, rates, credit, dollar, China) and its place in the latest ISM growth / contraction lists. A first reading of where macro helps or hurts earnings in the next 20–60 days: check the drivers before acting.",
    }),
    el(
      "div",
      { class: "toolbar" },
      el(
        "div",
        { class: "seg wrap-seg", role: "group", "aria-label": "Show" },
        [
          ["strong", "Strongest (2+ drivers agree)"],
          ["wind", "Tailwinds & headwinds"],
          ["tailwind", "Tailwinds"],
          ["headwind", "Headwinds"],
          ["all", "All industries"],
        ].map(([k, label]) =>
          el("button", {
            type: "button",
            "aria-pressed": String(S.filter === k),
            text: label,
            onclick: () => {
              S.filter = k;
              render();
            },
          }),
        ),
      ),
    ),
    el(
      "div",
      { class: "scroll-x" },
      el(
        "table",
        { class: "data screener-table" },
        el(
          "thead",
          {},
          el(
            "tr",
            {},
            ["Industry", "Net", "Reading", "Stocks", "Drivers"].map((h) =>
              el("th", { text: h, style: h === "Drivers" ? "text-align:left" : null }),
            ),
          ),
        ),
        el(
          "tbody",
          {},
          list.map((s) =>
            el(
              "tr",
              {},
              el(
                "td",
                {},
                el("a", { href: `screener.html?industry=${encodeURIComponent(s.industry)}`, text: s.industry }),
              ),
              el("td", {}, net(s.net)),
              el(
                "td",
                { class: "text-left" },
                s.tone ? el("span", { class: `tag ${TONE_CLASS[s.tone] || ""}`, text: s.tone }) : null,
              ),
              el("td", { text: s.stocks }),
              el("td", { class: "text" }, ...drivers(s.items)),
            ),
          ),
        ),
      ),
    ),
    d.unmapped_industries.length
      ? el("p", { class: "section-note", text: `Not linked to a macro driver: ${d.unmapped_industries.join(", ")}.` })
      : null,
  );
}

function ideaTable(list, side) {
  if (!list.length)
    return el("p", {
      class: "muted",
      text: `No ${side}-side outliers in ${side === "long" ? "tailwind" : "headwind"} industries today.`,
    });
  return el(
    "div",
    { class: "scroll-x" },
    el(
      "table",
      { class: "data screener-table" },
      el(
        "thead",
        {},
        el(
          "tr",
          {},
          ["Stock", "Industry", "Net", "Type", "EG1", "EG2", "PE1", "3m", "Vol filter"].map((h) =>
            el("th", { text: h }),
          ),
        ),
      ),
      el(
        "tbody",
        {},
        list.map((x) => {
          const c = S.cats[x.cls];
          return el(
            "tr",
            {},
            el(
              "td",
              {},
              el("a", { href: `stock.html?t=${encodeURIComponent(x.t)}` }, el("b", { text: x.t })),
              el("span", { class: "sub", text: x.name || "" }),
            ),
            el("td", { class: "text-left", text: x.industry }),
            el("td", {}, net(x.net)),
            el(
              "td",
              { class: "text-left" },
              c
                ? el("span", {
                    class: `tag ${c.side === "long" ? "tag-pos" : c.side === "short" ? "tag-neg" : ""}`,
                    title: x.why || c.text,
                    text: c.label,
                  })
                : null,
            ),
            el("td", { class: x.eg1 > 0 ? "up" : x.eg1 < 0 ? "down" : "", text: fmt.pct(x.eg1) }),
            el("td", { class: x.eg2 > 0 ? "up" : x.eg2 < 0 ? "down" : "", text: fmt.pct(x.eg2) }),
            el("td", { text: has(x.pe1) ? x.pe1.toFixed(1) : "–" }),
            el("td", { class: x.r3m > 0 ? "up" : x.r3m < 0 ? "down" : "", text: fmt.pct(x.r3m, 0) }),
            el("td", { text: x.vol_ok === true ? "passes" : x.vol_ok === false ? "below" : "–" }),
          );
        }),
      ),
    ),
  );
}

function ideasCard() {
  const i = S.data.ideas;
  const bias = S.data.bias;
  const lead = bias ? (bias.score > 0 ? "long" : bias.score < 0 ? "short" : null) : null;
  return el(
    "section",
    { class: "card panel", style: "margin-top:12px" },
    el("h2", { class: "panel-title", text: "Macro-driven ideas" }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text:
        "Bottom-up meets top-down: the screener's positive outliers and turnarounds in tailwind industries (long side), its negative outliers, post-growth stocks and value traps in headwind industries (short side). Strongest macro support first." +
        (lead ? ` The macro bias is ${bias.label.toLowerCase()}: the ${lead} side is the bias's side.` : ""),
    }),
    el("h3", { class: "sub-title", text: `Long side (${i.long.length})` }),
    ideaTable(i.long.slice(0, S.longLimit || 15), "long"),
    i.long.length > (S.longLimit || 15)
      ? el("button", {
          type: "button",
          class: "btn",
          style: "margin-top:8px",
          text: `Show all ${i.long.length}`,
          onclick: () => {
            S.longLimit = Infinity;
            render();
          },
        })
      : null,
    el("h3", { class: "sub-title", text: `Short side (${i.short.length})` }),
    ideaTable(i.short, "short"),
  );
}

function chinaCard() {
  const c = S.data.china;
  const tone = c.state === "disagree" ? "callout" : "reading";
  return el(
    "div",
    { class: "card tile china-check" },
    el("div", { class: "tile-label", text: "China check: official data vs the companies (lesson 14)" }),
    el("p", { class: tone, text: c.text }),
    el(
      "p",
      { class: "facts" },
      el("span", {}, "NBS (official) ", el("b", { text: has(c.nbs) ? c.nbs.toFixed(1) : "–" })),
      el("span", {}, "RatingDog (private) ", el("b", { text: has(c.ratingdog) ? c.ratingdog.toFixed(1) : "–" })),
      el("span", {}, "Private − official ", el("b", { text: has(c.gap) ? c.gap.toFixed(1) : "–" })),
      el("span", {}, "Chinese listings ", el("b", { text: String(c.companies_n) })),
      el("span", {}, "Median EPS revision 90d ", el("b", { text: fmt.pct(c.companies_rev90) })),
      el("span", {}, "Median sales growth ", el("b", { text: fmt.pct(c.companies_rg1) })),
      c.as_of ? el("span", { class: "muted", text: `PMIs ${c.as_of}` }) : null,
    ),
  );
}

function internationalCard() {
  const intl = S.data.international;
  const regions = Object.entries(intl.regions).sort((a, b) => b[1].n - a[1].n);
  const stocks = intl.stocks.filter(
    (x) => (S.intlRegion === "All" || x.region === S.intlRegion) && (S.intlRank === "all" || x.rank === S.intlRank),
  );
  const pctCell = (v, d = 1) => el("td", { class: v > 0 ? "up" : v < 0 ? "down" : "", text: fmt.pct(v, d) });
  return el(
    "section",
    { class: "card panel", style: "margin-top:12px" },
    el("h2", { class: "panel-title", text: "International ideas: listings of companies based abroad" }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text: "Companies headquartered outside the US with a US listing (mostly ADRs), from the screener's universe. EPS growth is compared across them (currency-neutral); P/E and sales growth are left out where estimates are in another currency than the share price. Leader = EPS growth in the top quarter of these listings in both years; laggard = falling in both years and in the bottom quarter.",
    }),
    chinaCard(),
    el(
      "div",
      { class: "scroll-x", style: "margin-top:12px" },
      el(
        "table",
        { class: "data" },
        el(
          "thead",
          {},
          el(
            "tr",
            {},
            ["Region", "Stocks", "EG1 median", "EG2 median", "Sales g1", "EPS rev. 90d", "3m return"].map((h) =>
              el("th", { text: h }),
            ),
          ),
        ),
        el(
          "tbody",
          {},
          regions.map(([r, v]) =>
            el(
              "tr",
              { class: r === S.intlRegion ? "highlight" : "" },
              el(
                "td",
                {},
                el("button", {
                  type: "button",
                  class: "linklike",
                  text: r,
                  onclick: () => {
                    S.intlRegion = r;
                    render();
                  },
                }),
              ),
              el("td", { text: v.n }),
              pctCell(v.eg1),
              pctCell(v.eg2),
              pctCell(v.rg1),
              pctCell(v.eps1_rev90),
              pctCell(v.r3m),
            ),
          ),
        ),
      ),
    ),
    el(
      "div",
      { class: "toolbar", style: "margin-top:12px" },
      el(
        "label",
        {},
        "Region ",
        el(
          "select",
          {
            class: "select",
            onchange: (ev) => {
              S.intlRegion = ev.target.value;
              render();
            },
          },
          ["All", ...regions.map(([r]) => r)].map((r) =>
            el("option", { value: r, text: r, selected: r === S.intlRegion }),
          ),
        ),
      ),
      el(
        "div",
        { class: "seg", role: "group", "aria-label": "Growth rank" },
        [
          ["all", "All"],
          ["leader", "Growth leaders"],
          ["laggard", "Laggards"],
        ].map(([k, label]) =>
          el("button", {
            type: "button",
            "aria-pressed": String(S.intlRank === k),
            text: label,
            onclick: () => {
              S.intlRank = k;
              render();
            },
          }),
        ),
      ),
    ),
    el(
      "div",
      { class: "scroll-x" },
      el(
        "table",
        { class: "data screener-table" },
        el(
          "thead",
          {},
          el(
            "tr",
            {},
            [
              "Stock",
              "Country",
              "Industry",
              "Mkt cap",
              "EG1",
              "EG2",
              "Sales g1",
              "EPS rev. 90d",
              "PE1",
              "3m",
              "Rank",
            ].map((h) => el("th", { text: h })),
          ),
        ),
        el(
          "tbody",
          {},
          stocks
            .slice(0, 80)
            .map((x) =>
              el(
                "tr",
                {},
                el(
                  "td",
                  {},
                  el("a", { href: `stock.html?t=${encodeURIComponent(x.t)}` }, el("b", { text: x.t })),
                  el("span", { class: "sub", text: x.name || "" }),
                ),
                el("td", { class: "text-left", text: x.country }),
                el("td", { class: "text-left", text: x.industry || "" }),
                el("td", { text: fmt.money(x.mcap) }),
                pctCell(x.eg1),
                pctCell(x.eg2),
                pctCell(x.rg1),
                pctCell(x.eps1_rev90),
                el("td", { text: has(x.pe1) ? x.pe1.toFixed(1) : x.other_currency ? "other ccy" : "–" }),
                pctCell(x.r3m, 0),
                el(
                  "td",
                  { class: "text-left" },
                  x.rank
                    ? el("span", { class: `tag ${x.rank === "leader" ? "tag-pos" : "tag-neg"}`, text: x.rank })
                    : null,
                ),
              ),
            ),
        ),
      ),
    ),
    stocks.length > 80 ? el("p", { class: "section-note", text: `Showing the 80 largest of ${stocks.length}.` }) : null,
  );
}

function ismCard() {
  const d = S.data.ism;
  const block = (k, title) => {
    const x = d[k];
    if (!x || x.status !== "ok")
      return el(
        "div",
        {},
        el("h3", { class: "sub-title", text: title }),
        el("p", {
          class: "muted",
          text: `Awaiting data: enter the ISM industry lists in data/manual/ism_industries.csv${x && x.month ? ` (last ${x.month})` : ""}.`,
        }),
      );
    return el(
      "div",
      {},
      el("h3", { class: "sub-title", text: `${title} — ${x.month}` }),
      el("p", { class: "reading" }, el("b", { class: "up", text: "Growing: " }), x.growth.join(", ") || "none"),
      el(
        "p",
        { class: "reading" },
        el("b", { class: "down", text: "Contracting: " }),
        x.contraction.join(", ") || "none",
      ),
      x.unknown.length
        ? el("p", {
            class: "section-note",
            text: `Names not recognised (check the spelling in the CSV): ${x.unknown.join(", ")}.`,
          })
        : null,
    );
  };
  return el(
    "section",
    { class: "card panel", style: "margin-top:12px" },
    el("h2", { class: "panel-title", text: "ISM industry lists (entered by hand)" }),
    el("p", {
      class: "section-note",
      style: "margin-top:0",
      text: "From the ISM Report On Business: which industries reported growth and which contraction. Read the respondents' comments for single-stock ideas (lesson 34).",
    }),
    block("manufacturing", "Manufacturing"),
    block("services", "Services"),
  );
}

function render() {
  setChildren(
    document.getElementById("content"),
    tiles(),
    ideasCard(),
    industriesCard(),
    internationalCard(),
    ismCard(),
  );
}

async function main() {
  const [data, stocks] = await Promise.all([
    loadJSON("data/themes.json").catch(() => null),
    loadJSON("data/screener/stocks.json").catch(() => null),
  ]);
  if (!data) {
    setChildren(
      document.getElementById("content"),
      el("div", { class: "card notice", text: "No data yet: built by the daily update." }),
    );
    return;
  }
  S.data = data;
  S.cats = (stocks && stocks.categories) || {};
  if (!data.international.regions[S.intlRegion]) S.intlRegion = "All";
  render();
}

main();
