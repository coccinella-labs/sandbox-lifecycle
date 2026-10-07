"""v2 re-pilot against the revised, durations-free observable set.

The collection preflight showed real executions make duration informative, so
fallback 1 was adopted: the observable set is now event type and exit code only.
This re-runs the acceptance conditions against the 100 real preflight traces
rather than a synthetic generator, because that is the stronger evidence.

Run:  python repilot.py preflight.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bench"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ceilings  # noqa: E402
from sbbench import features, ordered, probe  # noqa: E402

CUTOFFS = (2, 3, 4, 5, 6, 7, 8)
DECLARED_BUDGET_MAX = 0.3000
GRU_MIN_T8 = 0.9500
HEADROOM_CAPTURE_MIN = 0.90
NEGATIVE_CONTROL_TOL = 0.05


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "preflight.jsonl"
    rows = [{"events": r["events"], "label": r["label"]} for r in map(json.loads, open(path))]
    labels = sorted({r["label"] for r in rows})
    y = np.array([labels.index(r["label"]) for r in rows])
    chance = 1.0 / len(labels)
    print(f"  {len(rows)} real traces, {len(labels)} procedures, chance {chance:.4f}")
    print("  observable set: event type and exit code, duration withheld\n")

    verdicts: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        verdicts.append((name, ok, detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    print("declared budget under the restricted observable set")
    for family in ("counts_only", "exit_codes_only", "order_blind_counts"):
        scores = probe.probe(rows, y, features.FAMILIES[family]["featurizer"])
        mean = sum(scores) / len(scores)
        ok = mean <= DECLARED_BUDGET_MAX
        record(f"{family} <= {DECLARED_BUDGET_MAX:.4f}", ok,
               f"{mean:.4f} seeds {[round(s, 4) for s in scores]}")

    print("\nlabel aliasing on observable fields")
    aliases = ordered.detect_aliases(rows)
    record("zero aliases", not aliases, str(aliases) if aliases else "none found")

    print("\ntemporal probe against exact ceilings, durations withheld")
    for t in CUTOFFS:
        blind_c = ceilings.blind_ceiling(rows, t)
        order_c = ceilings.order_ceiling(rows, t)
        headroom = order_c - blind_c
        sub = [{"events": r["events"][:t], "label": r["label"]} for r in rows]
        scores = ordered.ordered_probe(sub, y, use_durations=False)
        gru = sum(scores) / len(scores)
        print(f"    t={t}  blind {blind_c:.4f}  order {order_c:.4f}  "
              f"headroom {headroom:+.4f}  GRU {gru:.4f}")
        if headroom <= 1e-9:
            record(f"t={t} negative control, GRU at blind ceiling",
                   abs(gru - blind_c) <= NEGATIVE_CONTROL_TOL,
                   f"GRU {gru:.4f} vs blind {blind_c:.4f}")
        else:
            captured = (gru - blind_c) / headroom
            record(f"t={t} captures >= {HEADROOM_CAPTURE_MIN:.0%} of headroom",
                   captured >= HEADROOM_CAPTURE_MIN, f"{captured:.4f}")
            if t == 8:
                record(f"GRU(t=8) >= {GRU_MIN_T8:.4f}", gru >= GRU_MIN_T8, f"{gru:.4f}")

    failed = [n for n, ok, _ in verdicts if not ok]
    print(f"\n  {len(verdicts) - len(failed)}/{len(verdicts)} conditions hold")
    if failed:
        print("  DESIGN STILL FAILS, do not collect at scale:")
        for n in failed:
            print(f"    {n}")
        sys.exit(1)
    print("  Design holds on real traces with duration withheld.")
    print("  Collection at scale remains a separate decision and is not authorized here.")


if __name__ == "__main__":
    main()