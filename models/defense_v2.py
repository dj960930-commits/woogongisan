"""V2: fixed defense-entry EMA intervention; legacy risk/cash has priority."""
import numpy as np
from .overlays import cross_defense


def evaluate(prices, btc, profile):
    targets, indicators = cross_defense(prices, btc, profile)
    rule = profile['defense_entry']
    ix = targets.index
    ratio = prices.GLD / prices['BRK.B']
    fast = ratio.ewm(span=rule['fast'], adjust=False, min_periods=rule['fast']).mean()
    slow = ratio.ewm(span=rule['slow'], adjust=False, min_periods=rule['slow']).mean()
    gold = (fast > slow).reindex(ix)
    gap = np.log(indicators.defense_fast / indicators.defense_slow)
    weakening = gap.diff(rule['long_weakening_sessions']) < 0
    # Keep the original research's finite relative-volatility readiness guard.
    ready = np.log(prices['BRK.B'] / prices.GLD).diff().rolling(
        rule['readiness_sessions'], min_periods=rule['readiness_sessions']).std().shift(1).reindex(ix).notna()
    active = False
    used = np.zeros(len(ix), dtype=bool)
    entered = np.zeros(len(ix), dtype=bool)
    original_gold = targets.GLD.to_numpy(copy=True)
    state = indicators.state.to_numpy()
    for i in range(len(ix)):
        if state[i] in (0, 1) or original_gold[i] <= 1e-9:
            active = False
            continue
        if active and gold.iloc[i]:
            active = False
        entry = (i == 0 or state[i-1] == 0) and not gold.iloc[i] and weakening.iloc[i] and ready.iloc[i]
        if not active and entry:
            active = True
            entered[i] = True
        if active:
            # Redirect only the invested defense budget; preserve legacy CASH.
            budget = targets.iloc[i, 1] + targets.iloc[i, 2]
            targets.iloc[i, 1] = budget
            targets.iloc[i, 2] = 0
            used[i] = True
    indicators['defense_short_fast'] = fast.reindex(ix)
    indicators['defense_short_slow'] = slow.reindex(ix)
    indicators['defense_long_weakening'] = weakening
    indicators['defense_entry_active'] = used
    indicators['defense_entry_started'] = entered
    assert np.isfinite(targets).all().all() and targets.min().min() > -1e-12
    assert np.allclose(targets.sum(axis=1), 1)
    return targets, indicators
