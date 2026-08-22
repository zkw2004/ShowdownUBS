from __future__ import annotations

from dataclasses import dataclass

from showdown.evaluator.base import ShowdownRule
from solver.candidates import Candidate
from solver.extract import Showdown


@dataclass
class SolveResult:
    codename: str
    observations: int
    survivors: list[Candidate]
    eliminated_at: dict[str, int]
    curve: list[int]


def predict_winners(rule: ShowdownRule, observation: Showdown) -> tuple[int, ...]:
    ranks = {seat: rule.rank(number, observation.community) for seat, number in observation.numbers.items()}
    best = max(ranks.values())
    return tuple(sorted(seat for seat, rank in ranks.items() if rank == best))


def solve(codename: str, observations: list[Showdown], candidates: list[Candidate]) -> SolveResult:
    survivors = list(candidates)
    eliminated_at: dict[str, int] = {}
    curve = [len(survivors)]
    for index, observation in enumerate(observations, start=1):
        remaining: list[Candidate] = []
        expected = tuple(sorted(observation.winners))
        for candidate in survivors:
            if predict_winners(candidate.rule, observation) == expected:
                remaining.append(candidate)
            else:
                eliminated_at[candidate.rule_id] = index
        survivors = remaining
        curve.append(len(survivors))
    return SolveResult(codename, len(observations), survivors, eliminated_at, curve)
