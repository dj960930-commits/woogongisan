"""V2.2 target policy. Portfolio caps release cash, and defense uses its final selection."""
import numpy as np

from .allocation_v21 import attack_weights
from .core_v1 import evaluate as core_evaluate


def evaluate(prices, btc, profile):
    target, indicators = core_evaluate(prices, btc)
    idx = target.index
    state = indicators.state.to_numpy()
    regular = np.isin(state, [2, 3, 4])
    rule = profile['defense_entry']
    cross = profile['cross']
    d = profile['defense']
    caps = profile['allocation']

    ratio = prices.GLD / prices['BRK.B']
    fast = ratio.ewm(span=rule['fast'], adjust=False, min_periods=rule['fast']).mean().reindex(idx)
    slow = ratio.ewm(span=rule['slow'], adjust=False, min_periods=rule['slow']).mean().reindex(idx)
    short_gold = (fast > slow).to_numpy()
    weakening = np.log(indicators.defense_fast / indicators.defense_slow).diff(rule['long_weakening_sessions']).lt(0)
    ready = np.log(ratio).diff().rolling(rule['readiness_sessions']).std().shift(1).reindex(idx).notna()
    gold = target.GLD.gt(0).to_numpy()
    has_asset = target[['BRK.B', 'GLD']].sum(axis=1).gt(0).to_numpy()
    entry = regular & gold & ~short_gold & weakening.to_numpy() & ready.to_numpy() & np.r_[True, state[:-1] == 0]

    risk_prices = prices[['BRK.B', 'GLD', 'TQQQ', 'SOXL']].copy()
    risk_prices['BTC'] = btc.shift(1).reindex(prices.index)
    ret = risk_prices.pct_change(cross['look'], fill_method=None).reindex(idx)
    gold_ret = prices.GLD.pct_change(cross['gold'], fill_method=None).reindex(idx)
    both_down = ret['BRK.B'].lt(0) & ret.GLD.lt(0)
    stress = both_down & (ret[['TQQQ', 'SOXL', 'BTC']].lt(0).sum(axis=1) >= cross['riskmin'])
    stress &= ret.notna().all(axis=1) & gold_ret.notna()
    defense_returns = ret[['BRK.B', 'GLD']].to_numpy()
    sma = prices.QQQ.rolling(d['qqq_sma']).mean().reindex(idx)
    weak = prices.QQQ.reindex(idx).lt(sma).to_numpy()

    weights = target.to_numpy(copy=True)
    raw = np.zeros(len(idx), dtype=bool)
    sheltered = raw.copy()
    redirected = raw.copy()
    started = raw.copy()
    bypassed = raw.copy()
    reserved = raw.copy()
    active = False
    age = cooldown = 0
    for j in range(len(idx)):
        if state[j] == 0:
            active = False
            age = cooldown = 0
            continue
        tentative = regular[j] and gold[j] and not short_gold[j] and (active or entry[j])
        chosen = int(gold[j] and not tentative)
        selected_return = defense_returns[j, chosen]
        raw[j] = regular[j] and stress.iloc[j] and selected_return <= cross['loss'] and (not chosen or gold_ret.iloc[j] < 0)
        emergency = regular[j] and both_down.iloc[j] and selected_return <= cross['emergency_loss']
        if not regular[j]:
            age = cooldown = 0
        elif age:
            if age < cross['minhold'] or (raw[j] and age < cross['maxhold']):
                sheltered[j] = True
                age += 1
            else:
                age = 0
                cooldown = cross['cooldown']
        elif cooldown and not emergency:
            cooldown -= 1
        elif raw[j] or (cooldown and emergency):
            sheltered[j] = True
            bypassed[j] = cooldown > 0
            age, cooldown = 1, 0
        started[j] = tentative and not active and not sheltered[j]
        active = redirected[j] = tentative and not sheltered[j]
        reserved[j] = weak[j] and has_asset[j] and not sheltered[j]
        budget = 0. if sheltered[j] or not has_asset[j] else (1 - d['cash_fraction'] if reserved[j] else 1.)
        weights[j] = 0.
        weights[j, 1 + chosen] = budget
        weights[j, 3] = 1 - budget

    # Setting both V2.1 caps to one returns its original score allocation.
    attack = attack_weights(prices, btc, idx, 1., 1.)
    attack.SOXL = attack.SOXL.clip(upper=caps['soxl_cap'])
    attack.BITO = attack.BITO.clip(upper=caps['btc_cap'])
    lever = attack.TQQQ + attack.SOXL
    multiplier = caps['lever_cap'] / lever.clip(lower=caps['lever_cap'])
    attack.TQQQ *= multiplier
    attack.SOXL *= multiplier
    attack.CASH = 1 - attack[['TQQQ', 'SOXL', 'BITO']].sum(axis=1)
    target.iloc[:, :] = weights
    target.loc[state == 0, :] = attack.loc[state == 0, target.columns]

    indicators['cross_trigger'] = raw
    indicators['cross_cash'] = sheltered
    indicators['cross_cooldown_bypassed'] = bypassed
    indicators['qqq_sma'] = sma
    indicators['defensive_cash'] = reserved
    indicators['cash_fraction'] = np.where(reserved, d['cash_fraction'], 0.)
    indicators['defense_short_fast'] = fast
    indicators['defense_short_slow'] = slow
    indicators['defense_long_weakening'] = weakening
    indicators['defense_entry_active'] = redirected
    indicators['defense_entry_started'] = started
    indicators['allocation_lever_cap'] = caps['lever_cap']
    indicators['allocation_native_btc'] = attack.BITO
    indicators['allocation_attack_cash'] = attack.CASH.where(state == 0, 0.)
    assert np.isfinite(target).all().all() and target.min().min() >= -1e-12
    np.testing.assert_allclose(target.sum(axis=1), 1., atol=1e-12)
    return target, indicators
