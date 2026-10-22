# This week: the weekly routine

`routine.html` ("This week" in the menu, linked from the home page as "Start here") puts the site's pages in the
course's order and says, from the published data, what each step needs this week. Logic:
`site/assets/routine-logic.js` (tested by `tests/js/routine.test.mjs`); page: `site/assets/routine.js`.

| Step | Page | Needs attention when |
|---|---|---|
| 1. Enter this week's reports | Data health | a hand-entered report is out and not entered, awaiting data, or a file has errors; manual reports due in the next 7 days are listed |
| 2. Read the Macro Desk | Macro Desk | the bias changed since the previous month, or the Macro Desk raises an alert (blocks disagree, data vs prices, ...); the regime and the recession odds are listed (Regime page) |
| 3. Macro → industries and regions | Macro ideas | the China check finds official data and companies disagreeing; strong tailwinds / headwinds are listed |
| 4. Screen for outliers | Screener | (weekly step) counts of positive / negative / post-growth outliers and how many pass the volatility filter; the sectors leading or improving and those lagging against the S&P 500 (Sectors page) |
| 5. Work up new trade ideas | Ideas | fewer than 10 open ideas, or fewer than 2 new ones in the last 7 days (lesson 33) |
| 6. Review open ideas and catalysts | Ideas | an open idea not updated for 7+ days, or reporting earnings within 7 days; moves of 10%+ since entry and high-importance macro events in the next 7 days are listed |
| 7. Check the portfolio | Portfolio | the current book's position count is outside the guide for the account size |

- Suggested time per step (our split of the course's 8–12 hours a week for a retail trader): 0.5 + 1.5 + 0.5 +
  1.5 + 4 + 1 + 1 = 10 hours.
- The ticks are kept in the browser (`localStorage` key `ptm.routine.v1`) per ISO week, so each week starts fresh.
  Ideas and the portfolio are read from the same browser storage as their own pages, plus the published ideas.
