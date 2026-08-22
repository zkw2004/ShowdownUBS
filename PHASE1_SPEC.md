# PHASE1_SPEC.md — First Contact

Scope, target and non-goals for Phase 1 only.
See `RULES.md` for game semantics and `PROTOCOL.md` for the wire contract.

---

## 1. Setup

| Parameter | Value |
|-----------|-------|
| Opponents | **1** (heads-up against one coordinator bot) |
| Hands | **100** |
| Matches per attempt | **1** (no legs; `leg_number` and `total_legs` are `null`) |
| Starting stack | 200 chips |
| `table_rule` | `"standard"` for the entire match |
| Points available | **300** |

## 2. Clear condition

> Finish the match with a **chip delta of +10 or better**.

That is the whole phase. Pass/fail, no partial credit. Finishing at +9 scores 0, finishing at +150 scores the same 300 as finishing at +10.

**Design consequence:** the objective is **reliability of clearing +10**, not expected chip delta maximisation. A strategy that clears +10 on 70% of runs beats one that averages +40 but busts on 50% of runs.

## 3. Retries

- Retry as often as I like. **Best single attempt counts.**
- One attempt at a time per team, with a short cooldown between.
- With no cap on bet sizes, results swing hard from attempt to attempt. **Do not rewrite the strategy after one bad run.** Judge changes against many simulated runs, not one live attempt.

---

## 4. In scope for Phase 1

- Correct, always-legal protocol handling.
- Standard-rule hand evaluation (pair beats non-pair, else higher number, else split).
- Position awareness (button acts first pre-reveal, last post-reveal).
- Pot-odds based call/fold decisions.
- Value betting and a controlled bluffing frequency.
- Variance control: avoid busting, since busting locks in a flat −200.

## 5. Explicitly OUT of scope for Phase 1

Do not build these yet. They belong to later phases and add risk without adding points here.

| Deferred | Belongs to |
|----------|-----------|
| Table-rule inference from `recent_hands` | Phase 2 |
| Per-codename rule caching across matches | Phase 2 |
| Leg handling (`leg_number`, `total_legs`, per-leg state reset) | Phase 2 |
| Six-seat position logic, button skipping busted seats | Phase 3 |
| Multiway hand-strength adjustment | Phase 3 |
| Per-opponent behavioural profiling of five named bots | Phase 3 |

**However:** structure the code so these slot in later without a rewrite. Specifically, keep the showdown evaluator behind an interface keyed on `table_rule`, with `"standard"` as the only registered implementation for now. See `ARCHITECTURE.md`.

---

## 6. Exact probability facts for this phase

Because numbers are drawn **independently** from 1-13, with no deck and no card removal, the following are exact and cheap to compute.

Let `N` be my number and `C` the community number.

### 6.1 Post-reveal, C known

| Event | Probability |
|-------|-------------|
| Opponent has a pair (their number == C) | 1/13 ≈ 0.0769 |
| I have a pair | 1 if N == C, else 0 |
| Opponent's number is exactly k | 1/13 for every k in 1..13 |

If I hold a pair (N == C), I lose only to an opponent also holding C, which is a split, not a loss. **A pair post-reveal is unbeatable and can at worst tie.** Probability of the tie is 1/13.

If I do not hold a pair, I am beaten by:
- opponent pairing C: 1/13
- opponent holding a number strictly greater than N and not equal to C

### 6.2 Pre-reveal, C unknown

| Event | Probability |
|-------|-------------|
| I will pair the community number | 1/13 |
| Opponent will pair the community number | 1/13 |
| Opponent's number > mine, given N | (13 − N) / 13 |
| Opponent's number == mine | 1/13 |
| Opponent's number < mine | (N − 1) / 13 |

Pre-reveal equity is computable in closed form by enumerating all 13 × 13 = 169 combinations of (opponent number, community number) for a fixed N. This is 169 iterations, trivially inside the 5-second budget. **Prefer exact enumeration over Monte Carlo.**

### 6.3 Key structural insight

Post-reveal, every non-pair hand is decided by a single numeric comparison, and the opponent's number is uniform on 1-13 independent of everything. This means showdown equity post-reveal is a **closed-form function of (N, C)** with no simulation required. The entire hand-strength model for Phase 1 can be a precomputed 13 × 13 lookup table plus a 13-entry pre-reveal table.

---

## 7. Definition of done

1. Server returns a legal action on 100% of `/move` calls across at least 20 simulated 100-hand matches, with zero substitutions.
2. p50 response latency under 50 ms, p99 under 200 ms.
3. Median chip delta across 200+ simulated matches is comfortably above +10, and the **fraction of matches clearing +10** is the headline metric being tuned.
4. Bust rate (chip delta of −200) below a target threshold, ideally under 5%.
5. Deployed behind HTTPS, `/health` returns 200, and a live attempt completes end to end.

See `TESTING.md` for how these are measured.
