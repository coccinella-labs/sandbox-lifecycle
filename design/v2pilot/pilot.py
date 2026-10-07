"""v2 pilot: build a tiny synthetic dataset that ATTACKTS the spec.

The pilot is not here to show that order helps. It is here to try to break
the information boundary before 4,000 rows are spent on it.

Attacks run, in order of how much they would invalidate the design:

  A1  durations carry zero information, by construction
  A2  the order-blind ceiling collapses to chance once durations are decoupled
  A3  no label pair is aliased on non-duration fields
  A4  order still helps at every cutoff, against the same-prefix baseline
  A5  the full-trace margin clears the declared threshold

Run:  python pilot.py
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

# One distribution for every duration, independent of label AND of position.
# This is the property v1ord violated and the property the whole design rests on.
DURATION_LO, DURATION_HI = 0.004, 0.060
WAIT_DURATION_LO, WAIT_DURATION_HI = 1.9, 2.1

# The four procedures, as ordered event type lists. Identical multisets, so
# counts and exit codes cannot separate them at full trace.
PROCEDURES: dict[str, list[tuple[str, int | None]]] = {
    "recover_then_wait": [
        ("sandbox_create", None), ("execute", 3), ("process_exit", 3),
        ("recover", None), ("wait", None),
        ("execute", 0), ("process_exit", 0), ("sandbox_teardown", None),
    ],
    "wait_during_outage": [
        ("sandbox_create", None), ("execute", 3), ("process_exit", 3),
        ("wait", None), ("recover", None),
        ("execute", 0), ("process_exit", 0), ("sandbox_teardown", None),
    ],
    "delayed_fault": [
        ("sandbox_create", None), ("wait", None), ("execute", 3), ("process_exit", 3),
        ("recover", None), ("execute", 0), ("process_exit", 0), ("sandbox_teardown", None),
    ],
    "cooldown": [
        ("sandbox_create", None), ("execute", 3), ("process_exit", 3),
        ("recover", None), ("execute", 0), ("process_exit", 0),
        ("wait", None), ("sandbox_teardown", None),
    ],
}

CUTOFFS = (2, 3, 4, 5, 6, 7, 8)
ROWS_PER_LABEL = 200
SEED = 20261007


def make_row(label: str, rng: random.Random, index: int) -> dict:
    events = []
    for type_, code in PROCEDURES[label]:
        ev: dict = {"type": type_}
        if type_ == "wait":
            ev["duration"] = round(rng.uniform(WAIT_DURATION_LO, WAIT_DURATION_HI), 6)
        elif type_ == "sandbox_create":
            ev["duration"] = 0.0
        elif type_ == "sandbox_teardown":
            ev["duration"] = 0.0
            ev["clean"] = True
        elif type_ in ("execute", "process_exit"):
            ev["duration"] = round(rng.uniform(DURATION_LO, DURATION_HI), 6)
        if code is not None:
            ev["exit_code"] = code
        events.append(ev)
    for i, ev in enumerate(events[:-1]):
        ev["t"] = round(sum(events[j].get("duration") or 0.0 for j in range(i)), 6)
    return {
        "id": f"v2pilot-{index:06d}",
        "source": "sandbox-lifecycle-v2-pilot",
        "collector_version": "0.0.0-pilot",
        "collected_at": "2026-10-07T00:00:00Z",
        "procedure": label,
        "events": events,
        "label": label,
    }


def build() -> list[dict]:
    rng = random.Random(SEED)
    rows = []
    for index, label in enumerate(sorted(PROCEDURES)):
        for n in range(ROWS_PER_LABEL):
            rows.append(make_row(label, rng, index * ROWS_PER_LABEL + n))
    return rows


def main() -> None:
    out = Path(__file__).resolve().parent / "pilot.jsonl"
    rows = build()
    out.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"  wrote {out} ({len(rows)} rows, {len(PROCEDURES)} labels)")

    bench = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/sbbench")
    sys.path.insert(0, str(bench))
    import numpy as np

    import ceilings
    from sbbench import features, ordered, probe

    def no_prefix_composition(row):
        """Every permitted non-order feature except the prefix composition."""
        return (
            features.order_blind_counts(row)
            + features.durations_only(row)
            + features.first_execute_duration(row)
        )

    ys = sorted({r["label"] for r in rows})
    y = np.array([ys.index(r["label"]) for r in rows])
    chance = 1.0 / len(ys)
    print(f"  chance {chance:.4f}\n")

    verdicts: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        verdicts.append((name, ok, detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    # A1: durations carry no information, by construction.
    print("A1  duration independence")
    dur_scores = probe.probe(rows, y, features.FAMILIES["durations_only"]["featurizer"])
    dur_mean = sum(dur_scores) / len(dur_scores)
    record("A1 durations_only <= 0.3000", dur_mean <= 0.30,
           f"{dur_mean:.4f} seeds {[round(s,4) for s in dur_scores]}")
    first_scores = probe.probe(rows, y, features.FAMILIES["first_execute_duration"]["featurizer"])
    first_mean = sum(first_scores) / len(first_scores)
    record("A1 first_execute_duration <= 0.3000", first_mean <= 0.30, f"{first_mean:.4f}")

    # A2: order-blind signal must come only from prefix composition, never from
    # durations. Stripping prefix composition must return the ceiling to chance.
    print("\nA2  order-blind ceiling decomposes into prefix composition only")
    declared_scores = probe.probe(rows, y, features.FAMILIES["order_blind_counts"]["featurizer"])
    declared_mean = sum(declared_scores) / len(declared_scores)
    record("A2 order_blind_counts <= 0.3000", declared_mean <= 0.30, f"{declared_mean:.4f}")
    no_prefix_scores = probe.probe(rows, y, no_prefix_composition)
    no_prefix_mean = sum(no_prefix_scores) / len(no_prefix_scores)
    record("A2 order_blind_full minus prefix composition <= 0.3000",
           no_prefix_mean <= 0.30,
           f"{no_prefix_mean:.4f} seeds {[round(s,4) for s in no_prefix_scores]}")

    # A3: no aliases on non-duration fields.
    print("\nA3  label aliasing")
    aliases = ordered.detect_aliases(rows)
    record("A3 zero aliases", not aliases, str(aliases) if aliases else "none found")

    # A4/A5: temporal probe per cutoff, measured against exact ceilings.
    print("\nA4/A5  temporal probe against exact ceilings")
    for t in CUTOFFS:
        blind_c = ceilings.blind_ceiling(rows, t)
        order_c = ceilings.order_ceiling(rows, t)
        headroom = order_c - blind_c
        sub_rows = [{"events": r["events"][:t], "label": r["label"]} for r in rows]
        gru = ordered.ordered_probe(sub_rows, y)
        gru_mean = sum(gru) / len(gru)
        print(
            f"    t={t}  blind_ceiling {blind_c:.4f}  order_ceiling {order_c:.4f}  "
            f"headroom {headroom:+.4f}  GRU {gru_mean:.4f}"
        )

        if headroom <= 1e-9:
            # Negative control: order cannot help, so the model must sit at the
            # blind ceiling. Exceeding it means information leaked.
            record(f"A4 t={t} is a negative control, GRU at blind ceiling",
                   abs(gru_mean - blind_c) <= 0.05,
                   f"GRU {gru_mean:.4f} vs blind_ceiling {blind_c:.4f}, "
                   f"headroom {headroom:+.4f}")
        else:
            captured = (gru_mean - blind_c) / headroom
            record(f"A4 t={t} captures >= 90% of headroom", captured >= 0.90,
                   f"{captured:.4f} of {headroom:+.4f}")
            if t == 8:
                record("A5 GRU(t=8) >= 0.9500", gru_mean >= 0.95, f"{gru_mean:.4f}")
                record("A5 GRU(t=8) within 0.05 of order_ceiling",
                       abs(gru_mean - order_c) <= 0.05,
                       f"GRU {gru_mean:.4f} vs order_ceiling {order_c:.4f}")

    failed = [n for n, ok, _ in verdicts if not ok]
    print(f"\n  {len(verdicts) - len(failed)}/{len(verdicts)} conditions hold")
    if failed:
        print("  DESIGN FAILS, do not collect at scale:")
        for n in failed:
            print(f"    {n}")
        sys.exit(1)
    print("  design holds on the pilot; collection is still not authorized")


if __name__ == "__main__":
    main()