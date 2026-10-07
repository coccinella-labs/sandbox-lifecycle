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
from features import DEFAULT_PREFIX_CUTOFF, FAMILIES, TIERS  # noqa: E402

SEPARATOR = "=" * 72


def score_family(rows, y, family: str) -> tuple[float, list[float]]:
    scores = probe.probe(rows, y, FAMILIES[family]["featurizer"])
    return sum(scores) / len(scores), scores


def format_scores(mean: float, scores: list[float], chance: float) -> str:
    seeds = ", ".join(f"{s:.4f}" for s in scores)
    verdict = "at chance" if mean <= chance + probe.CHANCE_TOLERANCE else "ABOVE CHANCE (leak)"
    return f"    {mean:.4f}  [{seeds}]  {verdict}"


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

        results: dict[str, tuple[float, list[float]]] = {}
        for family in FAMILIES:
            results[family] = score_family(rows, y, family)

        # Tier 1: declared budget. The feature set the gate commits to.
        print(f"\n  declared-budget baseline  ({TIERS['declared_budget']['description']})")
        for family in TIERS["declared_budget"]["families"]:
            mean, scores = results[family]
            print(f"    {family:<22}{format_scores(mean, scores, chance)}")
        declared = max(results[f][0] for f in TIERS["declared_budget"]["families"])

        # Tier 2: strongest non-temporal predictor.
        print(f"\n  order-blind baseline  ({TIERS['order_blind_full']['description']})")
        for family in TIERS["order_blind_full"]["families"]:
            mean, scores = results[family]
            print(f"    {family:<22}{format_scores(mean, scores, chance)}")
        full = max(results[f][0] for f in TIERS["order_blind_full"]["families"])

        # Tier 3: diagnostics, localizing any shortcut.
        print(f"\n  diagnostic subsets  ({TIERS['diagnostic']['description']})")
        for family in TIERS["diagnostic"]["families"]:
            mean, scores = results[family]
            print(f"    {family:<22}{format_scores(mean, scores, chance)}")

        print("\n  label aliasing on non-duration fields")
        aliases = ordered.detect_aliases(rows)
        if not aliases:
            print("    none: every label has a unique non-duration signature")
        for a, b in aliases:
            sep = ordered.duration_separability(rows, a, b)
            print(f"    {a} and {b} share an identical signature")
            print(f"      execute duration {a} [{sep['a_range'][0]:.4f}, {sep['a_range'][1]:.4f}]")
            print(f"      execute duration {b} [{sep['b_range'][0]:.4f}, {sep['b_range'][1]:.4f}]")
            print(
                f"      overlap {sep['overlap_seconds']:.4f}s, best single "
                f"threshold {sep['best_threshold_accuracy']:.4f}"
            )

        print("\n  temporal model  (ordered events under the declared budget)")
        scores = ordered.ordered_probe(rows, y)
        mean = sum(scores) / len(scores)
        seeds = ", ".join(f"{s:.4f}" for s in scores)
        print(f"    {'GRU':<22}{mean:.4f}  [{seeds}]")

        print("\n  gaps attributable to order")
        print(f"    vs declared budget      {mean - declared:+.4f}")
        print(f"    vs order-blind ceiling  {mean - full:+.4f}")
        if mean - declared > 0 and mean - full <= 0:
            print(
                f"    order helps against the declared budget only. The strongest\n"
                f"    non-temporal predictor already matches it, so this is not an\n"
                f"    order-specific result."
            )
        elif mean - full > 0:
            print("    order survives the strongest non-temporal baseline")

    print(f"\n  prefix cutoff in this report: {DEFAULT_PREFIX_CUTOFF} events (harness default)")
    print(f"{SEPARATOR}")


if __name__ == "__main__":
    args = sys.argv[1:] or ["v0=data.jsonl", "v1ord=v1ord/data_v1ord.jsonl"]
    run(args)