from showdown.equity import multiway_adjusted_equity, post_reveal_multiway_equity
from showdown.evaluator.registry import get_rule
from showdown.models import parse_context
from showdown.strategy.decide import _is_phase3, decide
from showdown.strategy.ranges import committed_opponent_seats
from showdown.strategy.state import ATTEMPT_STATE

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
    assert decide(body).action in {"call", "raise"}


def test_nine_calls_a_small_open_with_players_still_to_act() -> None:
    """Live leak: a 9 was assigned 8% equity because a seat that had not acted
    was priced as if it already held the raiser's range."""
    body = _six_seat_body()
    body.update(
        {
            "table_rule": "cinnabar",
            "round": "pre_reveal",
            "community_number": None,
            "your_number": 9,
            "your_seat": 0,
            "button_seat": 4,
            "to_call": 5,
            "pot": 9,
            "your_stack": 414,
            "min_raise_to": 10,
            "max_raise_to": 414,
            "legal_actions": ["fold", "call", "raise"],
            "current_hand_actions": [{"seat": 4, "round": "pre_reveal", "action": "raise", "amount": 6}],
            "players": [
                {"seat": 0, "name": "you", "chip_delta": 215, "stack": 414, "busted": False, "folded": False, "bet_this_round": 1},
                {"seat": 1, "name": "Dana", "chip_delta": 29, "stack": 227, "busted": False, "folded": False, "bet_this_round": 2},
                {"seat": 2, "name": "Miles", "chip_delta": -200, "stack": 0, "busted": True, "folded": True, "bet_this_round": 0},
                {"seat": 3, "name": "Theo", "chip_delta": -200, "stack": 0, "busted": True, "folded": True, "bet_this_round": 0},
                {"seat": 4, "name": "Rhea", "chip_delta": 381, "stack": 575, "busted": False, "folded": False, "bet_this_round": 6},
                {"seat": 5, "name": "Bram", "chip_delta": -200, "stack": 0, "busted": True, "folded": True, "bet_this_round": 0},
            ],
        }
    )
    assert decide(body).action in {"call", "raise"}


def test_ten_calls_an_overjam_when_pot_odds_are_good() -> None:
    """Live leak: 50% equity into a 30% pot was folded by an all-in 0.60 floor."""
    body = cloned_request()
    body.update(
        {
            "phase": 3,
            "table_rule": "verdigris",
            "round": "pre_reveal",
            "community_number": None,
            "your_number": 10,
            "to_call": 842,
            "pot": 846,
            "your_stack": 354,
            "legal_actions": ["fold", "call"],
            "current_hand_actions": [{"seat": 1, "round": "pre_reveal", "action": "raise", "amount": 844}],
            "players": [
                {"seat": 0, "name": "you", "chip_delta": 154, "stack": 354, "busted": False, "folded": False},
                {"seat": 1, "name": "Bram", "chip_delta": 489, "stack": 842, "busted": False, "folded": False},
            ],
        }
    )
    assert decide(body).action == "call"


def test_amaranth_thirteen_calls_a_small_open() -> None:
    body = _six_seat_body()
    body.update(
        {
            "table_rule": "amaranth",
            "round": "pre_reveal",
            "community_number": None,
            "your_number": 13,
            "to_call": 9,
            "pot": 14,
            "your_stack": 200,
            "min_raise_to": 16,
            "max_raise_to": 200,
            "legal_actions": ["fold", "call", "raise"],
            "current_hand_actions": [{"seat": 2, "round": "pre_reveal", "action": "raise", "amount": 11}],
        }
    )
    assert decide(body).action in {"call", "raise"}


def test_obsidian_opens_the_low_number_and_folds_the_high_number() -> None:
    body = _six_seat_body()
    body.update(
        {
            "table_rule": "obsidian",
            "round": "pre_reveal",
            "community_number": None,
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
    low = dict(body)
    low["your_number"] = 1
    high = dict(body)
    high["your_number"] = 13
    assert decide(low).action == "raise"
    assert decide(high).action == "fold"


def test_ten_calls_a_three_big_blind_open() -> None:
    """v11 treated a 6-chip open as 13-12 and folded tens (leg 1 hand 26)."""
    body = cloned_request()
    body.update(
        {
            "phase": 3,
            "table_rule": "verdigris",
            "round": "pre_reveal",
            "community_number": None,
            "your_number": 10,
            "to_call": 6,
            "pot": 9,
            "your_stack": 200,
            "min_raise_to": 12,
            "max_raise_to": 200,
            "legal_actions": ["fold", "call", "raise"],
            "current_hand_actions": [{"seat": 1, "round": "pre_reveal", "action": "raise", "amount": 8}],
        }
    )
    body["players"][0]["bet_this_round"] = 2
    body["players"][1]["bet_this_round"] = 8
    assert decide(body).action in {"call", "raise"}


def test_amaranth_twelve_calls_a_five_chip_open() -> None:
    """v11 folded 12 on amaranth because share 0.394 sat 0.003 under a 4% pad."""
    body = cloned_request()
    body.update(
        {
            "phase": 3,
            "table_rule": "amaranth",
            "round": "pre_reveal",
            "community_number": None,
            "your_number": 12,
            "to_call": 5,
            "pot": 9,
            "your_stack": 200,
            "min_raise_to": 10,
            "max_raise_to": 200,
            "legal_actions": ["fold", "call", "raise"],
            "current_hand_actions": [{"seat": 1, "round": "pre_reveal", "action": "raise", "amount": 6}],
        }
    )
    body["players"][0]["bet_this_round"] = 1
    body["players"][1]["bet_this_round"] = 6
    assert decide(body).action in {"call", "raise"}


def test_obsidian_two_folds_when_multiway_share_is_below_the_price() -> None:
    """A top-two number is still not an automatic call in a crowded pot."""
    body = _six_seat_body()
    body.update(
        {
            "phase": 3,
            "table_rule": "obsidian",
            "round": "pre_reveal",
            "community_number": None,
            "your_number": 2,
            "to_call": 107,
            "pot": 168,
            "your_stack": 193,
            "min_raise_to": 195,
            "max_raise_to": 200,
            "legal_actions": ["fold", "call", "raise"],
            "current_hand_actions": [
                {"seat": 5, "round": "pre_reveal", "action": "raise", "amount": 7},
                {"seat": 0, "round": "pre_reveal", "action": "call", "amount": 7},
                {"seat": 1, "round": "pre_reveal", "action": "fold"},
                {"seat": 2, "round": "pre_reveal", "action": "call", "amount": 7},
                {"seat": 3, "round": "pre_reveal", "action": "call", "amount": 7},
                {"seat": 4, "round": "pre_reveal", "action": "raise", "amount": 33},
                {"seat": 5, "round": "pre_reveal", "action": "raise", "amount": 114},
            ],
            "players": [
                {"seat": 0, "name": "you", "chip_delta": 0, "bet_this_round": 7, "stack": 193},
                {"seat": 1, "name": "one", "chip_delta": 8, "bet_this_round": 0, "stack": 208, "folded": True},
                {"seat": 2, "name": "two", "chip_delta": -3, "bet_this_round": 7, "stack": 190},
                {"seat": 3, "name": "three", "chip_delta": 81, "bet_this_round": 7, "stack": 274},
                {"seat": 4, "name": "four", "chip_delta": 0, "bet_this_round": 33, "stack": 167},
                {"seat": 5, "name": "five", "chip_delta": -86, "bet_this_round": 114, "stack": 0, "all_in": True},
            ],
        }
    )
    assert decide(body).action == "fold"


def test_six_max_button_does_not_open_a_seven() -> None:
    body = _six_seat_body()
    body.update(
        {
            "table_rule": "cinnabar",
            "round": "pre_reveal",
            "community_number": None,
            "your_number": 7,
            "your_seat": 0,
            "button_seat": 0,
            "pot": 3,
            "to_call": 2,
            "min_raise_to": 4,
            "max_raise_to": 200,
            "legal_actions": ["fold", "call", "raise"],
            "current_hand_actions": [],
            "players": [
                {"seat": 0, "name": "you", "chip_delta": 0, "bet_this_round": 0, "busted": False, "folded": False},
                {"seat": 1, "name": "Dana", "chip_delta": 0, "bet_this_round": 1, "busted": False, "folded": False},
                {"seat": 2, "name": "Miles", "chip_delta": 0, "bet_this_round": 2, "busted": False, "folded": False},
                {"seat": 3, "name": "Theo", "chip_delta": 0, "bet_this_round": 0, "busted": False, "folded": False},
                {"seat": 4, "name": "Rhea", "chip_delta": 0, "bet_this_round": 0, "busted": False, "folded": False},
                {"seat": 5, "name": "Bram", "chip_delta": 0, "bet_this_round": 0, "busted": False, "folded": False},
            ],
        }
    )
    assert decide(body).action == "fold"


def test_overjam_pot_odds_exclude_unmatched_chips() -> None:
    body = cloned_request()
    body.update(
        {
            "round": "pre_reveal",
            "community_number": None,
            "your_stack": 354,
            "pot": 846,
            "to_call": 842,
            "players": [
                {
                    "seat": 0,
                    "name": "you",
                    "bet_this_round": 2,
                    "stack": 354,
                    "folded": False,
                    "busted": False,
                },
                {
                    "seat": 1,
                    "name": "opponent",
                    "bet_this_round": 844,
                    "stack": 0,
                    "all_in": True,
                    "folded": False,
                    "busted": False,
                },
            ],
        }
    )
    context = parse_context(body)
    assert context.effective_call == 354
    assert context.effective_pot == 358
    assert abs(context.adjusted_pot_odds - (354 / 712)) < 1e-9


def test_all_in_opponent_remains_in_the_showdown_range() -> None:
    body = _six_seat_body()
    body["players"][1]["all_in"] = True
    body["players"][1]["stack"] = 0
    body["current_hand_actions"] = [{"seat": 2, "round": "post_reveal", "action": "bet", "amount": 4}]
    context = parse_context(body)
    assert committed_opponent_seats(context) == (1, 2)


def test_profiles_accumulate_across_all_four_legs() -> None:
    first = _six_seat_body()
    first["recent_hands"] = [
        {
            "hand_number": 1,
            "shown_numbers": {"1": 13},
            "actions": [{"seat": 1, "round": "pre_reveal", "action": "raise", "amount": 6}],
        }
    ]
    ATTEMPT_STATE.observe(parse_context(first))

    second = _six_seat_body()
    second["leg_number"] = 2
    second["match_id"] = "phase3-fixture-leg2"
    second["recent_hands"] = [
        {
            "hand_number": 1,
            "shown_numbers": {"1": 8},
            "actions": [{"seat": 1, "round": "pre_reveal", "action": "call", "amount": 2}],
        }
    ]
    ATTEMPT_STATE.observe(parse_context(second))

    profile = ATTEMPT_STATE.seat_profiles[1]
    assert profile.hands == 2
    assert profile.pre_raises == 1
    assert profile.pre_continues == 2


def test_medium_number_does_not_isolate_two_limpers() -> None:
    body = _six_seat_body()
    body.update(
        {
            "round": "pre_reveal",
            "community_number": None,
            "your_number": 9,
            "pot": 7,
            "to_call": 2,
            "min_raise_to": 4,
            "max_raise_to": 200,
            "legal_actions": ["fold", "call", "raise"],
            "current_hand_actions": [
                {"seat": 3, "round": "pre_reveal", "action": "call", "amount": 2},
                {"seat": 4, "round": "pre_reveal", "action": "call", "amount": 2},
            ],
            "players": [
                {"seat": 0, "name": "you", "chip_delta": 0, "bet_this_round": 0, "busted": False},
                {"seat": 1, "name": "one", "chip_delta": 0, "bet_this_round": 1, "busted": False},
                {"seat": 2, "name": "two", "chip_delta": 0, "bet_this_round": 2, "busted": False},
                {"seat": 3, "name": "three", "chip_delta": 0, "bet_this_round": 2, "busted": False},
                {"seat": 4, "name": "four", "chip_delta": 0, "bet_this_round": 2, "busted": False},
                {"seat": 5, "name": "five", "chip_delta": 0, "bet_this_round": 0, "busted": False},
            ],
        }
    )
    assert decide(body).action in {"fold", "call"}


def _late_heads_up_catchup_body() -> dict:
    """Leg 4 hand 56: ordinary calls cannot erase the standings gap in time."""
    body = cloned_request()
    body.update(
        {
            "phase": 3,
            "table_rule": "cinnabar",
            "round": "post_reveal",
            "community_number": 2,
            "your_number": 10,
            "hand_number": 56,
            "total_hands": 60,
            "leg_number": 4,
            "total_legs": 4,
            "match_id": "phase3-catchup-leg4",
            "your_seat": 0,
            "button_seat": 1,
            "pot": 27,
            "to_call": 11,
            "min_raise_to": 22,
            "max_raise_to": 440,
            "your_stack": 440,
            "legal_actions": ["fold", "call", "raise"],
            "current_hand_actions": [
                {"seat": 1, "round": "pre_reveal", "action": "call", "amount": 2},
                {"seat": 0, "round": "pre_reveal", "action": "raise", "amount": 8},
                {"seat": 1, "round": "pre_reveal", "action": "call", "amount": 8},
                {"seat": 0, "round": "post_reveal", "action": "check"},
                {"seat": 1, "round": "post_reveal", "action": "bet", "amount": 11},
            ],
            "players": [
                {
                    "seat": 0,
                    "name": "you",
                    "chip_delta": 248,
                    "bet_this_round": 0,
                    "stack": 440,
                    "busted": False,
                    "folded": False,
                },
                {
                    "seat": 1,
                    "name": "leader",
                    "chip_delta": 577,
                    "bet_this_round": 11,
                    "stack": 758,
                    "busted": False,
                    "folded": False,
                },
                {
                    "seat": 2,
                    "name": "two",
                    "chip_delta": -200,
                    "bet_this_round": 0,
                    "stack": 0,
                    "busted": True,
                    "folded": True,
                },
                {
                    "seat": 3,
                    "name": "three",
                    "chip_delta": -200,
                    "bet_this_round": 0,
                    "stack": 0,
                    "busted": True,
                    "folded": True,
                },
                {
                    "seat": 4,
                    "name": "four",
                    "chip_delta": -200,
                    "bet_this_round": 0,
                    "stack": 0,
                    "busted": True,
                    "folded": True,
                },
                {
                    "seat": 5,
                    "name": "five",
                    "chip_delta": -200,
                    "bet_this_round": 0,
                    "stack": 0,
                    "busted": True,
                    "folded": True,
                },
            ],
        }
    )
    return body


def test_late_heads_up_catchup_raise_targets_a_lead_flipping_pot() -> None:
    body = _late_heads_up_catchup_body()
    context = parse_context(body)
    assert context.chips_needed_to_lead == 330
    assert context.sole_leader_seat == 1
    # Winning 165 directly from the leader flips a 329-chip gap. Eight of
    # those chips were already committed before the current betting round.
    assert context.raise_to_for_table_lead == 157

    action = decide(body)
    assert action.action == "raise"
    assert action.amount is not None and action.amount >= 157
    assert body["_decision_trace"]["reason"] == "objective_catchup_raise"


def test_catchup_raise_does_not_replace_normal_early_pot_odds_play() -> None:
    body = _late_heads_up_catchup_body()
    body["hand_number"] = 40
    assert decide(body).action == "call"


def test_catchup_raise_only_targets_the_actual_table_leader() -> None:
    body = _late_heads_up_catchup_body()
    body["players"][2].update(
        {
            "chip_delta": 600,
            "stack": 800,
            "busted": False,
            "folded": True,
        }
    )
    assert decide(body).action == "call"


def test_late_top_number_open_is_sized_to_take_the_lead() -> None:
    body = _six_seat_body()
    body.update(
        {
            "round": "pre_reveal",
            "community_number": None,
            "hand_number": 55,
            "your_number": 13,
            "your_seat": 3,
            "pot": 3,
            "to_call": 2,
            "min_raise_to": 4,
            "max_raise_to": 200,
            "your_stack": 200,
            "legal_actions": ["fold", "call", "raise"],
            "current_hand_actions": [],
            "players": [
                {"seat": 0, "name": "one", "chip_delta": 100, "bet_this_round": 0, "busted": False},
                {"seat": 1, "name": "two", "chip_delta": 0, "bet_this_round": 1, "busted": False},
                {"seat": 2, "name": "three", "chip_delta": 0, "bet_this_round": 2, "busted": False},
                {"seat": 3, "name": "you", "chip_delta": 0, "bet_this_round": 0, "busted": False},
                {"seat": 4, "name": "four", "chip_delta": 0, "bet_this_round": 0, "busted": False},
                {"seat": 5, "name": "five", "chip_delta": 0, "bet_this_round": 0, "busted": False},
            ],
        }
    )
    action = decide(body)
    assert action.action == "raise"
    assert action.amount is not None and action.amount >= 51


def test_late_post_reveal_nuts_bet_can_take_the_lead() -> None:
    body = _six_seat_body()
    body.update(
        {
            "round": "post_reveal",
            "community_number": 7,
            "your_number": 7,
            "hand_number": 55,
            "pot": 20,
            "to_call": 0,
            "min_raise_to": 2,
            "max_raise_to": 200,
            "your_stack": 200,
            "legal_actions": ["check", "bet"],
            "current_hand_actions": [],
            "players": [
                {"seat": 0, "name": "you", "chip_delta": 0, "bet_this_round": 0, "busted": False},
                {"seat": 1, "name": "one", "chip_delta": 100, "bet_this_round": 0, "busted": False},
                {"seat": 2, "name": "two", "chip_delta": 0, "bet_this_round": 0, "busted": False},
                {"seat": 3, "name": "three", "chip_delta": 0, "bet_this_round": 0, "busted": False},
                {"seat": 4, "name": "four", "chip_delta": 0, "bet_this_round": 0, "busted": False},
                {"seat": 5, "name": "five", "chip_delta": 0, "bet_this_round": 0, "busted": False},
            ],
        }
    )
    action = decide(body)
    assert action.action == "bet"
    assert action.amount is not None and action.amount >= 51


def test_late_post_reveal_nuts_raise_can_take_the_lead() -> None:
    body = _six_seat_body()
    body.update(
        {
            "round": "post_reveal",
            "community_number": 7,
            "your_number": 7,
            "hand_number": 55,
            "pot": 30,
            "to_call": 10,
            "min_raise_to": 20,
            "max_raise_to": 200,
            "your_stack": 200,
            "legal_actions": ["fold", "call", "raise"],
            "current_hand_actions": [{"seat": 1, "round": "post_reveal", "action": "bet", "amount": 10}],
            "players": [
                {"seat": 0, "name": "you", "chip_delta": 0, "bet_this_round": 0, "stack": 200},
                {"seat": 1, "name": "one", "chip_delta": 100, "bet_this_round": 10, "stack": 290},
                {"seat": 2, "name": "two", "chip_delta": 0, "bet_this_round": 0, "folded": True},
                {"seat": 3, "name": "three", "chip_delta": 0, "bet_this_round": 0, "folded": True},
                {"seat": 4, "name": "four", "chip_delta": 0, "bet_this_round": 0, "folded": True},
                {"seat": 5, "name": "five", "chip_delta": 0, "bet_this_round": 0, "folded": True},
            ],
        }
    )
    action = decide(body)
    assert action.action == "raise"
    assert action.amount is not None and action.amount >= 51


def test_strategy_code_does_not_hardcode_opponent_names() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "showdown"
    forbidden = ("Dana", "Miles", "Theo", "Rhea", "Bram")
    for path in root.rglob("*.py"):
        text = path.read_text()
        for name in forbidden:
            assert name not in text, f"{path} hardcodes {name}"
