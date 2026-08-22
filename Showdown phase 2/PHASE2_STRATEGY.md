# PHASE2_STRATEGY.md — Decision Policy Under Unknown Rules

Strategy adaptations for Phase 2. Everything in `STRATEGY.md` still applies structurally; what changes is that hand strength is no longer a fixed function.

Read `PHASE2_SPEC.md` for scope and `RULE_INFERENCE.md` for how rules get decoded.

---

## 1. The central shift

In Phase 1, `your_number = 12` meant something fixed and known. In Phase 2 it means nothing until the rule is known.

**Every threshold in `STRATEGY.md` that referenced a raw number must be rewritten to reference equity instead.**

```
BAD:   if your_number >= 10: raise
GOOD:  if equity >= 0.69: raise
```

The equity engine already produces the right number for whichever rule is active, because it enumerates all 169 combinations under the injected `ShowdownRule`. The strategy layer should never look at `your_number` directly except for logging.

**This is a refactor of Phase 1 strategy code, and it should happen before anything else in Phase 2.** If Phase 1 thresholds were written against raw numbers, they are silently wrong the moment the rule changes, and the failure is invisible in testing under `standard`.

### 1.1 Percentile, not equity, for some thresholds

Some rules may compress or expand the equity distribution. A rule where most numbers are near-equivalent produces a flat equity curve where 0.55 is actually a strong hand.

For thresholds that mean "play my best hands", use **percentile rank within the rule's own equity distribution** rather than an absolute equity cutoff:

```python
# precomputed per rule
percentile[n] = fraction of numbers 1..13 with equity <= equity[n]
```

Use absolute equity for pot-odds comparisons (those are genuinely absolute) and percentile for range-construction decisions (open-raising, continuing, value-betting).

---

## 2. Objective function

Per leg:

```
maximise P(leg chip_delta >= +25)
```

### 2.1 This demands more aggression than Phase 1

| | Phase 1 | Phase 2 |
|---|---|---|
| Target | +10 | +25 |
| Hands | 100 | 40 |
| Required rate | +0.1 chips/hand | **+0.625 chips/hand** |

Roughly 6x the per-hand edge, against an opponent who knows the rule.

Practical consequences:

1. **Passive grinding does not clear.** Finishing +12 scores exactly the same as finishing −180: zero.
2. **Value-bet thinner** than Phase 1. Missing value costs more when there are only 40 hands to accumulate it.
3. **The risk caps from `STRATEGY.md` section 5.1 loosen**, but only once the rule is `SOLVED`. Under `UNKNOWN` they tighten instead.
4. **Busting is still catastrophic** and forfeits the leg's 100 points, so the caps do not disappear.

### 2.2 Per-leg independence

Each leg is scored separately and stacks reset. **Do not let leg 1's result influence leg 2's play.** Being down 100 in leg 1 has zero bearing on leg 2's 100 points.

Concretely: the "chase" logic from `STRATEGY.md` 5.3 triggers on **per-leg** hand count and **per-leg** chip delta, never on cumulative attempt state.

---

## 3. Strategy by confidence tier

`RULE_INFERENCE.md` section 4.3 defines the tiers. Each maps to a distinct posture.

### 3.1 `SOLVED` — rule known from the registry

This is the normal case after reconnaissance, and should cover all 4 legs on a scoring attempt.

Play the Phase 1 policy with per-rule tuned thresholds. Everything in `STRATEGY.md` sections 3, 4 and 5 applies, with two adjustments:

- Thresholds are per-rule, loaded from the tuned config for that codename.
- Aggression is raised to match the +25 target (Section 2.1).

### 3.2 `NARROW` — 2 to 5 candidate rules survive

Use the **elementwise minimum equity across survivors**:

```python
equity_safe(n, c) = min(rule.equity(n, c) for rule in survivors)
```

This never overestimates a hand, so it cannot commit chips to a hand that is worthless under a rule still in contention.

Posture:
- Value-bet only when `equity_safe` clears the normal threshold.
- Call only when `equity_safe` beats pot odds plus margin.
- Cap single-hand commitment at 25% of stack.
- No bluffing.
- Keep calling cheap bets to reach showdowns and eliminate survivors.

### 3.3 `UNKNOWN` — rule undetermined

Full fallback mode per `RULE_INFERENCE.md` section 5. Survive and gather data.

Key point: **calling wide is correct here**, because every showdown reached eliminates candidate rules and improves every remaining hand in the leg. Cap at `to_call <= 6` or 5% of stack.

### 3.4 `CONTRADICTED` — zero survivors

Treat as `UNKNOWN`, and log loudly. This means either the candidate space is too small or the observation extraction has a bug. It should never happen on a scoring attempt if reconnaissance was done.

---

## 4. Leg management

### 4.1 Detection

```python
new_leg = (leg_number != last_seen_leg_number)
```

Also handle `leg_number is None` (single-match phases) so the same code path serves Phase 1.

### 4.2 What must reset

| State | Action on new leg |
|-------|------------------|
| Opponent model | Reset **or** carry (see 4.3) |
| Rule survivor set | **Reset.** Different rule, different codename. |
| Per-leg chip tracking | Reset |
| Bluff RNG | Fine to carry |
| Rule registry | **Never reset.** Event-wide. |

### 4.3 The opponent model is the one thing that carries

> "The same opponent plays all four legs, under the same name, and plays the same way throughout."

This is explicit and exploitable. Behavioural statistics gathered in leg 1 apply in legs 2, 3 and 4:

- fold-to-bet frequency
- aggression ratio
- bet sizing patterns
- willingness to continue without a strong hand

**But be careful about what "the same way" means.** They play the same *strategy*, and they play each rule correctly. So their observable behaviour will differ between legs because the rule differs, even though the underlying policy is constant.

Therefore:

| Carry across legs | Do not carry across legs |
|-------------------|--------------------------|
| Rule-independent tendencies: fold frequency to a given bet size, aggression ratio, sizing tells | Anything indexed by raw number, such as "they raise with 11+" |

Normalise opponent statistics by **equity percentile under the active rule**, not by raw number. Then "they open the top 30% of their range" is a statement that transfers across legs, while "they open with 10 or higher" is not.

Since `recent_hands` resets per leg, carrying an opponent model requires local state. Key it off the attempt, not `match_id`. Keep it bounded and make the bot correct if the state is entirely absent.

---

## 5. Reading the opponent as a rule oracle

The opponent knows the rule and plays it correctly. Their behaviour is therefore **evidence about the rule**, available before any showdown.

Signals:

| Observation | Inference |
|-------------|-----------|
| They bet large with a number your model rates as weak | Your model is probably wrong about that number |
| They fold a number your model rates as strong | Same |
| They consistently commit with a specific number | That number is strong under this rule |
| They fold to pressure holding a high number | High is probably not dominant under this rule |

This is softer evidence than showdowns and should never override a hard elimination constraint. But under `UNKNOWN` tier, with few showdowns available, it is meaningful.

**Implementation:** treat it as a re-weighting of the survivor set, not an elimination. A rule that makes the opponent's observed actions look absurd is less likely, but not impossible; they may be bluffing. Never eliminate a candidate on behavioural evidence alone. Only showdowns eliminate.

Keep this optional. It is a refinement, not a requirement, and reconnaissance makes it largely unnecessary.

---

## 6. Configuration

Extend the Phase 1 `Config` with per-rule overrides:

```python
@dataclass(frozen=True)
class RuleConfig:
    codename: str
    open_raise_min_percentile: float
    value_bet_min_equity: float
    bet_size_pot_fraction: float
    bluff_frequency: float
    call_equity_margin: float
    max_commitment_fraction: float

@dataclass(frozen=True)
class Phase2Config:
    default: RuleConfig
    per_rule: dict[str, RuleConfig]
    unknown_mode: RuleConfig       # the fallback posture
    recon_mode: bool
    target_delta: int = 25
    hands_per_leg: int = 40
```

Starting values for the +25-in-40 target, to be tuned:

```python
default = RuleConfig(
    open_raise_min_percentile = 0.55,   # looser than Phase 1
    value_bet_min_equity      = 0.64,   # thinner than Phase 1's 0.70
    bet_size_pot_fraction     = 0.65,
    bluff_frequency           = 0.18,
    call_equity_margin        = 0.04,   # tighter margin, more calls
    max_commitment_fraction   = 0.45,
)

unknown_mode = RuleConfig(
    open_raise_min_percentile = 0.85,
    value_bet_min_equity      = 0.90,   # effectively never
    bet_size_pot_fraction     = 0.50,
    bluff_frequency           = 0.0,
    call_equity_margin        = 0.00,   # call wide for information
    max_commitment_fraction   = 0.15,
)
```

**Tune per rule.** A rule that flattens the equity distribution needs completely different cutoffs from one that sharpens it. Do not assume one config transfers.

---

## 7. Endgame logic, per leg

Same shape as `STRATEGY.md` 5.2 and 5.3, rescaled to 40 hands and a +25 target.

```python
progress = hand_number / 40

if progress > 0.75 and chip_delta >= 35:
    # comfortably clear, protect it
    tighten all thresholds
    disable bluffing
    cap commitment at 20% of stack

if progress > 0.85 and chip_delta < 25:
    # will not clear by grinding
    loosen thresholds substantially
    raise bluff frequency
    accept high variance
```

The second branch matters more in Phase 2 than in Phase 1. With a +25 bar and 40 hands, arriving at hand 35 sitting on +8 is common, and folding to the finish scores zero. **A safe +8 and a catastrophic −190 are worth identically nothing.** Variance is free at that point and must be taken.

Guard the threshold: only enter chase mode if there is enough stack left for it to plausibly work. Chasing +25 from +8 with 12 chips left is not a strategy.

---

## 8. Testing additions

Extend the `TESTING.md` suite:

| Test | Method |
|------|--------|
| Leg reset | Simulate 4 legs; assert no state leaks except the opponent model and rule registry |
| Rule swap | Same strategy code under 5 different synthetic rules; assert legal play and no crashes under each |
| Unknown-mode survival | Play a rule absent from the registry; assert bust rate near zero across 1000 legs |
| Tier transitions | Assert the tier moves `UNKNOWN` to `NARROW` to `SOLVED` as showdowns accumulate, and that strategy responds mid-leg |
| Percentile correctness | For each rule, assert percentile ranks are consistent with that rule's equity ordering |
| Per-leg target | Report `P(delta >= +25)` per rule, not the Phase 1 `+10` metric |
| Chase mode | Assert it triggers, and measure whether it increases or decreases `P(delta >= +25)`. It may not help. Verify empirically. |

### 8.1 Synthetic rules for testing

Build 5 or 6 structurally different synthetic rules purely as test fixtures: one inverted, one partition-based, one community-relative, one with wilds, one that ignores the community number entirely, plus `standard`.

**These are test fixtures, not predictions.** Their purpose is proving the strategy code is genuinely rule-agnostic. If performance collapses under one of them, that reveals a hidden assumption baked into the strategy layer, which is exactly the bug Phase 2 punishes.

---

## 9. Order of work

1. **Refactor Phase 1 strategy to be equity-driven, not number-driven.** Verify Phase 1 performance is unchanged.
2. Add leg detection and state reset.
3. Add the tier system and `UNKNOWN` fallback mode.
4. Build synthetic test rules; verify rule-agnostic play.
5. Build the offline solver; verify it against a Phase 1 log.
6. Run reconnaissance with `recon_mode = True`.
7. Solve the four rules; populate the registry.
8. Tune per-rule configs against the simulator.
9. Spend a scoring attempt.

Steps 1 through 5 are all doable before ever spending an attempt. Do them first.
