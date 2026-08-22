from __future__ import annotations

import json
import logging
import os

from fastapi import FastAPI, Request

from showdown.safety import fallback_action, sanitize
from showdown.strategy.decide import decide

app = FastAPI()
logger = logging.getLogger("showdown.moves")
LOG_MOVES = os.getenv("SHOWDOWN_LOG_MOVES", "").lower() in {"1", "true", "yes"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/move")
async def move(request: Request) -> dict:
    body = await request.json()
    try:
        action = decide(body)
    except Exception:
        logger.exception("decision_error")
        action = fallback_action(body)
    response = sanitize(action, body)
    if LOG_MOVES:
        logger.info("move_trace=%s", json.dumps(_trace(body, response), sort_keys=True, default=str))
    return response


def _trace(body: dict, response: dict) -> dict:
    """Log every input that affects a decision, without the 20-hand duplicate history."""
    players = body.get("players") or []
    return {
        "match_id": body.get("match_id"),
        "leg": body.get("leg_number"),
        "total_legs": body.get("total_legs"),
        "hand": body.get("hand_number"),
        "round": body.get("round"),
        "rule": body.get("table_rule"),
        "your_number": body.get("your_number"),
        "community_number": body.get("community_number"),
        "pot": body.get("pot"),
        "to_call": body.get("to_call"),
        "your_stack": body.get("your_stack"),
        "chip_delta": next((player.get("chip_delta") for player in players if player.get("name") == "you"), None),
        "legal_actions": body.get("legal_actions"),
        "min_raise_to": body.get("min_raise_to"),
        "max_raise_to": body.get("max_raise_to"),
        "current_hand_actions": body.get("current_hand_actions"),
        "response": response,
    }
