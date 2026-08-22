#!/usr/bin/env python3
"""Deploy verification and keep-warm for the live Showdown service.

Two jobs during a grinding session:

  wait  -- block until /health reports an expected commit, so a match is never
           started against a stale deploy
  warm  -- ping /health on an interval so a free-tier spin-down never eats the
           first move of a leg

Usage:
    python sim/service.py wait <sha>       # e.g. the output of git rev-parse --short=8 HEAD
    python sim/service.py warm             # ctrl-c to stop
    python sim/service.py status
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

DEFAULT_URL = "https://showdownubs-2.onrender.com"


def fetch_health(base_url: str, timeout: float = 30.0) -> dict:
    with urllib.request.urlopen(f"{base_url}/health", timeout=timeout) as response:
        return json.loads(response.read().decode())


def stamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def cmd_status(args: argparse.Namespace) -> int:
    try:
        health = fetch_health(args.url)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        print(f"[{stamp()}] unreachable: {error}")
        return 1
    print(f"[{stamp()}] {health}")
    return 0


def cmd_wait(args: argparse.Namespace) -> int:
    """Poll until the deployed version matches, so we never grind a stale build."""
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        try:
            health = fetch_health(args.url)
            live = str(health.get("version", "unknown"))
            if live.startswith(args.sha) or args.sha.startswith(live):
                print(f"[{stamp()}] deployed: {live}")
                return 0
            print(f"[{stamp()}] live={live} waiting for {args.sha}")
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            print(f"[{stamp()}] not up yet ({type(error).__name__})")
        time.sleep(args.interval)
    print(f"[{stamp()}] TIMED OUT after {args.timeout}s -- do not start a match")
    return 1


def cmd_warm(args: argparse.Namespace) -> int:
    print(f"[{stamp()}] keeping {args.url} warm every {args.interval}s (ctrl-c to stop)")
    while True:
        try:
            health = fetch_health(args.url)
            print(f"[{stamp()}] ok version={health.get('version', 'unknown')}")
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            print(f"[{stamp()}] PING FAILED: {error}")
        time.sleep(args.interval)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=DEFAULT_URL)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status").set_defaults(func=cmd_status)

    wait = sub.add_parser("wait")
    wait.add_argument("sha")
    wait.add_argument("--interval", type=float, default=10.0)
    wait.add_argument("--timeout", type=float, default=600.0)
    wait.set_defaults(func=cmd_wait)

    warm = sub.add_parser("warm")
    warm.add_argument("--interval", type=float, default=240.0)
    warm.set_defaults(func=cmd_warm)

    args = parser.parse_args()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print(f"\n[{stamp()}] stopped")
        return 0


if __name__ == "__main__":
    sys.exit(main())
