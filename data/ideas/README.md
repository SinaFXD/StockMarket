# Saved trade ideas

One file per idea, named after the ticker (`CRWD.md`). The website writes them: open a stock from the Screener,
start a trade idea, then **Publish to the repository**. This folder is public.

Format (checked by `python -m pipeline.workbench --check` on every update):

```
---
side: long             # long | short
status: researching    # researching | ready | active | closed | dropped
opened: 2026-10-22
updated: 2026-10-22
horizon_days: 40       # the course's window is 20-60 days
structure: stock       # stock | margin | cfd
entry_price: 239.34    # optional
assumptions:           # optional: your own numbers for the price targets
  pe: 120              # also ps, eps1, eps2, sales1, sales2 (in $), shares
---

## Business
## KPIs and management plan
## Industry drivers
## Catalysts
- 2026-11-10: Investor day
## Timing and technicals
## Structure
## Review notes
```

Method: `docs/08-workbench-method.md`.
