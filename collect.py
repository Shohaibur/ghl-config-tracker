"""Save a snapshot of the GHL sub-account to snapshots/YYYY-MM-DD/.

Read-only. If any request fails, nothing is saved (no half snapshots).
Run:  python collect.py
"""

import json
import sys
from datetime import date
from pathlib import Path

from ghl.client import GHLClient, GHLError
from ghl.collectors import MODELS, get_custom_fields, get_pipelines

ROOT = Path(__file__).resolve().parent


def main() -> int:
    # 1. Collect everything into memory first
    try:
        client = GHLClient()
        data = {}
        for model in MODELS:
            print(f"Custom fields: {model}")
            data[f"custom_fields_{model}"] = get_custom_fields(client, model)
            print(f"  {len(data[f'custom_fields_{model}'])} fields")
        print("Pipelines")
        data["pipelines"] = get_pipelines(client)
        for p in data["pipelines"]:
            print(f"  {p.get('name')}  ({len(p.get('stages') or [])} stages)")
    except GHLError as e:
        print(f"\nFAILED: {e}\nNo snapshot saved.")
        return 1

    # 2. Save to snapshots/YYYY-MM-DD/ (running twice in a day overwrites that day)
    out = ROOT / "snapshots" / date.today().isoformat()
    out.mkdir(parents=True, exist_ok=True)
    for name, items in data.items():
        path = out / f"{name}.json"
        path.write_text(json.dumps(items, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        print(f"Saved {path}")

    print(f"\nDone. Snapshot is in: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
