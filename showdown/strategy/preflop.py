from __future__ import annotations

from showdown.config import PHASE2_CONFIG, RuleConfig
from showdown.models import Action, Context
from showdown.strategy.sizing import call_or_check, raise_action
from showdown.strategy.trace import mark


def decide_preflop(ctx: Context, adjusted_equity: float, percentile: float, rule_config: RuleConfig, unknown: bool) -> Action:
    # The opponent's repeated pre-reveal raises identify a much stronger range
    # than the uniform opponent used by our equity table.  Never let an open
    # raise turn into a stack-threatening pre-reveal guessing contest.
    risk_fraction = ctx.to_call / max(ctx.your_stack, 1)
    if ctx.to_call > 0 and risk_fraction > 0.12 and ctx.can_fold:
        mark(ctx, "preflop_risk_cap_fold", risk_fraction=round(risk_fraction, 4))
        return Action("fold")
    if _opponent_raised_pre_reveal(ctx):
        if risk_fraction <= 0.04 and adjusted_equity >= 0.55 and ctx.can_call:
            mark(ctx, "preflop_raise_cheap_call", risk_fraction=round(risk_fraction, 4))
            return Action("call")
        mark(ctx, "preflop_raise_fold", risk_fraction=round(risk_fraction, 4))
        return Action("fold")

    is_button = ctx.your_seat == ctx.button_seat
    if is_button:
        return _decide_button(ctx, adjusted_equity, percentile, rule_config, unknown)
    return _decide_big_blind(ctx, adjusted_equity, percentile, rule_config, unknown)


def _decide_button(ctx: Context, adjusted_equity: float, percentile: float, rule_config: RuleConfig, unknown: bool) -> Action:
    if ctx.to_call <= ctx.big_blind:
        if not unknown and percentile >= rule_config.open_raise_min_percentile + 0.20:
            return raise_action(ctx, int(round(3.0 * ctx.big_blind)))
        if not unknown and percentile >= rule_config.open_raise_min_percentile:
            return raise_action(ctx, int(round(2.5 * ctx.big_blind)), prefer_call=True)
        return call_or_check(ctx)

    commit_fraction = ctx.to_call / max(ctx.your_stack, 1)
    if unknown:
        return _unknown_call_or_fold(ctx)
    if percentile >= 0.92 and commit_fraction <= rule_config.max_commitment_fraction:
        target = max(ctx.min_raise_to or 0, int(round((ctx.my_bet_this_round + ctx.to_call) * 2.5)))
        return raise_action(ctx, target)
    if percentile >= rule_config.open_raise_min_percentile and commit_fraction <= rule_config.max_commitment_fraction:
        return Action("call") if ctx.can_call else Action("fold")
    if ctx.to_call <= ctx.big_blind and ctx.can_call:
        return Action("call")
    return Action("fold")


def _decide_big_blind(ctx: Context, adjusted_equity: float, percentile: float, rule_config: RuleConfig, unknown: bool) -> Action:
    if ctx.to_call == 0:
        if not unknown and percentile >= rule_config.open_raise_min_percentile + 0.15:
            return raise_action(ctx, int(round(3.0 * ctx.big_blind)))
        return Action("check")

    raise_size_bb = (ctx.my_bet_this_round + ctx.to_call) / max(ctx.big_blind, 1)
    commit_fraction = ctx.to_call / max(ctx.your_stack, 1)
    if unknown:
        return _unknown_call_or_fold(ctx)
    if percentile >= 0.95 and commit_fraction <= rule_config.max_commitment_fraction:
        target = int(round((ctx.my_bet_this_round + ctx.to_call) * 2.5))
        return raise_action(ctx, target)
    if percentile >= rule_config.open_raise_min_percentile:
        return Action("call") if ctx.can_call else Action("fold")
    if percentile >= 0.30 and raise_size_bb <= 4.0:
        return Action("call") if ctx.can_call else Action("fold")
    if adjusted_equity > ctx.adjusted_pot_odds + 0.02 and commit_fraction <= 0.05 and ctx.can_call:
        return Action("call")
    return Action("fold")


def _unknown_call_or_fold(ctx: Context) -> Action:
    cap = max(0, min(6, int(ctx.your_stack * 0.05)))
    if PHASE2_CONFIG.recon_mode:
        cap = max(cap, int(ctx.your_stack * 0.10))
    if ctx.to_call <= cap and ctx.to_call < ctx.your_stack and ctx.can_call:
        return Action("call")
    return Action("fold")


def _opponent_raised_pre_reveal(ctx: Context) -> bool:
    for action in ctx.raw.get("current_hand_actions") or []:
        if not isinstance(action, dict):
            continue
        if action.get("round") == "pre_reveal" and action.get("seat") != ctx.your_seat and action.get("action") == "raise":
            return True
    return False
