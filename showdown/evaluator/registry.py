from __future__ import annotations

from showdown.evaluator.base import ShowdownRule
from showdown.evaluator.generic import rule_from_id
from showdown.evaluator.standard import StandardRule

import json
from pathlib import Path


RULES: dict[str, ShowdownRule] = {
    "standard": StandardRule(),
}


def _load_solved_rules() -> None:
    path = Path(__file__).resolve().parents[2] / "data" / "solved_rules.json"
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text())
        for codename, entry in payload.get("rules", {}).items():
            if entry.get("status") == "solved" and entry.get("rule_id"):
                RULES[codename] = rule_from_id(entry["rule_id"], codename)
    except (OSError, ValueError, TypeError):
        # A malformed optional registry must not take the live endpoint down.
        return


_load_solved_rules()


def get_rule(codename: str) -> ShowdownRule | None:
    """Return None for an unknown codename; never guess standard in Phase 2."""
    return RULES.get(codename)


def register_rule(codename: str, rule: ShowdownRule) -> None:
    RULES[codename] = rule
