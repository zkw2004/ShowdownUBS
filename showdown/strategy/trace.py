from __future__ import annotations

from typing import Any

from showdown.models import Context


def begin(ctx: Context, **details: Any) -> None:
    """Attach internal decision evidence to this request for main.py logging."""
    ctx.raw["_decision_trace"] = details


def mark(ctx: Context, reason: str, **details: Any) -> None:
    trace = ctx.raw.setdefault("_decision_trace", {})
    trace.update(details)
    trace["reason"] = reason
