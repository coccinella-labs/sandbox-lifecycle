# Validation v0.1.0

Run against the published `data.jsonl` before release. All checks passed.

| Check | Result |
|---|---|
| Row count | 4,000 (1,000 per procedure) |
| Schema violations (exact keys, 4 events in order, no extra fields) | 0 |
| Label distribution | 1,000 each of `success`, `nonzero_exit`, `timeout`, `recovered` |
| Label derivation recomputed from fields, mismatches | 0 |
| IDs unique and globally sequential | true |
| Quarantined rows | 0 |
| Canary token occurrences in data, quarantine, run metadata | 0 |

No schema or collection exceptions occurred during the v0 run. Had any row
contradicted its procedure, it would appear in quarantine with label
`anomalous`; the quarantine file is empty.
