"""Phase 1 Macro Desk: one function per leading indicator (rules from docs/02-indicator-rules.md).

Every rule takes a point-in-time ``View`` and the thresholds in ``config.SIGNALS`` and returns a ``Signal``
with ``score`` (+1/0/-1, or None when awaiting data), ``state``, ``reason_en``, ``as_of``, ``percentile_10y``
and, after ``build``, its monthly ``history``. Run on its own with ``python -m pipeline.signals``.
"""
