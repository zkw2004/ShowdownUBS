from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Request

from showdown.observe import observe
from showdown.safety import fallback_action, sanitize
from showdown.strategy.decide import decide

app = FastAPI()
# Uvicorn configures this logger at INFO level.  A new logger name
# may inherit a WARNING-only root logger and silently discard move traces.
logger = logging.getLogger("uvicorn.error")
LOG_MOVES = os.getenv("SHOWDOWN_LOG_MOVES", "1").lower() not in {"0", "false", "no"}
# Render exports the deployed commit.  Surfacing it on /health is the only way
# to tell a live deploy from a stale one before a match starts.
VERSION = (os.getenv("RENDER_GIT_COMMIT") or "dev")[:8]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": VERSION}


@app.post("/move")
async def move(request: Request) -> dict:
    body = await request.json()
    try:
        action = decide(body)
    except Exception:
        logger.exception("decision_error")
        action = fallback_action(body)
    response = sanitize(action, body)
    observe(body, response, LOG_MOVES)
    return response
