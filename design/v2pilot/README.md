# v2 pilot

A deliberately tiny synthetic dataset whose purpose is to attack the v2
information boundary before any collection happens. It does not demonstrate
that order helps. It tries to break the design.

Run against the frozen harness in `bench/`:

```bash
python design/v2pilot/pilot.py
```

Exits non-zero if any acceptance condition fails, so it is usable as a gate.

## Files

- `pilot.py`: generator plus the attack suite.
- `ceilings.py`: exact achievable ceilings at each cutoff.

## Ceilings

Absolute margins are incoherent when a prefix does not determine the label, so
acceptance is measured against computable ceilings:

| cutoff | blind ceiling | order ceiling | headroom |
|---|---|---|---|
| 2 | 0.5000 | 0.5000 | 0.0000 |
| 3 | 0.5000 | 0.5000 | 0.0000 |
| 4 | 0.5000 | 0.7500 | 0.2500 |
| 5 | 0.5000 | 1.0000 | 0.5000 |
| 6 | 0.5000 | 1.0000 | 0.5000 |
| 7 | 0.2500 | 1.0000 | 0.7500 |
| 8 | 0.2500 | 1.0000 | 0.7500 |

t=2 and t=3 are negative controls. Only `delayed_fault` is identifiable from
that prefix, so no model of any kind may exceed 0.5000. A model scoring above
it would indicate a leak rather than skill.

## Pilot size

200 rows per label, 800 total. The first run used 50 per label and the
temporal probe scored 0.7375 at full trace, purely from undertraining: at 200
per label it reaches 1.0000. Pilot size is part of the acceptance criteria for
this reason.

## Result

All 14 conditions hold. Duration decoupling removes the leak that made the
v1ord order-blind ceiling 0.9579; durations alone score 0.2458 and every
non-order feature except prefix composition scores 0.2563, both at chance.

The design holds on the pilot. Collection is not authorized by that result.
