# SOLVER_TOOLING.md — Offline Rule Solver

Build spec for the offline analysis tooling. This is a **separate program from the bot**, run on a laptop against downloaded match logs. It never runs inside `/move`.

Companion to `RULE_INFERENCE.md`, which covers the algorithm. This file covers the program.

---

## 1. Why this is separate from the bot

| | Bot | Solver |
|---|---|---|
| Runs | Inside `/move`, 5s budget | On a laptop, unbounded |
| Information | Partial (`recent_hands` only) | Complete match log |
| Constraints | No blocking I/O, must never crash | Free to do anything |
| Output | An action | A rule registry file |

Mixing them is how the bot ends up with a 6-second solver call in the request path. **Keep them in separate top-level packages with no imports between them**, except that both import the shared `evaluator/` package.

```
showdown/          # the bot, per ARCHITECTURE.md
sim/               # the local simulator, per TESTING.md
solver/            # this file
  ├── download.py
  ├── extract.py
  ├── candidates.py
  ├── eliminate.py
  ├── disambiguate.py
  ├── report.py
  └── cli.py
shared/
  └── evaluator/   # ShowdownRule interface + implementations, imported by all three
```

---

## 2. `download.py`

Fetch and cache match logs.

```python
def download_match(run_id: str, host: str, cache_dir: Path) -> dict:
    """GET {host}/matches/{run_id}?download=1, cache to disk, return parsed JSON."""
```

**Cache aggressively and never evict.** The main guide is explicit: runs are held in memory only on the coordinator, are lost if the server restarts, and older ones are eventually dropped. A log not saved is gone permanently.

Cache path: `data/matches/{run_id}.json`. Commit these to version control. They are the raw material for every rule solved.

Also persist a small index:

```json
{
  "run_id": "...",
  "phase": 2,
  "downloaded_at": "...",
  "legs": [
    {"leg_number": 1, "table_rule": "codename_a", "hands": 40},
    {"leg_number": 2, "table_rule": "codename_b", "hands": 40}
  ],
  "notes": "recon attempt 1"
}
```

---

## 3. `extract.py`

Convert a raw match log into solver observations.

```python
@dataclass(frozen=True)
class Showdown:
    codename: str
    leg_number: int | None
    hand_number: int
    community: int | None
    numbers: dict[int, int]      # seat -> dealt number
    winners: tuple[int, ...]     # seats that took the pot

def extract(match_json: dict) -> list[Showdown]:
    ...
```

### 3.1 Rules for extraction

| Rule | Reason |
|------|--------|
| **Discard hands containing a `fold` action** | The winner was decided by the fold, not the showdown. Carries no information about the rule. |
| Detect folds from the **action log**, not from empty `shown_numbers` | The offline log may include dealt numbers for folded hands. Only the action log proves a showdown occurred. |
| Cast `shown_numbers` keys from **string to int** | The wire format uses string keys. |
| Skip hands with `community_number: null` | Those ended pre-reveal, so there is no showdown to learn from. |
| Preserve **multi-seat `winners`** | Split pots are a strong constraint: they prove two hands rank exactly equal. |
| Record `codename` per leg | Group by this. |

### 3.2 The schema is unverified

The exact shape of `/matches/<runId>` JSON is **not documented in the guides**. It is described only as "the complete hand log: every hand, every action, and the numbers every player was actually dealt".

Therefore:

1. **Write `extract.py` last**, after the first real download. Do not guess the schema.
2. On first download, dump the structure and write the extractor against what is actually there.
3. Write a schema-shape assertion so a coordinator format change fails loudly rather than silently producing zero observations.

### 3.3 Validation

`extract()` must report, per leg:

```
leg 1  codename=X   hands=40  showdowns=22  folds=18  discarded=0
```

If `showdowns + folds != hands`, something is being silently dropped. Fail rather than proceed.

---

## 4. `candidates.py`

Generate the candidate rule space. See `RULE_INFERENCE.md` section 3 for the families.

```python
def generate_candidates() -> list[ShowdownRule]:
    """Return every candidate rule. Target: low thousands."""
```

### 4.1 Requirements

- Every candidate must implement the shared `ShowdownRule` interface, so a solved rule can be dropped straight into the bot's registry with no translation.
- Every candidate must carry a **human-readable description** and a **stable identifier**, so the report is interpretable and the solved rule is reproducible.
- Generation must be **deterministic**. Same code, same candidate set, same order.

```python
@dataclass(frozen=True)
class Candidate:
    rule_id: str            # stable, e.g. "partition:parity:odd_dominant:desc:pair_wins"
    description: str        # "Odd beats even; higher wins within group; pair beats non-pair"
    rule: ShowdownRule
```

### 4.2 Must include `standard`

The standard rule must be in the candidate set. It is the correctness fixture: running the solver against a Phase 1 log must recover it uniquely.

### 4.3 Size

A few thousand candidates against ~25 observations is roughly 100k rule evaluations per leg. Instant. **Err heavily toward more candidates.** A missing candidate produces zero survivors and costs an attempt; an extra candidate costs microseconds.

---

## 5. `eliminate.py`

```python
@dataclass
class SolveResult:
    codename: str
    observations: int
    survivors: list[Candidate]
    eliminated_at: dict[str, int]   # rule_id -> observation index that killed it

def solve(observations: list[Showdown], candidates: list[Candidate]) -> SolveResult:
    ...
```

### 5.1 Prediction

```python
def predict_winners(rule: ShowdownRule, obs: Showdown) -> tuple[int, ...]:
    keys = {seat: rule.rank(n, obs.community) for seat, n in obs.numbers.items()}
    best = max(keys.values())
    return tuple(sorted(s for s, k in keys.items() if k == best))
```

A candidate survives an observation iff `predict_winners(...) == obs.winners`.

### 5.2 Track elimination provenance

Record which observation killed each candidate. When the result is zero survivors, this immediately shows whether one anomalous hand killed everything (likely an extraction bug) or whether elimination was gradual (likely a genuinely missing candidate).

### 5.3 Report the elimination curve

Survivors remaining after each observation, as a series. This answers "how many showdowns are needed" empirically and directly informs how long the live `UNKNOWN` fallback will last if it is ever needed.

---

## 6. `disambiguate.py`

For when 2 or more candidates survive.

```python
def distinguishing_cases(a: ShowdownRule, b: ShowdownRule) -> list[tuple[int, int, int]]:
    """All (n1, n2, community) where a and b disagree on the winner."""
```

Only 13 x 13 x 13 = 2197 cases. Exhaustive and instant.

Output:
- How many cases distinguish them (if very few, they may never separate in 40 hands).
- Whether the disagreements cluster on rare or common situations.
- **Which survivor is safer to assume**: for each, compute expected chip loss over the full case space if that one is chosen and the other is true. Pick the lower.

That last point is the actionable output. If two rules cannot be separated, choose the one that is cheaper to be wrong about.

---

## 7. `report.py`

Two outputs.

### 7.1 Human report

```
LEG 1  codename: <name>
  observations:  22
  survivors:      1
  SOLVED: <description>
  elimination curve: 3200 -> 412 -> 68 -> 12 -> 3 -> 1 (obs 6)

LEG 2  codename: <name>
  observations:  19
  survivors:      2
  AMBIGUOUS
    A: <description>
    B: <description>
    distinguishing cases: 84 of 2197
    safer choice: A  (expected loss 0.31 vs 0.47 chips/hand if wrong)
```

### 7.2 Machine output: the rule registry

```json
{
  "version": 1,
  "solved_at": "2026-08-22",
  "rules": {
    "<codename>": {
      "rule_id": "...",
      "description": "...",
      "status": "solved",
      "observations_used": 22,
      "survivors": 1,
      "source_runs": ["<runId>"],
      "seen_in": [{"phase": 2, "leg": 1}]
    }
  }
}
```

The bot loads this at import time and builds its registry from it.

**Persist and commit this file.** It is worth up to 1000 points across Phases 2 and 3, and the source logs it was derived from are not recoverable once the coordinator drops them.

### 7.3 Merging across runs

Later runs add codenames and add observations to existing ones. The registry writer must **merge, not overwrite**:

- A codename already `solved` and confirmed by new observations: increment counts, append the run id.
- A codename already `solved` but **contradicted** by a new observation: this is a serious signal. Either the earlier solve was wrong or the mapping is not as stable as stated. Mark `status: "contradicted"`, do not silently overwrite, and surface it loudly.
- A codename previously `ambiguous` now resolved: promote to `solved`.

---

## 8. `cli.py`

```bash
python -m solver download <runId>
python -m solver solve <runId>              # extract + eliminate + report
python -m solver solve --all                # every cached run, merged
python -m solver verify <runId>             # check registry against a log
python -m solver registry                   # print current registry
```

`verify` is the important one for scoring attempts: after a real attempt, re-run every showdown against the registered rule and assert zero contradictions. A contradiction means the bot was playing the wrong model and the leg result is explained.

---

## 9. Correctness fixtures

The solver must pass these before being trusted.

| Fixture | Expectation |
|---------|-------------|
| A real Phase 1 log | Recovers `standard` as the sole survivor |
| Synthetic log, rule known, 30 showdowns | Recovers that rule uniquely |
| Synthetic log, rule known, 5 showdowns | Returns a survivor set **containing** the true rule (may not be unique) |
| Synthetic log with one corrupted observation | Returns zero survivors, and provenance points at the corrupted one |
| Log with only folded hands | Returns zero observations, does not crash |
| Log with split pots | Split-pot constraints correctly applied |
| Rule outside the candidate space | Returns zero survivors, reported clearly, does not silently pick a wrong survivor |

The last one is the failure mode that costs an attempt: a solver that confidently returns a wrong rule is far worse than one that reports it cannot solve it.

---

## 10. Sample-size study

Run once, informs everything else.

For each synthetic rule, generate showdowns one at a time and record survivors remaining:

```
rule            obs=5   obs=10  obs=15  obs=20  obs=25  obs=30
inverted         180      22       4       1       1       1
partition_x      450      95      18       6       2       1
community_rel     88      11       2       1       1       1
```

This tells you:

1. **How many showdowns reconnaissance needs.** If most rules resolve by 20, one recon attempt at ~22 showdowns per leg is enough.
2. **How long live `UNKNOWN` mode lasts** if a novel codename appears in Phase 3.
3. **Whether calling wide during recon is worth it.** If 15 showdowns suffice and normal play produces 15, the wide-calling recon mode is unnecessary. If it needs 30, it is essential.

Do this study **before** spending the reconnaissance attempt. It determines how that attempt should be configured.
