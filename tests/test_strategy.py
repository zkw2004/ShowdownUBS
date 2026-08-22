from showdown.strategy.decide import decide

from tests.conftest import cloned_request


def _button_complete_body(number: int) -> dict:
    body = cloned_request()
    body["round"] = "pre_reveal"
    body["community_number"] = None
    body["your_number"] = number
    body["your_seat"] = 1
    body["button_seat"] = 1
    body["pot"] = 3
    body["to_call"] = 1
    body["min_raise_to"] = 4
    body["max_raise_to"] = 200
    body["legal_actions"] = ["fold", "call", "raise"]
    body["players"][0]["bet_this_round"] = 2
    body["players"][1]["bet_this_round"] = 1
    return body


def test_preflop_button_low_number_completes() -> None:
    assert decide(_button_complete_body(3)).action == "call"


def test_preflop_button_bottom_number_folds_instead_of_completing() -> None:
    assert decide(_button_complete_body(1)).action == "fold"


def test_postflop_pair_calls_a_bet_instead_of_raising() -> None:
    body = cloned_request()
    body["your_number"] = 7
    body["community_number"] = 7
    action = decide(body)
    assert action.action == "call"


def test_postflop_weak_hand_folds_to_bet() -> None:
    body = cloned_request()
    body["your_number"] = 2
    body["community_number"] = 13
    action = decide(body)
    assert action.action == "fold"
