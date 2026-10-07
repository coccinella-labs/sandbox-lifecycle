"""Tests for the benchmark harness.

These run on synthetic fixtures so the suite needs no dataset download and
stays fast. The integration tests that do need real data are marked and skip
when the files are absent.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sbbench import features, ordered, probe  # noqa: E402


def event(type_: str, duration: float | None = None, exit_code: int | None = None) -> dict:
    out: dict = {"type": type_}
    if duration is not None:
        out["duration"] = duration
    if exit_code is not None:
        out["exit_code"] = exit_code
    return out


def row(label: str, events: list[dict]) -> dict:
    return {
        "id": "test",
        "label": label,
        "procedure": label,
        "events": [*events, {"type": "sandbox_teardown", "clean": True}],
    }


def success() -> dict:
    return row(
        "success",
        [
            event("sandbox_create", 0.0),
            event("execute", 0.005, 0),
            event("process_exit", None, 0),
        ],
    )


def nonzero() -> dict:
    return row(
        "nonzero_exit",
        [
            event("sandbox_create", 0.0),
            event("execute", 0.005, 3),
            event("process_exit", None, 3),
        ],
    )


def recovered() -> dict:
    return row(
        "recovered",
        [
            event("sandbox_create", 0.0),
            event("execute", 0.100, 3),
            event("process_exit", None, 3),
        ],
    )


def wait_first() -> dict:
    return row(
        "wait_first",
        [
            event("sandbox_create", 0.0),
            event("wait", 2.0),
            event("execute", 0.005, 3),
            event("process_exit", None, 3),
            event("execute", 0.005, 0),
            event("process_exit", None, 0),
        ],
    )


def wait_last() -> dict:
    return row(
        "wait_last",
        [
            event("sandbox_create", 0.0),
            event("execute", 0.005, 3),
            event("process_exit", None, 3),
            event("execute", 0.005, 0),
            event("process_exit", None, 0),
            event("wait", 2.0),
        ],
    )


# --- feature families ------------------------------------------------------


def test_order_blind_families_ignore_event_order():
    """Counts, exit codes and their combination must not see ordering."""
    a, b = wait_first(), wait_last()
    for name in ("counts_only", "exit_codes_only", "order_blind_counts"):
        assert features.FAMILIES[name]["featurizer"](a) == \
            features.FAMILIES[name]["featurizer"](b), name


def test_order_blind_full_is_strictly_wider_than_declared_budget():
    a = wait_first()
    declared = features.FAMILIES["order_blind_counts"]["featurizer"](a)
    full = features.FAMILIES["order_blind_full"]["featurizer"](a)
    assert len(full) > len(declared)
    assert full[: len(declared)] == declared


def test_every_family_is_declared_order_blind():
    for name, spec in features.FAMILIES.items():
        assert spec["order_blind"] is True, name
        assert spec["tier"] in features.TIERS, name


def test_tier_membership_matches_family_tiers():
    for tier, spec in features.TIERS.items():
        for family in spec["families"]:
            assert features.FAMILIES[family]["tier"] == tier, (tier, family)


def test_tiers_cover_every_family_exactly_once():
    assigned = [f for spec in features.TIERS.values() for f in spec["families"]]
    assert sorted(assigned) == sorted(features.FAMILIES)


def test_prefix_cutoff_is_parameterized():
    a = wait_first()
    two = features.prefix_fields(a, cutoff=2)
    four = features.prefix_fields(a, cutoff=4)
    assert len(two) == len(four)
    assert two != four, "cutoff must change what the observer sees"


def test_prefix_cutoff_excludes_later_events():
    """At cutoff 2 the process_exit at index 3 must not be visible."""
    a = wait_first()
    seen = features.prefix_fields(a, cutoff=2)
    codes_only = seen[len(features.EVENT_TYPES) : len(features.EVENT_TYPES) + 3]
    assert codes_only[0] == 0.0, "no exit codes are observable within two events"


def test_prefix_cutoff_rejects_nonpositive():
    with pytest.raises(ValueError):
        features.prefix_fields(wait_first(), cutoff=0)


def test_prefix_sweep_returns_one_featurizer_per_cutoff():
    sweep = features.prefix_fields_sweep([1, 2, 4])
    assert sorted(sweep) == [1, 2, 4]
    a = wait_first()
    assert len({tuple(fn(a)) for fn in sweep.values()}) == 3


def test_first_execute_duration_is_a_single_scalar():
    assert len(features.first_execute_duration(wait_first())) == 1


# --- alias detection -------------------------------------------------------


def test_alias_detected_when_only_duration_differs():
    rows = [nonzero(), recovered()]
    assert ordered.detect_aliases(rows) == [("nonzero_exit", "recovered")]


def test_no_alias_when_structure_differs():
    rows = [success(), wait_first()]
    assert ordered.detect_aliases(rows) == []


def test_signature_excludes_durations():
    """Two rows differing only in duration must share a signature."""
    assert ordered.categorical_signature(nonzero()) == \
        ordered.categorical_signature(recovered())


def test_duration_separability_reports_no_overlap_when_ranges_are_disjoint():
    sep = ordered.duration_separability([nonzero(), recovered()], "nonzero_exit", "recovered")
    assert sep["overlap_seconds"] == 0.0
    assert sep["best_threshold_accuracy"] == pytest.approx(1.0)


def test_duration_separability_detects_overlap_across_a_label():
    """Ranges that genuinely intersect must report a positive overlap."""
    fast = [nonzero() for _ in range(8)]
    slow = [recovered() for _ in range(8)]
    # Distinct objects, then widen both labels so their ranges intersect,
    # matching the shape of the released v0 data.
    for i, r in enumerate(fast):
        r["events"][1]["duration"] = 0.005 + (i % 4) * 0.002
    for i, r in enumerate(slow):
        r["events"][1]["duration"] = 0.007 + (i % 4) * 0.002
    sep = ordered.duration_separability(
        fast + slow, "nonzero_exit", "recovered"
    )
    assert sep["overlap_seconds"] > 0, sep
    assert sep["best_threshold_accuracy"] < 1.0, sep


# --- report ----------------------------------------------------------------


def synthetic_rows(repeats: int = 6) -> list[dict]:
    """Several rows per label so stratification applies, as in released data."""
    rows = []
    for _ in range(repeats):
        rows += [success(), nonzero(), recovered(), wait_first(), wait_last()]
    return rows


def test_report_runs_end_to_end_on_synthetic_rows(tmp_path):
    """The report must not crash and must emit all three tiers."""
    path = tmp_path / "synth.jsonl"
    rows = synthetic_rows()
    path.write_text("\n".join(json.dumps(r) for r in rows))
    out = subprocess.run(
        [sys.executable, "-m", "sbbench.report", f"synth={path}"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert out.returncode == 0, out.stderr
    assert "declared-budget baseline" in out.stdout
    assert "order-blind baseline" in out.stdout
    assert "temporal model" in out.stdout
    assert "gaps attributable to order" in out.stdout


def test_report_names_the_harness_prefix_cutoff(tmp_path):
    path = tmp_path / "synth.jsonl"
    rows = synthetic_rows()
    path.write_text("\n".join(json.dumps(r) for r in rows))
    out = subprocess.run(
        [sys.executable, "-m", "sbbench.report", f"synth={path}"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert f"{features.DEFAULT_PREFIX_CUTOFF} events" in out.stdout


def test_missing_path_is_skipped_not_fatal(tmp_path):
    out = subprocess.run(
        [sys.executable, "-m", "sbbench.report", "absent=/nonexistent.jsonl"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert out.returncode == 0
    assert "skip absent" in out.stdout


# --- integration, requires the real released data ---------------------------

V0 = Path("v0/data.jsonl")
V1ORD = Path("v1ord/data_v1ord.jsonl")


@pytest.mark.skipif(not V1ORD.exists(), reason="v1ord data not present")
def test_v1ord_declared_budget_is_at_chance():
    """The original gate claim must hold: counts and exit codes carry nothing."""
    import numpy as np

    from sbbench import probe

    rows, y, _ = probe.load(str(V1ORD))
    scores = probe.probe(rows, y, features.FAMILIES["order_blind_counts"]["featurizer"])
    assert abs(sum(scores) / len(scores) - 0.25) <= probe.CHANCE_TOLERANCE


@pytest.mark.skipif(not V1ORD.exists(), reason="v1ord data not present")
def test_v1ord_has_no_label_aliases():
    from sbbench import probe

    rows, _, _ = probe.load(str(V1ORD))
    assert ordered.detect_aliases(rows) == []


@pytest.mark.skipif(not V0.exists(), reason="v0 data not present")
def test_v0_alias_is_detected_in_released_data():
    from sbbench import probe

    rows, _, _ = probe.load(str(V0))
    assert ("nonzero_exit", "recovered") in ordered.detect_aliases(rows)

# --- observable-set parameterization ---------------------------------------


def test_event_channels_respects_declared_budget():
    ev = {"type": "execute", "exit_code": 3, "duration": 0.5}
    assert ordered.event_channels(ev, ordered.CHANNELS) == [3.0, 0.5]
    assert ordered.event_channels(ev, ("exit_code",)) == [3.0]


def test_event_channels_rejects_unknown_channel():
    with pytest.raises(ValueError):
        ordered.event_channels({"type": "execute"}, ("cpu_share",))


def test_ordered_probe_accepts_restricted_budget():
    """A durations-free observable set must be expressible, since v2 adopts it."""
    rows = synthetic_rows()
    labels = sorted({r["label"] for r in rows})
    import numpy as np

    y = np.array([labels.index(r["label"]) for r in rows])
    with_dur = ordered.ordered_probe(rows, y, epochs=2)
    without = ordered.ordered_probe(rows, y, epochs=2, use_durations=False)
    assert len(with_dur) == len(without) == len(ordered.SEEDS)


def test_default_budget_still_includes_duration():
    assert "duration" in ordered.CHANNELS


def test_probe_supports_separate_evaluation_set():
    """Fit and evaluate sets must be separable so a fixed split is honorable."""
    import numpy as np

    rows = synthetic_rows()
    labels = sorted({r["label"] for r in rows})
    y = np.array([labels.index(r["label"]) for r in rows])
    half = len(rows) // 2
    train, test = rows[:half], rows[half:]
    yt, ye = y[:half], y[half:]
    fn = features.FAMILIES["order_blind_counts"]["featurizer"]
    scores = probe.probe(train, yt, fn, eval_rows=test, eval_y=ye)
    assert len(scores) == len(probe.SEEDS)
    assert all(0.0 <= s <= 1.0 for s in scores)


def test_ordered_probe_supports_separate_evaluation_set():
    import numpy as np

    rows = synthetic_rows()
    labels = sorted({r["label"] for r in rows})
    y = np.array([labels.index(r["label"]) for r in rows])
    half = len(rows) // 2
    scores = ordered.ordered_probe(
        rows[:half], y[:half], epochs=2, eval_rows=rows[half:], eval_y=y[half:]
    )
    assert len(scores) == len(ordered.SEEDS)


def test_event_channel_helpers_are_pure():
    from sbbench.ordered import event_channels
    ev = {"type": "execute", "exit_code": 0, "duration": 0.25}
    assert event_channels(ev, ("exit_code", "duration")) == [0.0, 0.25]
