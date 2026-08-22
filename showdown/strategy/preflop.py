from __future__ import annotations

from showdown.config import CONFIG, PHASE2_CONFIG, RuleConfig
from showdown.equity import pre_reveal_multiway_equity_vs_range
from showdown.models import Action, Context
from showdown.strategy.sizing import call_or_check, multiple_of_amount_raise, raise_action
from showdown.strategy.state import ATTEMPT_STATE
from showdown.strategy.trace import mark


def decide_preflop(ctx: Context, adjusted_equity: float, percentile: float, rule_config: RuleConfig, unknown: bool) -> Action:
    opponent_raises = _opponent_pre_reveal_raise_count(ctx)
    if ctx.to_call > 0 and opponent_raises:
        if unknown:
            return _unknown_call_or_fold(ctx)
        return _respond_to_raise(ctx, opponent_raises, rule_config)

    if unknown:
        if ctx.to_call == 0:
            return Action("check")
        return _unknown_call_or_fold(ctx)

    return _decide_first_in(ctx, percentile, rule_config)


def _respond_to_raise(ctx: Context, opponent_raises: int, rule_config: RuleConfig) -> Action:
    # Estimate the raiser's range from their observed raise frequency instead
    # of assuming strength: an opponent who raises most hands has a range close
    # to uniform, and folding medium numbers to them forfeits the pot odds.
    aggressor = _latest_pre_reveal_raiser(ctx)
    freq = ATTEMPT_STATE.opponent.pre_raise_freq(aggressor)
    range_fraction = max(
        CONFIG.min_range_fraction,
        freq * (CONFIG.raise_range_decay ** (opponent_raises - 1)),
    )
    equity = pre_reveal_multiway_equity_vs_range(
        ctx.your_number, ctx.table_rule, range_fraction, ctx.live_opponent_count
    )
    risk_fraction = ctx.to_call / max(ctx.your_stack, 1)
    required = ctx.adjusted_pot_odds + rule_config.call_equity_margin + CONFIG.risk_extra_margin * risk_fraction
    detail = dict(
        opponent_raises=opponent_raises,
        live_opponents=ctx.live_opponent_count,
        aggressor_seat=aggressor,
        raise_freq=round(freq, 3),
        range_fraction=round(range_fraction, 3),
        range_equity=round(equity, 4),
        required_equity=round(required, 4),
        risk_fraction=round(risk_fraction, 4),
    )

    if ctx.to_call >= ctx.your_stack:
        if equity >= max(required, CONFIG.all_in_equity_threshold) and ctx.can_call:
            mark(ctx, "preflop_allin_call", **detail)
            return Action("call")
        mark(ctx, "preflop_allin_fold", **detail)
        return Action("fold") if ctx.can_fold else call_or_check(ctx)

    if equity >= CONFIG.preflop_value_reraise_equity and ctx.can_raise:
        # Multiway 3-bets have to get through every remaining seat. Only
        # isolate when heads-up, or when the number is effectively the nuts.
        if ctx.live_opponent_count <= 1 or equity >= 0.90:
            mark(ctx, "preflop_value_reraise", **detail)
            return multiple_of_amount_raise(
                ctx,
                ctx.my_bet_this_round + ctx.to_call,
                CONFIG.preflop_reraise_multiplier,
                cap_fraction_of_stack=rule_config.max_commitment_fraction,
            )
    if equity >= required and ctx.can_call:
        mark(ctx, "preflop_raise_call", **detail)
        return Action("call")
    if ctx.can_fold:
        mark(ctx, "preflop_raise_fold", **detail)
        return Action("fold")
    return call_or_check(ctx)


def _decide_first_in(ctx: Context, percentile: float, rule_config: RuleConfig) -> Action:
    """Open, complete, or fold when nobody has raised.

    v1 routed every non-button seat through the raise-defence path, so UTG/MP/CO
    treated the posted blinds as a raise and folded playable numbers. That is
    why a six-seat bot only ever printed chips from the button.
    """
    position = _position_name(ctx)
    if ctx.to_call == 0:
        if percentile >= rule_config.open_raise_min_percentile + 0.15:
            mark(ctx, "preflop_bb_iso", position=position)
            return raise_action(ctx, int(round(CONFIG.default_open_raise_to_bb * ctx.big_blind)))
        return Action("check")

    open_need = {
        "ep": rule_config.open_raise_min_percentile + 0.20,
        "mp": rule_config.open_raise_min_percentile + 0.10,
        "co": rule_config.open_raise_min_percentile,
        "btn": rule_config.open_raise_min_percentile,
        "sb": rule_config.open_raise_min_percentile + 0.08,
        "bb": rule_config.open_raise_min_percentile + 0.15,
    }[position]
    if percentile >= open_need + 0.20:
        mark(ctx, "preflop_open_raise", position=position)
        return raise_action(ctx, int(round(CONFIG.default_open_raise_to_bb * ctx.big_blind)))
    if percentile >= open_need:
        mark(ctx, "preflop_open_raise", position=position)
        return raise_action(ctx, int(round(CONFIG.medium_open_raise_to_bb * ctx.big_blind)), prefer_call=True)
    if percentile <= CONFIG.button_complete_min_percentile and ctx.can_fold:
        mark(ctx, "preflop_first_in_fold", position=position)
        return Action("fold")
    if position in {"btn", "sb", "co"} or ctx.to_call <= ctx.big_blind:
        mark(ctx, "preflop_complete", position=position)
        return call_or_check(ctx)
    if ctx.can_fold:
        mark(ctx, "preflop_first_in_fold", position=position)
        return Action("fold")
    return call_or_check(ctx)


def _position_name(ctx: Context) -> str:
    seats = sorted(
        int(player.get("seat", -1))
        for player in (ctx.raw.get("players") or [])
        if not bool(player.get("busted", False)) and int(player.get("seat", -1)) >= 0
    )
    if len(seats) <= 2:
        return "btn" if ctx.your_seat == ctx.button_seat else "bb"
    if ctx.button_seat not in seats or ctx.your_seat not in seats:
        return "mp"
    offset = (seats.index(ctx.your_seat) - seats.index(ctx.button_seat)) % len(seats)
    if offset == 0:
        return "btn"
    if offset == 1:
        return "sb"
    if offset == 2:
        return "bb"
    from_utg = offset - 3
    late = len(seats) - 3
    if from_utg <= 0:
        return "ep"
    if from_utg >= late - 1:
        return "co"
    return "mp"


def _unknown_call_or_fold(ctx: Context) -> Action:
    cap = max(0, min(6, int(ctx.your_stack * 0.05)))
    if PHASE2_CONFIG.recon_mode:
        cap = max(cap, int(ctx.your_stack * 0.10))
    if ctx.to_call <= cap and ctx.to_call < ctx.your_stack and ctx.can_call:
        return Action("call")
    return Action("fold")


def _opponent_pre_reveal_raise_count(ctx: Context) -> int:
    return sum(
        1
        for action in ctx.raw.get("current_hand_actions") or []
        if isinstance(action, dict)
        and action.get("round") == "pre_reveal"
        and action.get("seat") != ctx.your_seat
        and action.get("action") == "raise"
    )


def _latest_pre_reveal_raiser(ctx: Context) -> int | None:
    for action in reversed(ctx.raw.get("current_hand_actions") or []):
        if (
            isinstance(action, dict)
            and action.get("round") == "pre_reveal"
            and action.get("seat") != ctx.your_seat
            and action.get("action") == "raise"
        ):
            return int(action.get("seat", -1))
    return None
