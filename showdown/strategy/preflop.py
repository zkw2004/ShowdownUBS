from __future__ import annotations

from showdown.config import CONFIG
from showdown.models import Action, Context
from showdown.strategy.sizing import call_or_check, raise_action


def decide_preflop(ctx: Context, adjusted_equity: float) -> Action:
    is_button = ctx.your_seat == ctx.button_seat
    if is_button:
        return _decide_button(ctx)
    return _decide_big_blind(ctx, adjusted_equity)


def _decide_button(ctx: Context) -> Action:
    if ctx.to_call <= ctx.big_blind:
        if ctx.your_number >= CONFIG.open_raise_high_min_number:
            return raise_action(ctx, int(round(CONFIG.default_open_raise_to_bb * ctx.big_blind)))
        if ctx.your_number >= CONFIG.open_raise_mid_min_number:
            return raise_action(ctx, int(round(CONFIG.medium_open_raise_to_bb * ctx.big_blind)), prefer_call=True)
        return call_or_check(ctx)

    commit_fraction = ctx.to_call / max(ctx.your_stack, 1)
    if ctx.your_number >= 13 and commit_fraction <= CONFIG.max_preflop_commit_fraction:
        target = max(ctx.min_raise_to or 0, int(round((ctx.my_bet_this_round + ctx.to_call) * CONFIG.preflop_reraise_multiplier)))
        return raise_action(ctx, target)
    if ctx.your_number >= 8 and commit_fraction <= CONFIG.max_preflop_commit_fraction:
        return Action("call") if ctx.can_call else Action("fold")
    if ctx.to_call <= ctx.big_blind and ctx.can_call:
        return Action("call")
    return Action("fold")


def _decide_big_blind(ctx: Context, adjusted_equity: float) -> Action:
    if ctx.to_call == 0:
        if ctx.your_number >= CONFIG.big_blind_iso_raise_min_number:
            return raise_action(ctx, int(round(CONFIG.default_open_raise_to_bb * ctx.big_blind)))
        return Action("check")

    raise_size_bb = (ctx.my_bet_this_round + ctx.to_call) / max(ctx.big_blind, 1)
    commit_fraction = ctx.to_call / max(ctx.your_stack, 1)
    if ctx.your_number >= CONFIG.big_blind_reraise_min_number and commit_fraction <= CONFIG.max_preflop_commit_fraction:
        target = int(round((ctx.my_bet_this_round + ctx.to_call) * CONFIG.preflop_reraise_multiplier))
        return raise_action(ctx, target)
    if ctx.your_number >= CONFIG.big_blind_call_min_number:
        return Action("call") if ctx.can_call else Action("fold")
    if ctx.your_number >= CONFIG.big_blind_defend_min_number and raise_size_bb <= CONFIG.small_preflop_raise_cap_bb:
        return Action("call") if ctx.can_call else Action("fold")
    if adjusted_equity > ctx.adjusted_pot_odds + 0.02 and commit_fraction <= 0.05 and ctx.can_call:
        return Action("call")
    return Action("fold")
