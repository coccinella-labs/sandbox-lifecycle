# Temporal preflight result

Verdict: **the order signal is measurable on real executions at the sample size
the specification requires.** 8 of 8 conditions hold.

This run answers exactly one question and does not restate any other. It is not
v2 collection.

## The question

Does ordering remain measurable on real executions once the temporal probe has
the 200 rows per label that the information boundary spec requires?

The 100-trace preflight could not answer it. At 25 repeats per label the probe
scores 0.7500, which is a training-budget artifact rather than a dataset
property, and `sizecheck.py` demonstrates that mechanism directly.

## What was run

800 traces, 4 procedures x 200 repeats, real subprocess executions on
Darwin 27.0.0 arm64, randomized interleaved schedule, zero quarantined. Every
trace has exactly 8 events. Observable set is event type and exit code only;
duration is withheld.

```bash
python design/v2pilot/collect_preflight.py temporal_preflight.jsonl 200
python design/v2pilot/temporal_preflight.py temporal_preflight.jsonl
```

## Results

| cutoff | blind ceiling | order ceiling | headroom | GRU | seeds |
|---|---|---|---|---|---|
| 2 | 0.5000 | 0.5000 | 0.0000 | 0.5000 | 0.50, 0.50 |
| 3 | 0.5000 | 0.5000 | 0.0000 | 0.5000 | 0.50, 0.50 |
| 4 | 0.5000 | 0.7500 | 0.2500 | 0.7500 | 0.75, 0.75 |
| 5 | 0.5000 | 1.0000 | 0.5000 | 1.0000 | 1.00, 1.00 |
| 6 | 0.5000 | 1.0000 | 0.5000 | 1.0000 | 1.00, 1.00 |
| 7 | 0.2500 | 1.0000 | 0.7500 | 1.0000 | 1.00, 1.00 |
| 8 | 0.2500 | 1.0000 | 0.7500 | 1.0000 | 1.00, 1.00 |

The GRU captures 100% of available headroom at every cutoff where headroom
exists, and sits exactly on the blind ceiling at t=2 and t=3 where headroom is
zero by construction. Both seeds agree exactly at every cutoff, so the result
is not seed-dependent.

The ceilings are identical to the 100-trace preflight and to the synthetic
pilot, cell for cell. The information structure is a property of the procedures,
not of the sample.

## Scope, deliberately narrow

The observable-set claim is not re-tested here and this run must not be cited as
evidence for it. That claim is owned by the 100-trace preflight, which measured
`order_blind_counts` at 0.2500 with zero aliases once duration was withheld.
Re-measuring it at 200 repeats would produce a larger sample of a closed
question and would let this run retroactively appear to support it.

## What remains

Collecting v2 at scale is a separate decision and is not authorized by this
result. What is now established:

| Question | Evidence | Status |
|---|---|---|
| Are durations safe to expose? | 100 real traces, 0.2500 after removal | Pass |
| Are counts and exit codes order-blind? | 100 real traces, 0.2500, no aliases | Pass |
| Does ordering carry the intended signal on real executions? | 800 real traces, 8/8 | Pass |
| Is v2 collection authorized? | a decision, not a measurement | No |

The last remaining design input is the collection design for the actual
dataset: volume, split protocol at scale, and whether a model is trained at all
or whether v2 ships as a benchmark only.