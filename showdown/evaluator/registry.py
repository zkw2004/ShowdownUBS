from __future__ import annotations

from showdown.evaluator.base import ShowdownRule
from showdown.evaluator.standard import StandardRule


RULES: dict[str, ShowdownRule] = {
    "standard": StandardRule(),
}


def get_rule(codename: str) -> ShowdownRule:
    return RULES.get(codename, RULES["standard"])
