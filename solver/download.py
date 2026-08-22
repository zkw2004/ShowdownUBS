from __future__ import annotations

import json
from pathlib import Path
from urllib.request import urlopen


def download_match(run_id: str, host: str, cache_dir: Path = Path("data/matches")) -> dict:
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / f"{run_id}.json"
    url = f"{host.rstrip('/')}/matches/{run_id}?download=1"
    with urlopen(url, timeout=20) as response:  # nosec B310: user explicitly supplies coordinator host
        payload = json.loads(response.read().decode("utf-8"))
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload
