# ARCHITECTURE.md — Implementation Structure

How the code should be organised. Language and framework choices, module boundaries, and the rules the implementation must follow.

---

## 1. Stack

| Concern | Choice | Reason |
|---------|--------|--------|
| Language | Python 3.11+ | Fast enough for this workload, already familiar. |
| Web framework | **FastAPI** | Async, low overhead, automatic JSON parsing. |
| Server | `uvicorn` | Standard ASGI server. |
| Validation | Plain dicts with `.get()` defaults, **not** strict Pydantic models on the inbound request | The coordinator adds fields over time. Strict validation would reject unknown keys and cause a forfeit. |
| Testing | `pytest` | Unit tests for the pure functions. |
| Tunnel (dev) | `cloudflared` or `ngrok` | HTTPS exposure of a local server. |

Response models **may** use Pydantic since I control that shape.

---

## 2. Module layout

```
showdown/
├── main.py                 # FastAPI app, routes only. Thin.
├── models.py               # Response types, parsed-request accessor helpers.
├── evaluator/
│   ├── __init__.py
│   ├── base.py             # ShowdownRule interface
│   ├── standard.py         # table_rule == "standard"
│   └── registry.py         # codename -> rule implementation
├── equity.py               # Closed-form win/tie/lose probabilities. Pure.
├── strategy/
│   ├── __init__.py
│   ├── decide.py           # Top-level: request dict -> Action
│   ├── preflop.py          # pre_reveal decision logic
│   ├── postflop.py         # post_reveal decision logic
│   └── sizing.py           # Bet/raise amount selection, clamping
├── safety.py               # Legality validation, fallback action
├── config.py               # All tunable thresholds in one place
└── tests/
    ├── test_evaluator.py
    ├── test_equity.py
    ├── test_safety.py
    ├── test_strategy.py
    └── test_protocol.py

sim/
├── coordinator.py          # Local mock of the game server
├── opponents.py            # Baseline opponent bots to play against
└── run.py                  # Batch runner, statistics output
```

---

## 3. Layering rule

```
main.py  ->  strategy/  ->  equity.py  ->  evaluator/
             safety.py
```

**Dependencies point downward only.** No module imports anything above it.

- `evaluator/`, `equity.py`, `strategy/`, `safety.py` are **pure**. No I/O, no globals, no clock, no randomness except through an injected RNG.
- `main.py` is the only module that knows HTTP exists.
- This makes everything below `main.py` directly unit-testable and directly reusable by the local simulator without spinning up a server.

---

## 4. `main.py` contract

```python
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/move")
async def move(request: Request):
    body = await request.json()
    try:
        action = decide(body)
    except Exception:
        action = fallback_action(body)
    return sanitize(action, body)
```

Three hard requirements:

1. **The handler can never raise.** A bare `except Exception` wraps the entire decision path and falls back to a guaranteed-legal action.
2. **`sanitize()` runs on every path**, including the happy path. It re-validates the chosen action against `legal_actions` and clamps `amount` into `[min_raise_to, max_raise_to]`. If validation fails it downgrades to the fallback rather than returning something illegal.
3. **No blocking I/O in the request path.** No file writes, no network calls, no database. Any logging must be non-blocking or deferred.

### 4.1 Fallback action

```
if "check" in legal_actions:  return check
if "call"  in legal_actions:  return call     # only if the situation warrants
return fold
```

Note the coordinator's own substitution is check-else-fold. My fallback should match that at minimum, so an internal error is never worse than a timeout.

---

## 5. Evaluator interface

Even though Phase 1 only needs `"standard"`, define the seam now so Phases 2 and 3 slot in without touching strategy code.

```python
class ShowdownRule(Protocol):
    codename: str

    def rank(self, number: int, community: int | None) -> tuple:
        """Return a comparable ranking key. Higher tuple wins.
        Ties in the key mean a split pot."""
        ...
```

`standard.py`:

```python
def rank(number, community):
    is_pair = community is not None and number == community
    return (1 if is_pair else 0, number if not is_pair else 0)
```

`registry.py` maps codename to implementation, with a documented default:

```python
RULES = {"standard": StandardRule()}

def get_rule(codename: str) -> ShowdownRule:
    return RULES.get(codename, RULES["standard"])
```

Unknown codenames fall back to standard rather than crashing. In Phase 2 this registry gains inferred rules; in Phase 1 the fallback should never fire.

---

## 6. Equity module

Pure functions, no simulation.

```python
def post_reveal_equity(n: int, c: int) -> tuple[float, float, float]:
    """Returns (win, tie, lose) against one uniform opponent."""

def pre_reveal_equity(n: int) -> tuple[float, float, float]:
    """Enumerates all 13 x 13 (opponent, community) pairs."""
```

Both are **precomputed at import time** into lookup tables:
- Post-reveal: 13 × 13 = 169 entries.
- Pre-reveal: 13 entries.

Total work at startup is trivial and the request path becomes a dictionary lookup. **Never run Monte Carlo simulation inside `/move`.**

Both take the active `ShowdownRule` so the same code serves later phases.

---

## 7. Strategy module

`decide(body) -> Action` is the single entry point. It should:

1. Parse the request into a small typed context object (my number, community, round, pot, to_call, legal actions, position, stack, hand progress).
2. Determine position: `is_button = (your_seat == button_seat)`, and from that, whether I act first or last **in this specific round**.
3. Compute equity via the lookup table.
4. Compute pot odds: `to_call / (pot + to_call)`.
5. Branch to `preflop.decide()` or `postflop.decide()`.
6. Return an `Action`, with sizing resolved by `sizing.py`.

**All numeric thresholds live in `config.py`.** No magic numbers inline. This is what makes tuning against the simulator tractable.

### 7.1 Position must be recomputed every request

The acting order **flips between rounds**. Never cache it, never infer it from the previous hand. Derive it fresh from `your_seat` and `button_seat` and the current `round` on every single call.

---

## 8. Sizing module

Responsibilities:

- Convert a desired sizing intent (for example "raise to 3x the pot") into an absolute `amount`.
- **Remember `amount` is the round total, not the increment.** Compute it as `my_current_bet_this_round + additional_chips`, or directly as a target total.
- Clamp into `[min_raise_to, max_raise_to]`.
- If clamping would change the intent materially (for example the intended raise is below `min_raise_to`), decide explicitly whether to raise to the minimum or to fall back to call. Do not silently clamp.
- Handle `min_raise_to == max_raise_to`: the only legal raise is all-in.

---

## 9. State

Phase 1 needs **no persistent state** to clear. Keep the bot stateless if possible.

If opponent modelling is added later, state must be:
- Keyed by `match_id`.
- Held in a bounded in-memory dict with eviction, never on disk.
- Read and written without blocking.
- Safe to be entirely absent (a cold start mid-match must not crash or degrade badly).

Note that `recent_hands` already supplies the last 20 hands on every request, so a surprising amount of "state" is available for free with no storage at all. **Prefer deriving from `recent_hands` over maintaining local state.**

---

## 10. Configuration

`config.py` holds every tunable in one dataclass so the simulator can sweep them:

```python
@dataclass(frozen=True)
class Config:
    # pre_reveal
    open_raise_min_number: int
    open_raise_to_bb: float
    call_raise_min_number: int
    threebet_min_number: int

    # post_reveal
    value_bet_min_equity: float
    bet_size_pot_fraction: float
    bluff_frequency: float
    call_equity_margin: float

    # risk
    max_pot_commitment_fraction: float
    protect_lead_hand_threshold: int
```

Values themselves are argued for in `STRATEGY.md`.

---

## 11. Logging

- Log every request and decision to an in-memory ring buffer, flushed asynchronously outside the request path.
- Log at minimum: `hand_number`, `round`, `your_number`, `community_number`, `pot`, `to_call`, chosen action, chosen amount, computed equity, and which strategy branch fired.
- This log is what makes post-match analysis against `/matches/<runId>` useful. Without it, a bad run is uninterpretable.

---

## 12. Non-negotiables checklist

- [ ] `/move` never returns anything other than HTTP 200.
- [ ] Every returned action is a member of the request's `legal_actions`.
- [ ] Every returned `amount` is inside `[min_raise_to, max_raise_to]`, and omitted for `check`/`call`/`fold`.
- [ ] Unknown request fields are ignored, not rejected.
- [ ] `players` is read as a variable-length list.
- [ ] No blocking I/O inside `/move`.
- [ ] Position derived fresh from `your_seat`/`button_seat`/`round` on every call.
- [ ] `shown_numbers` keys cast from string to int before use.
