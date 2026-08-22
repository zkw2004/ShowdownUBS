import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from showdown.main import app
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
