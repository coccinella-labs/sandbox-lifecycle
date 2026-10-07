"""v2 validation: mechanical checks, run before anything is released.

Follows the v0 and v1ord convention that rows contradicting their procedure are
quarantined rather than published. This script validates an already-collected
file and reports whether the dataset design section 9 release gate holds.

Run:  python validate_v2.py v2.jsonl
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROCEDURES = ("recover_then_wait", "wait_during_outage", "delayed_fault", "cooldown")
EXPECTED_BAGS = {
    frozenset({("sandbox_create", None), ("execute", 3), ("process_exit", 3),
               ("recover", None), ("wait", None), ("execute", 0),
               ("process_exit", 0), ("sandbox_teardown", None)})
}
EXPECTED_EVENT_COUNT = 8
EXPECTED_EXITS = [3, 0]
EXPECTED_SPLITS = ("train", "validation", "test")
EXPECTED_COLLECTOR_VERSION = "2.0.0-v2"


def check(rows: list[dict]) -> list[tuple[str, bool, str]]:
    verdicts: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        verdicts.append((name, ok, detail))

    labels = Counter(r["label"] for r in rows)
    record("four labels, balanced", set(labels) == set(PROCEDURES)
           and len(set(labels.values())) == 1,
           f"{dict(labels)}")

    record("every trace has 8 events",
           all(len(r["events"]) == EXPECTED_EVENT_COUNT for r in rows),
           f"{sorted({len(r['events']) for r in rows})}")

    exits_ok = all(
        [e["exit_code"] for e in r["events"] if e["type"] == "process_exit"] == EXPECTED_EXITS
        for r in rows
    )
    record("exit codes are [3, 0] everywhere", exits_ok, "checked")

    record("teardown clean everywhere",
           all(r["events"][-1].get("clean") is True
               and r["events"][-1]["type"] == "sandbox_teardown" for r in rows),
           "checked")

    bags = defaultdict(set)
    for r in rows:
        bags[r["label"]].add(frozenset(
            (e["type"], e.get("exit_code")) for e in r["events"]
        ))
    all_bags = set().union(*bags.values()) if bags else set()
    record("one event bag across all labels", len(all_bags) == 1,
           f"{len(all_bags)} distinct bags")

    record("one collector version",
           len({r["collector_version"] for r in rows}) == 1
           and rows[0]["collector_version"] == EXPECTED_COLLECTOR_VERSION,
           f"{sorted({r['collector_version'] for r in rows})}")

    splits = Counter(r.get("split") for r in rows)
    record("three splits present", set(splits) == set(EXPECTED_SPLITS),
           f"{dict(splits)}")

    per_split_labels = defaultdict(set)
    for r in rows:
        per_split_labels[r.get("split")].add(r["label"])
    record("every label present in every split",
           all(v == set(PROCEDURES) for v in per_split_labels.values()),
           f"{ {k: len(v) for k, v in per_split_labels.items()} }")

    repeats_per_split = defaultdict(set)
    for r in rows:
        repeats_per_split[r.get("split")].add(r["repeat"])
    disjoint = all(
            not (repeats_per_split[a] & repeats_per_split[b])
            for i, a in enumerate(EXPECTED_SPLITS)
            for b in EXPECTED_SPLITS[i + 1:]
    )
    record("no repeat index spans two splits", disjoint,
           f"{ {k: len(v) for k, v in repeats_per_split.items()} }")

    ids = [r["id"] for r in rows]
    record("identifiers unique", len(set(ids)) == len(ids), f"{len(set(ids))}/{len(ids)}")

    # Timing is retained for audit but must not be observable; confirm the
    # withheld fields are present so the release stays auditable.
    has_t = all("t" in e for r in rows for e in r["events"])
    has_dur = any("duration" in e for r in rows for e in r["events"])
    record("withheld fields retained for audit", has_t and has_dur,
           f"t={has_t} duration={has_dur}")

    return verdicts


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "v2.jsonl"
    rows = [json.loads(line) for line in open(path)]
    print(f"  {path}: {len(rows)} rows")

    quarantine = Path(path + ".quarantine.jsonl")
    qrows = [json.loads(line) for line in open(quarantine)] if quarantine.exists() else []

    print("\n  mechanical checks")
    for name, ok, detail in check(rows):
        print(f"    [{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    quarantined_ok = len(qrows) == 0
    print(f"    [{'PASS' if quarantined_ok else 'FAIL'}] "
          f"zero quarantined rows: {len(qrows)}")

    run_meta = Path(path + ".run.json")
    if run_meta.exists():
        meta = json.loads(run_meta.read_text())
        obs = meta.get("observable_set")
        print(f"    [{'PASS' if obs == ['event_type', 'exit_code'] else 'FAIL'}] "
              f"declared observable set: {obs}")

    print("\n  benchmark gate is run separately by benchmark.py --final")
    print("  this script validates the data, not the model")


if __name__ == "__main__":
    main()