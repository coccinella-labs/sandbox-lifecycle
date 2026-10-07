# sandbox-lifecycle benchmark

Evaluation harness for the released `sandbox-lifecycle` configs. Its purpose
is to test whether a claimed signal survives progressively stronger
non-temporal baselines, before any new version is collected or any new model is
published.

## Why this exists

Two findings from auditing v0 and v1ord were only visible once feature families
were probed separately:

- v0's `nonzero_exit` and `recovered` share an identical non-duration
  signature, so the reported 0.75 MLP plateau is an aliasing artifact, not an
  information ceiling.
- v1ord's counts and exit codes are exactly chance-level, but durations are
  weakly label-bearing, reaching 0.6996 without any order information.

Both are the kind of thing a single accuracy number hides.

## Running it

```bash
python -m sbbench.report v0=v0/data.jsonl v1ord=v1ord/data_v1ord.jsonl
```

Requires `numpy`, `scikit-learn`, and `torch`. Data files are downloaded from
the Hugging Face dataset, not vendored here.

## What it reports

Per config, three blocks:

1. **Order-blind feature families.** `counts_only`, `exit_codes_only`,
   `order_blind_counts`, `durations_only`, `first_execute_duration`, and
   `prefix_fields`. Any family beating chance plus a 0.05 tolerance is flagged
   as a leak.
2. **Label aliasing on non-duration fields.** Detects labels that share a
   signature, then reports the duration ranges and overlap that separate them,
   plus the best achievable single-threshold accuracy on that pair.
3. **Ordered sequence probe.** A GRU over the full ordered trace, reported
   against the best order-blind family with the gap attributed to order.

## Current results

```text
v0     order-blind best 0.7500   GRU 0.7500   gap +0.0000
       nonzero_exit / recovered share a signature, overlap 0.0062s

v1ord  order-blind best 0.6996   GRU 1.0000   gap +0.3004
       counts and exit codes exactly 0.2500
```

The v0 gap of zero is the point of the alias check. It confirms no amount of
sequence modeling helps when two labels are indistinguishable on structure,
which is why the harness reports the alias rather than a score.

## Adding a version

A new config is not accepted until every order-blind family is at or near
chance. If one is not, either the gate must be restated against a narrower
information budget, as v1ord's is, or the version does not support an
order-based claim.

```bash
python -m sbbench.report v2=v2/data_v2.jsonl
```