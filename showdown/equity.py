from __future__ import annotations

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
