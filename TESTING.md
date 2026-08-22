# TESTING.md — Verification and Tuning

How correctness is verified and how strategy thresholds are tuned before spending a live attempt.

---

## 1. Why a local simulator is mandatory

Live attempts are rate-limited (one at a time, with a cooldown) and results swing hard under no-limit betting. A single 100-hand match tells almost nothing about whether a strategy change helped.

**A local simulator is the single highest-value thing to build after a working `/move` endpoint.** It turns strategy tuning from a slow guessing game into a measurable one.

Target: **1000 simulated 100-hand matches in under 30 seconds.** That is 100,000 hands, which is achievable in pure Python if the strategy path is a table lookup and no HTTP is involved.

---

## 2. Test layers

| Layer | What it covers | Runs in |
|-------|----------------|---------|
| 1. Unit | Pure functions: evaluator, equity, sizing, safety | ms |
| 2. Protocol | `/move` responds legally to adversarial request bodies | ms |
| 3. Simulation | Full matches against baseline opponents | seconds |
| 4. Live | Real attempts against the coordinator | minutes, rate-limited |

Never skip a layer. Most bugs that cost a live attempt are caught at layer 2.

---

## 3. Layer 1 — Unit tests

### 3.1 Evaluator (`test_evaluator.py`)

```
rank(5, 5) beats rank(13, 7)          # pair beats any non-pair
rank(13, 7) beats rank(12, 7)         # higher number wins
rank(9, 3) == rank(9, 3)              # identical results tie
rank(N, None) works for all N         # pre-reveal, no community number
```

Exhaustive check: for all 13 × 13 × 13 combinations of (my number, opponent number, community number), assert the winner matches a hand-written reference implementation.

### 3.2 Equity (`test_equity.py`)

```
post_reveal_equity(N, N) == (12/13, 1/13, 0)     for all N
sum of (win, tie, lose) == 1.0                    for all inputs
post_reveal_equity(13, 1).win > post_reveal_equity(2, 1).win
pre_reveal_equity(13).lose == 0                   # a 13 can never lose outright
pre_reveal_equity is monotonically increasing in N
```

Cross-validate the closed-form result against a brute-force enumeration written independently. If the two disagree, the closed form is wrong.

### 3.3 Sizing (`test_sizing.py`)

```
amount is always within [min_raise_to, max_raise_to]
amount is a round TOTAL, not an increment
min_raise_to == max_raise_to  ->  amount == that value (all-in)
requested size below min_raise_to  ->  explicit decision, not silent clamp
```

### 3.4 Safety (`test_safety.py`)

```
fallback_action returns check when check is legal
fallback_action returns fold when check is not legal
sanitize rejects an action not in legal_actions
sanitize strips amount from check/call/fold
sanitize adds no amount when min_raise_to is null
```

---

## 4. Layer 2 — Protocol tests

The goal is proving `/move` **cannot** produce an illegal response, whatever arrives.

### 4.1 Property-based fuzzing

Generate random but structurally valid request bodies covering:

- Every combination of `legal_actions` the game can produce.
- `round` in `{pre_reveal, post_reveal}`.
- `community_number` null and 1-13.
- `your_number` 1-13.
- `to_call` = 0 and > 0.
- `min_raise_to` / `max_raise_to` both null, equal, and a wide range.
- `your_stack` from 1 to 200.
- `your_seat` == and != `button_seat`.
- `pot` from 3 to 400.

Assert for every generated request:

```
1. HTTP status is 200
2. response["action"] is in request["legal_actions"]
3. if action in {bet, raise}: min_raise_to <= amount <= max_raise_to
4. if action in {check, call, fold}: "amount" not in response
5. latency < 200ms
```

### 4.2 Hostile input tests

The handler must return a legal action, not a 500, for:

- Missing optional fields.
- **Unknown extra fields** (this is expected behaviour from the coordinator).
- `players` with a different length than expected.
- `shown_numbers` with string keys (this is the real format).
- `recent_hands` empty.
- `recent_hands` with a hand where `community_number` is null and `shown_numbers` is empty.
- Deeply malformed JSON values in fields the strategy reads.

---

## 5. Layer 3 — Simulation

### 5.1 The mock coordinator

`sim/coordinator.py` must reimplement the game **exactly** as specified in `RULES.md`:

- Blind posting and alternation.
- Independent uniform draws from 1-13 for both players and the community.
- Two betting rounds with the correct, **round-dependent** acting order.
- Correct `to_call`, `min_raise_to`, `max_raise_to` computation.
- All-in and side-pot handling.
- Busting and match termination.
- Correct construction of `current_hand_actions` and `recent_hands`, including the 20-hand window and string keys in `shown_numbers`.

**Test the coordinator itself.** A bug here produces confidently wrong tuning. Validate it by replaying a real `/matches/<runId>` JSON through it and checking that the chip movements match exactly.

### 5.2 Baseline opponents

Build several, since tuning against one opponent overfits to it:

| Bot | Behaviour |
|-----|-----------|
| `AlwaysCall` | Never folds, never raises. Sanity floor. |
| `AlwaysFold` | Folds to any bet. Tests that value is extracted from folds. |
| `Random` | Uniform over `legal_actions`, random legal sizing. |
| `TightValue` | Only plays numbers ≥ 9, bets pot with pairs. |
| `Maniac` | Raises aggressively regardless of number. Tests bust resistance. |
| `PotOdds` | Calls on correct pot odds, no bluffing. Reasonable baseline. |
| `Mirror` | My own strategy, self-play. Tests for exploitable leaks. |

### 5.3 Metrics to report

Run 1000 matches against each opponent and report:

| Metric | Why it matters |
|--------|----------------|
| **P(chip_delta ≥ +10)** | **The actual objective. Headline number.** |
| Median chip delta | Robust central tendency |
| Mean chip delta | Sensitive to the tail, compare against median |
| 5th / 25th / 75th / 95th percentile delta | Shape of the distribution |
| Bust rate | Fraction of matches ending at −200 |
| Illegal action count | Must be **zero** |
| Mean and p99 decision latency | Must be well under 5s |
| Fold / call / bet / raise frequency | Sanity check on aggression |
| Win rate in big blinds per 100 hands | Standard comparable measure |

### 5.4 Reading the results

A change is an improvement only if `P(chip_delta >= +10)` rises **and** bust rate does not rise materially, across **most** opponents rather than one.

With 1000 matches, the standard error on a probability near 0.7 is about 1.4 percentage points. **A change of under 3 percentage points is noise.** Do not chase it.

---

## 6. Layer 4 — Live attempts

### 6.1 Pre-flight checklist

Before spending an attempt:

- [ ] All unit and protocol tests pass.
- [ ] Simulation shows `P(delta >= +10)` above target against every baseline.
- [ ] Zero illegal actions across the full simulation suite.
- [ ] `/health` returns 200 over the public HTTPS URL.
- [ ] `/move` returns a legal action to a hand-crafted `curl` against the public URL.
- [ ] Tunnel is stable and the URL registered with the coordinator is current.
- [ ] Logging is on and writing to the ring buffer.

### 6.2 Warm-up

Cold starts are a real risk. The coordinator probes `/health` first, but if the process itself is cold, the first `/move` may exceed 5 seconds.

- Precompute all lookup tables at **import time**, not on first request.
- Hit `/move` once locally with a synthetic request before registering, so every code path is JIT-warm and every module is imported.

### 6.3 After each attempt

1. Save the result link immediately. Runs are in-memory and eventually dropped.
2. Download the raw JSON: take the replay link, swap `/game/` for `/matches/`, append `?download=1`.
3. Parse it and reconcile against the local decision log:
   - Which hands lost the most chips?
   - In those hands, what did the strategy compute, and was the decision defensible given the information available at the time?
   - Were there any substituted actions (a sign of a timeout or illegality that the tests missed)?
4. **Feed the opponent's actual play back into the simulator** as a new baseline bot. This is the highest-value use of a live attempt: it converts one match into a tuning target worth thousands of simulated matches.

### 6.4 Discipline

- **Do not rewrite the strategy after one bad run.** The guide explicitly warns that results swing hard. A −60 finish with a sound strategy is common.
- Change **one thing at a time** and re-simulate before the next live attempt.
- Best attempt counts, so a bad run costs nothing but the cooldown. The real cost is drawing the wrong conclusion from it.

---

## 7. Definition of done for Phase 1

| Criterion | Target |
|-----------|--------|
| Illegal actions in simulation | 0 across 5000+ matches |
| Illegal actions live | 0 |
| p99 decision latency | < 200 ms |
| `P(chip_delta >= +10)` vs. `PotOdds` baseline | > 0.75 |
| `P(chip_delta >= +10)` vs. every baseline | > 0.60 |
| Bust rate | < 5% |
| Live attempt | Clears +10 |

---

## 8. Regression suite

Once Phase 1 clears, freeze the full test suite and re-run it after **every** change made for Phases 2 and 3. Multiway logic and rule inference both touch shared code, and it is easy to break a working Phase 1 bot while chasing Phase 3 points.

Keep a saved set of real match JSONs as fixtures. Replaying them through the evaluator and strategy is the cheapest possible regression check.
