from __future__ import annotations

from showdown.config import CONFIG
from showdown.equity import post_reveal_equity, pre_reveal_equity
from showdown.models import Action, parse_context
from showdown.strategy.postflop import decide_postflop
from showdown.strategy.preflop import decide_preflop


def decide(body: dict) -> Action:
    ctx = parse_context(body)
    if ctx.round_name == "post_reveal" and ctx.community_number is not None:
        win, tie, lose = post_reveal_equity(ctx.your_number, ctx.community_number, ctx.table_rule)
    else:
        win, tie, lose = pre_reveal_equity(ctx.your_number, ctx.table_rule)

    adjusted_equity = win + (tie / 2.0)
    aggression_margin = _effective_call_margin(ctx)
    bluff_enabled = _bluff_enabled(ctx)

    if ctx.round_name == "post_reveal" and ctx.community_number is not None:
        return decide_postflop(ctx, win, tie, adjusted_equity, aggression_margin, bluff_enabled)
    return decide_preflop(ctx, adjusted_equity)


def _effective_call_margin(ctx) -> float:
    margin = CONFIG.call_equity_margin
    if ctx.your_stack < CONFIG.short_stack_threshold:
        margin += CONFIG.short_stack_tighten
    if ctx.hand_number > CONFIG.protect_lead_after_hand and ctx.chip_delta > CONFIG.protect_lead_chip_delta:
        margin += CONFIG.protect_lead_tighten
    if ctx.hand_number > CONFIG.chase_after_hand and ctx.chip_delta < CONFIG.chase_if_below_delta:
        margin -= CONFIG.chase_loosen
    return max(0.0, margin)


def _bluff_enabled(ctx) -> bool:
    if ctx.hand_number > CONFIG.protect_lead_after_hand and ctx.chip_delta > CONFIG.protect_lead_chip_delta:
        return False
    return True
