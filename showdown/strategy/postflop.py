from __future__ import annotations

from showdown.config import CONFIG, PHASE2_CONFIG, RuleConfig
from showdown.models import Action, Context
from showdown.strategy.sizing import fraction_of_pot_raise
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

    # Pair / best unpaired number: never fold, and never turn a call into a
    # raising war.  Live logs showed the bot raising 12s to 52, folding the
    # jam, then later folding actual pairs once the 15%-of-stack cap fired
    # on a short stack.  That is how legs 1/3/4 dumped 50-150 chips.
    is_nuts = adjusted_equity >= 0.92
    if ctx.to_call > 0 and is_nuts and ctx.can_call:
        mark(ctx, "nuts_call")
        return Action("call")

    # Only a true jam is a "risk cap".  Measuring against current stack made
    # every 15-chip bet uncallable after one lost pot, which is how a 12
    # kept folding its way from -50 to -147.
    risk_fraction = ctx.to_call / max(ctx.your_stack, 1)
    if ctx.to_call > 0 and risk_fraction > 0.40 and ctx.can_fold:
        mark(ctx, "risk_cap_fold", risk_fraction=round(risk_fraction, 4))
        return Action("fold")

    # Facing a post-reveal bet or raise: call or fold, never raise.  Axl
    # answers raises with 100+ chip jams; inflating then folding is the
    # single leak that lost Hand 1 of the scored attempt.
    if ctx.to_call > 0:
        if _should_call(ctx, adjusted_equity, aggression_margin):
            mark(ctx, "pot_odds_call" if not _opponent_raised_post_reveal(ctx) else "opponent_raise_value_call")
            return Action("call")
        mark(ctx, "pot_odds_fold" if not _opponent_raised_post_reveal(ctx) else "opponent_raise_fold")
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


def _should_call(ctx: Context, adjusted_equity: float, aggression_margin: float) -> bool:
    required = ctx.adjusted_pot_odds + aggression_margin
    if ctx.to_call >= ctx.your_stack:
        if adjusted_equity >= CONFIG.all_in_equity_threshold:
            return True
        return adjusted_equity >= required and ctx.adjusted_pot_odds < CONFIG.all_in_pot_odds_threshold
    return adjusted_equity >= required
