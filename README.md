# sandbox-lifecycle v0.1.0

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
- `VALIDATION.md`: the validation report for this release.
- `LICENSE`: MIT.

## Labels

| Label | Count | Meaning |
|---|---|---|
| `success` | 1,000 | exit 0, clean teardown |
| `nonzero_exit` | 1,000 | fixed script exits 3, clean teardown |
| `timeout` | 1,000 | killed at the 5s budget, clean teardown |
| `recovered` | 1,000 | exit 3, prescribed cleanup runs, clean teardown |

## Use

```python
import json
rows = [json.loads(l) for l in open("data.jsonl")]
print(rows[0]["label"], [e["type"] for e in rows[0]["events"]])
```
