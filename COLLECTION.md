# Collection v0.1.0

## Procedure

Fixed harness, 1,000 sequences per procedure, run serially for determinism:

- `success`: `/bin/sh -c "exit 0"`, expect exit 0.
- `fail`: `/bin/sh -c "exit 3"`, expect exit 3.
- `timeout`: `/bin/sh -c "sleep 30"` under a 5.0 second budget, expect kill.
- `recover`: `/bin/sh -c "exit 3"`, then the prescribed `rm -f` cleanup routine.

Sequence IDs come from a single global counter, so they are unique and ordered
across procedures rather than restarting per procedure.

## Provenance

- Collector: `collect.py`, version 0.1.0 (pinned in this repo).
- Host: Darwin 27.0.0 arm64. OS and kernel recorded once per run in
  `run.json` equivalents, not per sequence.
- Wall time: about 85 minutes, dominated by the 1,000 five-second timeout
  kills. Runtime is evidence of how v0 was produced, not a dataset feature.
- `data.jsonl` (4,000 rows) plus `collect.py` reproduces the procedure;
  timing values will differ between runs.

## Privacy

Only structured lifecycle fields were recorded. A canary token was exported
into the collector's own environment before the run; post-run grep over data,
quarantine, and run metadata found zero occurrences. See VALIDATION.md.
