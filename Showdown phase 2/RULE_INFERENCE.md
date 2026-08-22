# RULE_INFERENCE.md — Decoding Table Rules

How to determine what a `table_rule` codename means. This is the core technical problem of Phase 2.

Two separate systems are described here:

| System | When it runs | Difficulty |
|--------|-------------|------------|
| **Offline solver** | On a laptop, after an attempt, with full information and no clock | The primary approach |
| **Live inference** | Inside `/move`, from partial observations | Backup only |

**Build the offline solver first.** Live inference is a fallback for codenames never seen before, and should never be the main path.

---

## 1. What a rule is, formally

From the spec: "Only the showdown changes: betting, forced bets, position and sizing are identical under every rule."

So a rule is a pure function:

```
rank : (number: int 1..13, community: int|None) -> comparable key
```

Higher key wins. Equal keys split the pot. That is the entire surface area.

The illustration the guide gives (odd beats even, then higher within group, **not a real rule**) fits this shape: it maps a number to `(parity_class, number)`. Real rules will have a different shape but the same signature.

**A rule may or may not use `community`.** The standard rule uses it only for the pair check. A rule could ignore it entirely, or make it central (for example, distance from the community number). Do not assume either way.

---

## 2. The offline solver (primary approach)

### 2.1 Input

Download the raw match log:

```
# take the replay link returned with a result
https://<host>/game/<runId>
# swap /game/ for /matches/ and append ?download=1
https://<host>/matches/<runId>?download=1
```

This contains, per the main guide, "every hand, every action, and the numbers every player was actually dealt". That is **full information**, including hands that ended in a fold and never reached showdown.

Whether folded hands include the dealt numbers should be checked on the first download. If they do, the sample size roughly doubles, though only hands that reached showdown carry a **labelled winner**, which is what the solver actually needs.

### 2.2 Extracting observations

For every hand that reached showdown, produce one observation:

```python
@dataclass(frozen=True)
class Showdown:
    codename: str          # table_rule for that leg
    leg_number: int
    hand_number: int
    community: int | None  # None if the hand ended pre-reveal
    numbers: dict[int, int]   # seat -> dealt number
    winners: list[int]        # seat numbers that took the pot
```

Group observations by `codename`. Each group is solved independently.

**Discard hands won by a fold.** They carry no information about the rule: the winner is determined by the fold, not the showdown. Detect these by checking for a `fold` action in the hand's action log, not by checking whether `shown_numbers` is empty, since the offline log may populate numbers regardless.

Expect roughly 15 to 25 usable observations per leg out of 40 hands.

### 2.3 The elimination algorithm

```
candidates = generate_candidate_rules()          # see Section 3

for obs in observations_for_this_codename:
    survivors = []
    for rule in candidates:
        if rule.predicts(obs) == obs.winners:
            survivors.append(rule)
    candidates = survivors

report(candidates)
```

`rule.predicts(obs)` computes `rank(n, c)` for each seat's number and returns the seat(s) with the maximum key, handling ties as a split.

### 2.4 Interpreting the result

| Survivors | Meaning | Action |
|-----------|---------|--------|
| Exactly 1 | Solved | Register it |
| 0 | The candidate space does not contain the true rule, **or** there is a bug in observation extraction | Widen the space; first re-verify extraction against a known-standard Phase 1 log |
| 2 or more | Underdetermined by this data | See 2.5 |

**Zero survivors is the important failure case.** Before widening the candidate space, sanity-check the solver by running it against a Phase 1 match log where the rule is known to be `standard`. If it does not uniquely recover the standard rule, the bug is in extraction, not in the candidate space.

### 2.5 Disambiguating multiple survivors

If two rules survive, they agree on every observed showdown but differ somewhere. Find where:

```python
def find_distinguishing_case(rule_a, rule_b):
    for n1 in range(1, 14):
        for n2 in range(1, 14):
            for c in range(1, 14):
                if rule_a.winner(n1, n2, c) != rule_b.winner(n1, n2, c):
                    yield (n1, n2, c)
```

There are only 13 x 13 x 13 = 2197 cases, so this is instant.

If the distinguishing cases are rare number combinations, they may not have come up in 40 hands. Options:

1. **Run a second reconnaissance attempt.** Fresh cards, same rules. More observations, likely resolving it.
2. **Pick the survivor that is safer to be wrong about.** Prefer the rule under which your intended strategy loses least if the other is true.
3. **Note the ambiguity and handle it live**: if a showdown contradicts the chosen survivor, switch to the other immediately and log it loudly.

### 2.6 Solver output

Write to a **persisted file**, not just stdout:

```json
{
  "chalcedony": {
    "description": "human-readable statement of the rule",
    "implementation": "module path or serialised form",
    "observations_used": 22,
    "survivors": 1,
    "solved_at": "2026-08-22",
    "seen_in": ["phase2 leg1"]
  }
}
```

This file is worth up to **1000 points** across Phases 2 and 3. Commit it. Back it up. Runs are held in memory only on the coordinator and are eventually dropped, so the source data is not recoverable later.

---

## 3. The candidate rule space

Generate broadly. The cost of an extra candidate is one function evaluation per observation, which is nothing. The cost of a missing candidate is zero survivors and a wasted attempt.

**Do not code against any specific hypothesis below as if it were the answer.** These are a generator, not a prediction. The real rules are unknown.

### 3.1 Families to generate

| Family | Parameterisation |
|--------|-----------------|
| Ordering inversions | higher wins; lower wins |
| Pair semantics | pair wins; pair loses; pair is neutral; only specific numbers pair |
| Partitions | odd/even, high-half/low-half, primes, multiples of k, a designated subset; either side may dominate; secondary ordering higher or lower |
| Community-relative | closest to community wins; furthest wins; must beat community; must be under community; wraps modulo 13 |
| Arithmetic | rank by `(n + c) % 13`, `abs(n - c)`, `(n * c) % 13`, `n XOR c` |
| Wild / special numbers | one or more numbers always win, always lose, or count as any value |
| Wrapped ordering | 1 beats 13 (ace-low style wrap), otherwise higher wins |
| Threshold rules | numbers above/below a cutoff form a dominant class |
| Composite | any partition combined with any secondary ordering |

### 3.2 Systematic generation

Beyond named families, generate rules structurally:

```python
# every rule of the form: primary class, then secondary ordering
for partition in ALL_PARTITIONS:           # parametrised families above
    for dominant_side in [0, 1]:
        for secondary in [ASCENDING, DESCENDING]:
            for pair_effect in [WINS, LOSES, NEUTRAL]:
                yield CompositeRule(partition, dominant_side, secondary, pair_effect)
```

This produces a few thousand candidates, which is trivially cheap against ~20 observations.

### 3.3 The brute-force fallback

If the structured space yields zero survivors, fall back to learning the **ranking directly** with no assumed structure.

Treat the rule as an unknown total preorder over the 13 numbers, possibly conditioned on the community number. Each showdown observation is a constraint:

```
observation: n1=4, n2=11, c=7, winner=seat holding 4
constraint:  rank(4, 7) > rank(11, 7)
```

Collect constraints and solve as a partial order (topological ordering over the observed pairs). This will not fully determine the rule from 20 observations, but it will produce a **partial ordering** good enough to play, and it makes no structural assumption at all.

Represent the learned partial order as a 13x13 dominance matrix per community value, defaulting unknown comparisons to "unknown" rather than guessing. The strategy layer can then treat unknown matchups as coinflips.

---

## 4. Live inference (fallback only)

Runs inside the bot when `table_rule` is not in the registry. Should be rare after reconnaissance. Must never be the main path.

### 4.1 Data source

`recent_hands` supplies the last 20 completed hands on every request, free. Per the protocol, each entry has `community_number`, `winners` and `shown_numbers`.

Critical details:
- `shown_numbers` keys are **strings**. Cast to int.
- Only seats that reached showdown appear. A hand won by a fold shows nothing, and that hand's `community_number` is `null` too if it ended before the reveal.
- `recent_hands` **resets at the start of every leg**. There is no cross-leg accumulation.

### 4.2 Live algorithm

Reuse the offline elimination directly, seeded from `recent_hands` on each request. The candidate set is a few thousand rules and observations number under 20, so a full re-run is well inside the 5-second budget. Measure it; if it is not, precompute the candidate set at import time and cache the survivor set keyed by `(codename, len(recent_hands))`.

**Do not maintain incremental state for this.** `recent_hands` is already the complete available history for the leg, and recomputing from scratch each request is stateless, restart-safe and simpler.

### 4.3 Confidence tiers

Drive strategy off how well determined the rule is:

| Survivors | Tier | Strategy posture |
|-----------|------|-----------------|
| 1 | `SOLVED` | Play the rule normally |
| 2 to 5 | `NARROW` | Use the equity **minimum** across survivors. Play tight but not passive. |
| > 5 | `UNKNOWN` | Fallback mode, Section 5 |
| 0 | `CONTRADICTED` | Fallback mode, and log loudly. Either a bug or the space is too small. |

Using the pessimistic equity across survivors is the key idea in `NARROW`: it never overestimates a hand, so it cannot be trapped into committing chips on a hand that is worthless under a rule still in contention.

---

## 5. Unknown-rule fallback mode

Behaviour when the rule is not determined. The goal is **survive the leg without busting while gathering observations**, not to win it.

### 5.1 Rules of engagement

| Rule | Rationale |
|------|-----------|
| Never commit more than 15% of stack in one hand | A wrong rule model makes every equity estimate meaningless |
| Never call an all-in | Cannot evaluate it |
| Never bluff | Bluffing requires knowing what the opponent fears |
| Fold to any large bet | No basis to call |
| Call small bets when cheap | **See 5.2** |
| Check whenever `to_call == 0` | Free |

### 5.2 Calling wide is correct while unknown

Every hand that **reaches showdown** produces a labelled observation. Every hand that ends in a fold produces nothing.

So during `UNKNOWN` tier, calling is worth more than its chip EV, because it buys information that improves every subsequent hand in the leg. Call small bets that a Phase 1 strategy would fold.

Cap this: cheap calls only, defined as `to_call <= 6` or `to_call / your_stack <= 0.05`, whichever is tighter. Information is worth chips, but not the leg.

**Note the asymmetry.** On a **reconnaissance attempt**, where score is irrelevant, this should be turned up to maximum: call almost everything, since every showdown is pure profit in information and chips do not matter at all. On a **scoring attempt**, cap it as above.

Expose this as a config flag: `recon_mode: bool`.

### 5.3 Exiting fallback

Re-evaluate the tier on every request. The moment survivors drop to 1, switch to normal play mid-leg. Do not wait for a hand boundary.

---

## 6. Integration with the existing evaluator

`ARCHITECTURE.md` already defines the seam:

```python
class ShowdownRule(Protocol):
    codename: str
    def rank(self, number: int, community: int | None) -> tuple: ...
```

Phase 2 changes:

```python
# registry.py
RULES: dict[str, ShowdownRule] = {
    "standard": StandardRule(),
    # populated from the solved-rules file
}

def get_rule(codename: str) -> tuple[ShowdownRule | None, Tier]:
    if codename in RULES:
        return RULES[codename], Tier.SOLVED
    return None, Tier.UNKNOWN
```

**Change from Phase 1:** an unknown codename must **no longer silently fall back to standard**. In Phase 1 that was safe because standard was the only rule. In Phase 2, playing standard under a different rule is actively harmful, and worse than playing scared. Return `UNKNOWN` and let the strategy layer enter fallback mode.

### 6.1 Equity regeneration

The Phase 1 equity engine enumerated all 13x13 combinations in closed form. That generalises for free: pass a different `ShowdownRule` and re-run the same enumeration.

**Precompute one equity table per registered rule at import time.** Thirteen rules at 169 entries each is nothing. The request path stays a dictionary lookup.

For `NARROW` tier, compute the elementwise minimum equity across surviving rules and cache that too, keyed by the survivor set.

---

## 7. Reconnaissance attempt protocol

The single highest-value action in Phase 2.

### 7.1 Configuration

```python
Config(
    recon_mode = True,
    # maximise showdowns reached
    fold_threshold = None,        # never fold when calling is affordable
    bluff_frequency = 0.0,        # bluffs win pots without showdowns, useless here
    max_commitment_fraction = 0.10,   # do not bust; a busted leg stops producing data
)
```

**The objective is number of showdowns reached, not chips.** Score is irrelevant because best attempt counts.

**But do not bust.** A busted leg ends early and stops producing observations. Busting in leg 2 costs the observations for legs 2, 3 and 4 if the attempt terminates, so keep single-hand commitment low even while calling wide.

### 7.2 Checklist

- [ ] `recon_mode` enabled
- [ ] Local decision log capturing `(leg_number, table_rule, hand_number, my_number, community, action)` for every request
- [ ] Verify all 4 codenames are distinct and record them in leg order
- [ ] Record whether `match_id` changes between legs
- [ ] Save the result link **immediately**
- [ ] Download `/matches/<runId>?download=1` **immediately**, since runs are dropped over time
- [ ] Run the solver, confirm each leg resolves to a unique survivor
- [ ] Run the solver against a known Phase 1 log first, as a correctness check

### 7.3 Second reconnaissance attempt

Worth running if any leg has more than one survivor. Fresh cards under the same rules produce new observations, and the distinguishing cases found in 2.5 tell you exactly what to look for.

---

## 8. Testing the solver

| Test | Method |
|------|--------|
| Recovers a known rule | Run against a Phase 1 log; must yield `standard` as the sole survivor |
| Recovers a synthetic rule | Generate 20 synthetic showdowns under a chosen rule; must recover it uniquely |
| Handles fold-ended hands | Inject hands with no showdown; must be discarded, not crash |
| Handles null community | Hands ending pre-reveal must not corrupt observations |
| Handles string keys | `shown_numbers` keyed by string must parse |
| Handles split pots | Multiple entries in `winners` must be matched correctly |
| Sample size sensitivity | Measure survivors vs. observation count, from 5 to 40, per candidate rule; tells you how many showdowns are needed |

The last one is worth doing properly. It answers "how much recon is enough" empirically instead of by guess.
