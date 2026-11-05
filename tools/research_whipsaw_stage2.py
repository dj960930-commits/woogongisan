"""Post-result structural hypothesis. Keep separate from the original 12 trials.

2x2: forced BRK vs selector; Cross excludes vs includes lock state.
No thresholds optimized. No live-model changes.
"""
from research_defense_whipsaw import main, ROOT

CANDIDATES = [
    dict(name='baseline'),
    dict(name='forced_selector', forced='selector'),
    dict(name='cross_in_lock', cross_lock=True),
    dict(name='selector_cross_in_lock', forced='selector', cross_lock=True),
]

if __name__ == '__main__':
    main(CANDIDATES, ROOT / 'release/whipsaw-research-stage2')
