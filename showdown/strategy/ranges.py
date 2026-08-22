from __future__ import annotations

from showdown.equity import ordered_numbers, pot_share_vs_ranges, top_numbers
from showdown.models import Context
from showdown.strategy.profiles import SeatProfile

# Typical first-in open widths by seat, used as the prior until that seat has
# been observed. These are position priors, not names.
POSITION_OPEN_FRACTION = {
    "ep": 0.30,
    "mp": 0.40,
    "co": 0.52,
    "btn": 0.62,
    "sb": 0.55,
    "bb": 0.38,
}
UNIFORM = tuple(range(1, 14))


def position_name(ctx: Context, seat: int | None = None) -> str:
    target = ctx.your_seat if seat is None else seat
    seats = sorted(
        int(player.get("seat", -1))
        for player in (ctx.raw.get("players") or [])
        if not bool(player.get("busted", False)) and int(player.get("seat", -1)) >= 0
    )
    if len(seats) <= 2:
        return "btn" if target == ctx.button_seat else "bb"
    if ctx.button_seat not in seats or target not in seats:
        return "mp"
    offset = (seats.index(target) - seats.index(ctx.button_seat)) % len(seats)
    if offset == 0:
        return "btn"
    if offset == 1:
        return "sb"
    if offset == 2:
        return "bb"
    from_utg = offset - 3
    late = len(seats) - 3
    if from_utg <= 0:
        return "ep"
    if from_utg >= late - 1:
        return "co"
    return "mp"


def committed_opponent_seats(ctx: Context) -> tuple[int, ...]:
    """Opponents who have voluntarily put chips in this hand.

    Players who have not acted yet are still in `live_opponent_seats`, but they
    are not yet in the pot. Pricing a call as if all of them already hold the
    raiser's range is what turned a 9 into an 8% fold.
    """
    invested: set[int] = set()
    for action in ctx.raw.get("current_hand_actions") or []:
        if not isinstance(action, dict):
            continue
        seat = int(action.get("seat", -1))
        if seat < 0 or seat == ctx.your_seat:
            continue
        if action.get("action") in {"call", "raise", "bet"}:
            invested.add(seat)
    return tuple(seat for seat in ctx.live_opponent_seats if seat in invested)


def infer_ranges(ctx: Context, profiles: dict[int, SeatProfile]) -> dict[int, tuple[int, ...]]:
    """One number-set per opponent we are actually up against right now."""
    community = ctx.community_number if ctx.round_name == "post_reveal" else None
    committed = committed_opponent_seats(ctx)
    unlogged_bet = ctx.to_call > 0 and not committed
    seats = committed if committed and ctx.to_call > 0 else ctx.live_opponent_seats
    if unlogged_bet:
        seats = ctx.live_opponent_seats
    ranges: dict[int, tuple[int, ...]] = {}
    for seat in seats:
        profile = profiles.get(seat, SeatProfile())
        if unlogged_bet:
            ranges[seat] = _betting_range(ctx, seat, profile, community)
        else:
            ranges[seat] = range_for_seat(ctx, seat, profile, community)
    return ranges


def _betting_range(ctx: Context, seat: int, profile: SeatProfile, community: int | None) -> tuple[int, ...]:
    """Range when we are facing chips but have no raise/bet tagged on that seat."""
    fraction = POSITION_OPEN_FRACTION[position_name(ctx, seat)]
    mixed = (profile.hands * profile.pfr + 8.0 * fraction) / (profile.hands + 8.0)
    mixed = max(0.20, min(0.80, mixed))
    ratio = ctx.effective_call / max(ctx.pot, 1)
    if ctx.round_name == "post_reveal":
        mixed = max(0.18, min(0.70, 0.32 + 0.50 * profile.post_aggression))
        if ratio >= 0.80:
            mixed *= 0.55 if profile.pfr < 0.42 else 0.85
        if ratio >= 1.50:
            mixed *= 0.70 if profile.pfr < 0.42 else 0.90
    elif ratio >= 2.0:
        mixed = max(0.20, mixed * 0.75)
    return top_numbers(ctx.table_rule, max(0.15, min(0.80, mixed)), community)


def range_for_seat(
    ctx: Context, seat: int, profile: SeatProfile, community: int | None
) -> tuple[int, ...]:
    raises, bets, calls = _seat_actions(ctx, seat)
    open_prior = POSITION_OPEN_FRACTION[position_name(ctx, seat)]
    mixed = (profile.hands * profile.pfr + 8.0 * open_prior) / (profile.hands + 8.0)
    mixed = max(0.20, min(0.80, mixed))
    ratio = ctx.effective_call / max(ctx.pot, 1)

    if raises >= 2:
        fraction = max(0.12, min(0.40, mixed * 0.45))
        if ratio >= 2.0:
            fraction = max(0.12, fraction * 0.85)
        return top_numbers(ctx.table_rule, fraction, community)
    if raises == 1 or bets:
        fraction = mixed
        if ctx.round_name == "post_reveal":
            fraction = max(0.18, min(0.70, 0.32 + 0.50 * profile.post_aggression))
            if ratio >= 0.80:
                fraction *= 0.55 if profile.pfr < 0.42 else 0.85
            if ratio >= 1.50:
                fraction *= 0.70 if profile.pfr < 0.42 else 0.90
        elif ratio >= 2.0:
            fraction = max(0.20, fraction * 0.75)
        return top_numbers(ctx.table_rule, max(0.15, min(0.80, fraction)), community)
    if calls:
        # Callers show up with most playable numbers, including some traps.
        keep = max(5, min(13, round(13 * min(0.85, mixed + 0.20))))
        return ordered_numbers(ctx.table_rule, community)[:keep]
    return UNIFORM


def pot_share(ctx: Context, ranges: dict[int, tuple[int, ...]]) -> float:
    community = ctx.community_number if ctx.round_name == "post_reveal" else None
    if not ranges:
        opponent_ranges = tuple(UNIFORM for _ in ctx.live_opponent_seats)
    else:
        opponent_ranges = tuple(ranges.values())
    return pot_share_vs_ranges(ctx.your_number, community, ctx.table_rule, opponent_ranges)


def _seat_actions(ctx: Context, seat: int) -> tuple[int, int, int]:
    raises = bets = calls = 0
    street = ctx.round_name
    for action in ctx.raw.get("current_hand_actions") or []:
        if not isinstance(action, dict) or int(action.get("seat", -1)) != seat:
            continue
        if action.get("round") != street and street == "post_reveal":
            # A pre-reveal raise still marks them as a committed player, but the
            # post-reveal range is built from what they did after the community.
            continue
        kind = action.get("action")
        if kind == "raise":
            raises += 1
        elif kind == "bet":
            bets += 1
        elif kind == "call":
            calls += 1
    if street == "post_reveal" and raises == 0 and bets == 0 and calls == 0:
        for action in ctx.raw.get("current_hand_actions") or []:
            if not isinstance(action, dict) or int(action.get("seat", -1)) != seat:
                continue
            kind = action.get("action")
            if kind == "raise":
                raises += 1
            elif kind == "call":
                calls += 1
    return raises, bets, calls
