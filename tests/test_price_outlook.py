import numpy as np
import pandas as pd
import pytest
from price_outlook import build,distribution


def prices():
    ix=pd.bdate_range(end='2026-10-30',periods=1600)
    values=np.exp(np.cumsum(np.random.default_rng(7).normal(0,.02,len(ix))))
    return pd.DataFrame({s:values for s in ('TQQQ','BRK.B','GLD')},index=ix)


def test_dates_ranges_current_anchor_and_heldout_evaluation():
    p=prices();r=build(p,{s:100 for s in p})
    assert r['as_of']=='2026-10-30'
    for asset in r['assets']:
        for w in asset['windows']:
            assert 0<w['lower']<=w['median']<=w['upper']
            assert w['target_date']>r['as_of']
            assert w['evaluation']['origins']>0
            assert w['evaluation']['spacing_sessions']==w['sessions']
            assert w['evaluation']['overlap'] is False
            assert 0<=w['evaluation']['historical_coverage']<=1


def test_prefix_predictions_ignore_future_and_reject_bad_inputs():
    p=prices();s=p.TQQQ;before=distribution(s.iloc[:1300],21)
    s=s.copy();s.iloc[1300:]*=10
    np.testing.assert_equal(before,distribution(s.iloc[:1300],21))
    with pytest.raises(ValueError):build(p,{s:0 for s in p})
