from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Showdown:
    codename: str
    leg_number: int | None
    hand_number: int
    community: int | None
    numbers: dict[int, int]
    winners: tuple[int, ...]


def extract(match_json: dict[str, Any]) -> list[Showdown]:
    """Extract actual showdowns from known coordinator log shapes.

    A schema mismatch raises ValueError rather than silently solving no rules.
    """
    hands = match_json.get("hands") or match_json.get("hand_history") or match_json.get("matches")
    if not isinstance(hands, list):
        raise ValueError("unrecognised match-log schema: expected a hands list")
    observations: list[Showdown] = []
    for hand in hands:
        if not isinstance(hand, dict):
            raise ValueError("unrecognised hand entry")
        actions = hand.get("actions") or hand.get("current_hand_actions") or []
        if any(isinstance(action, dict) and action.get("action") == "fold" for action in actions):
            continue
        community = hand.get("community_number")
        shown = hand.get("shown_numbers") or hand.get("numbers") or hand.get("dealt_numbers")
        winners = hand.get("winners")
        if community is None or not isinstance(shown, dict) or not isinstance(winners, (list, tuple)):
            continue
        codename = hand.get("table_rule") or hand.get("rule") or match_json.get("table_rule")
        if not isinstance(codename, str):
            raise ValueError("showdown hand has no table_rule")
        try:
            numbers = {int(seat): int(number) for seat, number in shown.items()}
            winner_seats = tuple(sorted(int(seat) for seat in winners))
            observations.append(Showdown(codename, _optional_int(hand.get("leg_number")), int(hand.get("hand_number", len(observations) + 1)), int(community), numbers, winner_seats))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"malformed showdown hand: {hand!r}") from exc
    return observations


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)
