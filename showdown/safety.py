from __future__ import annotations

from showdown.models import Action


def fallback_action(body: dict) -> Action:
    legal_actions = tuple(body.get("legal_actions") or ())
    if "check" in legal_actions:
        return Action("check")
    if "call" in legal_actions:
        return Action("call")
    return Action("fold")


def sanitize(action: Action, body: dict) -> dict:
    legal_actions = tuple(body.get("legal_actions") or ())
    if action.action not in legal_actions:
        return fallback_action(body).to_response()

    if action.action in {"check", "call", "fold"}:
        return Action(action.action).to_response()

    min_raise_to = body.get("min_raise_to")
    max_raise_to = body.get("max_raise_to")
    if min_raise_to is None or max_raise_to is None or action.amount is None:
        return fallback_action(body).to_response()

    amount = int(action.amount)
    if amount < int(min_raise_to) or amount > int(max_raise_to):
        return fallback_action(body).to_response()

    return Action(action.action, amount).to_response()
