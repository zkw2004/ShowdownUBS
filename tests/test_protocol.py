import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from showdown.main import app
from showdown.observe import _audit_hand, _move_trace
from tests.conftest import cloned_request


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    # `version` is the deployed commit, so only the status is fixed.
    assert response.json()["status"] == "ok"


def test_move_returns_legal_action() -> None:
    body = cloned_request()
    response = client.post("/move", json=body)
    payload = response.json()
    assert response.status_code == 200
    assert payload["action"] in body["legal_actions"]
    if payload["action"] in {"bet", "raise"}:
        assert body["min_raise_to"] <= payload["amount"] <= body["max_raise_to"]
    else:
        assert "amount" not in payload


def test_move_handles_unknown_fields() -> None:
    body = cloned_request()
    body["mystery_field"] = {"nested": ["data"]}
    response = client.post("/move", json=body)
    assert response.status_code == 200
    assert response.json()["action"] in body["legal_actions"]


def test_move_trace_logs_the_full_request_and_reply() -> None:
    body = cloned_request()
    body["leg_number"] = 2
    body["recent_hands"] = [{"hand_number": 1}]
    body["_decision_trace"] = {"adjusted_equity": 0.8, "reason": "value_raise"}
    trace = _move_trace(body, {"action": "call"})
    assert trace["response"] == {"action": "call"}
    assert trace["request"]["leg_number"] == 2
    assert trace["request"]["your_number"] == body["your_number"]
    assert trace["request"]["players"] == body["players"]
    assert trace["request"]["_decision_trace"]["reason"] == "value_raise"
    assert "recent_hands" not in trace["request"]


def test_audit_confirms_a_correct_mapping() -> None:
    # Under "standard" the higher number wins, so seat 1 taking it agrees.
    record = {"hand_number": 4, "community_number": 5, "shown_numbers": {"0": 9, "1": 11}, "winners": [1]}
    result = _audit_hand("standard", record)
    assert result["predicted"] == [1]
    assert result["verdict"] == "agree"


def test_audit_flags_a_wrong_mapping() -> None:
    # The lower number took the pot, which "standard" cannot explain.
    record = {"hand_number": 5, "community_number": 5, "shown_numbers": {"0": 9, "1": 11}, "winners": [0]}
    assert _audit_hand("standard", record)["verdict"] == "mismatch"


def test_audit_ignores_hands_without_a_showdown() -> None:
    record = {"hand_number": 6, "community_number": None, "shown_numbers": {}, "winners": [0]}
    assert _audit_hand("standard", record)["verdict"] == "no_showdown"


def test_audit_reports_an_unsolved_codename() -> None:
    record = {"hand_number": 7, "community_number": 5, "shown_numbers": {"0": 9, "1": 11}, "winners": [1]}
    assert _audit_hand("not-a-real-codename", record)["verdict"] == "rule_unsolved"
