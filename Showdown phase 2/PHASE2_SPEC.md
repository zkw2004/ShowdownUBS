# PHASE2_SPEC.md — Reading the Table

Scope, target and non-goals for Phase 2.
Builds on `PROTOCOL.md`, `RULES.md` and `ARCHITECTURE.md`, all of which still apply unchanged.
Read `PHASE1_SPEC.md` first if the Phase 1 baseline is not already built.

---

## 1. What changes from Phase 1

Exactly three things:

| Change | Detail |
|--------|--------|
| **Legs** | An attempt is **4 complete matches** played back to back, not 1. |
| **Hand count** | **40 hands per leg**, not 100. |
| **Table rule** | The **showdown ruleset is secret** and different on each leg. |

### 1.1 What does NOT change

Everything else is byte-for-byte identical to Phase 1:

- The wire protocol, every field, the 5-second budget, the substitution and forfeit rules.
- Blinds of 1 and 2, forced-bet alternation.
- Two betting rounds, `pre_reveal` and `post_reveal`.
- Button rotation and the position flip between rounds.
- `to_call` / `check` / `call` semantics.
- `amount` as a round total, `min_raise_to` / `max_raise_to` clamping.
- All-in and busting mechanics.
- Heads-up, still exactly **2 players**.

> **Only the showdown changes.** Betting, forced bets, position and sizing are identical under every rule.

**Implication for the codebase:** if `ARCHITECTURE.md` was followed and the evaluator sits behind the `ShowdownRule` interface, no strategy, sizing, protocol or position code needs to change. Phase 2 is a new evaluator plus leg handling. If any strategy code hardcoded "pair beats non-pair", fix that seam first before doing anything else.

---

## 2. Legs

An attempt is 4 legs. Each leg is a **complete, independent match**.

| Resets at the start of every leg | Value |
|----------------------------------|-------|
| Stacks | Fresh 200 for both players |
| `hand_number` | Restarts at 1 |
| `chip_delta` | Restarts at 0 |
| `recent_hands` | **Empty** |
| `table_rule` | A new codename |

New fields:

| Field | Type | Meaning |
|-------|------|---------|
| `leg_number` | int \| null | Which leg, 1-indexed. `null` in single-match phases. |
| `total_legs` | int \| null | `4` in Phase 2. `null` in single-match phases. |

**Implementation requirement:** any per-match state must be discarded when `leg_number` changes. Do not key state off `match_id` alone without checking whether `match_id` also changes between legs. Verify this on the first reconnaissance run and note the answer.

---

## 3. Table rules

Every match is played under one table rule: a modification to how the showdown is decided. Fixed for the whole match, announced in `table_rule` on **every** request.

### 3.1 What is known

- The rule is **fixed for the entire leg** and never changes mid-match.
- `table_rule` carries an **opaque codename** (the guide's non-real example is `chalcedony`). It identifies the ruleset without describing it.
- **The codename to ruleset mapping is fixed for the whole event.** The same codename always means the same ruleset, in every match, every attempt, and **every later phase**.
- The opponent **plays the rule correctly**. They know it.
- **Leg order and each leg's rule are identical on every retry.** Only the cards change.

### 3.2 What is NOT known

- What any rule is.
- How many rules exist in total.

### 3.3 The illustration that is NOT in play

The guide offers one example purely to show the shape of the thing:

> Odd numbers beat even numbers; within each group, higher still wins.

**This is explicitly not a real rule. Do not code against it.** It is included here only to establish that a rule is a reordering of which numbers beat which, not a change to betting.

### 3.4 Required behaviour

Read `table_rule` on **every request**. Do not assume it carries over from the previous request, previous hand, or previous leg. The same number can be a monster under one rule and worthless under another.

---

## 4. Scoring

| Condition | Points |
|-----------|--------|
| Per leg: `chip_delta >= +25` at the end of the leg | **100** |
| All four legs | **400** |

Points **accumulate per leg**. Clearing 2 legs scores 200. All four is not required to score.

### 4.1 The bar is harder than Phase 1

| | Phase 1 | Phase 2 |
|---|---|---|
| Target | +10 | **+25** |
| Hands available | 100 | **40** |
| Showdown rule | Known | **Unknown** |

Blinds cost roughly 1.5 chips per hand, so 40 hands of pure folding loses about 60 chips. Reaching +25 in 40 hands against an opponent who already knows the rule is a real edge requirement, not a coin flip.

**Every hand spent inferring the rule is a hand played close to blind.** That cost is the central problem of the phase, and Section 5 is how it gets eliminated.

### 4.2 Objective function

Per leg, maximise:

```
P(leg chip_delta >= +25)
```

Same reasoning as Phase 1: pass/fail per leg, so reliability beats expected value. But the bar is higher relative to the hand count, so the correct amount of aggression is **higher** than in Phase 1. Grinding a +12 over 40 hands scores zero.

---

## 5. The strategy that makes this tractable

Three facts from the guides combine into an exploit that removes almost all difficulty:

1. **"Retry as often as you like: your best single attempt counts."**
2. **"The leg order and each leg's rule are identical on every retry."**
3. **`/matches/<runId>` returns the complete hand log, including "the numbers every player was actually dealt".**

Therefore the rules do **not** have to be solved live under a 5-second clock from ~20 noisy partial observations. They are solved **offline with full information**.

### The plan

| Step | Action |
|------|--------|
| 1 | Spend one attempt on **reconnaissance**. Score is irrelevant, only the log matters. |
| 2 | Download the match JSON: take the replay link, swap `/game/` for `/matches/`, append `?download=1`. |
| 3 | Run the offline solver (`RULE_INFERENCE.md`) against every showdown in all 4 legs. |
| 4 | **Hardcode** the resulting codename to rule mapping into the evaluator registry. |
| 5 | Re-simulate and retune thresholds **per rule**. |
| 6 | Spend a real attempt with the rules known from hand 1. |

This converts "infer a hidden rule under time pressure" into "look up a dict key".

### 5.1 It compounds into Phase 3

The mapping is fixed **event-wide**, explicitly including later phases. Phase 3 uses the same codenames under the same mapping, and Phase 3 is worth **600 points**, the largest single block in the challenge.

Every rule decoded here is a rule already known there. The reconnaissance attempt pays for itself twice.

**Persist the solved mapping to a file that will not be lost.** It is worth up to 1000 points across Phases 2 and 3.

### 5.2 Assumption to verify immediately

The whole plan rests on: *leg N carries the same codename on every attempt.*

The guide states this. Verify it anyway on the second attempt by logging `(leg_number, table_rule)` pairs and comparing. It costs nothing and the plan is load-bearing on it.

Also verify, and record the answers:
- Does `match_id` change between legs, or only between attempts?
- Are all 4 codenames distinct within an attempt? (The guide says "a different table rule on each", so expected yes.)
- Does the same codename ever recur across phases? (Expected yes, in Phase 3.)

---

## 6. In scope for Phase 2

- Leg boundary detection and per-leg state reset.
- A rule registry keyed by codename, with solved rules populated.
- An **unknown-rule fallback mode** for any codename not yet in the registry.
- The offline rule solver, run against downloaded match JSON.
- Per-rule equity tables, regenerated by the same 13x13 enumeration used in Phase 1.
- Per-rule strategy threshold tuning.

## 7. Out of scope for Phase 2

| Deferred | Belongs to |
|----------|-----------|
| Six-seat position logic, button skipping busted seats | Phase 3 |
| Multiway hand-strength adjustment | Phase 3 |
| Profiling five distinct named opponents | Phase 3 |
| "Top the table" relative-scoring logic | Phase 3 |

Structure the rule registry and equity engine so Phase 3 needs no changes to either.

---

## 8. Definition of done

| Criterion | Target |
|-----------|--------|
| Illegal actions | 0, live and simulated |
| Leg reset correctness | Verified: no state leaks across `leg_number` changes |
| Rules solved | All 4 codenames from the reconnaissance run resolved to a unique rule |
| Solver confidence | Each rule survives elimination as the **only** candidate, or the ambiguity is documented |
| Simulated `P(delta >= +25)` per rule | > 0.60 against the modelled opponent |
| Unknown-rule fallback | Never busts in simulation against an unseen rule |
| Live | At least 2 legs cleared, targeting 4 |
