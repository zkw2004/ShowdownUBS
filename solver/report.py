from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from solver.eliminate import SolveResult


def render(results: list[SolveResult]) -> str:
    lines: list[str] = []
    for result in results:
        lines += [f"codename: {result.codename}", f"  observations: {result.observations}", f"  survivors: {len(result.survivors)}"]
        if len(result.survivors) == 1:
            lines.append(f"  SOLVED: {result.survivors[0].description}")
        elif not result.survivors:
            lines.append("  CONTRADICTED: no candidate survived")
        else:
            lines.extend(f"  candidate: {candidate.rule_id} — {candidate.description}" for candidate in result.survivors[:10])
        lines.append("  elimination curve: " + " -> ".join(map(str, result.curve)))
    return "\n".join(lines)


def merge_registry(results: list[SolveResult], source_runs: list[str], path: Path = Path("data/solved_rules.json")) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(path.read_text()) if path.exists() else {"version": 1, "rules": {}}
    rules = existing.setdefault("rules", {})
    for result in results:
        old = rules.get(result.codename, {})
        if len(result.survivors) == 1:
            candidate = result.survivors[0]
            if old.get("status") == "solved" and old.get("rule_id") != candidate.rule_id:
                status = "contradicted"
            else:
                status = "solved"
            rules[result.codename] = {
                "rule_id": candidate.rule_id,
                "description": candidate.description,
                "status": status,
                "observations_used": int(old.get("observations_used", 0)) + result.observations,
                "source_runs": sorted(set(old.get("source_runs", []) + source_runs)),
                "solved_at": str(date.today()),
            }
        elif not result.survivors:
            rules[result.codename] = {**old, "status": "contradicted", "observations_used": int(old.get("observations_used", 0)) + result.observations}
    path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n")
    return existing


def grouped(observations):
    by_name = defaultdict(list)
    for observation in observations:
        by_name[observation.codename].append(observation)
    return by_name
