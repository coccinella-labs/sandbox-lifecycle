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


def prefix_fields(row: Row, cutoff: int = 3) -> list[float]:
    """Fields observable within the first ``cutoff`` events, order-blind.

    Approximates an early observer that has seen part of the trace. Excludes
    any event past the cutoff, so it cannot see the final outcome.
    """
    seen = row["events"][:cutoff]
    counts = [float(sum(1 for e in seen if e["type"] == t)) for t in EVENT_TYPES]
    codes = [e["exit_code"] for e in seen if e.get("exit_code") is not None]
    durs = [e.get("duration") or 0.0 for e in seen]
    return (
        counts
        + [float(len(codes)), float(sum(codes)), float(max(codes)) if codes else 0.0]
        + [float(sum(durs)), float(max(durs))]
    )


#: Ordered as probes in the report. Order-blind families come first so a
#: leakage result is visible before the ordered families are scored.
FAMILIES: dict[str, dict] = {
    "counts_only": {
        "featurizer": counts_only,
        "order_blind": True,
        "description": "Event type counts. No exit codes, no durations.",
    },
    "exit_codes_only": {
        "featurizer": exit_codes_only,
        "order_blind": True,
        "description": "Exit-code multiset. No types, no durations.",
    },
    "order_blind_counts": {
        "featurizer": order_blind_counts,
        "order_blind": True,
        "description": "Counts plus exit codes, no durations. The v1ord gate family.",
    },
    "durations_only": {
        "featurizer": durations_only,
        "order_blind": True,
        "description": "Order-blind duration aggregates. No types, no exit codes.",
    },
    "first_execute_duration": {
        "featurizer": first_execute_duration,
        "order_blind": True,
        "description": "Duration of the first execute event only.",
    },
    "prefix_fields": {
        "featurizer": prefix_fields,
        "order_blind": True,
        "description": "Fields inside the first three events, order-blind.",
    },
}