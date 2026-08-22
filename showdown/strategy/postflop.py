from __future__ import annotations

from showdown.config import CONFIG, PHASE2_CONFIG, RuleConfig
from showdown.models import Action, Context
from showdown.strategy.sizing import call_or_check, fraction_of_pot_raise, multiple_of_amount_raise
from showdown.strategy.trace import mark


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
        action = _unknown_action(ctx)
        mark(ctx, "unknown_rule_fallback")
        return action

    # A large re-raise from the rule-aware opponent is much stronger evidence
    # than our unconditional equity against a random number.  Phase 2 awards
    # points per leg, so turning a value hand into a 200-chip bust is worse
    # than releasing it and preserving the remaining hands.  This is a hard
    # risk cap: no post-reveal call or re-raise may risk over 15% of stack.
    if (
        ctx.to_call > 0
        and ctx.to_call / max(ctx.your_stack, 1) > 0.15
        and ctx.can_fold
    ):
        mark(ctx, "risk_cap_fold", risk_fraction=round(ctx.to_call / max(ctx.your_stack, 1), 4))
        return Action("fold")

    # Do not turn a normal value bet into a raising war.  The opponent knows
    # the table rule, while our equity is calculated against an unconditioned
    # random number.  After their post-reveal raise, preserve showdown value
    # with a cheap call or release the hand; never make the second re-raise.
    if _opponent_raised_post_reveal(ctx):
        if ctx.to_call / max(ctx.your_stack, 1) <= 0.08 and ctx.can_call:
            mark(ctx, "opponent_raise_cheap_call", risk_fraction=round(ctx.to_call / max(ctx.your_stack, 1), 4))
            return Action("call")
        mark(ctx, "opponent_raise_fold", risk_fraction=round(ctx.to_call / max(ctx.your_stack, 1), 4))
        return Action("fold")

    if ctx.to_call == 0:
        if adjusted_equity >= max(rule_config.value_bet_min_equity + 0.10, 0.74):
            mark(ctx, "strong_value_bet")
            return fraction_of_pot_raise(ctx, rule_config.bet_size_pot_fraction)
        if adjusted_equity >= rule_config.value_bet_min_equity:
            if ctx.acting_last:
                mark(ctx, "medium_value_bet")
                return fraction_of_pot_raise(ctx, rule_config.bet_size_pot_fraction * 0.65, prefer_call=True)
            mark(ctx, "medium_value_check")
            return Action("check")
        if adjusted_equity < CONFIG.low_equity_bluff_threshold and bluff_enabled and ctx.acting_last:
            mark(ctx, "bluff_bet")
            return fraction_of_pot_raise(
                ctx,
                CONFIG.bluff_bet_fraction,
                cap_fraction_of_stack=min(CONFIG.bluff_max_stack_fraction, rule_config.max_commitment_fraction),
                prefer_call=True,
            )
        mark(ctx, "check")
        return Action("check")

    if _should_raise_for_value(ctx, adjusted_equity, aggression_margin):
        seen_total = ctx.my_bet_this_round + ctx.to_call
        mark(ctx, "value_raise")
        return multiple_of_amount_raise(ctx, seen_total, CONFIG.value_raise_multiplier, cap_fraction_of_stack=rule_config.max_commitment_fraction)

    if _should_call(ctx, adjusted_equity, aggression_margin):
        mark(ctx, "pot_odds_call")
        return Action("call")
    mark(ctx, "pot_odds_fold")
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


def _opponent_raised_post_reveal(ctx: Context) -> bool:
    for action in ctx.raw.get("current_hand_actions") or []:
        if not isinstance(action, dict):
            continue
        if action.get("round") == "post_reveal" and action.get("seat") != ctx.your_seat and action.get("action") == "raise":
            return True
    return False


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
