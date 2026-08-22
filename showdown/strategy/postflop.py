from __future__ import annotations

import math

from showdown.config import CONFIG, PHASE2_CONFIG, PHASE3_CONFIG, RuleConfig
from showdown.models import Action, Context
from showdown.strategy.profiles import SeatProfile
from showdown.strategy.ranges import strength_index
from showdown.strategy.sizing import call_or_check, fraction_of_pot_raise, multiple_of_amount_raise, raise_action
from showdown.strategy.trace import mark


def decide_postflop(
    ctx: Context,
    share: float,
    bluff_enabled: bool,
    edge: float,
    rule_config: RuleConfig,
    unknown: bool,
    profiles: dict[int, SeatProfile],
    ranges: dict[int, tuple[int, ...]],
) -> Action:
    if unknown:
        action = _unknown_action(ctx)
        mark(ctx, "unknown_rule_fallback")
        return action

    if ctx.to_call == 0:
        all_fold_probability = math.prod(
            profiles.get(seat, SeatProfile()).fold_to_bet for seat in ctx.live_opponent_seats
        )
        return _decide_unraised(ctx, share, bluff_enabled, all_fold_probability, rule_config)
    return _decide_facing_chips(ctx, share, edge, ranges)


def _decide_unraised(
    ctx: Context, share: float, bluff_enabled: bool, fold_rate: float, rule_config: RuleConfig
) -> Action:
    value_min = rule_config.value_bet_min_equity
    if ctx.is_multiway:
        value_min += PHASE3_CONFIG.extra_value_equity_per_opponent * max(0, ctx.live_opponent_count - 1)
    if strength_index(ctx) == 0:
        if (
            ctx.is_phase3
            and not ctx.leads_table
            and ctx.progress >= 0.80
            and ctx.chips_needed_to_lead > 0
            and fold_rate < 0.35
        ):
            # In Phase 3, +chips in second place still scores zero. With the
            # literal nuts late, create a pot large enough to take the lead;
            # cap the escalation until the final few hands.
            cap_fraction = 0.35 if ctx.progress < 0.90 else 0.65 if ctx.progress < 0.96 else 1.0
            desired_add = min(
                ctx.your_stack,
                max(ctx.pot, min(ctx.chips_needed_to_lead, int(ctx.your_stack * cap_fraction))),
            )
            mark(ctx, "objective_nuts_bet", fold_probability=round(fold_rate, 4))
            return raise_action(ctx, ctx.my_bet_this_round + desired_add)
        mark(ctx, "nuts_value_bet", fold_probability=round(fold_rate, 4))
        return fraction_of_pot_raise(ctx, _adaptive_value_fraction(rule_config, fold_rate))
    if share >= max(value_min + 0.08, 0.70):
        mark(ctx, "strong_value_bet")
        return fraction_of_pot_raise(ctx, _adaptive_value_fraction(rule_config, fold_rate))
    if share >= value_min or (share >= 0.46 and ctx.acting_last and not ctx.is_multiway):
        if ctx.acting_last or share >= value_min + 0.06:
            mark(ctx, "medium_value_bet")
            return fraction_of_pot_raise(ctx, rule_config.bet_size_pot_fraction * 0.6, prefer_call=True)
        mark(ctx, "medium_value_check")
        return Action("check")
    if (
        share < CONFIG.low_equity_bluff_threshold
        and bluff_enabled
        and ctx.acting_last
        and fold_rate >= 0.42
        and not ctx.is_multiway
    ):
        mark(ctx, "bluff_bet")
        return fraction_of_pot_raise(
            ctx,
            CONFIG.bluff_bet_fraction,
            cap_fraction_of_stack=min(CONFIG.bluff_max_stack_fraction, rule_config.max_commitment_fraction),
            prefer_call=True,
        )
    mark(ctx, "check")
    return Action("check")


def _adaptive_value_fraction(rule_config: RuleConfig, all_fold_probability: float) -> float:
    if all_fold_probability < 0.25:
        return rule_config.bet_size_pot_fraction * 1.25
    if all_fold_probability > 0.55:
        return rule_config.bet_size_pot_fraction * 0.70
    return rule_config.bet_size_pot_fraction


def _decide_facing_chips(ctx: Context, share: float, edge: float, ranges: dict[int, tuple[int, ...]]) -> Action:
    required = ctx.adjusted_pot_odds + edge
    extra = edge
    if ctx.effective_call >= ctx.your_stack:
        extra = 0.04 if ctx.leads_table and ctx.progress > 0.75 and ctx.lead_margin >= 30 else 0.0
        required = ctx.adjusted_pot_odds + extra
    detail = dict(
        live_opponents=ctx.live_opponent_count,
        committed_opponents=len(ranges),
        effective_pot=ctx.effective_pot,
        range_equity=round(share, 4),
        required_equity=round(required, 4),
        risk_fraction=round(ctx.risk_fraction, 4),
        pot_odds=round(ctx.adjusted_pot_odds, 4),
    )

    if strength_index(ctx) == 0 and ctx.can_raise and ctx.effective_call < ctx.your_stack:
        seen_total = ctx.my_bet_this_round + ctx.to_call
        if ctx.is_phase3 and not ctx.leads_table and ctx.progress >= 0.80:
            cap_fraction = 0.35 if ctx.progress < 0.90 else 0.65 if ctx.progress < 0.96 else 1.0
            objective_total = ctx.my_bet_this_round + min(
                ctx.your_stack,
                min(ctx.chips_needed_to_lead, int(ctx.your_stack * cap_fraction)),
            )
            mark(ctx, "objective_nuts_raise", **detail)
            return raise_action(
                ctx,
                max(int(round(seen_total * CONFIG.value_raise_multiplier)), objective_total),
            )
        mark(ctx, "nuts_value_raise", **detail)
        return multiple_of_amount_raise(ctx, seen_total, CONFIG.value_raise_multiplier)

    if share >= 0.70 and ctx.can_call:
        mark(ctx, "nuts_call", **detail)
        return Action("call")

    if share >= ctx.adjusted_pot_odds + extra and ctx.can_call:
        mark(ctx, "pot_odds_call", **detail)
        return Action("call")
    if ctx.can_fold:
        mark(ctx, "pot_odds_fold", **detail)
        return Action("fold")
    return call_or_check(ctx)


def _unknown_action(ctx: Context) -> Action:
    if ctx.to_call == 0:
        return Action("check")
    cap = max(0, min(6, int(ctx.your_stack * 0.05)))
    if PHASE2_CONFIG.recon_mode:
        cap = max(cap, int(ctx.your_stack * 0.10))
    if ctx.to_call <= cap and ctx.to_call < ctx.your_stack and ctx.can_call:
        return Action("call")
    return Action("fold")
