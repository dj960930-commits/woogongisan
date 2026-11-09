"""Compare independent BITO target caps on the final A01/G01/I02 blend."""
from tools import research_methodology_full as research

original_setup = research.setup

def setup(*args):
    targets = original_setup(*args)
    attack = targets['v21'][['TQQQ', 'SOXL', 'BITO']].sum(axis=1).gt(0)
    blend = targets['A01'].where(attack, targets['X04'], axis=0)
    for ceiling in (40, 60, 100):
        target = blend.copy()
        limited = target.BITO.clip(upper=ceiling / 100)
        target.CASH += target.BITO - limited
        target.BITO = limited
        targets[f'CAP{ceiling}'] = target
    return targets

if __name__ == '__main__':
    research.setup = setup
    research.OUT = research.OUT.parent / 'methodology-final-cap-comparison'
    research.main({'CAP40', 'CAP60', 'CAP100'})
