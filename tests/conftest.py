from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _reset_attempt_state():
    from showdown.strategy.state import ATTEMPT_STATE

    ATTEMPT_STATE.reset()
    yield


def sample_request() -> dict:
    return {
        "protocol_version": 2,
        "match_id": "phase1-seed7",
        "phase": 1,
        "table_rule": "standard",
        "small_blind": 1,
        "big_blind": 2,
        "starting_stack": 200,
        "your_stack": 185,
        "hand_number": 6,
        "total_hands": 100,
        "round": "post_reveal",
        "your_number": 3,
        "community_number": 5,
        "your_seat": 0,
        "button_seat": 1,
        "pot": 32,
        "to_call": 18,
        "min_raise_to": 36,
        "max_raise_to": 185,
        "legal_actions": ["fold", "call", "raise"],
        "players": [
            {
                "seat": 0,
                "name": "you",
                "folded": False,
                "chip_delta": -8,
                "bet_this_round": 0,
                "stack": 185,
                "all_in": False,
                "busted": False,
            },
            {
                "seat": 1,
                "name": "Gaston",
                "folded": False,
                "chip_delta": 8,
                "bet_this_round": 18,
                "stack": 183,
                "all_in": False,
                "busted": False,
            },
        ],
        "current_hand_actions": [],
        "recent_hands": [],
    }


def cloned_request() -> dict:
    return deepcopy(sample_request())
