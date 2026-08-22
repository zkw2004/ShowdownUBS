from __future__ import annotations

from showdown.config import CONFIG, PHASE2_CONFIG, PHASE3_CONFIG, RuleConfig
from showdown.equity import (
    post_reveal_equity,
    post_reveal_multiway_equity,
    pre_reveal_equity,
    pre_reveal_multiway_equity,
)
from showdown.evaluator.registry import get_rule
from showdown.models import Action, parse_context
from showdown.strategy.postflop import decide_postflop
from showdown.strategy.preflop import decide_preflop
from showdown.strategy.profiles import profiles_from_window
from showdown.strategy.ranges import infer_ranges, pot_share
from showdown.strategy.state import ATTEMPT_STATE
from showdown.strategy.trace import begin, mark


def decide(body: dict) -> Action:
    ctx = parse_context(body)
    ATTEMPT_STATE.observe(ctx)
    rule = get_rule(ctx.table_rule)
    unknown = rule is None
    rule_config = PHASE2_CONFIG.for_rule(ctx.table_rule, solved=not unknown)
    profiles = dict(ATTEMPT_STATE.seat_profiles)
    if not profiles:
        profiles = profiles_from_window(ctx)
    ranges = {} if unknown else infer_ranges(ctx, profiles)
    if not unknown and ctx.round_name == "post_reveal" and ctx.community_number is not None:
        win, tie, lose = post_reveal_equity(ctx.your_number, ctx.community_number, ctx.table_rule)
    elif not unknown:
        win, tie, lose = pre_reveal_equity(ctx.your_number, ctx.table_rule)
    else:
        win, tie, lose = (0.0, 0.0, 1.0)

    uniform_share = (
        post_reveal_multiway_equity(ctx.your_number, ctx.community_number, ctx.table_rule, ctx.live_opponent_count)
        if not unknown and ctx.round_name == "post_reveal" and ctx.community_number is not None
        else pre_reveal_multiway_equity(ctx.your_number, ctx.table_rule, ctx.live_opponent_count)
        if not unknown
        else 0.0
    )
    share = uniform_share if unknown else pot_share(ctx, ranges)
    percentile = _percentile(ctx, uniform_share, unknown)
    edge = _required_edge(ctx, rule_config)
    bluff_enabled = _bluff_enabled(ctx) and not unknown
    begin(
        ctx,
        rule_known=not unknown,
        win_equity=round(win, 4),
        tie_equity=round(tie, 4),
        adjusted_equity=round(share, 4),
        uniform_share=round(uniform_share, 4),
        percentile=round(percentile, 4),
        call_margin=round(edge, 4),
        bluff_enabled=bluff_enabled,
        max_commitment_fraction=rule_config.max_commitment_fraction,
        phase=ctx.phase,
        live_opponents=ctx.live_opponent_count,
        committed_opponents=len(ranges),
        multiway=ctx.is_multiway,
        leads_table=ctx.leads_table,
        chips_needed_to_lead=ctx.chips_needed_to_lead,
    )

    if ctx.round_name == "post_reveal" and ctx.community_number is not None:
        return decide_postflop(ctx, share, bluff_enabled, edge, rule_config, unknown, profiles, ranges)
    action = decide_preflop(ctx, share, percentile, edge, rule_config, unknown, ranges)
    if "reason" not in ctx.raw.get("_decision_trace", {}):
        mark(ctx, "preflop_policy")
    return action


def _is_phase3(ctx) -> bool:
    return ctx.is_phase3


def _required_edge(ctx, rule_config: RuleConfig) -> float:
    """Extra equity over pot odds. Multiway is already in the pot share, so do not add it again."""
    edge = rule_config.call_equity_margin
    if ctx.your_stack < CONFIG.short_stack_threshold:
        edge += CONFIG.short_stack_tighten
    if ctx.is_phase3:
        target = PHASE3_CONFIG.target_delta
    elif ctx.leg_number is not None:
        target = PHASE2_CONFIG.target_delta
    else:
        target = CONFIG.chase_if_below_delta
    protecting = ctx.progress > 0.75 and ctx.chip_delta >= target + 10 and (not ctx.is_phase3 or (ctx.leads_table and ctx.lead_margin >= 25))
    if protecting:
        edge += CONFIG.protect_lead_tighten
    needs_finish = ctx.chip_delta < target or (ctx.is_phase3 and not ctx.leads_table)
    if ctx.progress > 0.85 and needs_finish:
        edge = max(0.0, edge - CONFIG.chase_loosen)
    # A 4% pad folded amaranth 12 to a 5-chip open. Cheap calls use raw pot odds.
    if ctx.risk_fraction < 0.12 and not protecting:
        edge = 0.0
    return max(0.0, edge)


def _bluff_enabled(ctx) -> bool:
    if ctx.is_phase3:
        target = PHASE3_CONFIG.target_delta
    elif ctx.leg_number is not None:
        target = PHASE2_CONFIG.target_delta
    else:
        target = CONFIG.chase_if_below_delta
    if ctx.progress > 0.75 and ctx.chip_delta >= target + 10 and (not ctx.is_phase3 or ctx.leads_table):
        return False
    return True


def _percentile(ctx, adjusted_equity: float, unknown: bool) -> float:
    if unknown:
        return 0.0
    values: list[float] = []
    for number in range(1, 14):
        if ctx.round_name == "post_reveal" and ctx.community_number is not None:
            value = post_reveal_multiway_equity(number, ctx.community_number, ctx.table_rule, ctx.live_opponent_count)
        else:
            value = pre_reveal_multiway_equity(number, ctx.table_rule, ctx.live_opponent_count)
        values.append(value)
    return sum(value <= adjusted_equity for value in values) / len(values)
