# STRATEGY.md — Phase 1 Decision Policy

Concrete decision rules for heads-up play under `table_rule: "standard"`.
Thresholds here are **starting values to be tuned against the simulator**, not final answers. See `TESTING.md`.

---

## 1. Objective function

The clear condition is chip delta ≥ +10 over 100 hands, pass/fail. So the quantity being maximised is:

```
P(final chip_delta >= +10)
```

**Not** expected chip delta. These come apart badly under no-limit, where a single all-in coinflip has huge variance and busting locks in −200.

Practical consequences:

1. **Small consistent edges beat large volatile ones.** +10 is roughly 5 big blinds over 100 hands. That is a very low bar and does not require aggressive play.
2. **Avoid stack-threatening spots without a clear edge.** Never put a large fraction of the stack at risk on a marginal equity edge.
3. **Once comfortably ahead late in the match, tighten.** Protecting a +40 delta is worth more than a shot at +80.

---

## 2. The equity engine

Everything reduces to one number: probability of winning the pot at showdown against one uniform random opponent number.

### 2.1 Post-reveal (community number C known, my number N)

Opponent's number is uniform on 1-13, independent.

**If N == C (I have a pair):**
```
win  = 12/13   (any opponent number other than C loses to my pair)
tie  =  1/13   (opponent also holds C)
lose =  0
```
A pair post-reveal cannot lose. Play it for maximum value.

**If N != C (no pair):**
```
lose = 1/13                              (opponent pairs C)
     + count of k in 1..13 where k > N and k != C, divided by 13
tie  = 1/13   if N != C                  (opponent holds exactly N)
win  = 1 - lose - tie
```

Worked example, N = 10, C = 5:
- Opponent pairs C by holding 5: 1 outcome, I lose.
- Opponent beats me with a higher non-pair number: 11, 12, 13 → 3 outcomes, I lose.
- Opponent ties me holding 10: 1 outcome.
- Everything else (1,2,3,4,6,7,8,9) → 8 outcomes, I win.
```
win = 8/13 = 0.615,  tie = 1/13 = 0.077,  lose = 4/13 = 0.308
```

Note the structural quirk: **C being low is good for a high hand.** If C is high, C occupies one of the slots that would otherwise beat me, but it also means a pair is available at a rank above me. Compute it exactly rather than reasoning about it.

### 2.2 Pre-reveal (C unknown, my number N)

Enumerate all 169 combinations of (opponent number, community number), each with probability 1/169, and count wins, ties and losses using the standard rule. Precompute into a 13-entry table.

Approximate results:

| N | win | tie | lose |
|---|-----|-----|------|
| 13 | 0.923 | 0.077 | 0.000 |
| 12 | 0.846 | 0.077 | 0.077 |
| 11 | 0.769 | 0.077 | 0.154 |
| 10 | 0.692 | 0.077 | 0.231 |
| 9  | 0.615 | 0.077 | 0.308 |
| 8  | 0.538 | 0.077 | 0.385 |
| 7  | 0.462 | 0.077 | 0.462 |
| 6  | 0.385 | 0.077 | 0.538 |
| 5  | 0.308 | 0.077 | 0.615 |
| 4  | 0.231 | 0.077 | 0.692 |
| 3  | 0.154 | 0.077 | 0.769 |
| 2  | 0.077 | 0.077 | 0.846 |
| 1  | 0.000 | 0.077 | 0.923 |

> These are the *marginal* numbers, ignoring the pair mechanism cancelling out. Compute the real table in code by enumeration under the active `ShowdownRule` rather than hardcoding this. The pair mechanism is symmetric so it barely moves the ordering, but the exact values matter for threshold tuning.

**N = 7 is the exact midpoint.** Above it I am a favourite, below it an underdog, and the equity gradient is linear and steep: each rank is worth about 7.7 percentage points.

### 2.3 Pot odds

```
pot_odds = to_call / (pot + to_call)
```

Call is +EV when `win + tie/2 > pot_odds`. This is the base comparison; adjustments follow.

---

## 3. Pre-reveal policy

The blinds are 1 and 2, so the pot before any action is 3. This is small relative to a 200 stack, so pre-reveal is low-stakes. **Do not over-engineer it.**

### 3.1 As the button (acting first, having paid 1)

| My number | Action |
|-----------|--------|
| 11-13 | Raise to 6 (3× big blind) |
| 8-10 | Raise to 5, or call. Prefer raising for initiative. |
| 5-7 | Call (add 1 to complete). Cheap to see the reveal. |
| 1-4 | Call. Completing costs 1 chip into a pot of 3, so folding is almost never right. |

Note: as the button I have already put in 1 and only owe 1 more. Getting 3-to-1 on a single chip means calling is correct with essentially any number. **Folding pre-reveal from the button should be extremely rare.**

### 3.2 As the big blind (acting last, having paid 2)

**If the opponent calls (`to_call == 0`):**

| My number | Action |
|-----------|--------|
| 10-13 | Raise to 6. Build the pot with an equity edge. |
| 1-9 | Check. Free reveal, no reason to inflate the pot. |

**If the opponent raises (`to_call > 0`):**

| My number | Action |
|-----------|--------|
| 12-13 | Re-raise to roughly 2.5× their raise |
| 8-11 | Call |
| 5-7 | Call if the raise is small (≤ 4× big blind), otherwise fold |
| 1-4 | Fold to anything beyond a minimum raise |

### 3.3 Facing a large pre-reveal raise

Any raise beyond about 8× the big blind pre-reveal, from a bot, is either a very strong number or a bluff. Since a single number carries at most ~92% equity and typically far less, **do not stack off pre-reveal.** Cap pre-reveal commitment at roughly 15% of stack unless holding 13.

---

## 4. Post-reveal policy

This is where the money is, because now equity is known exactly.

### 4.1 Holding a pair (N == C)

Equity is 12/13 win, 1/13 tie, 0 lose. **This hand cannot lose.**

- Acting first: bet 60-75% of pot. Betting large is fine, but betting too large folds out worse hands and wins less.
- Acting last, checked to: bet 60-75% of pot.
- Facing a bet: **raise**, to roughly 2.5-3× their bet.
- Facing a re-raise: call or shove. With zero losing outcomes, committing the stack is correct.

The only caution: a pair only occurs 1/13 of the time, so this branch is rare. Do not build the strategy around it.

### 4.2 Not holding a pair

Compute exact equity from the lookup table, then:

**Acting first (`to_call == 0`):**

| Equity | Action |
|--------|--------|
| ≥ 0.70 | Value bet, 60% of pot |
| 0.55 - 0.70 | Bet 40% of pot, or check to control the pot |
| 0.35 - 0.55 | Check |
| < 0.35 | Check, and bluff at frequency `bluff_frequency` (start at 0.15) with a 50%-pot bet |

**Facing a bet (`to_call > 0`):**

Compare adjusted equity to pot odds:

```
adjusted_equity = win + (tie / 2)
call if adjusted_equity > pot_odds + call_equity_margin
```

Start `call_equity_margin` at **0.05**. The margin exists because folding is free and calling risks chips, so a break-even call is not worth taking against an unknown opponent.

| Situation | Action |
|-----------|--------|
| `adjusted_equity > pot_odds + 0.20` and equity ≥ 0.75 | Raise for value |
| `adjusted_equity > pot_odds + 0.05` | Call |
| Otherwise | Fold |

### 4.3 The bluffing branch

Bluffing works because a hand won by a fold reveals nothing. But against an unknown bot, bluff frequency is a pure guess. Start conservative:

- Only bluff when acting **last** and checked to, and only with equity < 0.35.
- Size at 50% of pot, which needs to work 33% of the time to break even.
- Frequency 0.15, tuned by the simulator.
- **Never bluff for more than 25% of stack.** A failed large bluff is what causes busts.

Use a seeded RNG so simulator runs are reproducible.

---

## 5. Risk management

These override everything above.

### 5.1 Never bust

Chip delta of −200 is catastrophic and unrecoverable. Hard limits:

- Never commit more than 40% of stack in a single hand without equity ≥ 0.80.
- Never call an all-in without equity ≥ 0.60 unless the pot odds are overwhelming (`pot_odds < 0.30`).
- If `your_stack` drops below 60 chips, tighten every threshold by 0.10 equity. A short stack has no room to recover from a mistake.

### 5.2 Protect a lead late

Track `hand_number / total_hands` and current chip delta.

```
if hand_number > 75 and chip_delta > 25:
    tighten all thresholds by 0.08
    disable bluffing
    cap single-hand commitment at 20% of stack
```

The clear condition is +10. Sitting on +25 with 25 hands left means the correct play is to **stop taking risk**, fold marginal spots, and let the blinds cost what they cost. Twenty-five hands of blinds costs at most about 37 chips if every hand is folded, so a lead of +50 or more is nearly locked by folding everything.

### 5.3 Chase only when necessary

The mirror case:

```
if hand_number > 90 and chip_delta < 10:
    loosen thresholds
    increase bluff frequency
    accept higher variance
```

With fewer than 10 hands left and below the clear line, a safe loss and a big loss score identically (zero). Variance becomes free. **This branch is the only place where maximising expected delta is wrong in the other direction.**

---

## 6. Opponent adaptation (optional for Phase 1)

`recent_hands` gives the last 20 completed hands free on every request, including `shown_numbers` for hands that reached showdown. Cheap, useful signals:

| Signal | How to compute | How to use |
|--------|---------------|------------|
| Opponent fold frequency | Count `fold` actions by their seat in `recent_hands` | High → bluff more |
| Opponent aggression | Ratio of `bet`/`raise` to `call`/`check` | High → widen calling range, they bluff |
| Showdown number quality | Mean of their `shown_numbers` values | Low mean → they showdown weak hands, so value bet thinner |
| Bet sizing tells | Do they size differently with strong hands? Cross-reference `actions` with `shown_numbers` | Exploit directly if a pattern exists |

**Only act on these after at least 15 observed hands.** Before that, the sample is noise.

This is genuinely optional for clearing +10. Build it only if the base strategy is falling short in simulation.

---

## 7. Starting configuration values

```python
Config(
    # pre_reveal
    open_raise_min_number = 8,
    open_raise_to_bb = 3.0,
    call_raise_min_number = 8,
    threebet_min_number = 12,

    # post_reveal
    value_bet_min_equity = 0.70,
    bet_size_pot_fraction = 0.60,
    bluff_frequency = 0.15,
    call_equity_margin = 0.05,

    # risk
    max_pot_commitment_fraction = 0.40,
    protect_lead_hand_threshold = 75,
)
```

Every one of these is a knob for the simulator to sweep. Do not treat any as settled.

---

## 8. What NOT to do

- **Do not build a full game-theory-optimal solver.** The state space is tiny but the clear bar is +10 over 100 hands. Exploitative simple play is enough and far less code.
- **Do not run Monte Carlo in the request path.** Equity is closed-form. Precompute it.
- **Do not tune against a single live attempt.** Variance under no-limit is enormous. Tune against hundreds of simulated matches.
- **Do not maximise expected chip delta.** Maximise P(delta ≥ +10).
- **Do not assume the opponent bot is good.** Coordinator bots at Phase 1 are likely simple. Check `recent_hands` for exploitable patterns before assuming a tough opponent.
