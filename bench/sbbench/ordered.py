"""Ordered-sequence probe and label-alias detection.

Two checks the accuracy matrix alone cannot make:

* Whether two labels share an identical field signature, which makes the
  task unsolvable from those fields no matter how long it trains.
* Whether an ordered model beats the best order-blind family, which is the
  only comparison that supports a claim about order carrying information.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.model_selection import train_test_split

SEEDS = (0, 1)
EVENT_TYPES = (
    "sandbox_create",
    "execute",
    "process_exit",
    "recover",
    "wait",
    "sandbox_teardown",
)


def load(path: str) -> tuple[list[dict], np.ndarray, list[str]]:
    rows = [json.loads(line) for line in open(path)]
    labels = sorted({r["label"] for r in rows})
    index = {label: i for i, label in enumerate(labels)}
    y = np.array([index[r["label"]] for r in rows])
    return rows, y, labels


def categorical_signature(row: dict) -> tuple:
    """Everything except durations: types in order, exit codes, final state."""
    return (
        tuple(e["type"] for e in row["events"]),
        tuple(e.get("exit_code") for e in row["events"]),
        row["events"][-1].get("clean"),
    )


def detect_aliases(rows: list[dict]) -> list[tuple[str, str]]:
    """Labels that are indistinguishable on all non-duration fields."""
    by_signature: dict[tuple, set[str]] = defaultdict(set)
    for row in rows:
        by_signature[categorical_signature(row)].add(row["label"])
    aliased = set()
    for labels in by_signature.values():
        if len(labels) > 1:
            aliased |= labels
    out = []
    for i, a in enumerate(sorted(aliased)):
        for b in sorted(aliased)[i + 1 :]:
            out.append((a, b))
    return out


def duration_separability(rows: list[dict], a: str, b: str) -> dict:
    """Range overlap between two labels on execute duration."""
    spans = {}
    for label in (a, b):
        vals = sorted(
            next(
                (e.get("duration") or 0.0 for e in r["events"] if e["type"] == "execute"),
                0.0,
            )
            for r in rows
            if r["label"] == label
        )
        spans[label] = vals
    lo_a, hi_a = spans[a][0], spans[a][-1]
    lo_b, hi_b = spans[b][0], spans[b][-1]
    overlap = min(hi_a, hi_b) - max(lo_a, lo_b)
    best = 0
    for i in range(1, 4000):
        t = lo_a + (hi_b - lo_a) * i / 4000
        correct = sum(1 for v in spans[a] if v < t) + sum(1 for v in spans[b] if v >= t)
        best = max(best, correct)
    n = len(spans[a]) + len(spans[b])
    return {
        "a_range": (lo_a, hi_a),
        "b_range": (lo_b, hi_b),
        "overlap_seconds": max(0.0, overlap),
        "best_threshold_accuracy": best / n,
    }


class GRU(nn.Module):
    def __init__(self, n_types: int, n_classes: int, width: int = 32) -> None:
        super().__init__()
        self.embed = nn.Embedding(n_types, 8)
        self.gru = nn.GRU(8 + 2, width, batch_first=True)
        self.head = nn.Linear(width, n_classes)

    def forward(self, types: torch.Tensor, feats: torch.Tensor) -> torch.Tensor:
        _, hid = self.gru(torch.cat([self.embed(types), feats], dim=-1))
        return self.head(hid[-1])


def ordered_probe(rows: list[dict], y: np.ndarray, epochs: int = 30) -> list[float]:
    n_types = len(EVENT_TYPES)
    t_index = {t: i for i, t in enumerate(EVENT_TYPES)}
    types, feats = [], []
    for row in rows:
        seq_t, seq_f = [], []
        for e in row["events"]:
            seq_t.append(t_index[e["type"]])
            code = e.get("exit_code")
            seq_f.append([float(code) if code is not None else 0.0, e.get("duration") or 0.0])
        types.append(seq_t)
        feats.append(seq_f)
    T = max(len(s) for s in types)
    types_a = np.zeros((len(rows), T), dtype=np.int64)
    feats_a = np.zeros((len(rows), T, 2), dtype=np.float32)
    for i, (ts, fs) in enumerate(zip(types, feats)):
        types_a[i, : len(ts)] = ts
        feats_a[i, : len(fs)] = fs
    scores = []
    for seed in SEEDS:
        torch.manual_seed(seed)
        idx = np.arange(len(rows))
        tr, te = train_test_split(idx, test_size=0.2, random_state=seed, stratify=y)
        model = GRU(n_types, len(set(y.tolist())))
        opt = torch.optim.Adam(model.parameters(), lr=1e-3)
        xt = torch.tensor(types_a[tr])
        xf = torch.tensor(feats_a[tr])
        yt = torch.tensor(y[tr])
        loss_fn = nn.CrossEntropyLoss()
        gen = torch.Generator().manual_seed(seed)
        n = len(tr)
        for _ in range(epochs):
            model.train()
            perm = torch.randperm(n, generator=gen)
            for start in range(0, n, 128):
                batch = perm[start : start + 128]
                opt.zero_grad()
                loss_fn(model(xt[batch], xf[batch]), yt[batch]).backward()
                opt.step()
        model.eval()
        with torch.no_grad():
            pred = model(torch.tensor(types_a[te]), torch.tensor(feats_a[te])).argmax(1)
        scores.append(float((pred.numpy() == y[te]).mean()))
    return scores


def main() -> None:
    configs = {
        "v0": sys.argv[1] if len(sys.argv) > 1 else "data.jsonl",
        "v1ord": sys.argv[2] if len(sys.argv) > 2 else "v1ord/data_v1ord.jsonl",
    }
    for name, path in configs.items():
        if not Path(path).exists():
            print(f"  skip {name}: {path} not found")
            continue
        rows, y, labels = load(path)
        print(f"\n{name}: {len(rows)} rows, {len(labels)} classes")
        aliases = detect_aliases(rows)
        if aliases:
            print("  LABEL ALIASES on non-duration fields:")
            for a, b in aliases:
                sep = duration_separability(rows, a, b)
                print(f"    {a} / {b}")
                print(f"      execute duration {a} [{sep['a_range'][0]:.4f}, {sep['a_range'][1]:.4f}]")
                print(f"      execute duration {b} [{sep['b_range'][0]:.4f}, {sep['b_range'][1]:.4f}]")
                print(
                    f"      overlap {sep['overlap_seconds']:.4f}s, "
                    f"best threshold accuracy {sep['best_threshold_accuracy']:.4f}"
                )
        else:
            print("  no label aliases: every label has a unique non-duration signature")
        scores = ordered_probe(rows, y)
        print(f"  ordered GRU: {float(np.mean(scores)):.4f}  seeds {[round(s,4) for s in scores]}")


if __name__ == "__main__":
    main()