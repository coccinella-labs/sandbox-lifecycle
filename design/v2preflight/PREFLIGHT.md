# v2 collection preflight result

Verdict: **duration independence fails on real executions. v2 is not collectable
as specified.** Section 6 of the collection design applies.

## What was run

100 traces, 4 procedures x 25 repeats, real subprocess executions on
Darwin 27.0.0 arm64. Procedure order was randomized per repeat, unlike
`collect_v1ord.py`, which ran all repeats of one procedure before the next and
therefore confounded time drift with the label.

```bash
python design/v2preflight/collect_preflight.py preflight.jsonl 25
python design/v2preflight/preflight.py preflight.jsonl
python design/v2preflight/fallback.py
```

## Results against the section 5 failure table

| Condition | Observed | Gate | Result |
|---|---|---|---|
| D2 any Holm-corrected KS p-value | 0.00004 at idx=5 execute | < 0.01 fails | FAIL, 2 rejections |
| D3 `durations_only` | 0.3400 | > 0.3000 fails | FAIL |
| D3 `first_execute_duration` | 0.4000 | > 0.3000 fails | FAIL |
| D4 `order_blind_full` | 0.6900 | > 0.4000 fails | FAIL |

`order_blind_counts` is exactly 0.2500, so counts and exit codes still carry
nothing. The entire excess comes from timing.

D2 localises the cause. At index 5 the second `execute` takes systematically
different time in `recover_then_wait` than in `wait_during_outage` or
`delayed_fault`, KS statistic 0.60 to 0.64. In `recover_then_wait` that execute
follows a 2s sleep; in the other two it follows a `recover`. What precedes a
command changes how long the command takes, which is a real effect and exactly
the leak the preflight was built to detect.

## Fallback measurement

Run against the same traces, held-out-repeat protocol:

| Observable set | Ceiling | Gate 0.4000 |
|---|---|---|
| all non-order features, current | 0.6900 | FAIL |
| fallback 1, durations dropped | 0.2500 | PASS |
| fallback 2, magnitude-blind timing | 0.2500 | PASS |

Both fallbacks restore independence on this evidence. Fallback 1 remains
preferred by the design because it is the only one that does not require
re-validating anything downstream of the harness.

## The information boundary is confirmed

Exact ceilings on the collected real traces match the synthetic pilot exactly:

| cutoff | blind | order | headroom |
|---|---|---|---|
| 2 | 0.5000 | 0.5000 | 0.0000 |
| 3 | 0.5000 | 0.5000 | 0.0000 |
| 4 | 0.5000 | 0.7500 | 0.2500 |
| 5 | 0.5000 | 1.0000 | 0.5000 |
| 6 | 0.5000 | 1.0000 | 0.5000 |
| 7 | 0.2500 | 1.0000 | 0.7500 |
| 8 | 0.2500 | 1.0000 | 0.7500 |

Real executions reproduce the pilot's structure precisely. The design's ordering
signal is sound; only the observable set was wrong.

## Specification error found by execution

Section 4 D3 and D4 specify leaving out a whole procedure: train on repeats of
three procedures, test on repeats of the fourth. That protocol is unanswerable.
The held-out label never appears in training, so any classifier scores exactly
0.0000 and the check passes for the wrong reason. The first implementation of
this preflight returned 0.0000 on both and looked like a clean pass.

The correct protocol splits on repeat index with every label present on both
sides, testing whether a model trained on some executions can identify the same
procedure from a different execution. That is the memorization risk, and it is
what `repeat_holdout_probe` implements. All numbers above use the corrected
protocol.

## D1 is diagnostic, not a gate

The `wait` slot has a coefficient of variation of 0.0007 in all four
procedures, because the wait budget is a fixed 2.0s sleep. Every procedure
contains exactly one wait, so the slot is label-invariant and a constant there
costs realism rather than leaking information. The section 5 failure table
covers D2, D3 and D4 only, so D1 is reported and not gated. For a collection
that claims real execution-time variation, the fixed wait budget should be
replaced with jittered budgets.