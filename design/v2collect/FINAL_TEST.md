# v2 benchmark result, final test split

Scored once. Fit on the 1,120 train traces, evaluated on the 240 test traces,
which were untouched until this run. Chance 0.2500.

| cutoff | blind ceiling | order ceiling | headroom | reference probe | captured | seeds |
|---|---|---|---|---|---|---|
| 2 | 0.5000 | 0.5000 | 0.0000 | 0.5000 | n/a | 0.50, 0.50 |
| 3 | 0.5000 | 0.5000 | 0.0000 | 0.5000 | n/a | 0.50, 0.50 |
| 4 | 0.5000 | 0.7500 | 0.2500 | 0.7500 | 1.0000 | 0.75, 0.75 |
| 5 | 0.5000 | 1.0000 | 0.5000 | 1.0000 | 1.0000 | 1.00, 1.00 |
| 6 | 0.5000 | 1.0000 | 0.5000 | 1.0000 | 1.0000 | 1.00, 1.00 |
| 7 | 0.2500 | 1.0000 | 0.7500 | 1.0000 | 1.0000 | 1.00, 1.00 |
| 8 | 0.2500 | 1.0000 | 0.7500 | 1.0000 | 1.0000 | 1.00, 1.00 |

12 of 12 conditions hold. Validation numbers were identical, so the split
carries no distribution shift between train and test for this task.

Ceilings match the 800-trace temporal preflight and the synthetic pilot cell for
cell, at every cutoff. The information structure is a property of the four
procedures rather than of the sample, which is why a 1,600-row release and a
100-row preflight agree.

## Leakage report

Within the declared observable set, all at chance:

| family | score |
|---|---|
| `order_blind_counts` | 0.2500 |
| `counts_only` | 0.2500 |
| `exit_codes_only` | 0.2500 |

Aliases on observable fields: none.

Withheld from the observable set, reported for audit and not gated:

| family | score |
|---|---|
| `order_blind_full` | 0.8056 |
| `durations_only` | 0.5056 |
| `first_execute_duration` | 0.3500 |
| `prefix_fields` | 0.5000 |

These read duration. They are above chance because real executions make timing
informative, which is why duration is withheld. Reporting them is how a reader
can confirm the exclusion was necessary rather than convenient.

## Interpretation

The reference probe captures the full headroom at every cutoff where headroom
exists, and sits exactly on the blind ceiling at `t=2` and `t=3` where headroom
is zero. The claim is narrow: under this observable boundary, lifecycle ordering
contains predictive information beyond the declared order-blind ceiling.

The reference probe is a GRU. It is not the conclusion. The benchmark is
structured so a transformer, TCN, HMM, or rule-based temporal system can be
scored against the same ceilings without reinterpretation.
