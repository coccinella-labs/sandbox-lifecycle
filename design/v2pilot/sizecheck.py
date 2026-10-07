"""Is the t=8 shortfall a design failure or undertraining?

The preflight supplies 25 repeats per label. The spec requires 200. This sweeps
the synthetic pilot, whose information structure is identical, to separate the two.
"""
import sys
import numpy as np
sys.path.insert(0, '/tmp/sbv2/bench'); sys.path.insert(0, '/tmp/sbv2/design/v2pilot')
import pilot, ceilings
from sbbench import ordered

print(f"  {'rows/label':<12} {'rows':<7} {'GRU t=8 (no durations)':<24} {'blind':<8} {'order'}")
for n in (25, 100, 200, 400):
    pilot.ROWS_PER_LABEL = n
    rows = pilot.build()
    small = [{'events': r['events'], 'label': r['label']} for r in rows]
    ys = sorted({r['label'] for r in rows})
    y = np.array([ys.index(r['label']) for r in rows])
    g = ordered.ordered_probe(small, y, use_durations=False)
    b = ceilings.blind_ceiling(rows, 8); o = ceilings.order_ceiling(rows, 8)
    print(f"  {n:<12} {n*4:<7} {sum(g)/len(g):<24.4f} {b:<8.4f} {o:.4f}")
