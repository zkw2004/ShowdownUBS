import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from showdown.main import app
from showdown.main import _trace
from tests.conftest import cloned_request


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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


def test_move_trace_captures_decision_inputs() -> None:
    body = cloned_request()
    body["leg_number"] = 2
    trace = _trace(body, {"action": "call"})
    assert trace["leg"] == 2
    assert trace["your_number"] == body["your_number"]
    assert trace["response"] == {"action": "call"}
