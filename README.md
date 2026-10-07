# sandbox-lifecycle

Controlled sandbox lifecycle traces across three dataset configurations.

| Version | What it is | Release |
|---|---|---|
| v0.1.0 | 4,000 controlled lifecycle sequences with mechanical labels | tag and release |
| v1.0.0 | 4,000 ordering sequences with identical event bags | tag and release |
| v2 | 1,600 real-execution traces and a benchmark with a cutoff sweep | no release, by design |

v2 is a benchmark configuration and artifact, not a third dataset release, so it
carries no tag. See Releases for v0.1.0 and v1.0.0.

## v0.1.0

4,000 sequences, each a create, execute, exit, and teardown with monotonic
timing. Labels derive mechanically from the controlled procedure and the
observed result. No stdout, stderr, environment, paths, hostnames, or
credentials are collected at any point. Build and test activity is a planned
future source, not part of this release.

## v1.0.0

4,000 sequences where every trace carries exactly 8 events with identical type
and exit-code bags across labels, and identical final state, exit 0 and clean.
Procedures differ only in where the wait falls in the failure lifecycle.

Order is sufficient for perfect separation, with one qualification the later
leakage analysis established: counts and exit codes reach exactly chance, so an
ordered model scoring 1.0000 beats the declared order-blind budget. Event
durations are also weakly label-bearing, and a probe over all permitted non-order
features reaches 0.9579, leaving order a margin of 0.0421 rather than 0.75. The
v2 design removes duration from the observable set as a result.

## v2

1,600 traces from real subprocess executions, 400 per procedure, split into
native train, validation, and test splits at 1,120 / 240 / 240.

The split is repeat-aware: every repeat index belongs entirely to one split, so
no two executions of the same procedure instance straddle a boundary. Split
membership is shuffled within contiguous 20-repeat blocks so it does not
correlate with collection time.

**What it measures.** Not `trace` to `label`, but a cutoff sweep:

```text
partial trace at t
  -> non-order information available at t
  -> additional information from ordering
  -> remaining headroom
```

The primary metric is the fraction of headroom captured at each cutoff. The
full-trace task saturates, so full-trace accuracy does not discriminate between
architectures and is not the headline number. Cutoffs 2 and 3 are negative
controls where the headroom is zero by construction.

**Observable set.** Event type and exit code only. `duration` and `t` are
retained in the file for auditability but are not observable to any model,
because real executions make duration informative. The leakage report shows
this explicitly rather than only asserting the boundary.

**Result.** 12 of 12 conditions hold on the test split, scored once after
fitting on train. The ceilings match the synthetic pilot and the two real
preflights cell for cell at every cutoff, so the information structure comes
from the procedure design rather than sampling.

| cutoff | blind ceiling | order ceiling | headroom | captured |
|---|---|---|---|---|
| 2 | 0.5000 | 0.5000 | 0.0000 | n/a |
| 3 | 0.5000 | 0.5000 | 0.0000 | n/a |
| 4 | 0.5000 | 0.7500 | 0.2500 | 1.0000 |
| 5 | 0.5000 | 1.0000 | 0.5000 | 1.0000 |
| 6 | 0.5000 | 1.0000 | 0.5000 | 1.0000 |
| 7 | 0.2500 | 1.0000 | 0.7500 | 1.0000 |
| 8 | 0.2500 | 1.0000 | 0.7500 | 1.0000 |

A GRU is used as the reference probe. It is not the conclusion, and the
benchmark is structured so a transformer, TCN, or rule-based temporal system can
be scored against the same ceilings without reinterpretation.

## Labels

v0.1.0:

| Label | Count | Meaning |
|---|---|---|
| `success` | 1,000 | exit 0, clean teardown |
| `nonzero_exit` | 1,000 | fixed script exits 3, clean teardown |
| `timeout` | 1,000 | killed at the 5s budget, clean teardown |
| `recovered` | 1,000 | exit 3, prescribed cleanup runs, clean teardown |

v1.0.0 and v2 share these labels, 1,000 and 400 each respectively, differing
only in wait position:

| Label | Meaning |
|---|---|
| `recover_then_wait` | fault, recovery, wait, then success |
| `wait_during_outage` | fault, wait during outage, recovery, success |
| `delayed_fault` | wait first, then fault, recovery, success |
| `cooldown` | fault, recovery, success, then wait |

## Published artifacts

- Dataset: https://huggingface.co/datasets/coccinella-labs/sandbox-lifecycle
  with `v0`, `v1ord`, and `v2` configs.
- Temporal model: https://huggingface.co/harpertoken/flow

```python
from datasets import load_dataset

ds = load_dataset("coccinella-labs/sandbox-lifecycle", "v2")
print(len(ds["train"]), len(ds["validation"]), len(ds["test"]))  # 1120 240 240
```

## Files

- `data.jsonl`, `collect.py`, `SCHEMA.md`, `COLLECTION.md`, `VALIDATION.md`:
  v0.1.0 data, collector, field specification, provenance, and validation.
- `data_v1ord.jsonl`, `collect_v1ord.py`, `VALIDATION_V1ORD.md`: v1.0.0.
- `v2/`: released v2 splits and run metadata. The monolithic collection file is
  deliberately not published, because on that path the train/validation/test
  contract is not exposed. `design/v2collect/collect_v2.py` documents the
  reasoning, alongside `design/v2collect/validate_v2.py` and
  `design/v2collect/benchmark.py`.
- `bench/`: the frozen evaluation harness, with feature-family probing, label
  aliasing detection, and the three baseline tiers.
- `design/`: the full v2 chain: information boundary, collection design,
  collection preflight, temporal preflight at spec sample size, pilot, and the
  final benchmark result.
- `LICENSE`: MIT.

## Not claimed

Nothing here supports a claim about production sandbox failures, unseen event
vocabularies, real timing behaviour, or any architecture being superior to
another. All traces come from one machine, one OS version, and one collection
session. Timing is out of scope by design.