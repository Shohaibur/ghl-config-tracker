"""Save a snapshot of the GHL sub-account to snapshots/YYYY-MM-DD_HHMM/.

Read-only. If any request fails, nothing is saved (no half snapshots).
Run:  python collect.py
(The viewer's "Take a new snapshot now" button uses the same code.)
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from ghl.client import GHLClient, GHLError
from ghl.collectors import MODELS, get_custom_fields, get_pipelines

ROOT = Path(__file__).resolve().parent
SNAPSHOTS = ROOT / "snapshots"


def collect_all(client: GHLClient, log=print) -> dict:
    """Read everything into memory first. Raises GHLError if any request fails."""
    data = {}
    for model in MODELS:
        log(f"Custom fields: {model}")
        data[f"custom_fields_{model}"] = get_custom_fields(client, model)
        log(f"  {len(data[f'custom_fields_{model}'])} fields")
    log("Pipelines")
    data["pipelines"] = get_pipelines(client)
    for p in data["pipelines"]:
        log(f"  {p.get('name')}  ({len(p.get('stages') or [])} stages)")
    return data


def save(data: dict, log=print) -> Path:
    """Write to snapshots/YYYY-MM-DD_HHMM/ (date + time, so you can take several a day)."""
    out = SNAPSHOTS / datetime.now().strftime("%Y-%m-%d_%H%M")
    out.mkdir(parents=True, exist_ok=True)
    for name, items in data.items():
        path = out / f"{name}.json"
        path.write_text(json.dumps(items, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        log(f"Saved {path}")
    return out


def take_snapshot(client: GHLClient | None = None, log=print) -> Path:
    client = client or GHLClient()
    return save(collect_all(client, log), log)


def main() -> int:
    try:
        out = take_snapshot()
    except GHLError as e:
        print(f"\nFAILED: {e}\nNo snapshot saved.")
        return 1
    print(f"\nDone. Snapshot is in: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
