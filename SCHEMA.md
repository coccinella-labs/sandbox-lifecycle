# Schema v0.1.0

One sequence per JSON line. Fixed fields only; producers must not add keys and
consumers may reject unknown ones.

## Sequence

| Field | Type | Meaning |
|---|---|---|
| `id` | string | `sb-YYYYMMDD-NNNNNN`, globally sequential counter per run |
| `source` | string | always `sandbox-lifecycle-v0` |
| `collector_version` | string | collector code version, `0.1.0` for this release |
| `collected_at` | string | UTC timestamp of collection |
| `procedure` | string | one of `success`, `fail`, `timeout`, `recover` |
| `events` | array | exactly four events in fixed order |
| `label` | string | mechanically derived, see below |

## Events

In order: `sandbox_create`, `execute`, `process_exit`, `sandbox_teardown`.

| Event | Fields |
|---|---|
| `sandbox_create` | `type`, `t` (0.0), `duration` |
| `execute` | `type`, `t`, `duration`, `exit_code` |
| `process_exit` | `type`, `t`, `exit_code`, `signal` (number or null) |
| `sandbox_teardown` | `type`, `t`, `duration`, `clean` (boolean) |

`t` is seconds since sequence start on a monotonic clock. `duration` is
seconds. Timestamps are measurements with millisecond precision, not logical
ordering; the event array order is the ordering guarantee.

## Timeout sentinel

`exit_code: -1` is reserved for termination by the fixed timeout budget and
cannot represent a normal process exit. This makes timeout classification
mechanically distinguishable from non-zero process exits: the derivation rule
matches `procedure == timeout` with `code == -1`, and no real exit code can
satisfy it by accident.

## Label derivation

Pure function of `(procedure, exit_code, clean)`:

| Procedure | Exit code | Clean | Label |
|---|---|---|---|
| `success` | 0 | true | `success` |
| `fail` | 3 | true | `nonzero_exit` |
| `timeout` | -1 | true | `timeout` |
| `recover` | 3 | true | `recovered` |
| any | any | false | `anomalous` |
| otherwise | | | `anomalous` |

Rows deriving `anomalous` are quarantined, not published. This release
contains zero such rows.

## Privacy boundary

The fixed field set is the entire exfiltration surface. There is no field for
standard output, standard error, arguments, environment, working directory,
hostname, or file contents, so secrets have no channel into the data. Verified
by canary test; see VALIDATION.md.
