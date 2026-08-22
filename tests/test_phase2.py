from showdown.evaluator.generic import FunctionalRule
from showdown.evaluator.standard import StandardRule
from showdown.models import parse_context
from showdown.strategy.decide import decide
from solver.candidates import generate_candidates
from solver.eliminate import solve
from solver.extract import Showdown

from tests.conftest import cloned_request


def _observations(rule):
    observations = []
    for first in range(1, 14):
        for second in range(1, 14):
            for community in range(1, 14):
                ranks = {0: rule.rank(first, community), 1: rule.rank(second, community)}
                best = max(ranks.values())
                observations.append(Showdown("fixture", 1, len(observations) + 1, community, {0: first, 1: second}, tuple(seat for seat, rank in ranks.items() if rank == best)))
    return observations


def test_solver_recovers_standard_from_complete_fixture() -> None:
    result = solve("fixture", _observations(StandardRule()), generate_candidates())
    assert [candidate.rule_id for candidate in result.survivors] == ["standard"]


def test_unknown_rule_uses_safe_legal_fallback() -> None:
    body = cloned_request()
    body["table_rule"] = "unseen-codename"
    body["to_call"] = 30
    body["legal_actions"] = ["fold", "call", "raise"]
    assert decide(body).action == "fold"


def test_context_reads_leg_metadata() -> None:
    body = cloned_request()
    body.update({"leg_number": 2, "total_legs": 4, "match_id": "attempt-a"})
    context = parse_context(body)
    assert (context.leg_number, context.total_legs, context.match_id) == (2, 4, "attempt-a")
