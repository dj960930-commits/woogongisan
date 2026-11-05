import json
from pathlib import Path
import numpy as np
import pandas as pd
from models.registry import load_model
from models.performance import replay

ROOT=Path(__file__).resolve().parents[1]

def inputs():
    return (pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True),
            pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close)

def test_v2_matches_researched_targets_and_preserves_risk_priority():
    p,b=inputs();t,i=load_model('woogong-v2').evaluate(p,b)
    ref=pd.read_csv(ROOT/'data/validation/v2/reference_targets.csv.gz',index_col=0,parse_dates=True)
    np.testing.assert_allclose(t,ref,atol=1e-12,rtol=0)
    old,_=load_model('woogong-1.3-d').evaluate(p,b)
    np.testing.assert_allclose(t.CASH,old.CASH,atol=1e-12)
    np.testing.assert_allclose(t.loc[i.state.isin([0,1])],old.loc[i.state.isin([0,1])],atol=1e-12)
    entries=i[i.defense_entry_started]
    assert i.state.shift(1).reindex(entries.index).eq(0).all()
    assert t.loc['2026-10-12','BRK.B']==1
    assert old.loc['2026-10-12','GLD']==1

def test_v2_past_is_unchanged_by_truncation_and_future_price_change():
    p,b=inputs();m=load_model('woogong-v2');full,_=m.evaluate(p,b)
    for cut in ['2014-12-31','2024-12-31']:
        prefix,_=m.evaluate(p.loc[:cut],b.loc[:cut])
        np.testing.assert_allclose(prefix,full.loc[prefix.index],atol=1e-12,rtol=0)
    altered=p.copy();altered.loc[altered.index>'2024-12-31',['QQQ','BRK.B','GLD']]*=2
    future,_=m.evaluate(altered,b)
    np.testing.assert_allclose(future.loc[:'2024-12-31'],full.loc[:'2024-12-31'],atol=1e-12,rtol=0)

def test_legacy_fingerprint_is_not_rewritten_by_new_registry():
    assert load_model('woogong-1.3-d').fingerprint=='843872c60ae50f38722e3b07a313ca54fa49308055a7b98230d45b3cb1ceb488'

def test_close_price_reference_does_not_backdate_a_new_position():
    t=np.zeros((3,6));t[:,3]=1;t[1:,3]=0;t[1:,1]=1
    cl=np.ones((3,6));cl[:,1]=[1,2,3]
    v,*_=replay(t,cl,np.zeros(3))
    np.testing.assert_allclose(v,[1,1/1.001,1.5/1.001],atol=1e-12)
    # Tomorrow-close execution cannot capture the intervening 50% rise either.
    delayed,*_=replay(t,cl,np.zeros(3),execution='next_close')
    np.testing.assert_allclose(delayed,[1,1,1/1.001],atol=1e-12)

def test_v2_evidence_replays_from_local_fixtures():
    model=load_model('woogong-v2');p,b=inputs();t,_=model.evaluate(p,b)
    evidence=json.loads((ROOT/'models/evidence/woogong-v2.backtest.json').read_text(encoding='utf-8'))
    assert evidence['model_fingerprint']==model.fingerprint
    for scope in ['actual_BITO','long_synthetic']:
        a=np.load(ROOT/f'data/validation/v2/inputs_{scope}.npz');ix=pd.DatetimeIndex(a['dates'])
        for row in [r for r in evidence['scenarios'] if r['period']==scope]:
            v,*_=replay(t.reindex(ix),a['cl'],a['rf'],a['div'],row['mode'],a['op'],row['slippage'],model.band)
            np.testing.assert_allclose(v[-1],row['final'],rtol=1e-11)

def test_v2_operational_cash_fallback_is_explicit_and_finite():
    from pipeline import latest_backtest
    p,b=inputs();m=load_model('woogong-v2');t,_=m.evaluate(p,b)
    p.loc[p.index[-1],'cash_return']=np.nan
    result=latest_backtest(p,t,m,return_daily=True)
    assert result['cash_zero_fallback_sessions']==1
    assert '미확인일 0' in result['basis']
    assert np.isfinite(result['_daily_nav']).all()
