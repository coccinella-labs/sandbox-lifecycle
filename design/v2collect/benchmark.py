"""v2 benchmark runner.

Produces every output the dataset and benchmark design requires:

  1. Per-cutoff blind ceiling, order ceiling, headroom, and captured fraction.
  2. Reference temporal probe score per cutoff, all seeds shown.
  3. Negative-control check at cutoffs where headroom is zero.
  4. Leakage report at every tier under the declared observable set.
  5. Sample size and split identifiers used.

The primary metric is captured headroom per cutoff, not full-trace accuracy,
because the full-trace task saturates at 1.0000 and cannot discriminate between
architectures.

Model selection uses train and validation only. The test split is scored once,
by ``--final``, and the report marks which split each number came from.

The published repository stores the splits as native files:

    v2/
      train.jsonl
      validation.jsonl
      test.jsonl
      run.json

Pass the directory. A single ``.jsonl`` path is also accepted and is filtered by
its ``split`` field, which is how the collector's local staging file is run.

Run:
    python benchmark.py --data ../../v2
    python benchmark.py --data ../../v2 --final
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def _find(name: str) -> Path | None:
    """Locate a sibling directory by walking up, so the runner works from any
    checkout depth rather than a hard-coded number of parent levels."""
    for parent in HERE.parents:
        candidate = parent / name
        if candidate.exists():
            return candidate
    return None


for _path in (_find("bench"), HERE.parents[1] / "v2pilot", HERE):
    if _path and _path.exists():
        sys.path.insert(0, str(_path))

import ceilings  # noqa: E402
from sbbench import features, ordered, probe  # noqa: E402

CUTOFFS = (2, 3, 4, 5, 6, 7, 8)
NEGATIVE_CONTROL_TOL = 0.05
#: Reference probe floor at full trace, from the dataset design section 9.
GRU_MIN_T8 = 0.9500
#: Order-blind ceiling must be at chance under the declared observable set.
BLIND_MAX = 0.3000


#: Published native split filenames, read when ``--data`` is a directory.
SPLIT_FILES = {"train": "train.jsonl", "validation": "validation.jsonl", "test": "test.jsonl"}


def load(path: str):
    """Return the three splits separately, plus the pooled rows.

    ``path`` may be the published ``v2/`` directory, in which case the native
    split files are read directly, or a single ``.jsonl`` file, which is filtered
    by its ``split`` field. The directory form is the published entry point; the
    single-file form exists for the collector's local staging output, which is
    deliberately not published.

    Fit and evaluation data are kept apart on purpose. The design requires the
    test split to be scored exactly once, so the runner must be able to fit on
    one split and score on another rather than internally resampling whatever
    it was handed.
    """
    target = Path(path)
    raw: list[dict] = []
    from_dir: dict[str, list[dict]] = {}

    if target.is_dir():
        for name, filename in SPLIT_FILES.items():
            file_path = target / filename
            if not file_path.exists():
                raise SystemExit(
                    f"missing split file: {file_path}\n"
                    f"expected the published layout with {', '.join(SPLIT_FILES.values())}"
                )
            from_dir[name] = [json.loads(line) for line in open(file_path)]
            raw.extend(from_dir[name])
    else:
        raw = [json.loads(line) for line in open(target)]

    labels = sorted({r["label"] for r in raw})
    index = {label: i for i, label in enumerate(labels)}

    def take(split: str):
        sel = from_dir.get(split) if from_dir else [
            r for r in raw if r.get("split") == split
        ]
        return (
            [{"events": r["events"], "label": r["label"]} for r in sel],
            np.array([index[r["label"]] for r in sel]),
        )

    parts = {name: take(name) for name in ("train", "validation", "test")}
    all_rows = [{"events": r["events"], "label": r["label"]} for r in raw]
    return parts, all_rows, labels


def ceilings_table(rows: list[dict]) -> dict[int, tuple[float, float, float]]:
    out = {}
    for t in CUTOFFS:
        b = ceilings.blind_ceiling(rows, t)
        o = ceilings.order_ceiling(rows, t)
        out[t] = (b, o, o - b)
    return out


def report_cutoffs(train, y_train, ev, y_ev, ceil: dict) -> list[tuple[str, bool, str]]:
    verdicts: list[tuple[str, bool, str]] = []
    print("\n  cutoff sweep: the primary metric is captured headroom")
    print(f"    {'t':<4} {'blind':<8} {'order':<8} {'headroom':<10} "
          f"{'probe':<8} {'captured':<10} seeds")
    for t in CUTOFFS:
        blind_c, order_c, headroom = ceil[t]
        tr = [{"events": r["events"][:t], "label": r["label"]} for r in train]
        ev_t = [{"events": r["events"][:t], "label": r["label"]} for r in ev]
        scores = ordered.ordered_probe(
            tr, y_train, use_durations=False, eval_rows=ev_t, eval_y=y_ev
        )
        gru = sum(scores) / len(scores)
        if headroom <= 1e-9:
            captured_str = "n/a"
            verdicts.append((
                f"t={t} negative control, probe at blind ceiling",
                abs(gru - blind_c) <= NEGATIVE_CONTROL_TOL,
                f"probe {gru:.4f} vs blind {blind_c:.4f}",
            ))
        else:
            captured = (gru - blind_c) / headroom
            captured_str = f"{captured:.4f}"
            verdicts.append((
                f"t={t} captures headroom",
                captured >= 0.90,
                f"{captured:.4f}",
            ))
        print(f"    {t:<4} {blind_c:<8.4f} {order_c:<8.4f} {headroom:<+10.4f} "
              f"{gru:<8.4f} {captured_str:<10} {[round(s, 4) for s in scores]}")
    gru8_scores = ordered.ordered_probe(
        train, y_train, use_durations=False, eval_rows=ev, eval_y=y_ev
    )
    gru8 = sum(gru8_scores) / len(gru8_scores)
    verdicts.append((f"probe(t=8) >= {GRU_MIN_T8}", gru8 >= GRU_MIN_T8, f"{gru8:.4f}"))
    return verdicts


#: Families that read only fields inside v2's declared observable set. These
#: must sit at chance; failing one is a leak and a gate failure.
OBSERVABLE_FAMILIES = ("order_blind_counts", "counts_only", "exit_codes_only")

#: Families that read duration. Under v2 these are outside the observable set,
#: so a score above chance is not a defect in the data, it is evidence that the
#: exclusion was necessary. Reported for audit, never gated.
WITHHELD_FAMILIES = (
    "order_blind_full",
    "durations_only",
    "first_execute_duration",
    "prefix_fields",
)


def leakage_report(train, y_train, ev, y_ev) -> list[tuple[str, bool, str]]:
    verdicts: list[tuple[str, bool, str]] = []
    print("\n  leakage report under the declared observable set")
    print("    observable: event type and exit code. duration and t withheld.")

    print("\n    within the observable set, must be at chance")
    print(f"    {'family':<24} {'score':<9} verdict")
    for family in OBSERVABLE_FAMILIES:
        scores = probe.probe(
            train, y_train, features.FAMILIES[family]["featurizer"],
            eval_rows=ev, eval_y=y_ev,
        )
        mean = sum(scores) / len(scores)
        at_chance = mean <= BLIND_MAX
        print(f"    {family:<24} {mean:<9.4f} "
              f"{'at chance' if at_chance else 'ABOVE CHANCE (leak)'}")
        verdicts.append((
            f"observable {family} <= {BLIND_MAX}", at_chance, f"{mean:.4f}"
        ))

    print("\n    withheld from the observable set, audit only, not gated")
    print("    these read duration, which real executions make informative")
    print(f"    {'family':<24} {'score':<9} verdict")
    for family in WITHHELD_FAMILIES:
        scores = probe.probe(
            train, y_train, features.FAMILIES[family]["featurizer"],
            eval_rows=ev, eval_y=y_ev,
        )
        mean = sum(scores) / len(scores)
        print(f"    {family:<24} {mean:<9.4f} "
              f"{'at chance' if mean <= BLIND_MAX else 'above chance, exclusion was necessary'}")

    aliases = ordered.detect_aliases(ev)
    print(f"\n    {'aliases on observable fields':<24} {len(aliases):<9} "
          f"{'none' if not aliases else aliases}")
    verdicts.append(("zero aliases on observable fields", not aliases,
                     str(aliases) if aliases else "none"))
    return verdicts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--data",
        default=str(HERE.parents[1] / "v2"),
        help="published v2/ directory, or a single split-bearing .jsonl file",
    )
    ap.add_argument("--final", action="store_true",
                    help="score the test split, once, for a release")
    args = ap.parse_args()

    parts, all_rows, labels = load(args.data)
    train, y_train = parts["train"]
    ev, y_ev = parts["test"] if args.final else parts["validation"]
    split = "test" if args.final else "validation"
    chance = 1.0 / len(labels)
    print("=" * 72)
    print("sandbox-lifecycle v2 benchmark")
    print("=" * 72)
    print(f"  data source:    {args.data}")
    print(f"  fit on:         train ({len(train)} traces)")
    print(f"  scored on:      {split} ({len(ev)} traces)")
    print(f"  labels:         {len(labels)}, chance {chance:.4f}")
    if not args.final:
        print("  NOTE: development scoring on validation. Test is untouched until --final.")

    ceil = ceilings_table(ev)
    verdicts = report_cutoffs(train, y_train, ev, y_ev, ceil)
    verdicts += leakage_report(train, y_train, ev, y_ev)

    failed = [n for n, ok, _ in verdicts if not ok]
    print(f"\n  {len(verdicts) - len(failed)}/{len(verdicts)} conditions hold")
    if failed:
        print("  BENCHMARK GATE FAILS:")
        for n in failed:
            print(f"    {n}")
        sys.exit(1)
    print("  Benchmark gate holds.")
    if args.final:
        print("  These are final test numbers. The test split is now spent.")
    else:
        print("  Development numbers only. Not a release result.")


if __name__ == "__main__":
    main()