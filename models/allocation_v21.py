"""V2.1 attack sizing: retain native BTC allocation; leverage spill goes to cash."""
import numpy as np
import pandas as pd

from .defense_v2 import evaluate as defense_v2


def attack_weights(prices, btc, index, lever_cap, soxl_cap):
    """Match frozen score, readiness and SOXL redistribution before leverage sizing."""
    risk = prices[["TQQQ"]].copy()
    risk["BTC"] = btc.shift(1).reindex(prices.index)
    risk["SOXL"] = prices.SOXL
    logp = np.log(risk.where(risk > 0))
    returns = logp.diff()
    scores = []
    for window in (42, 252):
        denominator = returns.rolling(window, min_periods=window).std(ddof=1).where(lambda x: x > 1e-12) * np.sqrt(window)
        scores.append(((logp - logp.shift(window)) / denominator).to_numpy())
    score = sum(scores) / 2
    weights = np.tile([.3, .5, .2], (len(prices), 1))
    ok = np.isfinite(score).all(axis=1)
    values = score[ok]
    ex = np.exp(values - values.max(axis=1, keepdims=True))
    weights[ok] = ex / ex.sum(axis=1, keepdims=True)
    weights = weights[prices.index.get_indexer(index)]
    aligned = prices.reindex(index)
    # Keep the frozen readiness ordering; changing the calendar alignment would
    # silently change early attack allocations relative to the research.
    ready = (aligned.TQQQ.shift(126).notna() & aligned.SOXL.shift(126).notna()
             & btc.reindex(index).shift(127).notna()).to_numpy()
    weights[~ready] = [1, 0, 0]
    original = weights[:, [0, 2, 1]].copy()  # TQQQ, SOXL, BITO
    caps = np.array([1., soxl_cap, 1.])
    clipped = np.minimum(original, caps)
    for _ in range(4):
        excess = 1 - clipped.sum(axis=1)
        room = np.maximum(caps - clipped, 0)
        score = np.where(room > 1e-12, original, 0)
        denominator = score.sum(axis=1)
        clipped += np.minimum(excess[:, None] * score / np.maximum(denominator[:, None], 1e-16), room)
    lever = clipped[:, 0] + clipped[:, 1]
    shrink = np.minimum(1, lever_cap / np.maximum(lever, 1e-16))
    clipped[:, :2] *= shrink[:, None]
    # BTC retains its allocation before leverage reduction. No mandatory floor.
    cash = 1 - clipped.sum(axis=1)
    return pd.DataFrame({"TQQQ": clipped[:, 0], "BRK.B": 0., "GLD": 0.,
                         "CASH": cash, "SOXL": clipped[:, 1], "BITO": clipped[:, 2]}, index=index)


def evaluate(prices, btc, profile):
    rules = profile["allocation"]
    if not (0 <= rules["lever_cap"] <= 1 and 0 <= rules["soxl_cap"] <= 1
            and rules["spill"] == "cash" and rules["btc_floor"] == 0 and rules["btc_cap"] == 1):
        raise ValueError("지원하지 않는 V2.1 공격 배분 규칙")
    target, indicators = defense_v2(prices, btc, profile)
    attack = indicators.state.eq(0)
    replacement = attack_weights(prices, btc, target.index, rules["lever_cap"], rules["soxl_cap"])
    target.loc[attack, :] = replacement.loc[attack, :]
    indicators["allocation_lever_cap"] = rules["lever_cap"]
    indicators["allocation_native_btc"] = replacement.BITO
    indicators["allocation_attack_cash"] = replacement.CASH.where(attack, 0.)
    assert np.isfinite(target).all().all() and target.min().min() > -1e-12
    assert np.allclose(target.sum(axis=1), 1)
    return target, indicators
