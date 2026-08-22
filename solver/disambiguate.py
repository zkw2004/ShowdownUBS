from __future__ import annotations

from showdown.evaluator.base import ShowdownRule
from solver.eliminate import predict_winners
from solver.extract import Showdown


def distinguishing_cases(a: ShowdownRule, b: ShowdownRule) -> list[tuple[int, int, int]]:
    cases: list[tuple[int, int, int]] = []
    for first in range(1, 14):
        for second in range(1, 14):
            for community in range(1, 14):
                obs = Showdown("comparison", None, 0, community, {0: first, 1: second}, ())
                if predict_winners(a, obs) != predict_winners(b, obs):
                    cases.append((first, second, community))
    return cases
