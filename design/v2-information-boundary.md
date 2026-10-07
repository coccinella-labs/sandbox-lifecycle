# v2 information-boundary specification

Status: draft, not collected. This page defines the claim before any data
exists, so the claim can be attacked rather than retrofitted.

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

Per event: type (one-hot), exit code, duration. Per prefix: the same,
multiset-reduced. No elapsed wall-clock time, because it is recoverable from
the sum of durations and reintroduces the v1ord leak.

## 5. What must be unavailable to every order-blind baseline

Duration must carry zero information about the label, by construction rather
than by observation. Every event duration is drawn from one
label-independent distribution, so no duration aggregate can correlate with the
label even in expectation. This is the single requirement that v1ord failed:
its durations reached 0.6996 alone and 0.9579 combined.

Counts and exit codes are free to vary across labels at a given cutoff. A
prefix multiset that differs across classes is legitimate information, not a
leak, because both baselines receive the identical prefix. This distinction is
load-bearing and was wrong in the first draft of this page: an order-blind
ceiling of 0.5000 at t=3 is correct behaviour, because the prefix multiset
identifies `delayed_fault` and nothing else. The invariant is therefore
duration-specific, not a blanket requirement that order-blind sit at chance.

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
| `durations_only` at t=8 | <= 0.3000 |
| `order_blind_counts` at t=8 | <= 0.3000 |
| `order_blind_full` minus prefix composition at t=8 | <= 0.3000 |
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

Label-independent durations are easier to guarantee synthetically than in a
real sandbox, where a slow process is slow for a reason. A real collection
must establish duration independence by measurement design or by
normalization, and must re-run this harness to prove it held. This is a
limitation of the approach, not a solved problem.