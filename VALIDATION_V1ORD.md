# Validation v1ord

Pilot (200 sequences) then full run (4,000), same gate both times.

| Check | Pilot | Full |
|---|---|---|
| Rows | 200 | 4,000 |
| Event counts | all 8 | all 8 |
| Type/exit bags identical across labels | true | true |
| Rows ending exit-0 + clean | all | all |
| Quarantined | 0 | 0 |
| Canary occurrences | 0 | 0 |
| Field-only accuracy | 0.3750 | 0.2362 / 0.2537 |
| Ordered GRU accuracy | 1.0000 | 1.0000 / 1.0000 |

Field results across seeds confirm chance-level aggregates; GRU replication
confirms ordering carries the signal.
