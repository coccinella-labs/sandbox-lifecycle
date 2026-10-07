"""Benchmark entry point.

Runs the order-blind feature-family matrix, the alias check, and the ordered
sequence probe, then prints a single report. Usage:

    python -m sbbench.report v0=v0/data.jsonl v1ord=v1ord/data_v1ord.jsonl
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ordered  # noqa: E402
import probe  # noqa: E402

SEPARATOR = "=" * 72


def run(configs: list[str]) -> None:
    parsed = []
    for arg in configs:
        name, _, path = arg.partition("=")
        parsed.append((name or Path(path).stem, path))

    print(SEPARATOR)
    print("sandbox-lifecycle benchmark")
    print(SEPARATOR)

    for name, path in parsed:
        if not Path(path).exists():
            print(f"\nskip {name}: {path} not found")
            continue
        rows, y, labels = probe.load(path)
        chance = 1.0 / len(labels)

        print(f"\n{name}  {len(rows)} rows  {len(labels)} classes  chance {chance:.4f}")

        print("\n  order-blind feature families")
        best_blind = 0.0
        for family, spec in probe.FAMILIES.items():
            scores = probe.probe(rows, y, spec["featurizer"])
            mean = sum(scores) / len(scores)
            best_blind = max(best_blind, mean)
            verdict = (
                "at chance"
                if mean <= chance + probe.CHANCE_TOLERANCE
                else "ABOVE CHANCE (leak)"
            )
            seeds = ", ".join(f"{s:.4f}" for s in scores)
            print(f"    {family:<22} {mean:.4f}  [{seeds}]  {verdict}")

        print("\n  label aliasing on non-duration fields")
        aliases = ordered.detect_aliases(rows)
        if not aliases:
            print("    none: every label has a unique non-duration signature")
        for a, b in aliases:
            sep = ordered.duration_separability(rows, a, b)
            print(f"    {a} and {b} share an identical signature")
            print(
                f"      execute duration {a} "
                f"[{sep['a_range'][0]:.4f}, {sep['a_range'][1]:.4f}]"
            )
            print(
                f"      execute duration {b} "
                f"[{sep['b_range'][0]:.4f}, {sep['b_range'][1]:.4f}]"
            )
            print(
                f"      overlap {sep['overlap_seconds']:.4f}s, best single "
                f"threshold {sep['best_threshold_accuracy']:.4f}"
            )

        print("\n  ordered sequence probe")
        scores = ordered.ordered_probe(rows, y)
        mean = sum(scores) / len(scores)
        seeds = ", ".join(f"{s:.4f}" for s in scores)
        gap = mean - best_blind
        print(f"    GRU                       {mean:.4f}  [{seeds}]")
        print(f"    best order-blind family    {best_blind:.4f}")
        print(f"    gap attributable to order  {gap:+.4f}")
        if gap <= 0:
            print("    order does not separate these classes better than fields alone")

    print(f"\n{SEPARATOR}")


if __name__ == "__main__":
    args = sys.argv[1:] or ["v0=data.jsonl", "v1ord=v1ord/data_v1ord.jsonl"]
    run(args)