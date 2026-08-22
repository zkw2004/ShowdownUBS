# PHASE3_STRATEGY.md — A Crowded Table

Phase 3 is the same game as Phase 1/2 with two changes that matter for the
bot: six seats, and you only score if you finish strictly first with `+10`.

The five named seats (Dana, Miles, Theo, Rhea, Bram) are the same bots every
leg. Their names are labels. This strategy never branches on a name. It
rebuilds a per-*seat* action profile from `recent_hands` and prices the
current hand from `current_hand_actions`.

## Objective

A 60-hand leg clears only when both hold:

1. Our chip delta is at least `+10`.
2. Our chip delta is strictly greater than every other non-busted seat.

`+49` while someone else is `+776` is a zero. Chip-EV grinding that finishes
second is the wrong objective. The bot maximises expected pot share on each
decision, then tightens only when it already leads late.

## Algorithm

Every `/move` does the same four steps.

### 1. Rank the number under the table rule

`verdigris` / `cinnabar` are standard (pair beats unpaired, high wins).
`obsidian` is inverted (unpaired low wins, pairs lose). `amaranth` keeps
pairs first, then unpaired 7, then high. Equity tables are built from the
rank function, so 13 is trash on obsidian and 7 is a premium on amaranth
without any special-case "if amaranth and number==7".

### 2. Infer a range for each opponent who is actually in the pot

`players` is the seating list, including folded and busted seats. Live
opponents are seats that are not us, not folded, and not busted.

That list is *not* the range we are facing. A raise from one seat does not
put a tight hand in every other seat. Players who have not acted yet can
still fold.

Committed opponents are seats that have `call` / `raise` / `bet` in
`current_hand_actions`. The call is priced against those seats only.

Each committed seat gets its own number-set:

- First-in open: top of the rule-ordered numbers, width from that seat's
  *position* (UTG tighter than the button), mixed with that seat's observed
  pre-reveal raise frequency from the last 20 hands.
- 3-bet: top 12–40%.
- Post-reveal bet/raise: top of the post-reveal ordering, shrunk when the
  bet is large relative to the pot, widened when that seat has been betting
  a lot.
- Call: most playable numbers, not the raiser's range.

A seat we have never seen uses the position prior, not a 13-only range.

### 3. Convert those ranges into a pot share

Against one opponent the engine already has exact win/tie/lose. Against
several opponents with *different* ranges, expected pot share is:

```
sum over subsets T of opponents
    P(we tie exactly the seats in T and beat everyone else) / (|T| + 1)
```

That is `2^n` terms, `n <= 5`. If anyone is ahead our share is 0. This is
the number `share` used below. It already includes multiway; there is no
second "add 3.5% per extra opponent" tax on top.

### 4. Take the highest-EV legal action

Facing chips:

```
call if share >= to_call / (pot + to_call) + edge
```

`to_call` is capped at our stack, so an overjam for 400 when we have 75 is
priced as calling 75 into the pot, not as 400/475. All-in spots use raw pot
odds. A 0.60 equity floor is what folded a 50% ten into a 30% pot.

Premium share (`>= 0.70`) always continues. Isolation 3-bets happen when
share is high and we are heads-up to the raiser (or the number is a lock),
so that a maniac does not get to play the fish's chips for us.

First-in at six seats is raise-or-fold, except the big blind (free check)
and a cheap small-blind complete. Limping a 4 or 6 with four people left to
act is how the chip leader prints blinds.

Unraised post-reveal: bet when share is a value hand; bluff only heads-up,
last to act, against a seat that has actually folded to bets. Facing a bet:
call or fold, never inflate a pot the table answers with a jam unless we
already have a lock.

Late in a Phase 3 leg, if we strictly lead by 25+ and are above `+10`,
`edge` goes up and bluffs turn off. If we still need the lead, `edge` goes
down. We never take a negative-EV call just because we are behind.

## Why the 150 happened

The previous policy applied the raiser's range to every live seat, then
added extra call margin per opponent, then required 60% equity to call an
all-in. That produced folds like:

- a 9 to a 6-chip open, because a player who had not acted was treated as
  holding the raiser's hand (`share ≈ 0.08`);
- a 10 into 846 at 50% equity, because 50% < 0.60;
- a 13 on amaranth to a 9-chip open, same multiway-range bug.

Those are algorithm bugs, not "Miles always jams" scripts. The same
mistakes would lose to any aggressive seat.

## Validation

`tests/test_phase3.py` covers six-seat legality, first-in opens, the live
fold leaks above, obsidian high/low, and that `showdown/` never mentions
the five names. Run:

```sh
.venv-test/bin/python -m pytest -q
```
