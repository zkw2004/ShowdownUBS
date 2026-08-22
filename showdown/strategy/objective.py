from __future__ import annotations

from showdown.models import Context


def objective_raise_target(ctx: Context, base_total: int) -> int:
    """Size a late raise toward a lead-flipping pot without jamming too early."""
    cap_fraction = 0.35 if ctx.progress < 0.90 else 0.65 if ctx.progress < 0.96 else 1.0
    cap_total = ctx.my_bet_this_round + int(ctx.your_stack * cap_fraction)
    objective_total = min(ctx.raise_to_for_table_lead, cap_total)
    return max(base_total, objective_total)


def should_force_leader_showdown(ctx: Context, share: float) -> bool:
    """Take a high-variance line when ordinary pots can no longer clear the leg.

    The unique table leader must be in the pot, contested by at most one other
    live opponent so the equity floor below stays meaningful.  Requiring a
    strictly heads-up pot never fired in practice: a four- or five-handed leg
    rarely isolates us against that specific opponent.  `ordinary_recovery`
    below, not the hand count, is what keeps this off while the gap is still
    winnable by normal play.
    """
    leader_seat = ctx.sole_leader_seat
    if (
        not ctx.is_phase3
        or ctx.leads_table
        or not ctx.can_raise
        or leader_seat is None
        or leader_seat not in ctx.live_opponent_seats
        or ctx.live_opponent_count > 2
        or ctx.remaining_hands > 20
    ):
        return False

    # Calling already creates enough direct transfer in a smaller-gap spot.
    matched_total = ctx.my_bet_this_round + ctx.effective_call
    if ctx.raise_to_for_table_lead <= matched_total:
        return False

    # If blinds and ordinary pots can plausibly bridge the gap, preserve EV.
    ordinary_recovery = max(
        ctx.effective_pot * 2,
        ctx.remaining_hands * ctx.big_blind * 6,
    )
    if ctx.chips_needed_to_lead <= ordinary_recovery:
        return False

    if ctx.remaining_hands <= 2:
        equity_floor = 0.25
    elif ctx.remaining_hands <= 5:
        equity_floor = 0.35
    elif ctx.remaining_hands <= 8:
        equity_floor = 0.45
    elif ctx.remaining_hands <= 12:
        equity_floor = 0.50
    else:
        equity_floor = 0.55
    return share >= equity_floor
