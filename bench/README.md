# sandbox-lifecycle benchmark

Evaluation harness for the released `sandbox-lifecycle` configs. Its purpose
is to test whether a claimed signal survives progressively stronger
non-temporal baselines, before any new version is collected or any new model is
published.

This harness is frozen. Later versions add configs, not changes to how configs
are measured.

One post-freeze addition, recorded for auditability: `ordered_probe` gained a
`use_durations` flag defaulting to `True`. Without it the harness could not
express a config whose observable set excludes duration, which v2 requires
after its collection preflight. The default preserves every released result,
verified unchanged: v0 0.7500 and v1ord 1.0000 before and after.

A second post-freeze addition: `probe` and `ordered_probe` accept optional
`eval_rows` and `eval_y`, which fit on one set and score on another instead of an
internal resplit. Without this the harness cannot honour a fixed
train/validation/test protocol, so a config with a reserved test split could not
be scored without spending it during development. Both parameters default to
None and released results are unchanged.

## Why this exists

Auditing v0 and v1ord surfaced findings that a single accuracy number hides:

- v0's `nonzero_exit` and `recovered` share an identical non-duration
  signature. The reported 0.75 MLP plateau is an aliasing artifact, not an
  information ceiling.
- v1ord's counts and exit codes are exactly chance-level, but durations are
  weakly label-bearing, and all non-order features combined reach 0.9579
  without any order information at all.

## Running it

```bash
python -m sbbench.report v0=v0/data.jsonl v1ord=v1ord/data_v1ord.jsonl
```

Requires `numpy`, `scikit-learn`, and `torch`. Tests run on synthetic fixtures
and need no data:

```bash
python -m pytest tests/
```

## The three tiers

A temporal claim is only meaningful relative to a named baseline. The report
scores all three and prints the gap against each.

| Tier | Meaning |
|---|---|
| declared-budget baseline | The intentionally narrower feature budget a gate commits to |
| order-blind baseline | All permitted non-order features, the strongest non-temporal ceiling |
| temporal model | Ordered events under the same declared budget |

v1ord is legitimate without being maximal. Its result holds against the
declared budget, and the order-blind ceiling is strictly stronger. Both numbers
are reported so neither reading is available on its own.

## What it reports

Per config:

1. **Declared-budget baseline.** `order_blind_counts`, which is the budget the
   published gate declares.
2. **Order-blind baseline.** `order_blind_full`: counts, exit codes, durations,
   and prefix aggregates together.
3. **Diagnostic subsets.** `counts_only`, `exit_codes_only`, `durations_only`,
   `first_execute_duration`, `prefix_fields`. These localize which field
   carries a shortcut rather than merely proving one exists.
4. **Label aliasing on non-duration fields.** Detects labels sharing a
   signature, then reports the duration ranges, their overlap, and the best
   single-threshold accuracy on that pair.
5. **Temporal model.** A GRU over the full ordered trace, with both gaps.

Any order-blind family beating chance by more than 0.05 is flagged as a leak.

## Current results

```text
v0     declared budget 0.7500  order-blind ceiling 0.8004  GRU 0.7500
       gaps: +0.0000 vs declared, -0.0504 vs ceiling
       nonzero_exit / recovered share a signature, overlap 0.0062s

v1ord  declared budget 0.2500  order-blind ceiling 0.9579  GRU 1.0000
       gaps: +0.7500 vs declared, +0.0421 vs ceiling
       counts and exit codes exactly 0.2500
```

The negative v0 gap is the alias check doing its job: sequence modeling cannot
help when two labels are indistinguishable on structure. The v1ord declared
budget of exactly 0.2500 is what preserves the original gate claim.

## Harness limitations

These are properties of the harness, not of any dataset:

- `prefix_fields` defaults to a fixed three-event cutoff. For any version
  whose cutoff is part of the claim, the cutoff must be swept and the sweep
  reported. `features.prefix_fields_sweep` exists for that, and the report
  always names the cutoff it used.
- Leak tolerance is a fixed 0.05 band, which two seeds of a chance model can
  exceed. Near-threshold results deserve a wider seed sweep.
- The GRU probe is a single architecture at one width. It establishes that
  order is usable, not that it is optimal.

## Adding a version

A new config is not accepted until every order-blind family is at or near
chance. If one is not, the gate must either be restated against a narrower
declared budget, as v1ord's is, or the version does not support an order-based
claim.

```bash
python -m sbbench.report v2=v2/data_v2.jsonl
```

v2 is design-first: define its information boundary on paper, run a pilot, and
collect full data only if the pilot passes this harness.