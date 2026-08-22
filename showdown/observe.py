"""Live observation logging for a scored attempt.

Phase 2 hides the showdown rule, so a failing leg is only diagnosable from the
run itself. Every completed hand in `recent_hands` is a labelled observation
(numbers shown, community, winner), which is enough to check the registry's
mapping for a codename against what the coordinator actually paid out.

Nothing here may raise into `/move`, and nothing here may block: a diagnostic
that costs a substitution is worse than no diagnostic at all.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from showdown.evaluator.registry import get_rule

logger = logging.getLogger("uvicorn.error")

_seen_legs: set[tuple[Any, Any]] = set()
_seen_hands: set[tuple[Any, Any, Any]] = set()
_audit: dict[str, dict[str, int]] = {}


def observe(body: dict[str, Any], response: dict[str, Any], log_moves: bool = True) -> None:
    try:
        _log_leg_start(body)
        _log_completed_hands(body)
        if log_moves:
            _emit("move", _move_trace(body, response))
    except Exception:
        logger.exception("observe_error")


def reset() -> None:
    _seen_legs.clear()
    _seen_hands.clear()
    _audit.clear()


def _emit(event: str, payload: dict[str, Any]) -> None:
    logger.info("%s=%s", event, json.dumps(payload, sort_keys=True, default=str))


def _log_leg_start(body: dict[str, Any]) -> None:
    """Dump one whole request per leg: the only full sample of the wire format."""
    key = (body.get("match_id"), body.get("leg_number"))
    if key in _seen_legs:
        return
    _seen_legs.add(key)
    codename = str(body.get("table_rule") or "")
    _emit(
        "leg_start",
        {
            "match_id": body.get("match_id"),
            "leg": body.get("leg_number"),
            "total_legs": body.get("total_legs"),
            "phase": body.get("phase"),
            "rule": codename,
            "rule_solved": get_rule(codename) is not None,
            "total_hands": body.get("total_hands"),
            "sample_request": body,
        },
    )


def _log_completed_hands(body: dict[str, Any]) -> None:
    match_id = body.get("match_id")
    leg = body.get("leg_number")
    codename = str(body.get("table_rule") or "")
    for record in body.get("recent_hands") or []:
        key = (match_id, leg, record.get("hand_number"))
        if key in _seen_hands:
            continue
        _seen_hands.add(key)
        _emit("hand_result", {"leg": leg, "rule": codename, **_audit_hand(codename, record)})


def _audit_hand(codename: str, record: dict[str, Any]) -> dict[str, Any]:
    """Compare the registry's predicted winner against the paid-out winner."""
    community = record.get("community_number")
    shown = {int(seat): int(number) for seat, number in (record.get("shown_numbers") or {}).items()}
    winners = sorted(int(seat) for seat in (record.get("winners") or []))
    result: dict[str, Any] = {
        "hand": record.get("hand_number"),
        "community": community,
        "shown": {str(seat): shown[seat] for seat in sorted(shown)},
        "winners": winners,
        "pot": record.get("pot"),
    }

    # A fold-out hand reveals no numbers, so it carries no rule evidence.
    if community is None or len(shown) < 2:
        result["verdict"] = "no_showdown"
        return result

    rule = get_rule(codename)
    if rule is None:
        result["verdict"] = "rule_unsolved"
        result["tally"] = _tally(codename, "rule_unsolved")
        return result

    ranked = {seat: rule.rank(number, community) for seat, number in shown.items()}
    best = max(ranked.values())
    predicted = sorted(seat for seat, rank in ranked.items() if rank == best)
    verdict = "agree" if predicted == winners else "mismatch"
    result["predicted"] = predicted
    result["verdict"] = verdict
    result["tally"] = _tally(codename, verdict)
    return result


def _tally(codename: str, verdict: str) -> dict[str, int]:
    counts = _audit.setdefault(codename, {})
    counts[verdict] = counts.get(verdict, 0) + 1
    return dict(counts)


def _move_trace(body: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    """The full coordinator request and our exact reply.

    `recent_hands` is omitted here because each completed hand is already
    emitted once as `hand_result`. Repeating the last 20 hands on every
    /move would overflow Heroku's log buffer mid-attempt.
    """
    request = {key: value for key, value in body.items() if key != "recent_hands"}
    return {"request": request, "response": response}
