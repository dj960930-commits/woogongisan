import numpy as np
import pandas as pd
from tools.research_dual_sleeve import ASSETS, RISK, limit, sleeves, replay


def test_caps_apply_after_the_sleeves_are_combined():
    raw = pd.DataFrame(0.,index=[0],columns=ASSETS)
    raw.loc[0,"TQQQ"] = .6
    raw.loc[0,"SOXL"] = .4
    capped,freed = limit(raw)
    np.testing.assert_allclose(capped.loc[0,["TQQQ","SOXL","CASH"]],[.42,.28,.30])
    np.testing.assert_allclose(freed,[.3])
    np.testing.assert_allclose(capped.sum(axis=1),1.)


def test_absolute_and_filtered_relative_wait_in_cash_when_all_assets_are_weak():
    index = pd.to_datetime(["2026-01-02"])
    signal = pd.DataFrame(-.1,index=index,columns=RISK)
    absolute,relative=sleeves(signal,index)
    assert absolute.CASH.iloc[0]==relative.CASH.iloc[0]==1.
    _,unfiltered=sleeves(signal,index,relative_gate=False)
    assert unfiltered.CASH.iloc[0]==0
    assert (unfiltered[RISK].iloc[0] > 0).sum()==2


def test_new_close_signal_cannot_earn_the_same_days_price_move():
    target=np.zeros((3,7));target[:,3]=1
    target[1:,3]=0;target[1:,0]=1
    close=np.ones((3,7));close[:,0]=[1,2,2]
    nav,_=replay(target,close,close,np.zeros(3),np.zeros_like(close),"same_close_reference",0)
    np.testing.assert_allclose(nav,[1,1/1.001,1/1.001],rtol=1e-12)
    delayed,_=replay(target,close,close,np.zeros(3),np.zeros_like(close),"next_close",0)
    np.testing.assert_allclose(delayed,[1,1,1/1.001],rtol=1e-12)
