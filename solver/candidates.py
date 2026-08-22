from __future__ import annotations

from dataclasses import dataclass

from showdown.evaluator.base import ShowdownRule
from showdown.evaluator.generic import FunctionalRule
from showdown.evaluator.standard import StandardRule


@dataclass(frozen=True)
class Candidate:
    rule_id: str
    description: str
    rule: ShowdownRule


def _candidate(kind: str, description: str, **kwargs: object) -> Candidate:
    parts = [kind] + [f"{key}={value}" for key, value in sorted(kwargs.items())]
    rule_id = ":".join(parts)
    return Candidate(rule_id, description, FunctionalRule(rule_id, rule_id, kind, **kwargs))


def generate_candidates() -> list[Candidate]:
    """Deterministic broad candidate space; all rules use the shared interface."""
    candidates = [Candidate("standard", "Pair beats non-pair; otherwise higher wins", StandardRule())]
    pair_effects = ("win", "lose", "neutral")
    for direction, direction_name in ((1, "higher"), (-1, "lower")):
        for pair in pair_effects:
            if direction == 1 and pair == "win":
                continue  # exactly StandardRule, included above once
            candidates.append(_candidate("ordering", f"{direction_name} wins; pair={pair}", direction=direction, pair_effect=pair))
    partitions = [("parity", 0), ("half", 0), ("prime", 0)]
    partitions += [("multiple", n) for n in range(2, 7)]
    partitions += [("threshold", n) for n in range(2, 14)]
    for primary, parameter in partitions:
        for dominant in (0, 1):
            for direction in (1, -1):
                for pair in pair_effects:
                    candidates.append(_candidate("partition", f"{primary} partition; side {dominant} dominates; {'higher' if direction == 1 else 'lower'} breaks ties; pair={pair}", primary=primary, parameter=parameter, dominant=dominant, direction=direction, pair_effect=pair))
    for primary in ("closest", "furthest", "above", "below", "wrapped"):
        for direction in (1, -1):
            for pair in pair_effects:
                candidates.append(_candidate("community", f"community-relative {primary}; pair={pair}", primary=primary, direction=direction, pair_effect=pair))
    for primary in ("sum_mod", "product_mod", "xor", "distance"):
        for direction in (1, -1):
            for pair in pair_effects:
                candidates.append(_candidate("arithmetic", f"{primary}; {'higher' if direction == 1 else 'lower'} wins; pair={pair}", primary=primary, direction=direction, pair_effect=pair))
    for wild in range(1, 14):
        for dominant in (0, 2):
            for direction in (1, -1):
                candidates.append(_candidate("wild", f"{wild} is {'always strong' if dominant == 2 else 'always weak'}", parameter=wild, dominant=dominant, direction=direction, pair_effect="neutral"))
    # Parameterised families intentionally overlap.  Keep one representative for
    # each observable truth table so "standard" can be a unique solve rather
    # than competing with aliases such as a monotone high-half partition.
    unique: list[Candidate] = []
    signatures: set[tuple[int, ...]] = set()
    for candidate in candidates:
        signature = tuple(
            (candidate.rule.rank(first, community) > candidate.rule.rank(second, community))
            - (candidate.rule.rank(first, community) < candidate.rule.rank(second, community))
            for community in range(1, 14)
            for first in range(1, 14)
            for second in range(1, 14)
        )
        if signature not in signatures:
            signatures.add(signature)
            unique.append(candidate)
    return unique
