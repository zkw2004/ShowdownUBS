from __future__ import annotations

from showdown.config import CONFIG
from showdown.models import Action, Context
from showdown.strategy.sizing import call_or_check, fraction_of_pot_raise, multiple_of_amount_raise


def decide_postflop(ctx: Context, win: float, tie: float, adjusted_equity: float, aggression_margin: float, bluff_enabled: bool) -> Action:
    is_pair = ctx.community_number is not None and ctx.your_number == ctx.community_number
    if is_pair:
        return _play_pair(ctx)

    if ctx.to_call == 0:
        if adjusted_equity >= CONFIG.high_value_equity:
            return fraction_of_pot_raise(ctx, CONFIG.strong_value_bet_fraction)
        if adjusted_equity >= CONFIG.medium_value_equity:
            if ctx.acting_last:
                return fraction_of_pot_raise(ctx, CONFIG.medium_value_bet_fraction, prefer_call=True)
            return Action("check")
        if adjusted_equity < CONFIG.low_equity_bluff_threshold and bluff_enabled and ctx.acting_last:
            return fraction_of_pot_raise(
                ctx,
                CONFIG.bluff_bet_fraction,
                cap_fraction_of_stack=CONFIG.bluff_max_stack_fraction,
                prefer_call=True,
            )
        return Action("check")

    if _should_raise_for_value(ctx, adjusted_equity, aggression_margin):
        seen_total = ctx.my_bet_this_round + ctx.to_call
        return multiple_of_amount_raise(ctx, seen_total, CONFIG.value_raise_multiplier, cap_fraction_of_stack=CONFIG.max_normal_commit_fraction)

    if _should_call(ctx, adjusted_equity, aggression_margin):
        return Action("call")
    return Action("fold")


def _play_pair(ctx: Context) -> Action:
    if ctx.to_call == 0:
        return fraction_of_pot_raise(ctx, CONFIG.pair_bet_fraction)
    seen_total = ctx.my_bet_this_round + ctx.to_call
    return multiple_of_amount_raise(ctx, seen_total, CONFIG.pair_raise_multiplier)


def _should_raise_for_value(ctx: Context, adjusted_equity: float, aggression_margin: float) -> bool:
    if not ctx.can_raise:
        return False
    return adjusted_equity > ctx.adjusted_pot_odds + aggression_margin and adjusted_equity >= CONFIG.strong_raise_equity


def _should_call(ctx: Context, adjusted_equity: float, aggression_margin: float) -> bool:
    required = ctx.adjusted_pot_odds + aggression_margin
    if ctx.to_call >= ctx.your_stack:
        if adjusted_equity >= CONFIG.all_in_equity_threshold:
            return True
        return adjusted_equity >= required and ctx.adjusted_pot_odds < CONFIG.all_in_pot_odds_threshold
    return adjusted_equity >= required
