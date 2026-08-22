from __future__ import annotations

from showdown.config import CONFIG, PHASE2_CONFIG, PHASE3_CONFIG, RuleConfig
from showdown.models import Action, Context
from showdown.equity import post_reveal_multiway_equity_vs_range
from showdown.strategy.sizing import call_or_check, fraction_of_pot_raise
from showdown.strategy.state import ATTEMPT_STATE
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

    aggressor = _latest_post_reveal_aggressor(ctx)
    aggro = ATTEMPT_STATE.opponent.pre_raise_freq(aggressor)

    if ctx.to_call == 0:
        return _decide_unraised(ctx, adjusted_equity, bluff_enabled, aggro, rule_config)
    return _decide_facing_chips(ctx, aggression_margin, aggro, rule_config, aggressor)


def _decide_unraised(ctx: Context, adjusted_equity: float, bluff_enabled: bool, aggro: float, rule_config: RuleConfig) -> Action:
    multiway_offset = PHASE3_CONFIG.extra_value_equity_per_opponent * max(0, ctx.live_opponent_count - 1)
    value_min = rule_config.value_bet_min_equity + multiway_offset
    if adjusted_equity >= max(value_min + 0.10, 0.74):
        mark(ctx, "strong_value_bet")
        return fraction_of_pot_raise(ctx, rule_config.bet_size_pot_fraction)
    if adjusted_equity >= value_min:
        if ctx.acting_last:
            mark(ctx, "medium_value_bet")
            return fraction_of_pot_raise(ctx, rule_config.bet_size_pot_fraction * 0.6, prefer_call=True)
        # Out of position a check invites the aggressive opponent's bet; the
        # facing-chips logic then decides with their action already on record.
        mark(ctx, "medium_value_check")
        return Action("check")
    if (
        adjusted_equity < CONFIG.low_equity_bluff_threshold
        and bluff_enabled
        and ctx.acting_last
        and aggro < CONFIG.bluff_max_opponent_aggro
    ):
        # Only bluff opponents who have shown they can fold; an opponent who
        # raises most hands calls (or raises) most bets, so bluffing burns chips.
        mark(ctx, "bluff_bet")
        return fraction_of_pot_raise(
            ctx,
            CONFIG.bluff_bet_fraction,
            cap_fraction_of_stack=min(CONFIG.bluff_max_stack_fraction, rule_config.max_commitment_fraction),
            prefer_call=True,
        )
    mark(ctx, "check")
    return Action("check")


def _decide_facing_chips(
    ctx: Context, aggression_margin: float, aggro: float, rule_config: RuleConfig, aggressor: int | None
) -> Action:
    # Width of the opponent's betting range scales with their observed
    # aggression; a raise over our own bet narrows it further.
    raised_over_us = _opponent_raised_post_reveal(ctx)
    range_fraction = CONFIG.bet_range_base + CONFIG.bet_range_aggro_weight * aggro
    if raised_over_us:
        range_fraction *= CONFIG.raise_range_decay
    range_fraction = max(CONFIG.min_range_fraction, min(1.0, range_fraction))

    equity = post_reveal_multiway_equity_vs_range(
        ctx.your_number,
        ctx.community_number or 1,
        ctx.table_rule,
        range_fraction,
        ctx.live_opponent_count,
    )
    risk_fraction = ctx.to_call / max(ctx.your_stack, 1)
    required = ctx.adjusted_pot_odds + aggression_margin + CONFIG.risk_extra_margin * risk_fraction
    detail = dict(
        raised_over_us=raised_over_us,
        live_opponents=ctx.live_opponent_count,
        aggressor_seat=aggressor,
        raise_freq=round(aggro, 3),
        range_fraction=round(range_fraction, 3),
        range_equity=round(equity, 4),
        required_equity=round(required, 4),
        risk_fraction=round(risk_fraction, 4),
    )

    if equity >= 0.90 and ctx.can_call:
        mark(ctx, "nuts_call", **detail)
        return Action("call")

    if ctx.to_call >= ctx.your_stack:
        if equity >= max(required, CONFIG.all_in_equity_threshold) and ctx.can_call:
            mark(ctx, "postflop_allin_call", **detail)
            return Action("call")
        mark(ctx, "postflop_allin_fold", **detail)
        return Action("fold") if ctx.can_fold else call_or_check(ctx)

    # Never raise into a bet or raise. Heads-up Axl and the six-seat table
    # both answer inflation with jams; the extra opponents make that worse.
    if equity >= required and ctx.can_call:
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


def _opponent_raised_post_reveal(ctx: Context) -> bool:
    for action in ctx.raw.get("current_hand_actions") or []:
        if not isinstance(action, dict):
            continue
        if action.get("round") == "post_reveal" and action.get("seat") != ctx.your_seat and action.get("action") == "raise":
            return True
    return False


def _latest_post_reveal_aggressor(ctx: Context) -> int | None:
    for action in reversed(ctx.raw.get("current_hand_actions") or []):
        if (
            isinstance(action, dict)
            and action.get("round") == "post_reveal"
            and action.get("seat") != ctx.your_seat
            and action.get("action") in {"bet", "raise"}
        ):
            return int(action.get("seat", -1))
    return None
