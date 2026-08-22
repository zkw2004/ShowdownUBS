from showdown.models import Action
from showdown.safety import fallback_action, sanitize

from tests.conftest import cloned_request


def test_fallback_prefers_check() -> None:
    body = cloned_request()
    body["legal_actions"] = ["check", "bet"]
    assert fallback_action(body).action == "check"


def test_fallback_uses_call_when_available() -> None:
    body = cloned_request()
    body["legal_actions"] = ["fold", "call", "raise"]
    assert fallback_action(body).action == "call"


def test_sanitize_rejects_illegal_action() -> None:
    body = cloned_request()
    action = Action("bet", 50)
    assert sanitize(action, body) == {"action": "call"}


def test_sanitize_strips_amount_for_call() -> None:
    body = cloned_request()
    action = Action("call", 999)
    assert sanitize(action, body) == {"action": "call"}


def test_sanitize_rejects_raise_without_bounds() -> None:
    body = cloned_request()
    body["min_raise_to"] = None
    body["max_raise_to"] = None
    assert sanitize(Action("raise", 100), body) == {"action": "call"}
