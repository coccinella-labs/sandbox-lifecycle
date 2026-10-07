# v2 collection design

> **Superseded for collection. Retained as evidence.**
>
> This is the pre-collection design for *proving duration independence*, and it
> did its job: the measurements it specifies (D1 through D4) found that
> independence **fails** on real executions, which is why the observable set
> changed. The 25-repeat pilot below is the preflight experiment, not the
> collection specification.
>
> The shipped collection is 400 repeats per procedure, 1,600 traces, published
> as native train/validation/test splits at 1,120 / 240 / 240. See
> `v2-dataset-and-benchmark-design.md`, and `v2preflight/PREFLIGHT.md` for the
> measurement outcome.
>
> The section 5 failure table and the fallback hierarchy remain accurate
> descriptions of how the decision was reached.

Predecessor: `v2-information-boundary.md`. Status at time of writing: design,
not collected.

This document specifies how real sandbox traces would be produced and, most
importantly, how duration independence would be measured and what constitutes
failure. If duration independence cannot be demonstrated on real executions,
that is a finding, not a reason to quietly proceed.

## 1. What collection must demonstrate

That order carries information about sandbox lifecycle outcome on traces
produced by real executions, and that the result survives every non-order
baseline in the frozen harness.

## 2. Execution harness

Each procedure is executed in a real sandbox. Traces are emitted by the same
event vocabulary as v0 and v1ord: `sandbox_create`, `execute`,
`process_exit`, `recover`, `wait`, `sandbox_teardown`.

The four procedures remain those of v1ord, so v2 is comparable to v1ord. What
changes is that durations are now produced by real process timing rather than
assigned by the generator.

## 3. Repeats are the null distribution

This is the structural difference from v0 and v1ord. Each procedure is executed
`K` times, with `K = 25` for the collection pilot. The repeats of one procedure
share a label but differ in real timing, so within-procedure variance is the
null against which any label-bearing duration signal is measured.

Without repeats there is no null: a single trace per procedure cannot
distinguish "durations differ because of the procedure" from "durations differ
by chance", which is precisely the ambiguity that produced the v1ord leak.

Total pilot: 4 procedures x 25 repeats = 100 traces.

## 4. Measuring duration independence

Duration independence is a measured property, never an assumption. Four checks,
all computed per event position and per cutoff in `{2, 3, 4, 5, 6, 7, 8}`.

### D1  Within-procedure spread

For each procedure, report the coefficient of variation of each event duration
across its repeats. A procedure whose durations are nearly constant across
repeats is behaving like a generator, not a real execution.

### D2  Across-procedure separation

For each event position, test whether any procedure's duration distribution is
distinguishable from another's. Use a two-sample Kolmogorov-Smirnov test per
pair, with Holm correction across pairs.

### D3  Label-informativeness of duration

Train the order-blind `durations_only` probe on the repeats of three procedures
and evaluate on held-out repeats of the fourth. This is the leave-one-repeat-out
protocol, so a model cannot memorize one trace's specific timing.

### D4  Full order-blind ceiling

Run the frozen `order_blind_full` family under the same leave-one-repeat-out
protocol and record the result. This is the number any temporal claim must
exceed.

## 5. What constitutes failure

Duration independence fails if any of the following holds. On failure the
collection stops and one of the fallbacks in section 6 is chosen deliberately.

| Condition | Threshold |
|---|---|
| D3 `durations_only` leave-one-repeat-out accuracy | > 0.3000 |
| D3 `first_execute_duration` leave-one-repeat-out accuracy | > 0.3000 |
| D2 any Holm-corrected KS p-value | < 0.01 |
| D4 `order_blind_full` leave-one-repeat-out accuracy | > 0.4000 |

The D4 bound is deliberately looser than the full-trace bound in the
information-boundary spec. A real ceiling above chance is tolerable when it
comes from prefix composition, which is legitimate information. It is not
tolerable when it comes from timing.

## 6. Fallbacks, in order of preference

1. **Drop durations from the observable set.** Types and exit codes only. This
   satisfies duration independence by construction, at the cost of timing
   information. The bound in section 5 becomes vacuous and the spec's
   full-trace conditions apply unchanged.
2. **Magnitude-blind timing.** Replace durations with a single coarse bit per
   event: `duration > 5s` or not. This preserves the fact that a wait was long
   while removing the graded information that leaked in v1ord. Independence
   must then be re-measured under D1 through D4.
3. **Retarget the signal.** If durations cannot be tamed, the temporal property
   under study changes to one that does not depend on timing at all, for
   example the interleaving of recovery actions with respect to exit events.
   This is a new information boundary and needs its own pilot.

Fallback 1 is preferred because it is the only one that does not require
re-validating anything downstream of the harness.

## 7. Evaluation protocol

All evaluation is leave-one-repeat-out: train on repeats of three procedures,
test on repeats of the fourth, rotating. The v0 and v1ord row-level random
split is not reused, because with real traces it would place near-identical
timings from the same execution on both sides of the split.

## 8. Acceptance before scaling

The 100-trace pilot must pass the frozen harness with thresholds from
`v2-information-boundary.md`, plus every section 5 row. Only then is
collection at 4,000 rows considered. Passing the harness means the design
satisfies its own tests, not that v2 is approved.

## 9. Not claimed

Nothing here supports a claim about real sandbox failures, production
observability, or unseen event vocabularies. The procedure set stays closed and
controlled. Any claim that a temporal model anticipates real failures requires
a different dataset with naturally occurring failures, which this is not.