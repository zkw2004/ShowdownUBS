from __future__ import annotations

from showdown.config import CONFIG, PHASE2_CONFIG, RuleConfig
from showdown.models import Action, Context
from showdown.strategy.sizing import call_or_check, fraction_of_pot_raise, multiple_of_amount_raise


def decide_postflop(
    ctx: Context,
    win: float,
    tie: float,
    adjusted_equity: float,
    aggression_margin: float,
    bluff_enabled: bool,
    rule_config: RuleConfig,
    unknown: bool,
) -> Action:
    if unknown:
        return _unknown_action(ctx)

    if ctx.to_call == 0:
        if adjusted_equity >= max(rule_config.value_bet_min_equity + 0.10, 0.74):
            return fraction_of_pot_raise(ctx, rule_config.bet_size_pot_fraction)
        if adjusted_equity >= rule_config.value_bet_min_equity:
            if ctx.acting_last:
                return fraction_of_pot_raise(ctx, rule_config.bet_size_pot_fraction * 0.65, prefer_call=True)
            return Action("check")
        if adjusted_equity < CONFIG.low_equity_bluff_threshold and bluff_enabled and ctx.acting_last:
            return fraction_of_pot_raise(
                ctx,
                CONFIG.bluff_bet_fraction,
                cap_fraction_of_stack=min(CONFIG.bluff_max_stack_fraction, rule_config.max_commitment_fraction),
                prefer_call=True,
            )
        return Action("check")

    if _should_raise_for_value(ctx, adjusted_equity, aggression_margin):
        seen_total = ctx.my_bet_this_round + ctx.to_call
        return multiple_of_amount_raise(ctx, seen_total, CONFIG.value_raise_multiplier, cap_fraction_of_stack=rule_config.max_commitment_fraction)

    if _should_call(ctx, adjusted_equity, aggression_margin):
        return Action("call")
    return Action("fold")


def _unknown_action(ctx: Context) -> Action:
    if ctx.to_call == 0:
        return Action("check")
    cap = max(0, min(6, int(ctx.your_stack * 0.05)))
    if PHASE2_CONFIG.recon_mode:
        cap = max(cap, int(ctx.your_stack * 0.10))
    if ctx.to_call <= cap and ctx.to_call < ctx.your_stack and ctx.can_call:
        return Action("call")
    return Action("fold")


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
