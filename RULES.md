# RULES.md — SHOWDOWN Game Semantics

Pure game logic, decoupled from the HTTP layer. See `PROTOCOL.md` for the wire contract.

---

## 1. Match structure

- A **match** is a fixed run of hands. Stacks carry across hands within a match.
- Everyone starts a match with **200 chips**.
- **Chip delta** is the score: chips up or down against the starting 200. Finish on 230 and chip delta is `+30`.
- Hit **0 chips** and the player is **busted**. In heads-up that ends the match, and the busted player's chip delta is a flat **−200** regardless of how many hands were left.

---

## 2. Anatomy of one hand

```
1. Forced bets post automatically   (small blind 1, big blind 2)
2. Deal                             (each player gets a secret number 1-13)
3. Betting round: pre_reveal
4. Reveal                           (one shared community number, 1-13)
5. Betting round: post_reveal
6. Showdown                         (best number takes the pot)
```

**There are exactly two betting rounds.** No more.

### 2.1 Forced bets

- Posted **before** anything is dealt. Not a decision. Not an action.
- One player puts in `1` (small blind), the other puts in `2` (big blind).
- They **never appear** in `current_hand_actions`. They show up as `bet_this_round` on the `players[]` entries.
- Because the big blind is a real bet of 2, there is **always something to match** in the first betting round.
- Who pays which alternates every hand, so the cost is shared evenly.

### 2.2 The deal

- Each player gets one secret number, **1 to 13**.
- Each is drawn **independently**. Two players holding the same number is common.
- Implication: this is **not** a standard deck. There is no card removal effect. Every number 1-13 is equally likely for every player and for the community number, independent of everything else.

### 2.3 The reveal

- One shared **community number**, drawn the same way from 1 to 13, made public.
- `community_number` is `null` before this point.

---

## 3. Showdown resolution (standard rule)

Evaluated in this order:

1. **Pair beats non-pair.** If my number equals the community number, I have a pair. Any pair beats any non-pair.
2. **Otherwise the higher number wins.**
3. **Identical results split the pot.**

If everyone else folds, the remaining player **wins the pot immediately and nothing is shown**. Not their number, not the community number. This is why bluffing works: a hand won by a fold never reveals anything.

> Under `table_rule: "standard"` (all of Phase 1) the above is the complete ruleset.
> Later phases substitute a different, undisclosed showdown ruleset. See `PHASE1_SPEC.md` for scope.

### 3.1 Hand-strength ordering under standard rules

Given `your_number` = N and `community_number` = C:

```
if N == C:  PAIR      (strongest tier, all pairs equal since C is shared)
else:       HIGH      (ranked by N, 13 strongest down to 1 weakest)
```

Because C is shared, both players either pair the same number or neither does. So:
- Only one player can hold a pair unless **both** hold N == C, in which case they split.
- Absent a pair, the comparison is a straight numeric comparison of the two secret numbers.

---

## 4. The five actions

| Action | Legal when | Effect |
|--------|-----------|--------|
| `check` | `to_call == 0` | Pass without betting. Free. |
| `call`  | `to_call > 0` | Add `to_call` chips to match the current bet and stay in. |
| `bet`   | Nobody has opened this round | Open the betting. Requires `amount`. |
| `raise` | A bet already exists this round | Put in more than the current bet. Requires `amount`. |
| `fold`  | Someone has bet at me | Give up the hand and the chips already committed. |

**`legal_actions` is authoritative.** Reply with one of those and an illegal move is impossible.

`fold` only appears when someone has bet, so a hand that would have been free to see through can never be accidentally thrown away.

### 4.1 check vs. call is not a choice

`check` and `call` are **mutually exclusive** and determined entirely by `to_call`:

```
to_call == 0  ->  "check" in legal_actions, "call" NOT in legal_actions
to_call >  0  ->  "call"  in legal_actions, "check" NOT in legal_actions
```

`to_call` is purely the comparison between **the highest `bet_this_round` at the table** and **my own `bet_this_round`**. If they are equal, `to_call` is 0.

Note that `to_call` can be 0 even when I have already put chips in this round. The common case: I am the big blind, my `bet_this_round` is already 2 from the forced bet, the opponent merely calls to 2, and action returns to me facing `to_call == 0`.

### 4.2 Decision shape

The real decision is never "check or call". It is:

```
if to_call == 0:   check  or  bet
if to_call >  0:   fold   or  call  or  raise
```

---

## 5. Bet sizing

The game is **no-limit**. There is no cap on bet size. The stack is the only ceiling.

### 5.1 `amount` is a round total, not an increment

`amount` is the **total I will have put in for that betting round once the action completes**.

```
Already in 6 this round, want to add 18 more  ->  send amount = 24
```

Raise **to** 24, not **by** 24.

### 5.2 Legal range

Keep `amount` inside `[min_raise_to, max_raise_to]`. Both are sent on every request, already accounting for stack size and the minimum-raise rule.

- If `min_raise_to == max_raise_to`, betting the whole stack is the only affordable raise, and it is legal.
- Both are `null` when betting and raising are not possible.

### 5.3 All-in

- Putting the entire stack in is going **all-in**.
- If the opponent bets more than I can cover, I can still call for **everything I have** and play for the part of the pot I matched. Chips I could not cover go back to them.
- An all-in player cannot act again this hand but is still live for showdown.
- Having literally 0 chips means **busted**, not all-in. A busted player receives no further `/move` calls.

---

## 6. Position

Seats are fixed for the whole match. `your_seat` is mine. `players` comes back in seat order.

Each hand one seat holds the **button** (`button_seat`). It moves to the other seat every hand.

### 6.1 Heads-up position table

```
                     seat 0     seat 1
                               [BUTTON]

forced bet             2          1

acts pre_reveal       2nd        1st
                     (last)    (first)

acts post_reveal      1st        2nd
                    (first)     (last)
```

- The **button** pays the smaller forced bet (1) and acts **first** pre-reveal.
- After the reveal that **flips**: the button acts **last**, having watched the other player first.
- The **non-button** seat pays 2, acts **last** pre-reveal, and **first** post-reveal.

**The acting order is not the same in both betting rounds.** This reversal is the single easiest thing to get backwards. Recompute it from `your_seat` vs. `button_seat` on **every request**. Never carry it over from the previous hand.

### 6.2 Rotation

```
hand 12    button seat 0     pays 1: seat 0     pays 2: seat 1
hand 13    button seat 1     pays 1: seat 1     pays 2: seat 0
hand 14    button seat 0     pays 1: seat 0     pays 2: seat 1
```

Acting last post-reveal is an advantage because the decision is made with more information. The alternation shares that advantage evenly.

### 6.3 Why position matters for reading the opponent

The coordinator always calls when it is my turn, so the order never has to be worked out to play legally. But `button_seat` tells me which side of the table I am on this hand, which is what makes `current_hand_actions` readable. The same opponent plays very differently depending on whether they are acting first or last.

---

## 7. Worked example of a full hand

Bot is on the button (pays small blind 1), I am the big blind (pays 2).

| Step | State |
|------|-------|
| Blinds post | Bot `bet_this_round = 1`, me `bet_this_round = 2`, pot = 3 |
| Bot acts first (pre-reveal) | Bot calls, adds 1, now `bet_this_round = 2`, pot = 4 |
| My turn | `to_call = 0` because my 2 already matches. `check` is legal. |
| I check | Pre-reveal round closes. |
| Reveal | `community_number` becomes visible. |
| I act **first** (post-reveal) | Order flipped. Bot is the button so it acts last. |
| Bot acts last | It sees my action before deciding. |
| Showdown | If neither folded, best number under the table rule takes the pot. |

Next hand the button moves to me: I pay 1, act first pre-reveal, and act last post-reveal.

---

## 8. Derived facts worth encoding

1. **`chip_delta` is frozen at hand start; `stack` is live.** Do not mix them when reasoning mid-hand.
2. **Independent draws** mean exact probabilities are computable with no card-removal correction:
   - P(opponent pairs the community number) = 1/13
   - P(I pair) = 1/13
   - P(opponent's number > mine) given my number N = (13 − N) / 13
   - P(opponent's number == mine) = 1/13
3. **A fold reveals nothing**, so opponent modelling has to lean on betting patterns, not shown numbers, for folded hands.
4. `recent_hands` `shown_numbers` keys are **strings**, not ints. Cast when indexing.
5. `recent_hands` holds only the last **20** hands and resets at the start of every match.
