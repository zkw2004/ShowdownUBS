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
    phase: int | None
    chip_delta: int
    my_bet_this_round: int
    acting_last: bool
    live_opponent_seats: tuple[int, ...]
    player_deltas: tuple[tuple[int, int], ...]

    @property
    def effective_call(self) -> int:
        """Chips we actually put in if we call. Never more than our stack."""
        return max(0, min(self.to_call, self.your_stack))

    @property
    def effective_pot(self) -> int:
        """Pot we are eligible to win after unmatched overbets are returned.

        The protocol includes the bettor's full overbet in `pot`, even when
        our shorter stack cannot cover it. Contributions above our final
        round total belong to a side pot (or are returned), so counting them
        made short-stack calls look much cheaper than they really were.
        """
        cap_total = self.my_bet_this_round + self.effective_call
        inaccessible = 0
        for player in self.raw.get("players") or []:
            if int(player.get("seat", -1)) == self.your_seat:
                continue
            if bool(player.get("folded", False)) or bool(player.get("busted", False)):
                continue
            contribution = int(player.get("bet_this_round", 0) or 0)
            inaccessible += max(0, contribution - cap_total)
        return max(0, self.pot - inaccessible)

    @property
    def adjusted_pot_odds(self) -> float:
        call = self.effective_call
        if call <= 0:
            return 0.0
        denominator = self.effective_pot + call
        return call / denominator if denominator > 0 else 1.0

    @property
    def risk_fraction(self) -> float:
        return self.effective_call / max(self.your_stack, 1)

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

    @property
    def live_opponent_count(self) -> int:
        return len(self.live_opponent_seats)

    @property
    def is_multiway(self) -> bool:
        return self.live_opponent_count >= 2

    @property
    def highest_other_delta(self) -> int:
        others = [delta for seat, delta in self.player_deltas if seat != self.your_seat]
        return max(others, default=self.chip_delta)

    @property
    def leads_table(self) -> bool:
        return self.chip_delta > self.highest_other_delta

    @property
    def chips_needed_to_lead(self) -> int:
        return max(0, self.highest_other_delta - self.chip_delta + 1)

    @property
    def is_phase3(self) -> bool:
        """Phase is a match property. Do not infer it from who is still in this pot."""
        if self.phase == 3:
            return True
        if self.phase in {1, 2}:
            return False
        return self.total_hands == 60 or len(self.player_deltas) >= 3

    @property
    def lead_margin(self) -> int:
        return self.chip_delta - self.highest_other_delta

    @property
    def progress(self) -> float:
        hands = max(self.total_hands, 1)
        return min(1.0, max(0.0, self.hand_number / hands))


def parse_context(body: dict[str, Any]) -> Context:
    players = body.get("players") or []
    your_seat = int(body.get("your_seat", 0) or 0)
    button_seat = int(body.get("button_seat", 0) or 0)
    round_name = body.get("round") or "pre_reveal"
    is_button = your_seat == button_seat
    acting_last = _acting_last(players, your_seat, button_seat, round_name, is_button)

    my_player = _find_my_player(players, your_seat)
    chip_delta = int((my_player or {}).get("chip_delta", body.get("your_stack", 0) or 0) or 0)
    my_bet_this_round = int((my_player or {}).get("bet_this_round", 0) or 0)
    live_opponent_seats = tuple(
        int(player.get("seat", -1))
        for player in players
        if int(player.get("seat", -1)) != your_seat
        and not bool(player.get("folded", False))
        and not bool(player.get("busted", False))
    )
    player_deltas = tuple(
        (int(player.get("seat", -1)), int(player.get("chip_delta", 0) or 0))
        for player in players
        if not bool(player.get("busted", False))
    )

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
        phase=_optional_int(body.get("phase")),
        chip_delta=chip_delta,
        my_bet_this_round=my_bet_this_round,
        acting_last=acting_last,
        live_opponent_seats=live_opponent_seats,
        player_deltas=player_deltas,
    )


def _find_my_player(players: list[dict[str, Any]], your_seat: int) -> dict[str, Any] | None:
    for player in players:
        if player.get("name") == "you" or player.get("seat") == your_seat:
            return player
    return None


def _acting_last(
    players: list[dict[str, Any]], your_seat: int, button_seat: int, round_name: str, is_button: bool
) -> bool:
    """Return positional last-to-act for heads-up and multiway tables.

    Busted seats are skipped when finding the small and big forced bets. A
    folded player is still part of the original order but can no longer be the
    player receiving a decision, so it does not affect whether *we* occupy the
    positional last seat.
    """
    live_seats = sorted(
        int(player.get("seat", -1)) for player in players if not bool(player.get("busted", False)) and int(player.get("seat", -1)) >= 0
    )
    if len(live_seats) <= 2:
        return (not is_button) if round_name == "pre_reveal" else is_button
    if button_seat not in live_seats:
        return False
    button_index = live_seats.index(button_seat)
    if round_name == "post_reveal":
        return your_seat == button_seat
    big_blind_seat = live_seats[(button_index + 2) % len(live_seats)]
    return your_seat == big_blind_seat


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
