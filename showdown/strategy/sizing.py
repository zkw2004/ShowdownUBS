from __future__ import annotations

from showdown.models import Action, Context


def raise_action(ctx: Context, target_total: int, prefer_call: bool = False) -> Action:
    action_name = "raise" if "raise" in ctx.legal_actions else "bet" if "bet" in ctx.legal_actions else ""
    if not action_name or ctx.min_raise_to is None or ctx.max_raise_to is None:
        return call_or_check(ctx)

    if prefer_call and target_total < ctx.min_raise_to:
        return call_or_check(ctx)

    amount = max(ctx.min_raise_to, min(target_total, ctx.max_raise_to))
    return Action(action=action_name, amount=amount)


def fraction_of_pot_raise(ctx: Context, fraction: float, cap_fraction_of_stack: float | None = None, prefer_call: bool = False) -> Action:
    desired_add = max(ctx.big_blind, int(round(max(ctx.pot, ctx.big_blind) * fraction)))
    if cap_fraction_of_stack is not None:
        desired_add = min(desired_add, int(ctx.your_stack * cap_fraction_of_stack))
    target_total = ctx.my_bet_this_round + desired_add
    return raise_action(ctx, target_total, prefer_call=prefer_call)


def multiple_of_amount_raise(ctx: Context, seen_total: int, multiplier: float, cap_fraction_of_stack: float | None = None) -> Action:
    target_total = int(round(seen_total * multiplier))
    if cap_fraction_of_stack is not None:
        cap_total = ctx.my_bet_this_round + int(ctx.your_stack * cap_fraction_of_stack)
        target_total = min(target_total, cap_total)
    return raise_action(ctx, target_total)


def call_or_check(ctx: Context) -> Action:
    if ctx.can_check:
        return Action("check")
    if ctx.can_call:
        return Action("call")
    return Action("fold")
