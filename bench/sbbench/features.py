"""Feature families for sandbox-lifecycle probing.

Each family declares exactly what information the model is allowed to see.
The benchmark reports these alongside accuracy so a score can be read as a
statement about information access, not just predictive power.
"""

from __future__ import annotations

from typing import Callable, Sequence

Row = dict
Featurizer = Callable[[Row], Sequence[float]]

#: Canonical event vocabulary, discovered from the data rather than assumed.
EVENT_TYPES: tuple[str, ...] = (
    "sandbox_create",
    "execute",
    "process_exit",
    "recover",
    "wait",
    "sandbox_teardown",
)

#: Default early-observer cutoff, in events. Chosen to match the shortest
#: informative prefix in the released configs, not as a claim about them.
DEFAULT_PREFIX_CUTOFF: int = 3


def _exit_codes(row: Row) -> list[int]:
    return [e["exit_code"] for e in row["events"] if e.get("exit_code") is not None]


def _durations(row: Row) -> list[float]:
    return [e.get("duration") or 0.0 for e in row["events"]]


def order_blind_counts(row: Row) -> list[float]:
    """Event type counts and the exit-code multiset. No durations, no order.

    This is the family the v1ord publish gate used, and the one whose
    chance-level result is the load-bearing claim for ``flow``.
    """
    counts = [float(sum(1 for e in row["events"] if e["type"] == t)) for t in EVENT_TYPES]
    codes = _exit_codes(row)
    return counts + [float(len(codes)), float(sum(codes)), float(max(codes)), float(min(codes))]


def counts_only(row: Row) -> list[float]:
    """Event type counts with no exit codes and no durations."""
    return [float(sum(1 for e in row["events"] if e["type"] == t)) for t in EVENT_TYPES]


def exit_codes_only(row: Row) -> list[float]:
    """The exit-code multiset alone."""
    codes = _exit_codes(row)
    return [float(len(codes)), float(sum(codes)), float(max(codes)), float(min(codes))]


def durations_only(row: Row) -> list[float]:
    """Order-blind duration aggregates. No types, no exit codes.

    Included because durations are weakly label-bearing in v1ord. A model that
    beats chance here has not learned order, it has learned wall-clock shape.
    """
    durs = _durations(row)
    return [
        float(len(durs)),
        float(sum(durs)),
        float(max(durs)),
        float(min(durs)),
        float(sorted(durs)[len(durs) // 2]),
    ]


def first_execute_duration(row: Row) -> list[float]:
    """A single scalar: the duration of the first execute event.

    The strongest order-blind shortcut found in v1ord. Published as its own
    family so the leak is visible in the report rather than buried in a
    feature list.
    """
    for event in row["events"]:
        if event["type"] == "execute":
            return [event.get("duration") or 0.0]
    return [0.0]


def prefix_fields(row: Row, cutoff: int = DEFAULT_PREFIX_CUTOFF) -> list[float]:
    """Fields observable within the first ``cutoff`` events, order-blind.

    Approximates an early observer that has seen part of the trace. Excludes
    any event past the cutoff, so it cannot see the final outcome.

    The cutoff is a harness parameter, not a dataset property. A fixed value
    supports the released configs only; any version whose cutoff is part of the
    claim must sweep it and report the sweep. See ``prefix_fields_sweep``.
    """
    if cutoff < 1:
        raise ValueError(f"cutoff must be at least 1, got {cutoff}")
    seen = row["events"][:cutoff]
    counts = [float(sum(1 for e in seen if e["type"] == t)) for t in EVENT_TYPES]
    codes = [e["exit_code"] for e in seen if e.get("exit_code") is not None]
    durs = [e.get("duration") or 0.0 for e in seen]
    return (
        counts
        + [float(len(codes)), float(sum(codes)), float(max(codes)) if codes else 0.0]
        + [float(sum(durs)), float(max(durs))]
    )


def prefix_fields_sweep(cutoffs: Sequence[int]) -> dict[int, Featurizer]:
    """One order-blind featurizer per cutoff, for experiments where the cutoff
    is itself the quantity under study rather than a fixed probe."""
    return {c: (lambda row, c=c: prefix_fields(row, c)) for c in cutoffs}


def order_blind_full(row: Row) -> list[float]:
    """Every permitted non-order feature, concatenated.

    This is the honest ceiling for a non-temporal predictor: counts, exit codes,
    durations, and prefix aggregates together. A temporal model is only
    interesting when it beats this, not merely a hand-picked narrow budget.
    """
    return (
        order_blind_counts(row)
        + durations_only(row)
        + first_execute_duration(row)
        + prefix_fields(row)
    )


#: Tier taxonomy. The three tiers a temporal claim is measured against, kept
#: explicit because v1ord is legitimate without being maximal: its result holds
#: against the declared budget, and the full order-blind tier is strictly
#: stronger.
TIERS: dict[str, dict] = {
    "declared_budget": {
        "families": ["order_blind_counts"],
        "description": "Intentionally narrower feature budget, the one the gate declares.",
    },
    "order_blind_full": {
        "families": ["order_blind_full"],
        "description": "All permitted non-order features. Strongest non-temporal ceiling.",
    },
    "diagnostic": {
        "families": [
            "counts_only",
            "exit_codes_only",
            "durations_only",
            "first_execute_duration",
            "prefix_fields",
        ],
        "description": "Subsets that localize which field carries a shortcut.",
    },
}

#: Ordered so the declared budget and the full ceiling bracket the diagnostics,
#: and a leakage result is visible before the ordered model is scored.
FAMILIES: dict[str, dict] = {
    "order_blind_counts": {
        "featurizer": order_blind_counts,
        "order_blind": True,
        "tier": "declared_budget",
        "description": "Counts plus exit codes, no durations. The v1ord gate budget.",
    },
    "order_blind_full": {
        "featurizer": order_blind_full,
        "order_blind": True,
        "tier": "order_blind_full",
        "description": "Counts, exit codes, durations, and prefix aggregates together.",
    },
    "counts_only": {
        "featurizer": counts_only,
        "order_blind": True,
        "tier": "diagnostic",
        "description": "Event type counts. No exit codes, no durations.",
    },
    "exit_codes_only": {
        "featurizer": exit_codes_only,
        "order_blind": True,
        "tier": "diagnostic",
        "description": "Exit-code multiset. No types, no durations.",
    },
    "durations_only": {
        "featurizer": durations_only,
        "order_blind": True,
        "tier": "diagnostic",
        "description": "Order-blind duration aggregates. No types, no exit codes.",
    },
    "first_execute_duration": {
        "featurizer": first_execute_duration,
        "order_blind": True,
        "tier": "diagnostic",
        "description": "Duration of the first execute event only.",
    },
    "prefix_fields": {
        "featurizer": prefix_fields,
        "order_blind": True,
        "tier": "diagnostic",
        "description": "Fields inside the first three events, order-blind.",
    },
}