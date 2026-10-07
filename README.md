# sandbox-lifecycle

v0.1.0: controlled lifecycle events. v1.0.0: ordering experiment. Both releases live in this repo; see Releases.

Controlled sandbox lifecycle events: 4,000 sequences, each a create, execute,
exit, and teardown with monotonic timing. Labels derive mechanically from the
controlled procedure and the observed result. No stdout, stderr, environment,
paths, hostnames, or credentials are collected at any point.

v0.1.0 covers controlled sandbox lifecycle events only. Build and test activity
is a planned future source, not part of this release.

## Files

- `data.jsonl`: 4,000 sequences, one JSON object per line.
- `collect.py`: the v0 collector that produced this release, pinned at
  `collector_version 0.1.0`. Rerunning it reproduces the procedure; timing
  values will differ run to run, which is signal rather than noise.
- `SCHEMA.md`: field specification, the timeout sentinel, and label rules.
- `COLLECTION.md`: collection procedure and run provenance.
- `VALIDATION.md`: the validation report for v0.1.0.
- `data_v1ord.jsonl`: 4,000 ordering sequences (v1.0.0).
- `collect_v1ord.py`: the v1ord collector.
- `VALIDATION_V1ORD.md`: the validation report for v1ord.
- `LICENSE`: MIT.

## v1ord: ordering experiment

`data_v1ord.jsonl` holds 4,000 sequences designed so order is the only signal:
every sequence carries exactly 8 events with identical type and exit-code bags
across labels, and identical final state (exit 0, clean). Procedures differ
only in where the wait falls in the failure lifecycle. Produced by
`collect_v1ord.py`. Field-only baseline scores chance; ordered GRU scores
1.0000 on two seeds. See VALIDATION_V1ORD.md.

## Labels

| Label | Count | Meaning |
|---|---|---|
| `success` | 1,000 | exit 0, clean teardown |
| `nonzero_exit` | 1,000 | fixed script exits 3, clean teardown |
| `timeout` | 1,000 | killed at the 5s budget, clean teardown |
| `recovered` | 1,000 | exit 3, prescribed cleanup runs, clean teardown |

v1ord labels (all end exit 0, clean; 1,000 each; differ only in wait position):

| Label | Meaning |
|---|---|
| `recover_then_wait` | fault, recovery, wait, then success |
| `wait_during_outage` | fault, wait during outage, recovery, success |
| `delayed_fault` | wait first, then fault, recovery, success |
| `cooldown` | fault, recovery, success, then wait |

## Use

```python
import json
rows = [json.loads(l) for l in open("data.jsonl")]
print(rows[0]["label"], [e["type"] for e in rows[0]["events"]])
```
