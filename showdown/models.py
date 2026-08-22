from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Action:
    action: str
    amount: int | None = None

    def to_response(self) -> dict[str, Any]:
        payload = {"action": self.action}
        if self.amount is not None and self.action in {"bet", "raise"}:
            payload["amount"] = self.amount
        return payload


@dataclass(frozen=True)
class Context:
    raw: dict[str, Any]
    round_name: str
    table_rule: str
    your_number: int
    community_number: int | None
    pot: int
    to_call: int
    min_raise_to: int | None
    max_raise_to: int | None
    legal_actions: tuple[str, ...]
    your_seat: int
    button_seat: int
    your_stack: int
    big_blind: int
    hand_number: int
    total_hands: int
    leg_number: int | None
    total_legs: int | None
    match_id: str | None
    chip_delta: int
    my_bet_this_round: int
    acting_last: bool

    @property
    def adjusted_pot_odds(self) -> float:
        if self.to_call <= 0:
            return 0.0
        denominator = self.pot + self.to_call
        return self.to_call / denominator if denominator > 0 else 1.0

    @property
    def can_raise(self) -> bool:
        return "bet" in self.legal_actions or "raise" in self.legal_actions

    @property
    def can_check(self) -> bool:
        return "check" in self.legal_actions

    @property
    def can_call(self) -> bool:
        return "call" in self.legal_actions

    @property
    def can_fold(self) -> bool:
        return "fold" in self.legal_actions


def parse_context(body: dict[str, Any]) -> Context:
    players = body.get("players") or []
    your_seat = int(body.get("your_seat", 0) or 0)
    button_seat = int(body.get("button_seat", 0) or 0)
    round_name = body.get("round") or "pre_reveal"
    is_button = your_seat == button_seat
    acting_last = (not is_button) if round_name == "pre_reveal" else is_button

    my_player = _find_my_player(players, your_seat)
    chip_delta = int((my_player or {}).get("chip_delta", body.get("your_stack", 0) or 0) or 0)
    my_bet_this_round = int((my_player or {}).get("bet_this_round", 0) or 0)

    return Context(
        raw=body,
        round_name=round_name,
        table_rule=str(body.get("table_rule", "standard") or "standard"),
        your_number=int(body.get("your_number", 1) or 1),
        community_number=_optional_int(body.get("community_number")),
        pot=int(body.get("pot", 0) or 0),
        to_call=int(body.get("to_call", 0) or 0),
        min_raise_to=_optional_int(body.get("min_raise_to")),
        max_raise_to=_optional_int(body.get("max_raise_to")),
        legal_actions=tuple(str(action) for action in (body.get("legal_actions") or [])),
        your_seat=your_seat,
        button_seat=button_seat,
        your_stack=int(body.get("your_stack", 0) or 0),
        big_blind=int(body.get("big_blind", 2) or 2),
        hand_number=int(body.get("hand_number", 1) or 1),
        total_hands=int(body.get("total_hands", 100) or 100),
        leg_number=_optional_int(body.get("leg_number")),
        total_legs=_optional_int(body.get("total_legs")),
        match_id=_optional_str(body.get("match_id")),
        chip_delta=chip_delta,
        my_bet_this_round=my_bet_this_round,
        acting_last=acting_last,
    )


def _find_my_player(players: list[dict[str, Any]], your_seat: int) -> dict[str, Any] | None:
    for player in players:
        if player.get("name") == "you" or player.get("seat") == your_seat:
            return player
    return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
