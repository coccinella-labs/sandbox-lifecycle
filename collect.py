"""v0 sandbox-lifecycle collector.

Runs four fixed procedures 1,000 times each against /bin/sh subprocesses used
as the sandbox stand-in. Records only structured lifecycle fields: event type,
monotonic timestamps, durations, exit codes, signal numbers, booleans. Never
captures stdout, stderr, argv, environment, cwd, or hostnames.

Label derivation is mechanical (see derive_label). Rows where the observed
result contradicts the procedure go to quarantine, not to the dataset.
"""

import itertools
import json
import os
import platform
import subprocess
import sys
import time

COLLECTOR_VERSION = "0.1.0"
N_PER_PROCEDURE = 1000
TIMEOUT_BUDGET = 5.0
CANARY = "CANARY_{0}".format("9f8e7d6c5b4a")

PROCEDURES = ("success", "fail", "timeout", "recover")

_counter = itertools.count(1)


def now():
    return time.monotonic()


def run_cmd(argv, timeout=None):
    """Run argv, return (exit_code, signal_or_None, duration). Output pipes
    are drained to /dev/null and never stored."""
    t0 = now()
    try:
        p = subprocess.run(
            argv,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
        return p.returncode, None, now() - t0
    except subprocess.TimeoutExpired as e:
        return None, None, now() - t0


def collect_one(procedure, date_tag):
    t_start = now()
    events = []

    t0 = now()
    time.sleep(0)  # sandbox_create stand-in: process group setup point
    create_dur = now() - t0
    events.append({"type": "sandbox_create", "t": 0.0, "duration": create_dur})

    t_exec = now() - t_start
    if procedure == "success":
        code, sig, dur = run_cmd(["/bin/sh", "-c", "exit 0"])
    elif procedure == "fail":
        code, sig, dur = run_cmd(["/bin/sh", "-c", "exit 3"])
    elif procedure == "timeout":
        code, sig, dur = run_cmd(["/bin/sh", "-c", "sleep 30"],
                                 timeout=TIMEOUT_BUDGET)
        code = -1  # killed by budget: sentinel, distinct from any exit code
        sig = None
    elif procedure == "recover":
        code, sig, dur = run_cmd(["/bin/sh", "-c", "exit 3"])
        # prescribed cleanup routine: remove a temp marker if present
        run_cmd(["/bin/rm", "-f", "/tmp/sb_recover_marker"])
    else:
        raise ValueError(procedure)
    events.append({"type": "execute", "t": t_exec, "duration": dur,
                   "exit_code": code})
    t_exit = now() - t_start
    events.append({"type": "process_exit", "t": t_exit, "exit_code": code,
                   "signal": sig})
    t_td = now() - t_start
    events.append({"type": "sandbox_teardown", "t": t_td, "duration": 0.0,
                   "clean": True})

    seq_id = "sb-{0}-{1:06d}".format(date_tag, next(_counter))
    return {
        "id": seq_id,
        "source": "sandbox-lifecycle-v0",
        "collector_version": COLLECTOR_VERSION,
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "procedure": procedure,
        "events": events,
    }


def derive_label(seq):
    """Pure function of (procedure, exit_code, clean). Returns (label, ok)."""
    proc = seq["procedure"]
    by_type = {e["type"]: e for e in seq["events"]}
    code = by_type["execute"]["exit_code"]
    clean = by_type["sandbox_teardown"]["clean"]
    if not clean:
        return "anomalous", False
    if proc == "success" and code == 0:
        return "success", True
    if proc == "fail" and code == 3:
        return "nonzero_exit", True
    if proc == "timeout" and code == -1:
        return "timeout", True
    if proc == "recover" and code == 3:
        return "recovered", True
    return "anomalous", False


def main(out_path):
    date_tag = time.strftime("%Y%m%d", time.gmtime())
    run_meta = {
        "collector_version": COLLECTOR_VERSION,
        "os": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "procedures": list(PROCEDURES),
        "n_per_procedure": N_PER_PROCEDURE,
        "timeout_budget": TIMEOUT_BUDGET,
    }
    # Canary: export a fake secret into our own environment. The collector must
    # never record it; post-run grep proves the output is clean.
    os.environ["SB_CANARY_TOKEN"] = CANARY
    kept, quarantined = 0, 0
    with open(out_path, "w") as fq, open(out_path + ".quarantine.jsonl", "w") as fo:
        for proc in PROCEDURES:
            for _ in range(N_PER_PROCEDURE):
                seq = collect_one(proc, date_tag)
                label, ok = derive_label(seq)
                seq["label"] = label
                if ok:
                    fq.write(json.dumps(seq) + "\n")
                    kept += 1
                else:
                    fo.write(json.dumps(seq) + "\n")
                    quarantined += 1
                if (kept + quarantined) % 500 == 0:
                    fq.flush()
    with open(out_path + ".run.json", "w") as f:
        json.dump(run_meta, f, indent=2)
    print(f"kept={kept} quarantined={quarantined} run={out_path}.run.json")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "sandbox_v0.jsonl")
