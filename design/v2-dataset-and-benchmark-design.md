# v2 dataset and benchmark design

Predecessors: `v2-information-boundary.md` (observable set), `v2-collection-design.md`
(duration-independence protocol), `v2preflight/PREFLIGHT.md` (independence
failed), `v2pilot/TEMPORAL_PREFLIGHT.md` (temporal question cleared).

Status: collection authorized. Nothing collected under this design yet.

## 1. Primary artifact

The benchmark. A trained model is optional and may never be built.

The experiment established that under the declared observable boundary,
lifecycle ordering carries predictive information beyond the declared
order-blind ceiling. It did not establish that GRUs are well suited to sandbox
lifecycle prediction. The GRU is the **reference temporal probe**, not the
conclusion, so the benchmark stays open to a transformer, TCN, HMM, rule-based
temporal system, or a small purpose-built sequence model without reinterpretation.

## 2. What the benchmark measures

Not `trace → label`. The measured object is a cutoff sweep:

```text
partial trace at t
  → non-order information available at t
  → additional information from ordering
  → remaining headroom
```

The primary metric is **fraction of headroom captured at each cutoff**:

```text
captured(t) = (score(t) - blind_ceiling(t)) / (order_ceiling(t) - blind_ceiling(t))
```

evaluated only where `headroom(t) > 0`, with `t=2` and `t=3` as negative
controls where headroom is zero and no model may exceed the blind ceiling.

## 3. Saturation, stated plainly

At `t=5` the reference probe already reaches 1.0000, and `t=7` and `t=8` add
nothing. **The full-trace task is saturated.** Any competent sequence model will
score 1.0000 there, so full-trace accuracy is not a useful discriminator between
architectures and must not be the headline metric.

The benchmark's discriminating power lives entirely in the cutoff sweep, where
the difficulty gradient runs from impossible (`t=2,3`, ceiling 0.5000) through
partial (`t=4`, ceiling 0.7500) to saturated (`t>=5`). Reporting `captured(t)`
across that gradient is what separates a model that learned ordering from one
that memorized a procedure signature.

## 4. Volume

Recommended: **400 repeats per procedure, 1,600 traces**, a fresh dedicated
collection.

Justification, stated as a trade rather than a preference:

- Above 200 repeats per procedure, accuracy buys nothing. The reference probe
  reached 1.0000 with both seeds identical at 200, and the ceilings are a
  property of the procedures rather than the sample. Volume beyond 200 buys
  **comparability, not accuracy**.
- 200 repeats per procedure leaves roughly 1,100 training traces after a
  three-way split. That is thin for a transformer and risks a benchmark that
  reports architecture failure as signal quality.
- 400 repeats leaves roughly 1,120 training traces. Not generous, but enough
  that a weak architecture failing is informative rather than starved.
- 1,600 traces is roughly 1.9 hours of collection at the observed 4.2s per trace.

If the intent narrows to a small reproducible benchmark rather than a public
architecture comparison, the existing 800 traces are sufficient and nothing new
needs collecting.

## 5. Collection

A fresh collection, not an extension of the 800 preflight traces, so the
release has one coherent provenance, one collector version, and one split.
The 800 preflight traces remain published as evidence for the temporal question
and are not folded into the dataset.

- Same four procedures as v1ord, so v2 remains comparable.
- Randomised interleaved schedule. `collect_v1ord.py` ran all repeats of one
  procedure before the next, confounding time drift with the label; that is a
  likely source of the v1ord timing artifact and is not repeated.
- Fixed 2.0s wait budget, unchanged and deliberately not jittered. It is
  label-invariant, so it costs realism without leaking, and jittering would add a
  variable without moving the information boundary.
- Collector records OS, release, machine, seed, and schedule in run metadata.

## 6. Split protocol

Repeat-aware and fixed. Every repeat index belongs entirely to one split, so no
two executions of the same procedure instance straddle a boundary.

| split | repeats per procedure | share | traces |
|---|---|---|---|
| train | 0 to 279 | 70% | 1,120 |
| validation | 280 to 339 | 15% | 240 |
| test | 340 to 399 | 15% | 240 |

The permutation is generated once from a recorded seed and stored in the
release, so the split is reproducible and cannot drift between releases.

**The test split is not touched during development.** Baselines are trained and
selected on train, tuned on validation, and evaluated on test exactly once. Any
architecture comparison published later reports test numbers produced under that
rule.

The row-level random split used by v0 and v1ord is not reused. With real traces
it would place near-identical timings from the same execution on both sides of
the boundary.

## 7. Observable set

Event type and exit code only. Duration is retained in the stored traces for
auditability but is **not observable to any model**, and the leakage report
verifies that excluding it is correct. Elapsed time `t` is retained for the same
reason and is likewise not observable.

## 8. Required benchmark outputs

Every run of the benchmark reports:

1. Per-cutoff blind ceiling, order ceiling, headroom, and captured fraction.
2. Reference temporal probe score per cutoff, all seeds shown.
3. Negative-control check at `t=2` and `t=3`.
4. Leakage report: order-blind probes at each tier under the declared observable
   set, plus alias detection on observable fields.
5. Sample size and split identifiers used.

The leakage report is not optional. It is what caught the v0 alias and the v1ord
duration leak, and a benchmark that cannot detect those is worse than no
benchmark.

## 9. Validation gate before release

Rows are quarantined unless the procedure matches mechanically, exactly 8 events
occur, exit codes are `[3, 0]`, and teardown is clean. Release requires:

- zero quarantined rows in the published file
- blind ceiling 0.2500 at `t=8` under the declared observable set
- zero aliases on observable fields
- blind and order ceilings matching the recorded pilot ceilings at every cutoff
- reference probe at `t=8` at or above 0.9500

## 10. Not claimed

Nothing here supports a claim about production sandbox failures, unseen event
vocabularies, real timing behaviour, or cross-architecture superiority. All
traces come from one machine, one OS version, and one collection session, which
is a generalisation limit that additional volume does not remove.

Timing is out of scope by design. This benchmark asks whether ordering alone
carries the label once execution time is withheld. A benchmark about realistic
timing variation is a separate experiment needing its own design.