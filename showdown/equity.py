from __future__ import annotations

import math
from functools import lru_cache

from showdown.evaluator.base import ShowdownRule
from showdown.evaluator.registry import get_rule


def _outcome(my_rank: tuple[int, int], opponent_rank: tuple[int, int]) -> str:
    if my_rank > opponent_rank:
        return "win"
    if my_rank < opponent_rank:
        return "lose"
    return "tie"


def compute_post_reveal_table(rule: ShowdownRule) -> dict[tuple[int, int], tuple[float, float, float]]:
    table: dict[tuple[int, int], tuple[float, float, float]] = {}
    for my_number in range(1, 14):
        for community in range(1, 14):
            my_rank = rule.rank(my_number, community)
            wins = ties = losses = 0
            for opponent_number in range(1, 14):
                result = _outcome(my_rank, rule.rank(opponent_number, community))
                if result == "win":
                    wins += 1
                elif result == "tie":
                    ties += 1
                else:
                    losses += 1
            table[(my_number, community)] = (wins / 13.0, ties / 13.0, losses / 13.0)
    return table


def compute_pre_reveal_table(rule: ShowdownRule) -> dict[int, tuple[float, float, float]]:
    table: dict[int, tuple[float, float, float]] = {}
    for my_number in range(1, 14):
        wins = ties = losses = 0
        for opponent_number in range(1, 14):
            for community in range(1, 14):
                result = _outcome(rule.rank(my_number, community), rule.rank(opponent_number, community))
                if result == "win":
                    wins += 1
                elif result == "tie":
                    ties += 1
                else:
                    losses += 1
        total = 13.0 * 13.0
        table[my_number] = (wins / total, ties / total, losses / total)
    return table


POST_REVEAL_TABLES = {
    name: compute_post_reveal_table(rule)
    for name, rule in {"standard": get_rule("standard")}.items()
}
PRE_REVEAL_TABLES = {
    name: compute_pre_reveal_table(rule)
    for name, rule in {"standard": get_rule("standard")}.items()
}


def post_reveal_equity(number: int, community: int, table_rule: str = "standard") -> tuple[float, float, float]:
    rule = get_rule(table_rule)
    if rule is None:
        raise KeyError(f"unknown table rule: {table_rule}")
    table = POST_REVEAL_TABLES.setdefault(rule.codename, compute_post_reveal_table(rule))
    return table[(number, community)]


def pre_reveal_equity(number: int, table_rule: str = "standard") -> tuple[float, float, float]:
    rule = get_rule(table_rule)
    if rule is None:
        raise KeyError(f"unknown table rule: {table_rule}")
    table = PRE_REVEAL_TABLES.setdefault(rule.codename, compute_pre_reveal_table(rule))
    return table[number]


def _fraction_to_range_size(fraction: float) -> int:
    return max(1, min(13, math.ceil(13 * fraction)))


def pre_reveal_equity_vs_range(number: int, table_rule: str, fraction: float) -> tuple[float, float, float]:
    """Equity when the opponent holds only the top `fraction` of numbers.

    "Top" is ordered by the number's own pre-reveal strength under the rule, so
    a raiser's range under an inverted ordering is the low numbers, not the high.
    """
    rule = get_rule(table_rule)
    if rule is None:
        raise KeyError(f"unknown table rule: {table_rule}")
    return _pre_equity_vs_top_k(number, rule.codename, _fraction_to_range_size(fraction))


def post_reveal_equity_vs_range(number: int, community: int, table_rule: str, fraction: float) -> tuple[float, float, float]:
    """Equity vs the top `fraction` of opponent numbers given the community."""
    rule = get_rule(table_rule)
    if rule is None:
        raise KeyError(f"unknown table rule: {table_rule}")
    return _post_equity_vs_top_k(number, community, rule.codename, _fraction_to_range_size(fraction))


def multiway_adjusted_equity(single_opponent_equity: tuple[float, float, float], opponents: int) -> float:
    """Expected pot share against `opponents` independent equal ranges.

    A single-opponent tuple gives probabilities of strictly winning, tying, and
    losing.  In a multiway pot we must have no opponent ahead.  When `t`
    opponents tie us, our share is 1 / (t + 1), so this calculates exact
    expected showdown share without enumerating up to 13**5 combinations.
    """
    if opponents <= 0:
        return 1.0
    win, tie, _ = single_opponent_equity
    share = 0.0
    for ties in range(opponents + 1):
        strict_wins = opponents - ties
        share += math.comb(opponents, ties) * (win ** strict_wins) * (tie ** ties) / (ties + 1)
    return share


def pre_reveal_multiway_equity(number: int, table_rule: str, opponents: int) -> float:
    return multiway_adjusted_equity(pre_reveal_equity(number, table_rule), opponents)


def post_reveal_multiway_equity(number: int, community: int, table_rule: str, opponents: int) -> float:
    return multiway_adjusted_equity(post_reveal_equity(number, community, table_rule), opponents)


def pre_reveal_multiway_equity_vs_range(number: int, table_rule: str, fraction: float, opponents: int) -> float:
    return multiway_adjusted_equity(pre_reveal_equity_vs_range(number, table_rule, fraction), opponents)


def post_reveal_multiway_equity_vs_range(
    number: int, community: int, table_rule: str, fraction: float, opponents: int
) -> float:
    return multiway_adjusted_equity(post_reveal_equity_vs_range(number, community, table_rule, fraction), opponents)


@lru_cache(maxsize=8192)
def _pre_equity_vs_top_k(number: int, codename: str, k: int) -> tuple[float, float, float]:
    rule = get_rule(codename)
    strength = {n: (win + tie / 2.0) for n, (win, tie, _) in (
        PRE_REVEAL_TABLES.setdefault(codename, compute_pre_reveal_table(rule)).items()
    )}
    opponents = sorted(range(1, 14), key=lambda n: strength[n], reverse=True)[:k]
    wins = ties = losses = 0
    for opponent in opponents:
        for community in range(1, 14):
            result = _outcome(rule.rank(number, community), rule.rank(opponent, community))
            if result == "win":
                wins += 1
            elif result == "tie":
                ties += 1
            else:
                losses += 1
    total = float(len(opponents) * 13)
    return (wins / total, ties / total, losses / total)


@lru_cache(maxsize=8192)
def _post_equity_vs_top_k(number: int, community: int, codename: str, k: int) -> tuple[float, float, float]:
    rule = get_rule(codename)
    opponents = sorted(range(1, 14), key=lambda n: rule.rank(n, community), reverse=True)[:k]
    my_rank = rule.rank(number, community)
    wins = ties = losses = 0
    for opponent in opponents:
        result = _outcome(my_rank, rule.rank(opponent, community))
        if result == "win":
            wins += 1
        elif result == "tie":
            ties += 1
        else:
            losses += 1
    total = float(len(opponents))
    return (wins / total, ties / total, losses / total)
