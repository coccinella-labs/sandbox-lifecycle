---
license: mit
tags:
- event-sequences
- systems
- sandbox
- benchmark
- provenance
task_categories:
- tabular-classification
configs:
- config_name: v2
  data_files:
  - split: train
    path: v2/train.jsonl
  - split: validation
    path: v2/validation.jsonl
  - split: test
    path: v2/test.jsonl
---

# sandbox-lifecycle v2

1,600 controlled sandbox lifecycle traces, 400 per procedure, collected from
real subprocess executions. v2 is a **benchmark**, not a training set for
another model.

## What this measures

The task is not `trace` to `label`. It is a cutoff sweep:

```text
partial trace at t
  -> non-order information available at t
  -> additional information from ordering
  -> remaining headroom
```

The primary metric is the fraction of headroom captured at each cutoff. The
full-trace task saturates at 1.0000, so full-trace accuracy cannot discriminate
between architectures and is not the headline number.

## Observable set

Event type and exit code only. `duration` and `t` are present in the file for
auditability but are **not observable to any model**. Real executions make
duration informative, which is why they are withheld.

## Procedures

Every trace has exactly the same 8 events with an identical multiset of types
and exit codes, and identical final state (exit 0, clean). Labels differ only
by where `wait` and `recover` sit:

```text
recover_then_wait   create execute exit recover WAIT execute exit teardown
wait_during_outage  create execute exit WAIT recover execute exit teardown
delayed_fault       create WAIT execute exit recover execute exit teardown
cooldown            create execute exit recover execute exit WAIT teardown
```

## Final test results

Fit on 1,120 train traces, scored once on the 240 untouched test traces.

| cutoff | blind ceiling | order ceiling | headroom | probe | captured |
|---|---|---|---|---|---|
| 2 | 0.5000 | 0.5000 | 0.0000 | 0.5000 | n/a |
| 3 | 0.5000 | 0.5000 | 0.0000 | 0.5000 | n/a |
| 4 | 0.5000 | 0.7500 | 0.2500 | 0.7500 | 1.0000 |
| 5 | 0.5000 | 1.0000 | 0.5000 | 1.0000 | 1.0000 |
| 6 | 0.5000 | 1.0000 | 0.5000 | 1.0000 | 1.0000 |
| 7 | 0.2500 | 1.0000 | 0.7500 | 1.0000 | 1.0000 |
| 8 | 0.2500 | 1.0000 | 0.7500 | 1.0000 | 1.0000 |

`t=2` and `t=3` are negative controls. Only `delayed_fault` is identifiable from
that prefix, so no model may exceed 0.5000. The reference probe sits exactly on
the blind ceiling at both.

## Leakage report

Within the observable set, all exactly at chance: `order_blind_counts`,
`counts_only`, and `exit_codes_only` at 0.2500. Zero label aliases.

Withheld and reported for audit: `order_blind_full` 0.8056, `durations_only`
0.5056, `first_execute_duration` 0.3500. Above chance because real executions
make timing informative. This is why duration is withheld.

## Splits

Repeat-aware and fixed, 70/15/15. Every repeat index belongs entirely to one
split, so no two executions of the same procedure instance straddle a boundary.
Split membership is shuffled within contiguous time blocks, so it does not
correlate with collection time. The full index map is in `v2.jsonl.run.json`.

Splits are published as native dataset splits, so `test` is reachable directly.

```python
from datasets import load_dataset
ds = load_dataset("coccinella-labs/sandbox-lifecycle", "v2")
train, validation, test = ds["train"], ds["validation"], ds["test"]
print(len(train), len(validation), len(test))   # 1120 240 240
```

The `split` column is retained in every row for auditability.

## Source

Collector, validation, benchmark, and the full design chain are in
https://github.com/coccinella-labs/sandbox-lifecycle under `design/`.

## Not claimed

Nothing here supports a claim about production sandbox failures, unseen event
vocabularies, real timing behaviour, or any architecture being superior to
another. All traces come from one machine, one OS version, and one collection
session. Timing is out of scope by design.