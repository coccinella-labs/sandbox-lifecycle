"""Which fallback does the preflight data support?

Design section 6 ranks the fallbacks. Fallback 1 drops durations from the
observable set entirely, which satisfies independence by construction. This
measures whether that is sufficient, using the traces already collected.
"""
import json, sys
import numpy as np
sys.path.insert(0, '/tmp/sbv2/bench')
from sbbench import features
from preflight import repeat_holdout_probe
sys.path.insert(0, '/tmp/sbv2/design/v2pilot')
sys.path.insert(0, '/tmp/sbv2/design/v2pilot')
import ceilings

rows = [json.loads(l) for l in open('preflight.jsonl')]
labels = sorted({r['label'] for r in rows})

def no_duration(r):
    """Counts and exit codes only. Every duration removed from observation."""
    return features.order_blind_counts(r)

def magnitudes_only(r):
    """Fallback 2: one coarse bit per event, duration > 5s or not."""
    return features.order_blind_counts(r) + [
        float(1.0 if (e.get('duration') or 0.0) > 5.0 else 0.0) for e in r['events']
    ]

print(f"  {len(rows)} traces, {len(labels)} procedures, held-out-repeat protocol\n")
print(f"  {'observable set':<34} {'ceiling':<10} {'gate 0.4000'}")
for name, fn in (("all non-order features (current)", features.order_blind_full),
                 ("fallback 1: durations dropped", no_duration),
                 ("fallback 2: magnitude-blind timing", magnitudes_only)):
    mean, per = repeat_holdout_probe(rows, fn)
    print(f"  {name:<34} {mean:<10.4f} {'PASS' if mean <= 0.40 else 'FAIL'}")

print("\n  exact ceilings on the collected traces")
print(f"  {'cutoff':<8} {'blind':<9} {'order':<9} {'headroom'}")
for t in (2,3,4,5,6,7,8):
    b = ceilings.blind_ceiling(rows, t); o = ceilings.order_ceiling(rows, t)
    print(f"  {t:<8} {b:<9.4f} {o:<9.4f} {o-b:+.4f}")
