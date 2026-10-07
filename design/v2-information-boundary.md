# v2 information-boundary specification

> **Superseded. Retained as evidence, not as the current specification.**
>
> This is the pre-collection draft, written before any data existed so the
> claim could be attacked rather than retrofitted. It was attacked and partly
> rejected. Two things in it describe a different experiment from the one that
> shipped, and are the reason it must not be read as current:
>
> - **It includes `duration` in the observable set.** The collection preflight
>   found that real executions make duration label-informative
>   (`order_blind_full` reached 0.6900), so fallback 1 was adopted and duration
>   was removed entirely. See `v2preflight/PREFLIGHT.md`.
> - **It tests cutoffs `{3, 5, 7, 8}`.** The shipped benchmark sweeps
>   `{2, 3, 4, 5, 6, 7, 8}`, because `t=2` and `t=3` turned out to be negative
>   controls with zero headroom, which the narrower set did not reveal.
>
> Final observable boundary: **`event_type + exit_code`**, duration and `t`
> withheld. The authoritative documents are
> `v2-dataset-and-benchmark-design.md` for the shipped design and
> `v2preflight/PREFLIGHT.md` for why duration was excluded.

Status at time of writing: draft, not collected.

## 1. What is observable at cutoff t

An observer at cutoff `t` sees events `0..t-1` in order, with their types,
exit codes, and durations. It sees no future event, no total trace length, and
no label. Cutoffs tested: `t in {3, 5, 7, 8}`, where 8 is the full trace.

## 2. What is deliberately hidden

Everything after `t`. Specifically hidden at every cutoff: the final teardown,
the final exit code, and therefore the outcome the label describes.

## 3. What determines the label

The label is a function of the relative order of marker events within the
observed prefix. It is never a function of a scalar, a threshold, or a total.

## 4. Which non-order features are allowed

Per event: type (one-hot) and exit code. Nothing else.

Duration was removed from the observable set. The collection preflight showed
that real executions make duration informative: `durations_only` reached 0.3400,
`first_execute_duration` 0.4000, and the full order-blind ceiling 0.6900, with a
Holm-corrected KS rejection where the second `execute` runs measurably slower
after a wait than after a recover. Timing is therefore not an inert nuisance
variable in this environment, and no observable set containing it yields an
order-only claim.

This is fallback 1 of the collection design. It is preferred over magnitude-blind
timing because it introduces no new semantic variable that would need its own
definition and validation.

No elapsed wall-clock time either, for the same reason.

## 5. What must be unavailable to every order-blind baseline

Nothing further is required, because duration is no longer observable. The
remaining order-blind features are counts and exit codes, and these are free to
vary across labels at a given cutoff. A prefix multiset that differs across
classes is legitimate information, not a leak, because both baselines receive
the identical prefix.

This distinction is load-bearing and was wrong in the first draft of this page:
an order-blind ceiling of 0.5000 at t=3 is correct behaviour, because the prefix
multiset identifies `delayed_fault` and nothing else. The invariant is about
what is observable, not a blanket requirement that order-blind sit at chance.

## 6. What temporal property carries the remaining signal

Relative position. Two traces with identical multisets of types and exit codes
receive different labels according to where `wait` and `recover` sit with
respect to the `execute` and `process_exit` pairs.

## 7. Exact pilot acceptance thresholds

Absolute margins are incoherent when a prefix genuinely does not determine the
label, so thresholds are stated against computable ceilings:

- `blind_ceiling(t)`: best accuracy obtainable from the prefix multiset alone.
- `order_ceiling(t)`: best accuracy obtainable from the ordered prefix.
- `headroom(t) = order_ceiling(t) - blind_ceiling(t)`.

Both are exact lookups on controlled data, not estimates. All conditions must
hold on the pilot at three seeds, chance 0.2500:

| Condition | Threshold |
|---|---|
| rows per label | >= 200, so the temporal probe is trained rather than undertrained |
| `order_blind_counts` at t=8 | <= 0.3000 |
| `order_blind_full` under the declared observable set at t=8 | <= 0.3000 |
| GRU at t=8 | >= 0.9500, and within 0.05 of `order_ceiling(8)` |
| GRU captures >= 90% of `headroom(t)` for every t in {4,5,6,7,8} | ratio >= 0.90 |
| GRU at t=3 | within 0.05 of `blind_ceiling(3)` = 0.5000, a negative control |
| label aliases on non-duration fields | exactly 0 |

Two of these are negative controls. At `t=3` and `t=2` the prefix determines
only one of four labels, so `headroom` is exactly 0.0000 and no model may
exceed 0.5000 there. A GRU scoring above 0.5000 at t=3 would indicate a leak,
not skill.

Failure of any row means the information boundary is wrong and gets
redesigned. No partial credit, and no collecting at scale.

## 8. Which cutoffs are tested

`t in {3, 5, 7, 8}`. t=3 is before the discriminating arrangement completes and
is the anticipation test. t=8 is the full-trace test. Cutoffs are swept, not
fixed, and the sweep is reported.

## Known realism cost

This design cannot speak to timing. It asks whether ordering alone carries the
label once execution time is withheld, which is a real and answerable systems
question, but it is not a claim about temporal patterns in wall-clock data. A
benchmark about realistic timing variation is a separate experiment and needs
its own design.

The 2.0s wait budget remains fixed on purpose. It is label-invariant, since
every procedure contains exactly one wait, so it costs nothing here. Jittering
it would add a variable without changing the information boundary.