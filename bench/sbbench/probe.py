"""Run every feature family against both released configs and report the matrix.

Reports accuracy per family and flags any order-blind family that beats a
tolerance band above chance, which is the signal that a config is leaking.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from features import FAMILIES  # noqa: E402

SEEDS = (0, 1, 2)
#: A family within this band of chance is treated as chance-level. Two seeds of
#: a chance model move by more than this, so the band is deliberately loose.
CHANCE_TOLERANCE = 0.05


def load(path: str) -> tuple[list[dict], np.ndarray, list[str]]:
    rows = [json.loads(line) for line in open(path)]
    labels = sorted({r["label"] for r in rows})
    index = {label: i for i, label in enumerate(labels)}
    y = np.array([index[r["label"]] for r in rows])
    return rows, y, labels


def probe(
    rows: list[dict],
    y: np.ndarray,
    featurizer,
    eval_rows: list[dict] | None = None,
    eval_y: np.ndarray | None = None,
) -> list[float]:
    X = np.array([featurizer(r) for r in rows], dtype=np.float32)
    counts = np.bincount(y)
    if eval_rows is not None:
        # Fit on rows, score on a separate evaluation set. This is what lets a
        # config honour a fixed split with the evaluation set untouched.
        Xe = np.array([featurizer(r) for r in eval_rows], dtype=np.float32)
        scores = []
        for seed in SEEDS:
            scaler = StandardScaler().fit(X)
            model = MLPClassifier(
                hidden_layer_sizes=(32,), max_iter=3000, random_state=seed
            ).fit(scaler.transform(X), y)
            scores.append(model.score(scaler.transform(Xe), eval_y))
        return scores
    # Stratification needs at least two rows per class. Small fixtures fall back
    # to an unstratified split rather than raising, so the report degrades to a
    # noisy score instead of crashing.
    stratify = y if counts.min() >= 2 else None
    scores = []
    for seed in SEEDS:
        Xtr, Xte, ytr, yte = train_test_split(
            X, y, test_size=0.2, random_state=seed, stratify=stratify
        )
        scaler = StandardScaler().fit(Xtr)
        model = MLPClassifier(
            hidden_layer_sizes=(32,), max_iter=3000, random_state=seed
        ).fit(scaler.transform(Xtr), ytr)
        scores.append(model.score(scaler.transform(Xte), yte))
    return scores


def main() -> None:
    configs = {
        "v0": sys.argv[1] if len(sys.argv) > 1 else "data.jsonl",
        "v1ord": sys.argv[2] if len(sys.argv) > 2 else "v1ord/data_v1ord.jsonl",
    }
    findings: list[tuple[str, str, float]] = []

    for name, path in configs.items():
        if not Path(path).exists():
            print(f"  skip {name}: {path} not found")
            continue
        rows, y, labels = load(path)
        chance = 1.0 / len(labels)
        print(f"\n{name}: {len(rows)} rows, {len(labels)} classes, chance {chance:.4f}")
        for family, spec in FAMILIES.items():
            scores = probe(rows, y, spec["featurizer"])
            mean = float(np.mean(scores))
            verdict = "at chance" if mean <= chance + CHANCE_TOLERANCE else "ABOVE CHANCE"
            print(
                f"  {family:<22} {mean:.4f}  seeds "
                f"{[round(s, 4) for s in scores]}  {verdict}"
            )
            if spec["order_blind"] and mean > chance + CHANCE_TOLERANCE:
                findings.append((name, family, mean))

    print()
    if findings:
        print("LEAKAGE: order-blind families that beat chance")
        for name, family, mean in findings:
            print(f"  {name}: {family} reached {mean:.4f} without seeing order")
        print("\nA config with findings above is not order-only.")
    else:
        print("LEAKAGE: no order-blind family beat chance.")
    return None


if __name__ == "__main__":
    main()