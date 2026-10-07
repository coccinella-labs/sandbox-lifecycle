"""v1-ordering collector: identical multisets, order-only labels.

Every sequence has exactly 8 events with the identical multiset
{create:1, execute:2 (codes 3,0), exit:2 (codes 3,0), recover:1, wait:1,
teardown:1} and identical final state (exit 0, clean). Procedures differ ONLY
in where the wait falls in the failure lifecycle. Count, bags, durations, and
final fields are constant across classes by construction, so any classifier
advantage must come from order.
"""

import itertools
import json
import os
import platform
import subprocess
import sys
import time

COLLECTOR_VERSION = "1.0.0-ord"
N_PER_PROCEDURE = 1000
WAIT_BUDGET = 2.0
CANARY = "CANARY_{0}".format("7a1e4c8b3d6f")

PROCEDURES = ("recover_then_wait", "wait_during_outage", "delayed_fault",
              "cooldown")

_counter = itertools.count(1)


def now():
    return time.monotonic()


def run_cmd(argv, timeout=None):
    t0 = now()
    try:
        p = subprocess.run(argv, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=timeout)
        return p.returncode, None, now() - t0
    except subprocess.TimeoutExpired:
        return None, None, now() - t0


def collect_one(procedure, date_tag):
    t_start = now()
    events = []

    def E(typ, t, **kw):
        d = {"type": typ, "t": t}
        d.update(kw)
        events.append(d)

    t0 = now()
    time.sleep(0)
    E("sandbox_create", 0.0, duration=now() - t0)

    def do_exec(code):
        t = now() - t_start
        c, _, dur = run_cmd(["/bin/sh", "-c", f"exit {code}"])
        E("execute", t, duration=dur, exit_code=c)
        t2 = now() - t_start
        E("process_exit", t2, exit_code=c, signal=None)
        return c

    def do_recover():
        t = now() - t_start
        run_cmd(["/bin/rm", "-f", "/tmp/sb_recover_marker"])
        E("recover", t, duration=now() - t_start - t, clean=True)

    def do_wait():
        t = now() - t_start
        time.sleep(WAIT_BUDGET)
        E("wait", t, duration=now() - t_start - t)

    if procedure == "recover_then_wait":
        do_exec(3)
        do_recover()
        do_wait()
        do_exec(0)
    elif procedure == "wait_during_outage":
        do_exec(3)
        do_wait()
        do_recover()
        do_exec(0)
    elif procedure == "delayed_fault":
        do_wait()
        do_exec(3)
        do_recover()
        do_exec(0)
    elif procedure == "cooldown":
        do_exec(3)
        do_recover()
        do_exec(0)
        do_wait()
    else:
        raise ValueError(procedure)

    t_td = now() - t_start
    E("sandbox_teardown", t_td, duration=0.0, clean=True)

    seq_id = "sb1o-{0}-{1:06d}".format(date_tag, next(_counter))
    return {
        "id": seq_id,
        "source": "sandbox-lifecycle-v1ord",
        "collector_version": COLLECTOR_VERSION,
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "procedure": procedure,
        "events": events,
    }


def derive_label(seq):
    exits = [e["exit_code"] for e in seq["events"]
             if e["type"] == "process_exit"]
    clean = seq["events"][-1].get("clean") is True
    if exits[-1] != 0 or not clean:
        return seq["procedure"], False
    if seq["procedure"] in PROCEDURES and len(seq["events"]) == 8:
        return seq["procedure"], True
    return seq["procedure"], False


def main(out_path, n_per_proc=N_PER_PROCEDURE):
    date_tag = time.strftime("%Y%m%d", time.gmtime())
    run_meta = {
        "collector_version": COLLECTOR_VERSION,
        "os": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "procedures": list(PROCEDURES),
        "n_per_procedure": n_per_proc,
        "wait_budget": WAIT_BUDGET,
    }
    os.environ["SB_CANARY_TOKEN"] = CANARY
    kept, quarantined = 0, 0
    with open(out_path, "w") as fq, open(out_path + ".quarantine.jsonl", "w") as fo:
        for proc in PROCEDURES:
            for _ in range(n_per_proc):
                seq = collect_one(proc, date_tag)
                label, ok = derive_label(seq)
                seq["label"] = label
                if ok:
                    fq.write(json.dumps(seq) + "\n")
                    kept += 1
                else:
                    fo.write(json.dumps(seq) + "\n")
                    quarantined += 1
    with open(out_path + ".run.json", "w") as f:
        json.dump(run_meta, f, indent=2)
    print(f"kept={kept} quarantined={quarantined}")


if __name__ == "__main__":
    n = int(sys.argv[2]) if len(sys.argv) > 2 else N_PER_PROCEDURE
    main(sys.argv[1] if len(sys.argv) > 1 else "sandbox_v1ord.jsonl", n)
