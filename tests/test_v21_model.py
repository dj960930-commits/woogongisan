from pathlib import Path
import numpy as np
import pandas as pd

from models import core_v1
from models.registry import load_model
from models.performance import replay

ROOT = Path(__file__).resolve().parents[1]


def inputs():
    return (pd.read_csv(ROOT/'data/equities.csv', index_col=0, parse_dates=True),
            pd.read_csv(ROOT/'data/btc.csv', parse_dates=['date_utc']).set_index('date_utc').close)


def test_frozen_models_keep_their_identity_and_targets():
    assert load_model('woogong-v2').fingerprint == '85f8f984dd51349a26e5dde39525a991877588ad51c06ddfa0c3a127fefab60d'
    assert load_model('woogong-1.3-d').fingerprint == '843872c60ae50f38722e3b07a313ca54fa49308055a7b98230d45b3cb1ceb488'
    p, btc = inputs()
    target, _ = load_model('woogong-v2').evaluate(p, btc)
    reference = pd.read_csv(ROOT/'data/validation/v2/reference_targets.csv.gz', index_col=0, parse_dates=True)
    np.testing.assert_allclose(target, reference, atol=1e-12, rtol=0)


def test_v21_matches_the_original_research_intervention_and_preserves_defense():
    p, btc = inputs()
    base, _ = load_model('woogong-v2').evaluate(p, btc)
    new, indicators = load_model('woogong-v2.1').evaluate(p, btc)
    # Independent research oracle: retain the frozen allocator, change only its
    # literal leverage cap and omit BTC's leverage-spill assignment. Production
    # never executes modified source; this checks refactoring against that oracle.
    source = (ROOT/'models/core_v1.py').read_text(encoding='utf-8')
    source = source.replace('.6/np.maximum(lever', '.7/np.maximum(lever')
    source = source.replace(' clipped[:,2]+=np.where(ready,np.minimum(released,np.maximum(caps[2]-clipped[:,2],0)),0.)', '')
    namespace = dict(core_v1.__dict__)
    exec(compile(source, str(ROOT/'models/core_v1.py'), 'exec'), namespace)
    expected_attack, _ = namespace['evaluate'](p, btc)
    attack = indicators.state.eq(0)
    np.testing.assert_allclose(new.loc[attack], expected_attack.loc[attack], atol=1e-12, rtol=0)
    np.testing.assert_array_equal(new.loc[~attack], base.loc[~attack])
    assert (new.loc[attack, ['TQQQ','SOXL']].sum(axis=1) <= .7 + 1e-12).all()
    assert (new.SOXL <= .4 + 1e-12).all()
    assert new.loc[attack, 'CASH'].max() > .1
    assert new.loc[attack, 'BITO'].min() < .4
    assert (new.BITO >= -1e-12).all() and np.allclose(new.sum(axis=1), 1.)


def test_v21_past_is_unchanged_by_prefix_or_future_prices():
    p, btc = inputs()
    model = load_model('woogong-v2.1')
    full, _ = model.evaluate(p, btc)
    for cutoff in ['2014-12-31','2024-12-31']:
        prefix, _ = model.evaluate(p.loc[:cutoff], btc.loc[:cutoff])
        np.testing.assert_allclose(prefix, full.loc[prefix.index], atol=1e-12, rtol=0)
    changed = p.copy()
    changed.loc[changed.index > '2024-12-31'] *= 2
    altered_btc = btc.copy()
    altered_btc.loc[altered_btc.index > '2024-12-31'] *= 3
    altered, _ = model.evaluate(changed, altered_btc)
    np.testing.assert_allclose(altered.loc[:'2024-12-31'], full.loc[:'2024-12-31'], atol=1e-12, rtol=0)


def test_v21_actual_bito_cash_research_result_is_reproduced():
    p, btc = inputs()
    model = load_model('woogong-v2.1')
    target, _ = model.evaluate(p, btc)
    a = np.load(ROOT/'data/validation/v2/inputs_actual_BITO.npz')
    ix = pd.DatetimeIndex(a['dates'])
    nav, *_ = replay(target.reindex(ix), a['cl'], a['rf'], a['div'], 'same_close_reference', a['op'], 0., model.band)
    np.testing.assert_allclose(nav[-1], 10.317682, rtol=1e-6)
