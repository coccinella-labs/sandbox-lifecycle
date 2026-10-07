"""Exact achievable ceilings at each cutoff.

An absolute margin threshold is incoherent when a prefix genuinely does not
determine the label. At t=3 only delayed_fault is identifiable from the prefix
multiset, so no model of any kind can exceed 0.5000 there. These functions
compute both ceilings directly, by lookup, because the data is controlled.

  blind_ceiling(t):  best accuracy from the prefix multiset alone
  order_ceiling(t):  best accuracy from the ordered prefix

A temporal model should approach order_ceiling. Order is worth studying only
where order_ceiling exceeds blind_ceiling.
"""

from __future__ import annotations

from collections import defaultdict


def _key(events: list[dict], cutoff: int, ordered_keys: bool) -> tuple:
    seen = events[:cutoff]
    pairs = ((e["type"], e.get("exit_code")) for e in seen)
    return tuple(pairs) if ordered_keys else tuple(sorted(pairs))


def _ceiling(rows: list[dict], cutoff: int, ordered_keys: bool) -> float:
    """Bayes-optimal accuracy under the given representation, by lookup."""
    buckets: dict[tuple, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        buckets[_key(r["events"], cutoff, ordered_keys)][r["label"]] += 1
    correct = sum(max(counts.values()) for counts in buckets.values())
    return correct / len(rows)


def blind_ceiling(rows: list[dict], cutoff: int) -> float:
    return _ceiling(rows, cutoff, ordered_keys=False)


def order_ceiling(rows: list[dict], cutoff: int) -> float:
    return _ceiling(rows, cutoff, ordered_keys=True)