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


def heterogeneous_pot_share(equities: tuple[tuple[float, float, float], ...]) -> float:
    """Expected pot share against opponents who each have their own (win, tie, lose).

    Independence is the same assumption as `multiway_adjusted_equity`, but every
    live opponent can hold a different range. Share is zero whenever anyone is
    ahead; when `t` opponents tie us the pot is split `t + 1` ways.
    """
    n = len(equities)
    if n == 0:
        return 1.0
    share = 0.0
    for mask in range(1 << n):
        probability = 1.0
        ties = 0
        for index, (win, tie, _) in enumerate(equities):
            if mask & (1 << index):
                probability *= tie
                ties += 1
            else:
                probability *= win
        share += probability / (ties + 1)
    return share


def equity_vs_numbers(
    number: int, community: int | None, table_rule: str, numbers: tuple[int, ...]
) -> tuple[float, float, float]:
    """Win/tie/lose against an explicit set of opponent numbers, uniform on the set."""
    if not numbers:
        return (1.0, 0.0, 0.0)
    rule = get_rule(table_rule)
    if rule is None:
        raise KeyError(f"unknown table rule: {table_rule}")
    unique = tuple(sorted(set(int(n) for n in numbers if 1 <= int(n) <= 13)))
    if not unique:
        return (1.0, 0.0, 0.0)
    if community is None:
        return _pre_equity_vs_numbers(number, rule.codename, unique)
    return _post_equity_vs_numbers(number, community, rule.codename, unique)


def pot_share_vs_ranges(
    number: int,
    community: int | None,
    table_rule: str,
    ranges: tuple[tuple[int, ...], ...],
) -> float:
    """Showdown pot share against one range per live opponent."""
    if not ranges:
        return 1.0
    equities = tuple(equity_vs_numbers(number, community, table_rule, opponent) for opponent in ranges)
    return heterogeneous_pot_share(equities)


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


@lru_cache(maxsize=8192)
def _pre_equity_vs_numbers(number: int, codename: str, numbers: tuple[int, ...]) -> tuple[float, float, float]:
    rule = get_rule(codename)
    wins = ties = losses = 0
    for opponent in numbers:
        for community in range(1, 14):
            result = _outcome(rule.rank(number, community), rule.rank(opponent, community))
            if result == "win":
                wins += 1
            elif result == "tie":
                ties += 1
            else:
                losses += 1
    total = float(len(numbers) * 13)
    return (wins / total, ties / total, losses / total)


@lru_cache(maxsize=8192)
def _post_equity_vs_numbers(
    number: int, community: int, codename: str, numbers: tuple[int, ...]
) -> tuple[float, float, float]:
    rule = get_rule(codename)
    my_rank = rule.rank(number, community)
    wins = ties = losses = 0
    for opponent in numbers:
        result = _outcome(my_rank, rule.rank(opponent, community))
        if result == "win":
            wins += 1
        elif result == "tie":
            ties += 1
        else:
            losses += 1
    total = float(len(numbers))
    return (wins / total, ties / total, losses / total)


def ordered_numbers(table_rule: str, community: int | None = None) -> tuple[int, ...]:
    """Numbers 1-13, strongest first, under the active table rule."""
    rule = get_rule(table_rule)
    if rule is None:
        return tuple(range(13, 0, -1))
    if community is None:
        table = PRE_REVEAL_TABLES.setdefault(rule.codename, compute_pre_reveal_table(rule))
        strength = {n: (win + tie / 2.0) for n, (win, tie, _) in table.items()}
        return tuple(sorted(range(1, 14), key=lambda n: strength[n], reverse=True))
    return tuple(sorted(range(1, 14), key=lambda n: rule.rank(n, community), reverse=True))


def top_numbers(table_rule: str, fraction: float, community: int | None = None) -> tuple[int, ...]:
    count = _fraction_to_range_size(fraction)
    return ordered_numbers(table_rule, community)[:count]
