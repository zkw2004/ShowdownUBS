from __future__ import annotations

import re
from dataclasses import dataclass, field

from showdown.models import Context

# Beta-style prior on the opponent's pre-reveal raise frequency: centred on 0.5
# with the weight of four observed hands, so the first few live hands dominate
# quickly without the very first raise reading as a 100% maniac.
_PRIOR_RAISES = 2.0
_PRIOR_HANDS = 4.0


@dataclass
class OpponentModel:
    """Aggregates the opponent's observed behaviour across hands and legs.

    Each request repeats the current hand's action list, so per-hand flags are
    accumulated under the hand's identity and folded into the counters when a
    new hand begins.
    """

    hands_observed: int = 0
    pre_raise_hands: int = 0
    by_seat: dict[int, "OpponentModel"] = field(default_factory=dict)
    _current_key: tuple | None = None
    _current_pre_raise: bool = False
    _current_pre_raise_seats: set[int] = field(default_factory=set)

    def update(self, ctx: Context) -> None:
        key = (ctx.match_id, ctx.leg_number, ctx.hand_number)
        if key != self._current_key:
            self._flush()
            self._current_key = key
        for action in ctx.raw.get("current_hand_actions") or []:
            if (
                isinstance(action, dict)
                and action.get("seat") != ctx.your_seat
                and action.get("round") == "pre_reveal"
                and action.get("action") == "raise"
            ):
                self._current_pre_raise = True
                seat = int(action.get("seat", -1))
                if seat >= 0:
                    self._current_pre_raise_seats.add(seat)

    def _flush(self) -> None:
        if self._current_key is not None:
            self.hands_observed += 1
            if self._current_pre_raise:
                self.pre_raise_hands += 1
            for seat in self._current_pre_raise_seats:
                model = self.by_seat.setdefault(seat, OpponentModel())
                model.hands_observed += 1
                model.pre_raise_hands += 1
            for seat, model in self.by_seat.items():
                if seat not in self._current_pre_raise_seats:
                    model.hands_observed += 1
        self._current_pre_raise = False
        self._current_pre_raise_seats.clear()

    def pre_raise_freq(self, seat: int | None = None) -> float:
        if seat is not None:
            model = self.by_seat.get(seat)
            if model is not None:
                return model.pre_raise_freq()
        return (self.pre_raise_hands + _PRIOR_RAISES) / (self.hands_observed + _PRIOR_HANDS)


def _match_key(match_id: str | None) -> str | None:
    # Legs of one match arrive as e.g. "phase2-seed123-leg1" / "-leg2": strip
    # the leg suffix so opponent reads carry across legs but reset per match.
    if match_id is None:
        return None
    return re.sub(r"-leg\d+$", "", match_id)


@dataclass
class AttemptState:
    last_leg: int | None = None
    last_match_id: str | None = None
    last_match_key: str | None = None
    opponent: OpponentModel = field(default_factory=OpponentModel)

    def observe(self, ctx: Context) -> bool:
        """Return whether this request begins a new leg."""
        match_key = _match_key(ctx.match_id)
        if match_key is not None and match_key != self.last_match_key:
            self.opponent = OpponentModel()
            self.last_match_key = match_key
        new_leg = ctx.leg_number is not None and ctx.leg_number != self.last_leg
        if new_leg:
            self.last_leg = ctx.leg_number
        if ctx.match_id is not None:
            self.last_match_id = ctx.match_id
        self.opponent.update(ctx)
        return new_leg

    def reset(self) -> None:
        self.last_leg = None
        self.last_match_id = None
        self.last_match_key = None
        self.opponent = OpponentModel()


ATTEMPT_STATE = AttemptState()
