"""v2 collector: the released benchmark dataset.

Fresh collection. The 800-trace temporal preflight remains published evidence
and is deliberately not merged into this release, so the benchmark has one
provenance, one collector version, and one split.

Differences from collect_preflight.py, all deliberate:

  * Split membership is assigned by shuffling repeat indices with a recorded
    seed, not by contiguous ranges. Repeat index correlates with collection
    time, so contiguous ranges would correlate split membership with machine
    state drift over the session.
  * Every label is present in every split by construction, since the shuffle
    operates on repeat indices shared by all four procedures.
  * Traces carry their split, and the full index-to-split map is written to run
    metadata so the split is auditable and reproducible.

Observable set is event type and exit code only. Duration and elapsed time are
stored for auditability and are not observable to any model.

Run:  python collect_v2.py v2.jsonl 400

The collected file is published as three native splits under ``v2/`` plus run
metadata at ``v2/run.json``. The monolithic collection file is deliberately not
published: on that path ``load_dataset`` exposes one 1600-row split with
``split`` as a plain column, so ``ds["test"]`` does not exist. Publishing it
would create an attractive but broken entry point to the benchmark contract.
"""

from __future__ import annotations

import itertools
import json
import os
import platform
import random
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

COLLECTOR_VERSION = "2.0.0-v2"
WAIT_BUDGET = 2.0
REPEATS = 400
SPLIT_SEED = 20261008
SCHEDULE_SEED = 20261008
#: 70 / 15 / 15, expressed as fractions of repeats per procedure.
SPLIT_FRACTIONS = (("train", 0.70), ("validation", 0.15), ("test", 0.15))

PROCEDURES = ("recover_then_wait", "wait_during_outage", "delayed_fault", "cooldown")

_counter = itertools.count(1)
_schedule_rng = random.Random(SCHEDULE_SEED)


def now() -> float:
    return time.monotonic()


def build_split_map(repeats: int, block: int = 20) -> dict[int, str]:
    """Assign every repeat index to exactly one split.

    Stratified by collection order. Repeat index correlates with wall-clock
    time of capture, so a plain shuffle still leaves split membership weakly
    correlated with machine-state drift across the session: in a 400-repeat
    trial a single shuffle put 62 train repeats in the first hundred and 81 in
    the last hundred.

    Each contiguous block of ``block`` repeats is shuffled independently and
    then sliced by the split fractions. That keeps the global split sizes exact
    while guaranteeing every block contributes the same proportion to every
    split, so split membership is decorrelated from collection order by
    construction rather than by luck.
    """
    rng = random.Random(SPLIT_SEED)
    out: dict[int, str] = {}
    sizes = {name: int(round(block * fraction)) for name, fraction in SPLIT_FRACTIONS}
    assigned = sum(sizes.values())
    if assigned != block:
        # Assign the remainder to the final split so no repeat is dropped.
        sizes[SPLIT_FRACTIONS[-1][0]] += block - assigned
    for start in range(0, repeats, block):
        chunk = list(range(start, min(start + block, repeats)))
        rng.shuffle(chunk)
        cursor = 0
        for name, _ in SPLIT_FRACTIONS:
            for i in chunk[cursor : cursor + sizes[name]]:
                out[i] = name
            cursor += sizes[name]
    return out


def run_cmd(argv, timeout=None):
    t0 = now()
    try:
        p = subprocess.run(
            argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout
        )
        return p.returncode, now() - t0
    except subprocess.TimeoutExpired:
        return None, now() - t0


def collect_one(procedure: str, repeat: int, date_tag: str) -> dict:
    t_start = now()
    events: list[dict] = []

    def E(typ, t, **kw):
        d = {"type": typ, "t": t}
        d.update(kw)
        events.append(d)

    t0 = now()
    time.sleep(0)
    E("sandbox_create", 0.0, duration=now() - t0)

    def do_exec(code: int) -> int:
        t = now() - t_start
        c, dur = run_cmd(["/bin/sh", "-c", f"exit {code}"])
        E("execute", t, duration=dur, exit_code=c)
        E("process_exit", now() - t_start, exit_code=c, signal=None)
        return c

    def do_recover() -> None:
        t = now() - t_start
        marker = f"/tmp/sb_v2_marker_{os.getpid()}"
        run_cmd(["/bin/sh", "-c", f": > {marker}"])
        run_cmd(["/bin/rm", "-f", marker])
        E("recover", t, duration=now() - t_start - t, clean=True)

    def do_wait() -> None:
        t = now() - t_start
        time.sleep(WAIT_BUDGET)
        E("wait", t, duration=now() - t_start - t)

    if procedure == "recover_then_wait":
        do_exec(3); do_recover(); do_wait(); do_exec(0)
    elif procedure == "wait_during_outage":
        do_exec(3); do_wait(); do_recover(); do_exec(0)
    elif procedure == "delayed_fault":
        do_wait(); do_exec(3); do_recover(); do_exec(0)
    elif procedure == "cooldown":
        do_exec(3); do_recover(); do_exec(0); do_wait()
    else:
        raise ValueError(procedure)

    E("sandbox_teardown", now() - t_start, duration=0.0, clean=True)
    return {
        "id": f"sbv2-{date_tag}-{next(_counter):06d}",
        "source": "sandbox-lifecycle-v2",
        "collector_version": COLLECTOR_VERSION,
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "procedure": procedure,
        "repeat": repeat,
        "events": events,
    }


def derive_label(seq: dict) -> tuple[str, bool]:
    exits = [e["exit_code"] for e in seq["events"] if e["type"] == "process_exit"]
    clean = seq["events"][-1].get("clean") is True
    ok = (
        seq["procedure"] in PROCEDURES
        and len(seq["events"]) == 8
        and exits == [3, 0]
        and clean
    )
    return seq["procedure"], ok


def main(out_path: str, repeats: int) -> None:
    date_tag = time.strftime("%Y%m%d", time.gmtime())
    split_map = build_split_map(repeats)

    schedule = [(proc, r) for r in range(repeats) for proc in PROCEDURES]
    _schedule_rng.shuffle(schedule)

    kept = quarantined = 0
    split_counts: Counter = Counter()
    with open(out_path, "w") as fq, open(out_path + ".quarantine.jsonl", "w") as fq_bad:
        for procedure, repeat in schedule:
            seq = collect_one(procedure, repeat, date_tag)
            label, ok = derive_label(seq)
            seq["label"] = label
            seq["split"] = split_map[repeat]
            if ok:
                fq.write(json.dumps(seq) + "\n")
                kept += 1
                split_counts[seq["split"]] += 1
            else:
                fq_bad.write(json.dumps(seq) + "\n")
                quarantined += 1

    meta = {
        "collector_version": COLLECTOR_VERSION,
        "os": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "procedures": list(PROCEDURES),
        "repeats_per_procedure": repeats,
        "wait_budget": WAIT_BUDGET,
        "schedule": "randomized interleaved",
        "schedule_seed": SCHEDULE_SEED,
        "split_seed": SPLIT_SEED,
        "split_fractions": dict(SPLIT_FRACTIONS),
        "split_index_map": {str(k): v for k, v in sorted(split_map.items())},
        "observable_set": ["event_type", "exit_code"],
        "not_observable": ["duration", "t"],
        "kept": kept,
        "quarantined": quarantined,
        "split_counts": dict(split_counts),
    }
    with open(out_path + ".run.json", "w") as f:
        json.dump(meta, f, indent=2)
    print(f"  kept={kept} quarantined={quarantined} splits={dict(split_counts)}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "v2.jsonl"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else REPEATS
    main(out, n)