from __future__ import annotations

from showdown.config import CONFIG, PHASE2_CONFIG, RuleConfig
from showdown.models import Action, Context
from showdown.strategy.ranges import position_name, strength_index
from showdown.strategy.sizing import call_or_check, multiple_of_amount_raise, raise_action
from showdown.strategy.trace import mark


def decide_preflop(
    ctx: Context,
    share: float,
    percentile: float,
    edge: float,
    rule_config: RuleConfig,
    unknown: bool,
    ranges: dict[int, tuple[int, ...]],
) -> Action:
    opponent_raises = _opponent_pre_reveal_raise_count(ctx)
    if ctx.to_call > 0 and opponent_raises:
        if unknown:
            return _unknown_call_or_fold(ctx)
        return _respond_to_raise(ctx, share, edge, rule_config, ranges, opponent_raises)

    if unknown:
        if ctx.to_call == 0:
            return Action("check")
        return _unknown_call_or_fold(ctx)

    return _decide_first_in(ctx, percentile, rule_config)


def _respond_to_raise(
    ctx: Context,
    share: float,
    edge: float,
    rule_config: RuleConfig,
    ranges: dict[int, tuple[int, ...]],
    opponent_raises: int,
) -> Action:
    call = ctx.effective_call
    required = ctx.adjusted_pot_odds + edge
    detail = dict(
        opponent_raises=opponent_raises,
        live_opponents=ctx.live_opponent_count,
        committed_opponents=len(ranges),
        range_equity=round(share, 4),
        required_equity=round(required, 4),
        risk_fraction=round(ctx.risk_fraction, 4),
        pot_odds=round(ctx.adjusted_pot_odds, 4),
    )

    if (
        share >= CONFIG.preflop_value_reraise_equity
        and ctx.can_raise
        and call < ctx.your_stack * 0.30
    ):
        # Isolate when heads-up to the raiser, or when the number is a lock.
        if len(ranges) <= 1 or share >= 0.90:
            mark(ctx, "preflop_value_reraise", **detail)
            return multiple_of_amount_raise(
                ctx,
                ctx.my_bet_this_round + ctx.to_call,
                CONFIG.preflop_reraise_multiplier,
                cap_fraction_of_stack=rule_config.max_commitment_fraction,
            )

    if share >= 0.70 and ctx.can_call:
        mark(ctx, "preflop_premium_call", **detail)
        return Action("call")

    if strength_index(ctx) <= 1 and ctx.can_call and (ctx.adjusted_pot_odds <= 0.50 or ctx.risk_fraction < 0.40):
        mark(ctx, "preflop_top_number_call", **detail)
        return Action("call")

    if _should_call(share, ctx, edge):
        mark(ctx, "preflop_raise_call", **detail)
        return Action("call") if ctx.can_call else call_or_check(ctx)
    if ctx.can_fold:
        mark(ctx, "preflop_raise_fold", **detail)
        return Action("fold")
    return call_or_check(ctx)


def _decide_first_in(ctx: Context, percentile: float, rule_config: RuleConfig) -> Action:
    """Open, complete, or fold when nobody has raised.

    Six-seat first-in is raise-or-fold except in the big blind: completing a 4
    or 6 builds a multiway pot that the chip leader then wins. Heads-up still
    completes cheaply because one chip into a pot of 3 is almost always right.
    """
    position = position_name(ctx)
    if ctx.to_call == 0:
        if percentile >= rule_config.open_raise_min_percentile + 0.15:
            mark(ctx, "preflop_bb_iso", position=position)
            return raise_action(ctx, int(round(CONFIG.default_open_raise_to_bb * ctx.big_blind)))
        return Action("check")

    open_need = {
        "ep": rule_config.open_raise_min_percentile + 0.18,
        "mp": rule_config.open_raise_min_percentile + 0.08,
        "co": rule_config.open_raise_min_percentile - 0.05,
        "btn": rule_config.open_raise_min_percentile - 0.08,
        "sb": rule_config.open_raise_min_percentile,
        "bb": rule_config.open_raise_min_percentile + 0.12,
    }[position]
    if ctx.is_phase3 and ctx.live_opponent_count >= 2:
        # v11 opened sevens from the button and bled chips to callers with tens.
        open_need = {"ep": 0.78, "mp": 0.70, "co": 0.62, "btn": 0.60, "sb": 0.66, "bb": 0.72}[position]
    else:
        open_need = max(0.35, min(0.85, open_need))

    if percentile >= open_need + 0.18:
        mark(ctx, "preflop_open_raise", position=position)
        return raise_action(ctx, int(round(CONFIG.default_open_raise_to_bb * ctx.big_blind)))
    if percentile >= open_need:
        mark(ctx, "preflop_open_raise", position=position)
        return raise_action(ctx, int(round(CONFIG.medium_open_raise_to_bb * ctx.big_blind)), prefer_call=True)

    six_max = ctx.is_phase3 and ctx.live_opponent_count >= 2 and position not in {"bb"}
    if six_max:
        # Completing 1 from the small blind is still cheap; everywhere else,
        # limp-folding is how the table leader prints blinds.
        if position == "sb" and percentile >= 0.30:
            mark(ctx, "preflop_complete", position=position)
            return call_or_check(ctx)
        if ctx.can_fold:
            mark(ctx, "preflop_first_in_fold", position=position)
            return Action("fold")
        return call_or_check(ctx)

    complete_floor = CONFIG.button_complete_min_percentile if position in {"btn", "sb"} else 0.38
    if percentile <= complete_floor and ctx.can_fold:
        mark(ctx, "preflop_first_in_fold", position=position)
        return Action("fold")
    if position in {"btn", "sb", "co"} or (ctx.to_call <= ctx.big_blind and percentile >= 0.38):
        mark(ctx, "preflop_complete", position=position)
        return call_or_check(ctx)
    if ctx.can_fold:
        mark(ctx, "preflop_first_in_fold", position=position)
        return Action("fold")
    return call_or_check(ctx)


def _should_call(share: float, ctx: Context, edge: float) -> bool:
    call = ctx.effective_call
    if call <= 0 or not ctx.can_call:
        return False
    # All-in uses raw pot odds. A 0.60 equity floor folded 50% tens into pots
    # that only needed 30%. Protecting a lead is the only place we stay picky.
    extra = edge
    if call >= ctx.your_stack:
        extra = 0.04 if ctx.leads_table and ctx.progress > 0.75 and ctx.lead_margin >= 30 else 0.0
    return share >= ctx.adjusted_pot_odds + extra


def _unknown_call_or_fold(ctx: Context) -> Action:
    cap = max(0, min(6, int(ctx.your_stack * 0.05)))
    if PHASE2_CONFIG.recon_mode:
        cap = max(cap, int(ctx.your_stack * 0.10))
    if ctx.to_call <= cap and ctx.to_call < ctx.your_stack and ctx.can_call:
        return Action("call")
    return Action("fold")


def _opponent_pre_reveal_raise_count(ctx: Context) -> int:
    return sum(
        1
        for action in ctx.raw.get("current_hand_actions") or []
        if isinstance(action, dict)
        and action.get("round") == "pre_reveal"
        and action.get("seat") != ctx.your_seat
        and action.get("action") == "raise"
    )
