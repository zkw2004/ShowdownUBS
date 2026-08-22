from __future__ import annotations

from showdown.config import CONFIG, PHASE2_CONFIG, RuleConfig
from showdown.equity import post_reveal_equity, pre_reveal_equity
from showdown.evaluator.registry import get_rule
from showdown.models import Action, parse_context
from showdown.strategy.postflop import decide_postflop
from showdown.strategy.preflop import decide_preflop
from showdown.strategy.state import ATTEMPT_STATE
from showdown.strategy.trace import begin, mark


def decide(body: dict) -> Action:
    ctx = parse_context(body)
    ATTEMPT_STATE.observe(ctx)
    rule = get_rule(ctx.table_rule)
    unknown = rule is None
    rule_config = PHASE2_CONFIG.for_rule(ctx.table_rule, solved=not unknown)
    if not unknown and ctx.round_name == "post_reveal" and ctx.community_number is not None:
        win, tie, lose = post_reveal_equity(ctx.your_number, ctx.community_number, ctx.table_rule)
    elif not unknown:
        win, tie, lose = pre_reveal_equity(ctx.your_number, ctx.table_rule)
    else:
        win, tie, lose = (0.0, 0.0, 1.0)

    adjusted_equity = win + (tie / 2.0)
    percentile = _percentile(ctx, adjusted_equity, unknown)
    aggression_margin = _effective_call_margin(ctx, rule_config)
    bluff_enabled = _bluff_enabled(ctx) and not unknown
    begin(
        ctx,
        rule_known=not unknown,
        win_equity=round(win, 4),
        tie_equity=round(tie, 4),
        adjusted_equity=round(adjusted_equity, 4),
        percentile=round(percentile, 4),
        call_margin=round(aggression_margin, 4),
        bluff_enabled=bluff_enabled,
        max_commitment_fraction=rule_config.max_commitment_fraction,
    )

    if ctx.round_name == "post_reveal" and ctx.community_number is not None:
        return decide_postflop(ctx, win, tie, adjusted_equity, aggression_margin, bluff_enabled, rule_config, unknown)
    action = decide_preflop(ctx, adjusted_equity, percentile, rule_config, unknown)
    if "reason" not in ctx.raw.get("_decision_trace", {}):
        mark(ctx, "preflop_policy")
    return action


def _effective_call_margin(ctx, rule_config: RuleConfig) -> float:
    margin = rule_config.call_equity_margin
    if ctx.your_stack < CONFIG.short_stack_threshold:
        margin += CONFIG.short_stack_tighten
    hands = ctx.total_hands or PHASE2_CONFIG.hands_per_leg
    target = PHASE2_CONFIG.target_delta if ctx.leg_number is not None else CONFIG.chase_if_below_delta
    if ctx.hand_number / hands > 0.75 and ctx.chip_delta >= target + 10:
        margin += CONFIG.protect_lead_tighten
    if ctx.hand_number / hands > 0.85 and ctx.chip_delta < target and ctx.your_stack > target - ctx.chip_delta:
        margin -= CONFIG.chase_loosen
    return max(0.0, margin)


def _bluff_enabled(ctx) -> bool:
    hands = ctx.total_hands or PHASE2_CONFIG.hands_per_leg
    target = PHASE2_CONFIG.target_delta if ctx.leg_number is not None else CONFIG.chase_if_below_delta
    if ctx.hand_number / hands > 0.75 and ctx.chip_delta >= target + 10:
        return False
    return True


def _percentile(ctx, adjusted_equity: float, unknown: bool) -> float:
    if unknown:
        return 0.0
    values: list[float] = []
    for number in range(1, 14):
        if ctx.round_name == "post_reveal" and ctx.community_number is not None:
            win, tie, _ = post_reveal_equity(number, ctx.community_number, ctx.table_rule)
        else:
            win, tie, _ = pre_reveal_equity(number, ctx.table_rule)
        values.append(win + tie / 2.0)
    return sum(value <= adjusted_equity for value in values) / len(values)
