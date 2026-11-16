"""Compare two snapshots and report what changed.

Reads only the local snapshot files. It never talks to GHL.
Run:  python diff.py                       (compares the two newest snapshots)
      python diff.py OLD_FOLDER NEW_FOLDER  (compare two specific ones)
The report is printed and saved to reports/.
(The viewer's "Changes" page uses the same code.)
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SNAPSHOTS = ROOT / "snapshots"
REPORTS = ROOT / "reports"

FIELD_FILES = {
    "custom_fields_contact": "Contact custom fields",
    "custom_fields_opportunity": "Opportunity custom fields",
    "custom_fields_business": "Company (business) custom fields",
}
# Timestamps change without anyone editing anything, so they are not "changes"
IGNORE_KEYS = {"id", "name", "dateAdded", "dateUpdated", "createdAt", "updatedAt"}

# One change = (kind, text). Kinds: Added, Deleted, Renamed, Changed, Reordered
Change = tuple[str, str]


def list_snapshots() -> list[Path]:
    """All snapshot folders, oldest first."""
    if not SNAPSHOTS.exists():
        return []
    return sorted(d for d in SNAPSHOTS.iterdir() if d.is_dir())


def load(folder: Path, name: str):
    path = folder / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def short(value) -> str:
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= 80 else text[:77] + "..."


def diff_items(old: list, new: list, label, skip_keys=frozenset()) -> list[Change]:
    """Match items by id and list added / deleted / renamed / changed."""
    o = {i["id"]: i for i in old if i.get("id")}
    n = {i["id"]: i for i in new if i.get("id")}
    changes = []
    for i in sorted(n.keys() - o.keys(), key=lambda k: n[k].get("name") or ""):
        changes.append(("Added", label(n[i])))
    for i in sorted(o.keys() - n.keys(), key=lambda k: o[k].get("name") or ""):
        changes.append(("Deleted", label(o[i])))
    for i in sorted(o.keys() & n.keys(), key=lambda k: n[k].get("name") or ""):
        a, b = o[i], n[i]
        if a.get("name") != b.get("name"):
            changes.append(("Renamed", f'"{a.get("name")}" → "{b.get("name")}"'))
        for k in sorted((set(a) | set(b)) - IGNORE_KEYS - set(skip_keys)):
            if a.get(k) != b.get(k):
                changes.append(("Changed", f'"{b.get("name")}" `{k}`: {short(a.get(k))} → {short(b.get(k))}'))
    return changes


def field_label(f: dict) -> str:
    return f'"{f.get("name")}" ({f.get("dataType")}, `{f.get("fieldKey")}`)'


def diff_pipelines(old: list, new: list) -> list[Change]:
    changes = diff_items(old, new, lambda p: f'pipeline "{p.get("name")}" ({len(p.get("stages") or [])} stages)',
                         skip_keys={"stages"})
    o = {p["id"]: p for p in old if p.get("id")}
    for p in new:
        if p.get("id") not in o:
            continue
        old_stages, new_stages = o[p["id"]].get("stages") or [], p.get("stages") or []
        stage_changes = diff_items(old_stages, new_stages, lambda s: f'stage "{s.get("name")}"', skip_keys={"position"})
        # Order check: same stages, different order
        common = {s.get("id") for s in old_stages} & {s.get("id") for s in new_stages}
        old_order = [s.get("name") for s in old_stages if s.get("id") in common]
        new_order = [s.get("name") for s in new_stages if s.get("id") in common]
        if old_order != new_order:
            stage_changes.append(("Reordered", "stages: " + " → ".join(new_order)))
        changes += [(kind, f'[{p.get("name")}] {text}') for kind, text in stage_changes]
    return changes


def compare(old_dir: Path, new_dir: Path) -> list[tuple[str, list[Change]]]:
    """Return sections like [("Pipelines", [("Added", "..."), ...]), ...]. Empty list = no changes."""
    sections = []
    for name, title in FIELD_FILES.items():
        old, new = load(old_dir, name), load(new_dir, name)
        if old is not None and new is not None:
            changes = diff_items(old, new, field_label)
            if changes:
                sections.append((title, changes))
    old, new = load(old_dir, "pipelines"), load(new_dir, "pipelines")
    if old is not None and new is not None:
        changes = diff_pipelines(old, new)
        if changes:
            sections.append(("Pipelines", changes))
    return sections


def render_report(old_dir: Path, new_dir: Path, sections) -> str:
    report = [f"# GHL changes: {old_dir.name} → {new_dir.name}", ""]
    if not sections:
        report.append("No changes.")
    else:
        report.append(f"{sum(len(c) for _, c in sections)} change(s).")
        for title, changes in sections:
            report += ["", f"## {title}", *[f"- {kind}: {text}" for kind, text in changes]]
    return "\n".join(report) + "\n"


def main() -> int:
    if len(sys.argv) == 3:
        old_dir, new_dir = SNAPSHOTS / sys.argv[1], SNAPSHOTS / sys.argv[2]
    else:
        folders = list_snapshots()
        if len(folders) < 2:
            print("Need at least 2 snapshots. Run: python collect.py")
            return 1
        old_dir, new_dir = folders[-2], folders[-1]
    for d in (old_dir, new_dir):
        if not d.is_dir():
            print(f"Snapshot folder not found: {d}")
            return 1

    text = render_report(old_dir, new_dir, compare(old_dir, new_dir))
    print(text)
    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f"{old_dir.name}_to_{new_dir.name}.md"
    out.write_text(text, encoding="utf-8")
    print(f"Saved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
