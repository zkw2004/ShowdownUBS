from showdown.strategy.decide import decide

from tests.conftest import cloned_request


def test_preflop_button_low_number_completes() -> None:
    body = cloned_request()
    body["round"] = "pre_reveal"
    body["community_number"] = None
    body["your_number"] = 2
    body["your_seat"] = 1
    body["button_seat"] = 1
    body["pot"] = 3
    body["to_call"] = 1
    body["min_raise_to"] = 4
    body["max_raise_to"] = 200
    body["legal_actions"] = ["fold", "call", "raise"]
    body["players"][0]["bet_this_round"] = 2
    body["players"][1]["bet_this_round"] = 1
    action = decide(body)
    assert action.action == "call"


def test_postflop_pair_calls_a_bet_instead_of_raising() -> None:
    body = cloned_request()
    body["your_number"] = 7
    body["community_number"] = 7
    action = decide(body)
    assert action.action == "call"


def test_postflop_pair_bets_when_checked_to() -> None:
    body = cloned_request()
    body.update({
        "your_number": 7,
        "community_number": 7,
        "to_call": 0,
        "pot": 16,
        "min_raise_to": 2,
        "max_raise_to": 185,
        "legal_actions": ["check", "bet"],
    })
    action = decide(body)
    assert action.action == "bet"
    assert action.amount is not None


def test_postflop_weak_hand_folds_to_bet() -> None:
    body = cloned_request()
    body["your_number"] = 2
    body["community_number"] = 13
    action = decide(body)
    assert action.action == "fold"
