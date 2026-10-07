# v2 pilot and re-pilot

Two pilots. The first attacks the spec before any collection. The second
re-runs acceptance after the collection preforced the observable set to exclude
duration.

## Files

- `pilot.py`: generator plus the original attack suite, durations included.
- `ceilings.py`: exact achievable ceilings at each cutoff.
- `repilot.py`: acceptance conditions under the durations-free observable set.
- `sizecheck.py`: separates design failure from undertraining.

## Original pilot

Ran at 200 rows per label, all 14 conditions hold. It also invalidated the first
draft of the information boundary, which required order-blind ceilings to sit at
chance. That is wrong whenever a prefix multiset legitimately differs across
labels. See `v2pilot/README.md` history in git.

## Preflight consequence

The collection preflight showed real executions make duration informative:
`order_blind_full` reached 0.6900 with durations observable. Fallback 1 was
adopted, so the observable set is now event type and exit code only.

## Re-pilot

`repilot.py` re-runs acceptance with `use_durations=False`.

On real preflight traces, 8 of 12 conditions hold. The declared-budget and
aliasing conditions pass at exactly chance on all three order-blind families,
which is the new evidence that matters: removing duration restores
independence on real executions.

The four temporal conditions fail at 0.7500, which is undertraining rather than
a design failure. The preflight supplies 25 repeats per label and the spec
requires 200. `sizecheck.py` demonstrates the mechanism:

| rows per label | rows | GRU at t=8, no durations | blind ceiling | order ceiling |
|---|---|---|---|---|
| 25 | 100 | 0.7500 | 0.2500 | 1.0000 |
| 100 | 400 | 0.8750 | 0.2500 | 1.0000 |
| 200 | 800 | 1.0000 | 0.2500 | 1.0000 |
| 400 | 1600 | 1.0000 | 0.2500 | 1.0000 |

The real preflight reproduces the 25-row artifact exactly at 0.7500. At the
spec's stated minimum the full condition set passes, 12 of 12.

## Temporal preflight at spec sample size

800 real traces, 200 repeats per procedure, answers the one question the
100-trace run could not: does ordering remain measurable on real executions
once the probe has the sample size the spec requires? It does, 8 of 8, with
both seeds identical at every cutoff. See `TEMPORAL_PREFLIGHT.md`. That run does
not re-test the observable-set claim, which stays owned by the 100-trace
preflight.

## Combined evidence

Real traces establish the observable-set claim: order-blind sits at 0.2500 and
zero aliases once duration is withheld. The synthetic pilot at adequate size
establishes the temporal claim. Neither alone would be sufficient, and the
split is recorded rather than papered over.
