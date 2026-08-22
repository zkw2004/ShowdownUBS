from __future__ import annotations

from dataclasses import dataclass

from showdown.models import Context

# Weak prior so the first dozen observed hands move the read, while a seat we
# have never seen still looks like a typical 6-max opener rather than a nit.
_PRIOR_RAISES = 3.0
_PRIOR_HANDS = 8.0
_PRIOR_FOLDS = 2.0
_PRIOR_BETS_FACED = 5.0


@dataclass(frozen=True)
class SeatProfile:
    """Action frequencies for one seat. Names are ignored; the key is the seat."""

    hands: int = 0
    pre_raises: int = 0
    bets_faced: int = 0
    folds_to_bet: int = 0
    post_bets: int = 0
    post_actions: int = 0

    @property
    def pfr(self) -> float:
        return (self.pre_raises + _PRIOR_RAISES) / (self.hands + _PRIOR_HANDS)

    @property
    def fold_to_bet(self) -> float:
        return (self.folds_to_bet + _PRIOR_FOLDS) / (self.bets_faced + _PRIOR_BETS_FACED)

    @property
    def post_aggression(self) -> float:
        return (self.post_bets + 2.0) / (self.post_actions + 6.0)


def profiles_from_window(ctx: Context) -> dict[int, SeatProfile]:
    """Rebuild per-seat stats from `recent_hands` on every request.

    The protocol already sends the last 20 completed hands. Using that window
    keeps the model correct after a dyno restart and never keys off names.
    """
    buckets: dict[int, _MutableSeat] = {}
    for hand in ctx.raw.get("recent_hands") or []:
        if not isinstance(hand, dict):
            continue
        _ingest_hand(buckets, hand, ctx.your_seat)
    return {seat: bucket.freeze() for seat, bucket in buckets.items()}


@dataclass
class _MutableSeat:
    hands: int = 0
    pre_raises: int = 0
    bets_faced: int = 0
    folds_to_bet: int = 0
    post_bets: int = 0
    post_actions: int = 0

    def freeze(self) -> SeatProfile:
        return SeatProfile(
            hands=self.hands,
            pre_raises=self.pre_raises,
            bets_faced=self.bets_faced,
            folds_to_bet=self.folds_to_bet,
            post_bets=self.post_bets,
            post_actions=self.post_actions,
        )


def _ingest_hand(buckets: dict[int, _MutableSeat], hand: dict, your_seat: int) -> None:
    actions = [action for action in (hand.get("actions") or []) if isinstance(action, dict)]
    seats = {
        int(action.get("seat", -1))
        for action in actions
        if int(action.get("seat", -1)) >= 0 and int(action.get("seat", -1)) != your_seat
    }
    for shown_seat in (hand.get("shown_numbers") or {}):
        try:
            seat = int(shown_seat)
        except (TypeError, ValueError):
            continue
        if seat >= 0 and seat != your_seat:
            seats.add(seat)
    for seat in seats:
        buckets.setdefault(seat, _MutableSeat()).hands += 1

    raised_pre: set[int] = set()
    for action in actions:
        seat = int(action.get("seat", -1))
        if seat < 0 or seat == your_seat:
            continue
        bucket = buckets.setdefault(seat, _MutableSeat())
        kind = action.get("action")
        round_name = action.get("round")
        if round_name == "pre_reveal" and kind == "raise":
            raised_pre.add(seat)
        if round_name == "post_reveal":
            bucket.post_actions += 1
            if kind in {"bet", "raise"}:
                bucket.post_bets += 1

    for seat in raised_pre:
        buckets[seat].pre_raises += 1

    _count_folds_to_aggression(buckets, actions, your_seat)


def _count_folds_to_aggression(buckets: dict[int, _MutableSeat], actions: list[dict], your_seat: int) -> None:
    last_aggressor: dict[str, int | None] = {"pre_reveal": None, "post_reveal": None}
    for action in actions:
        seat = int(action.get("seat", -1))
        round_name = action.get("round")
        kind = action.get("action")
        if round_name not in last_aggressor or seat < 0:
            continue
        if kind in {"bet", "raise"}:
            last_aggressor[round_name] = seat
            continue
        if seat == your_seat or last_aggressor[round_name] is None:
            continue
        if last_aggressor[round_name] == seat:
            continue
        bucket = buckets.setdefault(seat, _MutableSeat())
        bucket.bets_faced += 1
        if kind == "fold":
            bucket.folds_to_bet += 1
