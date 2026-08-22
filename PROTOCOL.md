# PROTOCOL.md — SHOWDOWN Wire Contract

This file describes **only** the HTTP contract between the game coordinator and my bot.
No game strategy, no hand-evaluation logic. See `RULES.md` for game semantics.

---

## 1. Endpoints my server must expose

| Method | Path      | Required | Purpose |
|--------|-----------|----------|---------|
| `POST` | `/move`   | Yes      | Called every time it is my bot's turn. Must return an action. |
| `GET`  | `/health` | Optional but recommended | Warm-up probe before a match so a cold start does not eat the first move. Return HTTP 200 with any body. |

If `/health` is absent, the coordinator falls back to an `OPTIONS` probe against `/move`.

The server must be reachable over **HTTPS**. Local development is fine behind a tunnel:

```bash
cloudflared tunnel --url http://localhost:5000
# or
ngrok http 5000
```

---

## 2. Request schema (`POST /move`)

The coordinator sends a JSON body. Full example:

```json
{
  "protocol_version": 2,
  "match_id": "phase1-seed7",
  "phase": 1,
  "table_rule": "standard",
  "small_blind": 1,
  "big_blind": 2,
  "starting_stack": 200,
  "your_stack": 185,
  "hand_number": 6,
  "total_hands": 100,
  "round": "post_reveal",
  "your_number": 3,
  "community_number": 5,
  "your_seat": 0,
  "button_seat": 1,
  "pot": 32,
  "to_call": 18,
  "min_raise_to": 36,
  "max_raise_to": 185,
  "legal_actions": ["fold", "call", "raise"],
  "players": [
    {
      "seat": 0,
      "name": "you",
      "folded": false,
      "chip_delta": -8,
      "bet_this_round": 0,
      "stack": 185,
      "all_in": false,
      "busted": false
    },
    {
      "seat": 1,
      "name": "Gaston",
      "folded": false,
      "chip_delta": 8,
      "bet_this_round": 18,
      "stack": 183,
      "all_in": false,
      "busted": false
    }
  ],
  "current_hand_actions": [
    { "round": "pre_reveal",  "seat": 1, "action": "raise", "amount": 7 },
    { "round": "pre_reveal",  "seat": 0, "action": "call",  "amount": 7 },
    { "round": "post_reveal", "seat": 0, "action": "check" },
    { "round": "post_reveal", "seat": 1, "action": "bet",   "amount": 18 }
  ],
  "recent_hands": [
    {
      "hand_number": 2,
      "community_number": 13,
      "winners": [1],
      "pot": 24,
      "shown_numbers": { "0": 9, "1": 11 },
      "actions": [
        { "round": "pre_reveal",  "seat": 1, "action": "raise", "amount": 5 },
        { "round": "pre_reveal",  "seat": 0, "action": "call",  "amount": 5 },
        { "round": "post_reveal", "seat": 0, "action": "check" },
        { "round": "post_reveal", "seat": 1, "action": "bet",   "amount": 7 },
        { "round": "post_reveal", "seat": 0, "action": "call",  "amount": 7 }
      ]
    }
  ]
}
```

### 2.1 Top-level fields

| Field | Type | Meaning |
|-------|------|---------|
| `protocol_version` | int | Wire version. Currently `2`. |
| `match_id` | string | Stable for the whole match. Key any local state off this. |
| `phase` | int | Which challenge phase this match belongs to. |
| `table_rule` | string | Opaque codename for the showdown ruleset. `"standard"` in Phase 1. |
| `small_blind` / `big_blind` | int | The two forced bets. `1` and `2`. |
| `starting_stack` | int | What everyone began the match with. `200`. |
| `your_stack` | int | My live remaining chips. |
| `hand_number` / `total_hands` | int | Position within the match. |
| `round` | string | `"pre_reveal"` or `"post_reveal"`. |
| `your_number` | int | My secret number this hand, 1 to 13. |
| `community_number` | int \| null | The shared number. `null` before the reveal. |
| `your_seat` | int | My seat index. |
| `button_seat` | int | Which seat holds the button this hand. |
| `pot` | int | Chips already in the middle. |
| `to_call` | int | Chips I must add **right now** to stay in. `0` means checking is free. |
| `min_raise_to` | int \| null | Lowest legal value for `amount` on a bet/raise. `null` if I cannot bet or raise. |
| `max_raise_to` | int \| null | Highest legal value for `amount`. `null` if I cannot bet or raise. |
| `legal_actions` | string[] | **Authoritative.** Reply with one of these. |
| `players` | object[] | Seat-ordered list. I am always present under the name `"you"`. |
| `current_hand_actions` | object[] | Every action so far this hand. |
| `recent_hands` | object[] | Last 20 completed hands. |

### 2.2 `players[]` entry

| Field | Type | Meaning |
|-------|------|---------|
| `seat` | int | Seat index. |
| `name` | string | `"you"` for me. Opponent names are arbitrary and mean nothing. |
| `folded` | bool | Folded out of the current hand. Still listed. |
| `stack` | int | Live remaining chips, **updates within the hand**. |
| `chip_delta` | int | Score vs. the 200 starting stack. **Frozen at the start of the hand.** |
| `bet_this_round` | int | Chips put in this betting round. Forced bets show up here. |
| `all_in` | bool | Entire stack committed. Cannot act again this hand, still live for showdown. |
| `busted` | bool | Stack hit 0. Out of the match. |

### 2.3 `current_hand_actions[]` / `recent_hands[].actions[]` entry

| Field | Type | Meaning |
|-------|------|---------|
| `round` | string | `"pre_reveal"` or `"post_reveal"`. |
| `seat` | int | Who acted. |
| `action` | string | One of `check`, `call`, `bet`, `raise`, `fold`. |
| `amount` | int | That seat's **round total after the action**. Present for `bet`/`raise`/`call`. Absent for `check`/`fold`. |

Forced bets are **not** actions and never appear in these logs. Read `bet_this_round` instead.

### 2.4 `recent_hands[]` entry

| Field | Type | Meaning |
|-------|------|---------|
| `hand_number` | int | Which hand. |
| `community_number` | int \| null | `null` if the hand ended before the reveal. |
| `winners` | int[] | Seat numbers that took the pot. |
| `pot` | int | Size of the pot won. |
| `shown_numbers` | object | Map of seat index (as a **string** key) to the number shown at showdown. Only seats that reached showdown appear. Empty for hands won by a fold. |
| `actions` | object[] | Same shape as `current_hand_actions`. |

---

## 3. Response schema

Return **HTTP 200** with a JSON body:

```json
{"action": "raise", "amount": 24}
```

| Action | `amount` | Notes |
|--------|----------|-------|
| `check` | omit | |
| `call`  | omit | |
| `fold`  | omit | |
| `bet`   | **required** | Must be within `[min_raise_to, max_raise_to]`. |
| `raise` | **required** | Must be within `[min_raise_to, max_raise_to]`. |

`amount` is the **total I will have put in for that betting round once the action completes**, not the extra on top. If I have already put in 6 this round and want to add 18 more, I send `24`. Raise **to** 24, not **by** 24.

A missing or out-of-range `amount` is **not clamped**. It counts as an illegal move.

---

## 4. Hard constraints

| Constraint | Detail |
|------------|--------|
| Latency | Respond within **5 seconds**. |
| Status | Must be HTTP **200**. |
| Idempotency | `/move` is **never retried**. Keep it fast and side-effect-free. |
| Failure substitution | A timeout, bad response, illegal action or bad `amount` is substituted with `check`, or `fold` if checking is not legal. |
| Forfeit | **Five** substitutions in a row forfeits the match. |

### Implications for implementation

1. No blocking I/O, no external API calls, no disk writes inside the `/move` handler.
2. Wrap the entire handler in a try/except. On any internal exception, fall back to a guaranteed-legal action derived from `legal_actions` rather than letting a 500 escape.
3. Never construct an action from assumption. Always validate the chosen action against `legal_actions` and the chosen `amount` against `[min_raise_to, max_raise_to]` before returning.

---

## 5. Forward compatibility

- `players` is a **list in seat order**. Read it as a list. Do not assume a fixed length or a fixed shape.
- **Ignore any field not recognised.** Fields are added over the course of the event and never removed.
- Parse defensively: use `.get()` style access with sensible defaults rather than strict schema validation that would reject an unknown key.

---

## 6. Information I never receive

- Another player's number before showdown.
- Anything about matches other than my own.
- What any `table_rule` codename actually means.

---

## 7. Reviewing results

| Endpoint | Purpose |
|----------|---------|
| `/game/<runId>` | Replay viewer. Steps through each hand visually. |
| `/matches/<runId>` | Same match as raw JSON, with every hand, every action, and every dealt number. |
| `/matches/<runId>?download=1` | Save the match as a file. |

Take the replay link returned with a result and swap `/game/` for `/matches/` to get the JSON.

Runs are held **in memory only**. They are lost on server restart and older ones are eventually dropped. Download anything worth keeping.
