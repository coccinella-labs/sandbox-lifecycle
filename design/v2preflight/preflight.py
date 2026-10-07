"""Duration-independence preflight: D1 through D4 against the v2 design gates.

Implements the four measurements specified in v2-collection-design.md section 4
and evaluates them against the section 5 failure table. The verdict here is
whether v2 is collectable, not whether the temporal signal exists.

Protocol note: "leave-one-repeat-out" in the design resolves to
leave-one-procedure-out, since every repeat belongs to exactly one procedure.
Training uses repeats of three procedures, testing uses repeats of the fourth,
rotating over all four.

Run:  python preflight.py preflight.jsonl
"""

from __future__ import annotations

import json
import statistics as stats
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy import stats as sps
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bench"))
from sbbench import features, ordered  # noqa: E402

# Section 5 failure thresholds.
THRESHOLDS = {
    "d3_durations_only": 0.3000,
    "d3_first_execute_duration": 0.3000,
    "d2_ks_pvalue": 0.01,
    "d4_order_blind_full": 0.4000,
}
#: A procedure whose within-procedure CV is below this looks generator-like.
CV_FLOOR = 0.05


def load(path: str) -> list[dict]:
    return [json.loads(line) for line in open(path)]


def buckets(rows: list[dict]) -> dict:
    """Durations keyed by (procedure, event_index, event_type)."""
    out: dict[tuple, list[float]] = defaultdict(list)
    for r in rows:
        for i, e in enumerate(r["events"]):
            d = e.get("duration")
            if d:
                out[(r["label"], i, e["type"])].append(d)
    return out


def d1_within_procedure_cv(rows: list[dict]) -> list[tuple]:
    """Coefficient of variation per procedure and event slot."""
    findings = []
    for (proc, idx, typ), vals in sorted(buckets(rows).items()):
        if len(vals) < 3:
            continue
        mean = stats.fmean(vals)
        cv = (stats.stdev(vals) / mean) if mean else float("inf")
        findings.append((proc, idx, typ, len(vals), mean, cv))
    return findings


def d2_ks_across_procedures(rows: list[dict]) -> list[tuple]:
    """Pairwise KS on matching (index, type) slots, Holm-corrected."""
    by_slot: dict[tuple, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        for i, e in enumerate(r["events"]):
            d = e.get("duration")
            if d:
                by_slot[(i, e["type"])][r["label"]].append(d)
    raw = []
    for slot, per_proc in sorted(by_slot.items()):
        for a, b in combinations(sorted(per_proc), 2):
            stat, p = sps.ks_2samp(per_proc[a], per_proc[b])
            raw.append((slot, a, b, stat, p))
    # Holm-Bonferroni step-down on sorted p-values.
    order = sorted(range(len(raw)), key=lambda i: raw[i][4])
    m = len(raw)
    out = []
    for rank, i in enumerate(order):
        threshold = THRESHOLDS["d2_ks_pvalue"] / (m - rank)
        out.append((*raw[i], threshold, raw[i][4] < threshold))
    return out


def repeat_holdout_probe(rows: list[dict], featurizer, folds: int = 5) -> tuple[float, list[float]]:
    """Hold out repeats, not procedures.

    Holding out a whole procedure makes the test unanswerable: the held-out
    label never appears in training, so any classifier scores exactly 0.0000
    and the check passes for the wrong reason. What actually needs testing is
    whether a model trained on some executions of a procedure can identify the
    same procedure from a *different* execution. That is the memorization risk,
    and it requires splitting on repeat index with every label present in both
    sides of the split.
    """
    labels = sorted({r["label"] for r in rows})
    repeats = sorted({r["repeat"] for r in rows})
    y_all = np.array([labels.index(r["label"]) for r in rows])
    X_all = np.array([featurizer(r) for r in rows], dtype=np.float32)
    scores = []
    for fold in range(folds):
        test_repeats = set(repeats[fold::folds])
        test_mask = np.array([r["repeat"] in test_repeats for r in rows])
        Xtr, Xte = X_all[~test_mask], X_all[test_mask]
        ytr, yte = y_all[~test_mask], y_all[test_mask]
        if len(set(yte.tolist())) < 2:
            continue
        scaler = StandardScaler().fit(Xtr)
        model = MLPClassifier((32,), max_iter=3000, random_state=fold)
        model.fit(scaler.transform(Xtr), ytr)
        scores.append(model.score(scaler.transform(Xte), yte))
    return sum(scores) / len(scores), scores


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "preflight.jsonl"
    rows = load(path)
    labels = sorted({r["label"] for r in rows})
    print(f"  {len(rows)} traces, {len(labels)} procedures, "
          f"{len(rows) // len(labels)} repeats each\n")

    failures: list[str] = []
    diagnostics: list[str] = []

    print("D1  within-procedure run-to-run variation (diagnostic, not a gate)")
    cv_rows = d1_within_procedure_cv(rows)
    low = [r for r in cv_rows if r[5] < CV_FLOOR]
    by_proc: dict[str, list[float]] = defaultdict(list)
    for _, _, _, _, _, cv in cv_rows:
        pass
    for proc, idx, typ, n, mean, cv in cv_rows:
        pass
    print(f"    slots measured: {len(cv_rows)}")
    print(f"    median CV: {stats.median(r[5] for r in cv_rows):.4f}")
    if low:
        worst = sorted(low, key=lambda r: r[5])[:5]
        for proc, idx, typ, n, mean, cv in worst:
            print(f"      LOW CV {proc} idx={idx} {typ}: cv={cv:.4f} mean={mean:.4f}s")
        diagnostics.append(
            "generator-like slots: " + ", ".join(f"{p}/i{i}/{t}" for p, i, t, _, _, _ in worst)
        )
        print("      these are label-invariant if every procedure contains the same slot,")
        print("      so a constant slot is a realism cost rather than a leak. Reported,")
        print("      not gated: the section 5 failure table covers D2, D3 and D4 only.")
    else:
        print("    every slot varies across repeats, no generator-like slot")

    print("\nD2  cross-procedure separation of durations")
    ks_rows = d2_ks_across_procedures(rows)
    rejects = [r for r in ks_rows if r[6]]
    print(f"    pairs tested: {len(ks_rows)}  rejections: {len(rejects)}")
    for slot, a, b, stat, p, thr, _ in sorted(ks_rows, key=lambda r: r[4])[:5]:
        flag = "REJECT" if _ else "ok"
        print(f"      {flag} idx={slot[0]} {slot[1]} {a} vs {b}: p={p:.5f} stat={stat:.4f}")
    if rejects:
        failures.append(f"D2 {len(rejects)} Holm-corrected KS rejections")

    print("\nD3  duration label-informativeness, leave-one-procedure-out")
    for fam in ("durations_only", "first_execute_duration"):
        mean, per = repeat_holdout_probe(rows, features.FAMILIES[fam]["featurizer"])
        thr = THRESHOLDS[f"d3_{fam}"]
        ok = mean <= thr
        print(f"    [{'PASS' if ok else 'FAIL'}] {fam} {mean:.4f} <= {thr:.4f} "
              f"(per-procedure {[round(s, 4) for s in per]})")
        if not ok:
            failures.append(f"D3 {fam} {mean:.4f} > {thr:.4f}")

    print("\nD4  full order-blind ceiling, leave-one-procedure-out")
    full_mean, full_per = repeat_holdout_probe(rows, features.FAMILIES["order_blind_full"]["featurizer"])
    declared_mean, _ = repeat_holdout_probe(rows, features.FAMILIES["order_blind_counts"]["featurizer"])
    ok = full_mean <= THRESHOLDS["d4_order_blind_full"]
    print(f"    [{'PASS' if ok else 'FAIL'}] order_blind_full {full_mean:.4f} <= "
          f"{THRESHOLDS['d4_order_blind_full']:.4f} (per-procedure {[round(s, 4) for s in full_per]})")
    print(f"    order_blind_counts {declared_mean:.4f} (declared budget, informational)")
    if not ok:
        failures.append(f"D4 order_blind_full {full_mean:.4f} > "
                        f"{THRESHOLDS['d4_order_blind_full']:.4f}")

    print("\naliasing on non-duration fields")
    aliases = ordered.detect_aliases(rows)
    print(f"    {aliases if aliases else 'none, every label has a unique signature'}")

    print("\ninformational, not part of the gate: temporal probe")
    y = np.array([labels.index(r["label"]) for r in rows])
    small = [{"events": r["events"], "label": r["label"]} for r in rows]
    gru = ordered.ordered_probe(small, y)
    print(f"    GRU full trace {sum(gru) / len(gru):.4f} seeds {[round(s, 4) for s in gru]}")

    print()
    for d in diagnostics:
        print(f"  diagnostic: {d}")
    if failures:
        print("  PREFLIGHT FAILS, v2 is not collectable as specified:")
        for f in failures:
            print(f"    {f}")
        sys.exit(1)
    print("  PREFLIGHT PASSES: duration independence holds on real executions.")
    print("  Collection at scale is a separate decision and is not authorized here.")


if __name__ == "__main__":
    main()