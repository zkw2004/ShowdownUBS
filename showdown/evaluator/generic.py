from __future__ import annotations

from dataclasses import dataclass
from math import gcd


@dataclass(frozen=True)
class FunctionalRule:
    """A serialisable family of rules used by the solver and registry."""

    codename: str
    rule_id: str
    kind: str
    primary: str = "number"
    direction: int = 1
    pair_effect: str = "win"
    dominant: int = 1
    parameter: int = 0

    def rank(self, number: int, community: int | None) -> tuple[int, ...]:
        pair = community is not None and number == community
        pair_rank = {"win": 1 if pair else 0, "lose": 0 if pair else 1, "neutral": 0}[self.pair_effect]
        if self.kind == "standard":
            return (pair_rank, 0 if pair and self.pair_effect == "win" else number)
        if self.kind == "ordering":
            return (pair_rank, self.direction * number)
        if self.kind == "partition":
            value = _partition_value(self.primary, number, self.parameter)
            return (pair_rank, int(value == self.dominant), self.direction * number)
        if self.kind == "community":
            if community is None:
                return (pair_rank, self.direction * number)
            distance = abs(number - community)
            if self.primary == "closest":
                value = -distance
            elif self.primary == "furthest":
                value = distance
            elif self.primary == "above":
                value = int(number >= community)
            elif self.primary == "below":
                value = int(number <= community)
            else:  # wrapped circular distance
                value = -min(distance, 13 - distance)
            return (pair_rank, value, self.direction * number)
        if self.kind == "arithmetic":
            if community is None:
                return (pair_rank, self.direction * number)
            if self.primary == "sum_mod":
                value = (number + community) % 13
            elif self.primary == "product_mod":
                value = (number * community) % 13
            elif self.primary == "xor":
                value = number ^ community
            else:
                value = abs(number - community)
            return (pair_rank, self.direction * value, self.direction * number)
        if self.kind == "wild":
            if number == self.parameter:
                return (pair_rank, self.dominant, 0)
            return (pair_rank, 1 - self.dominant, self.direction * number)
        raise ValueError(f"unknown rule kind: {self.kind}")


def _partition_value(primary: str, number: int, parameter: int) -> int:
    if primary == "parity":
        return number % 2
    if primary == "half":
        return int(number > 6)
    if primary == "prime":
        return int(number in {2, 3, 5, 7, 11, 13})
    if primary == "multiple":
        return int(parameter > 0 and number % parameter == 0)
    if primary == "threshold":
        return int(number >= parameter)
    if primary == "coprime":
        return int(parameter > 0 and gcd(number, parameter) == 1)
    raise ValueError(f"unknown partition: {primary}")


def rule_from_id(rule_id: str, codename: str | None = None) -> FunctionalRule:
    """Rebuild a deterministic solver candidate from its stable identifier."""
    parts = rule_id.split(":")
    kind = parts[0]
    if kind == "standard":
        return FunctionalRule(codename or "standard", rule_id, "standard")
    values = {part.split("=", 1)[0]: part.split("=", 1)[1] for part in parts[1:] if "=" in part}
    return FunctionalRule(
        codename=codename or rule_id,
        rule_id=rule_id,
        kind=kind,
        primary=values.get("primary", "number"),
        direction=int(values.get("direction", "1")),
        pair_effect=values.get("pair_effect", values.get("pair", "win")),
        dominant=int(values.get("dominant", "1")),
        parameter=int(values.get("parameter", "0")),
    )
