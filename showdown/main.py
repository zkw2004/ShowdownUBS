from __future__ import annotations

from fastapi import FastAPI, Request

from showdown.safety import fallback_action, sanitize
from showdown.strategy.decide import decide

app = FastAPI()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/move")
async def move(request: Request) -> dict:
    body = await request.json()
    try:
        action = decide(body)
    except Exception:
        action = fallback_action(body)
    return sanitize(action, body)
