"""v2 collection preflight: real executions, repeated, order-randomized.

Runs each v1ord procedure K times in a real subprocess environment and writes
raw traces with genuine timing. The purpose is measurement, not publication:
the output feeds the D1-D4 duration-independence checks.

Two deliberate differences from collect_v1ord.py:

  * Procedure order is randomized per repeat. collect_v1ord.py ran all repeats
    of one procedure before the next, so system state and time drift were
    confounded with the label. That is one plausible source of the v1ord
    duration leak.
  * Every repeat is retained with its repeat index, which makes the
    leave-one-repeat-out protocol in preflight.py well defined.

Run:  python collect_preflight.py out.jsonl 25
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

COLLECTOR_VERSION = "0.0.0-preflight"
WAIT_BUDGET = 2.0
PROCEDURES = ("recover_then_wait", "wait_during_outage", "delayed_fault", "cooldown")

_counter = itertools.count(1)
_rng = random.Random(20261007)


def now() -> float:
    return time.monotonic()


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
        marker = f"/tmp/sb_preflight_marker_{os.getpid()}"
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
        "id": f"v2pf-{date_tag}-{next(_counter):06d}",
        "source": "sandbox-lifecycle-v2-preflight",
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
    schedule = [(proc, r) for r in range(repeats) for proc in PROCEDURES]
    _rng.shuffle(schedule)

    kept = quarantined = 0
    with open(out_path, "w") as fq, open(out_path + ".quarantine.jsonl", "w") as fq_bad:
        for procedure, repeat in schedule:
            seq = collect_one(procedure, repeat, date_tag)
            label, ok = derive_label(seq)
            seq["label"] = label
            if ok:
                fq.write(json.dumps(seq) + "\n")
                kept += 1
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
        "purpose": "temporal preflight at spec sample size",
        "wait_budget": WAIT_BUDGET,
        "schedule": "randomized interleaved",
        "seed": 20261007,
    }
    with open(out_path + ".run.json", "w") as f:
        json.dump(meta, f, indent=2)
    print(f"  kept={kept} quarantined={quarantined}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "preflight.jsonl"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    main(out, n)