from __future__ import annotations

import argparse
import json
from pathlib import Path

from solver.candidates import generate_candidates
from solver.download import download_match
from solver.eliminate import solve
from solver.extract import extract
from solver.report import grouped, merge_registry, render


def _solve_file(path: Path):
    observations = extract(json.loads(path.read_text()))
    candidates = generate_candidates()
    return [solve(codename, items, candidates) for codename, items in grouped(observations).items()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Decode Showdown Phase 2 table rules")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("download")
    fetch.add_argument("run_id")
    fetch.add_argument("--host", required=True)
    solve_parser = sub.add_parser("solve")
    solve_parser.add_argument("run_id", nargs="?")
    solve_parser.add_argument("--all", action="store_true")
    sub.add_parser("registry")
    args = parser.parse_args()
    if args.command == "download":
        download_match(args.run_id, args.host)
        return
    if args.command == "registry":
        path = Path("data/solved_rules.json")
        print(path.read_text() if path.exists() else "{\"version\": 1, \"rules\": {}}")
        return
    paths = sorted(Path("data/matches").glob("*.json")) if args.all else [Path("data/matches") / f"{args.run_id}.json"]
    results = [result for path in paths for result in _solve_file(path)]
    print(render(results))
    merge_registry(results, [path.stem for path in paths])


if __name__ == "__main__":
    main()
