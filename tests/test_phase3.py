from showdown.equity import multiway_adjusted_equity, post_reveal_multiway_equity
from showdown.evaluator.registry import get_rule
from showdown.models import parse_context
from showdown.strategy.decide import _is_phase3, decide

from tests.conftest import cloned_request


def _six_seat_body() -> dict:
    body = cloned_request()
    body.update(
        {
            "phase": 3,
            "total_hands": 60,
            "leg_number": 1,
            "total_legs": 4,
            "match_id": "phase3-fixture-leg1",
            "your_seat": 0,
            "button_seat": 0,
            "players": [
                {"seat": 0, "name": "you", "chip_delta": 12, "bet_this_round": 1},
                {"seat": 1, "name": "Dana", "chip_delta": 8, "bet_this_round": 2},
                {"seat": 2, "name": "Miles", "chip_delta": 14, "bet_this_round": 0},
                {"seat": 3, "name": "Theo", "chip_delta": -2, "bet_this_round": 0, "folded": True},
                {"seat": 4, "name": "Rhea", "chip_delta": 3, "bet_this_round": 0, "busted": True},
                {"seat": 5, "name": "Bram", "chip_delta": 1, "bet_this_round": 0},
            ],
        }
    )
    return body


def test_multiway_equity_is_expected_pot_share() -> None:
    # A certain win stays a whole pot; with a possible tie the expected share
    # decreases as additional live opponents can tie or beat us.
    assert multiway_adjusted_equity((1.0, 0.0, 0.0), 5) == 1.0
    heads_up = post_reveal_multiway_equity(13, 1, "standard", 1)
    six_way = post_reveal_multiway_equity(13, 1, "standard", 5)
    assert 0.0 < six_way < heads_up


def test_context_filters_folded_and_busted_opponents() -> None:
    context = parse_context(_six_seat_body())
    assert context.live_opponent_seats == (1, 2, 5)
    assert context.live_opponent_count == 3
    assert context.is_multiway
    assert not context.leads_table
    assert context.chips_needed_to_lead == 3


def test_six_seat_request_returns_a_legal_action() -> None:
    body = _six_seat_body()
    body.update(
        {
            "round": "post_reveal",
            "your_number": 13,
            "community_number": 1,
            "pot": 8,
            "to_call": 2,
            "legal_actions": ["fold", "call", "raise"],
            "min_raise_to": 6,
            "max_raise_to": 200,
            "current_hand_actions": [{"seat": 1, "round": "post_reveal", "action": "bet", "amount": 2}],
        }
    )
    assert decide(body).action == "call"


def test_phase_is_read_from_the_request_not_the_current_pot() -> None:
    body = _six_seat_body()
    # Everyone else folded: this pot is heads-up, the match is still Phase 3.
    body["players"] = [
        {"seat": 0, "name": "you", "chip_delta": 4, "folded": False, "busted": False},
        {"seat": 1, "name": "Dana", "chip_delta": 20, "folded": False, "busted": False},
        {"seat": 2, "name": "Miles", "chip_delta": 8, "folded": True, "busted": False},
        {"seat": 3, "name": "Theo", "chip_delta": -2, "folded": True, "busted": False},
        {"seat": 4, "name": "Rhea", "chip_delta": 3, "folded": True, "busted": False},
        {"seat": 5, "name": "Bram", "chip_delta": 1, "folded": True, "busted": False},
    ]
    context = parse_context(body)
    assert context.phase == 3
    assert context.live_opponent_count == 1
    assert not context.is_multiway
    assert _is_phase3(context)


def test_utg_opens_a_top_number_instead_of_treating_blinds_as_a_raise() -> None:
    body = _six_seat_body()
    body.update(
        {
            "round": "pre_reveal",
            "community_number": None,
            "your_number": 13,
            "your_seat": 3,
            "button_seat": 0,
            "pot": 3,
            "to_call": 2,
            "min_raise_to": 4,
            "max_raise_to": 200,
            "legal_actions": ["fold", "call", "raise"],
            "current_hand_actions": [],
            "players": [
                {"seat": 0, "name": "Dana", "chip_delta": 0, "bet_this_round": 0, "busted": False},
                {"seat": 1, "name": "Miles", "chip_delta": 0, "bet_this_round": 1, "busted": False},
                {"seat": 2, "name": "Theo", "chip_delta": 0, "bet_this_round": 2, "busted": False},
                {"seat": 3, "name": "you", "chip_delta": 0, "bet_this_round": 0, "busted": False},
                {"seat": 4, "name": "Rhea", "chip_delta": 0, "bet_this_round": 0, "busted": False},
                {"seat": 5, "name": "Bram", "chip_delta": 0, "bet_this_round": 0, "busted": False},
            ],
        }
    )
    assert decide(body).action == "raise"


def test_utg_folds_trash_first_in() -> None:
    body = _six_seat_body()
    body.update(
        {
            "round": "pre_reveal",
            "community_number": None,
            "your_number": 2,
            "your_seat": 3,
            "button_seat": 0,
            "pot": 3,
            "to_call": 2,
            "min_raise_to": 4,
            "max_raise_to": 200,
            "legal_actions": ["fold", "call", "raise"],
            "current_hand_actions": [],
            "players": [
                {"seat": 0, "name": "Dana", "chip_delta": 0, "bet_this_round": 0, "busted": False},
                {"seat": 1, "name": "Miles", "chip_delta": 0, "bet_this_round": 1, "busted": False},
                {"seat": 2, "name": "Theo", "chip_delta": 0, "bet_this_round": 2, "busted": False},
                {"seat": 3, "name": "you", "chip_delta": 0, "bet_this_round": 0, "busted": False},
                {"seat": 4, "name": "Rhea", "chip_delta": 0, "bet_this_round": 0, "busted": False},
                {"seat": 5, "name": "Bram", "chip_delta": 0, "bet_this_round": 0, "busted": False},
            ],
        }
    )
    assert decide(body).action == "fold"


def test_amaranth_treats_seven_as_the_nuts() -> None:
    rule = get_rule("amaranth")
    assert rule is not None
    assert rule.rank(7, 1) > rule.rank(13, 1)
    assert rule.rank(7, 4) > rule.rank(12, 4)
    assert rule.rank(12, 9) > rule.rank(11, 9)
    # Live H25: pair of 13s beat an unpaired 7.
    assert rule.rank(13, 13) > rule.rank(7, 13)


def test_short_stack_calls_an_overjam_with_a_premium() -> None:
    """to_call 413 vs stack 75 used to make required_equity 1.5 and fold a 7."""
    body = cloned_request()
    body.update(
        {
            "phase": 3,
            "table_rule": "amaranth",
            "round": "pre_reveal",
            "community_number": None,
            "your_number": 7,
            "to_call": 413,
            "pot": 709,
            "your_stack": 75,
            "legal_actions": ["fold", "call"],
            "current_hand_actions": [
                {"seat": 0, "round": "pre_reveal", "action": "raise", "amount": 6},
                {"seat": 1, "round": "pre_reveal", "action": "raise", "amount": 419},
            ],
            "players": [
                {"seat": 0, "name": "you", "chip_delta": -73, "stack": 75, "busted": False, "folded": False},
                {"seat": 1, "name": "Miles", "chip_delta": 408, "stack": 608, "busted": False, "folded": False},
            ],
        }
    )
    assert decide(body).action == "call"


def test_twelve_calls_a_small_open_instead_of_folding() -> None:
    """The 15% range floor made every 12 look like a fold to a 10-chip raise."""
    body = cloned_request()
    body.update(
        {
            "phase": 3,
            "table_rule": "cinnabar",
            "round": "pre_reveal",
            "community_number": None,
            "your_number": 12,
            "to_call": 8,
            "pot": 15,
            "your_stack": 199,
            "min_raise_to": 18,
            "max_raise_to": 199,
            "legal_actions": ["fold", "call", "raise"],
            "current_hand_actions": [{"seat": 1, "round": "pre_reveal", "action": "raise", "amount": 10}],
        }
    )
    assert decide(body).action == "call"
