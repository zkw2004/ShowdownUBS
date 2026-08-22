# PHASE3_STRATEGY.md — A Crowded Table

Phase 3 extends the Phase 2 strategy to six-seat, multiway tables. Rules use
the same codenames and registry as Phase 2; the change is how equities,
opponent state, position, and the objective are interpreted.

## Objective

Each 60-hand leg clears only when both conditions hold:

1. Our chip delta is at least `+10`.
2. Our chip delta is strictly greater than every non-busted player’s delta.

The decision trace reports `leads_table` and `chips_needed_to_lead`, so live
attempts can be checked against this objective rather than merely whether the
bot is positive.

## Live players

`players` is always the table seating. It is not the current hand’s live
range. The implementation removes our own seat and all `folded: true` or
`busted: true` players before calculating multiway equity. A busted player is
also omitted from the standing comparison because they cannot continue in the
leg.

## Multiway equity

The Phase 2 equity engine provides exact win/tie/loss probabilities against
one opponent range. Phase 3 converts that to exact expected pot share against
all currently live opponents. To receive any share, no opponent may be ahead;
if `t` opponents tie, our share is `1 / (t + 1)`.

This is calculated analytically from the one-opponent probabilities, avoiding
an expensive enumeration of up to `13**5` possible opponent-number vectors.
The same calculation is used:

- pre-reveal against the latest raiser’s inferred range;
- post-reveal against the latest bettor/raiser’s inferred range; and
- when building rule-relative percentiles for voluntary actions.

For now, that active opponent’s inferred range is applied to every live
opponent in the pot. This is deliberately conservative; later tuning can use
one inferred range for the aggressor and wider ranges for players who checked
or called.

As a result, a number that is profitable heads-up can correctly become a fold
with several live opponents.

## Opponent reads

Phase 2’s smoothed pre-reveal raise frequency continues across all four legs.
Phase 3 additionally keeps a separate frequency bucket per seat, allowing the
bot to use the latest pre-reveal raiser or post-reveal bettor’s own history
when estimating the range it faces. The aggregate remains the fallback while
an individual has little or no history.

The five named opponents are intentionally not assigned behavioural meanings.
Their observed actions, not their names, drive the model.

## Position

For three or more non-busted seats, positional last-to-act is derived from the
live seating order:

- post-reveal: the button is last;
- pre-reveal: the second live seat after the button (the big blind) is last.

Busted seats are skipped for these calculations. The original heads-up
button/non-button logic is retained unchanged for two live seats.

## Multiway risk controls

The Phase 2 range policy remains in effect, with Phase 3 offsets:

- add `0.035` call-equity margin for every opponent beyond the first;
- add `0.04` value-equity requirement for every opponent beyond the first;
- retain rule-aware range equity, stack-risk adjustment, commitment caps, and
  unknown-rule fallback.

The stricter thresholds reflect that a bet must get through every remaining
player rather than one opponent.

## Endgame

At 75% of a Phase 3 leg, the bot protects a lead only if it is both at least
`+20` and currently strictly leads the table. At 85%, it can loosen the call
margin only if it still needs the `+10` threshold or needs chips to take the
lead. This keeps Phase 2’s independent-leg logic while applying the Phase 3
top-table condition.

## Validation

`tests/test_phase3.py` verifies that multiway equity decreases with additional
live opponents, folded/busted players are filtered, standings are computed,
and a six-seat request returns a legal action. Run the complete suite before
deploying:

```sh
pytest -q
```
