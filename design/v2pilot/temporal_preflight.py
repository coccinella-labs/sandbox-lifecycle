"""Temporal preflight at the sample size the specification requires.

200 repeats x 4 procedures = 800 real traces. This is not v2 collection and is
not labelled as such. Its sole question is:

    Does the order signal remain measurable on real executions once the
    temporal probe has the 200 rows per label that the information boundary
    spec requires?

It deliberately does NOT re-test the observable-set claim. That belongs to the
100-trace preflight, which established order_blind_counts at 0.2500 with zero
aliases after duration was withheld. Re-running it here at 200 repeats would
produce a larger sample of a question that is already closed, and would invite
the 800-trace result to retroactively become evidence for it.

Verdict mapping:
  pass                      -> proceed to the actual v2 collection design
  short only from undertraining -> investigate probe and training budget
  order-blind baselines rise -> another leak, v2 stays unauthorized
  ordering signal disappears -> the real task does not support the claim

Run:  python temporal_preflight.py temporal_preflight.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bench"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ceilings  # noqa: E402
from sbbench import ordered  # noqa: E402

CUTOFFS = (2, 3, 4, 5, 6, 7, 8)
HEADROOM_CAPTURE_MIN = 0.90
GRU_MIN_T8 = 0.9500
NEGATIVE_CONTROL_TOL = 0.05
MIN_ROWS_PER_LABEL = 200


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "temporal_preflight.jsonl"
    raw = [json.loads(line) for line in open(path)]
    labels = sorted({r["label"] for r in raw})
    rows = [{"events": r["events"], "label": r["label"]} for r in raw]
    y = np.array([labels.index(r["label"]) for r in rows])
    per_label = len(rows) // len(labels)
    chance = 1.0 / len(labels)
    print(f"  {len(rows)} real traces, {len(labels)} procedures, "
          f"{per_label} repeats each, chance {chance:.4f}")

    if per_label < MIN_ROWS_PER_LABEL:
        print(f"  BELOW SPEC MINIMUM of {MIN_ROWS_PER_LABEL} rows per label.")
        print("  A shortfall here is a training-budget result, not a dataset result.")
        sys.exit(2)

    print("  observable set: event type and exit code, duration withheld")
    print("  question: does ordering remain measurable on real executions?\n")

    verdicts: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        verdicts.append((name, ok, detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    for t in CUTOFFS:
        blind_c = ceilings.blind_ceiling(rows, t)
        order_c = ceilings.order_ceiling(rows, t)
        headroom = order_c - blind_c
        sub = [{"events": r["events"][:t], "label": r["label"]} for r in rows]
        scores = ordered.ordered_probe(sub, y, use_durations=False)
        gru = sum(scores) / len(scores)
        print(f"    t={t}  blind {blind_c:.4f}  order {order_c:.4f}  "
              f"headroom {headroom:+.4f}  GRU {gru:.4f}  "
              f"seeds {[round(s, 4) for s in scores]}")
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
        print("  TEMPORAL PREFLIGHT FAILS:")
        for n in failed:
            print(f"    {n}")
        sys.exit(1)
    print("  Order signal is measurable on real executions at spec sample size.")
    print("  This clears the temporal question only. It does not authorize v2")
    print("  collection, and it does not re-test the observable-set claim, which")
    print("  remains owned by the 100-trace preflight.")


if __name__ == "__main__":
    main()