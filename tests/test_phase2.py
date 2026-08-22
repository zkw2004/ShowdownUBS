from showdown.evaluator.generic import FunctionalRule
from showdown.evaluator.standard import StandardRule
from showdown.models import parse_context
from showdown.strategy.decide import decide
from solver.candidates import generate_candidates
from solver.eliminate import solve
from solver.extract import Showdown
from solver.extract import extract

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


def test_extract_reads_phase2_leg_log_schema() -> None:
    match = {
        "legs": [{"rule_id": "obsidian", "result": {"hand_logs": [{
            "hand_number": 1,
            "community_number": 4,
            "shown_numbers": {"0": 2, "1": 7},
            "winners": [1],
            "actions": [{"action": "check"}],
        }]}}]
    }
    assert extract(match) == [Showdown("obsidian", 1, 1, 4, {0: 2, 1: 7}, (1,))]


def test_large_post_reveal_reraise_never_commits_a_large_fraction_of_stack() -> None:
    body = cloned_request()
    body.update({
        "table_rule": "standard",
        "round": "post_reveal",
        "your_number": 11,
        "community_number": 12,
        "pot": 84,
        "to_call": 104,
        "your_stack": 169,
        "legal_actions": ["fold", "call", "raise"],
        "min_raise_to": 169,
        "max_raise_to": 169,
    })
    assert decide(body).action == "fold"


def test_post_reveal_opponent_raise_is_not_reraised() -> None:
    body = cloned_request()
    body.update({
        "table_rule": "standard",
        "round": "post_reveal",
        "your_number": 13,
        "community_number": 8,
        "pot": 40,
        "to_call": 12,
        "your_stack": 180,
        "legal_actions": ["fold", "call", "raise"],
        "current_hand_actions": [
            {"seat": 0, "round": "post_reveal", "action": "bet", "amount": 8},
            {"seat": 1, "round": "post_reveal", "action": "raise", "amount": 20},
        ],
    })
    assert decide(body).action == "call"


def test_pre_reveal_reraise_war_is_folded_before_large_commitment() -> None:
    body = cloned_request()
    body.update({
        "table_rule": "standard",
        "round": "pre_reveal",
        "your_number": 13,
        "to_call": 19,
        "your_stack": 223,
        "pot": 43,
        "legal_actions": ["fold", "call", "raise"],
        "current_hand_actions": [
            {"seat": 1, "round": "pre_reveal", "action": "raise", "amount": 5},
            {"seat": 0, "round": "pre_reveal", "action": "raise", "amount": 12},
            {"seat": 1, "round": "pre_reveal", "action": "raise", "amount": 31},
        ],
    })
    assert decide(body).action == "fold"


def test_strong_hand_defends_a_single_small_pre_reveal_raise() -> None:
    body = cloned_request()
    body.update({
        "table_rule": "standard",
        "round": "pre_reveal",
        "your_number": 13,
        "to_call": 3,
        "your_stack": 200,
        "legal_actions": ["fold", "call", "raise"],
        "current_hand_actions": [{"seat": 1, "round": "pre_reveal", "action": "raise", "amount": 5}],
    })
    assert decide(body).action == "call"
