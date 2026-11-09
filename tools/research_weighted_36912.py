"""36912 weighted simple-return research; production profiles remain unchanged."""
import json
import numpy as np
import pandas as pd
from tools import research_dual_sleeve as core

OUT = core.ROOT / 'release/model-research/studies/weighted-36912-study'
SCHEMES = {'recent12_4_2_1': [12,4,2,1], 'recent4_3_2_1': [4,3,2,1], 'equal': [1,1,1,1]}

def score(prices, btc, weights):
    x = prices[['TQQQ','SOXL','QQQ','GLD','BRK.B']].copy()
    x['BITO'] = btc.shift(1).reindex(x.index)
    x = x.reindex(columns=core.RISK)
    cashlog = np.log1p(prices.cash_return.fillna(0))
    parts = []
    for n,w in zip([63,126,189,252],weights):
        excess = (x / x.shift(n)-1).sub(np.expm1(cashlog.rolling(n,min_periods=n).sum()),axis=0)
        parts.append(excess*w)
    return sum(parts)/sum(weights)

def build(prices,btc):
    base,ind = core.load_model('woogong-v2.1').evaluate(prices,btc)
    base['QQQ']=0.; base=base.reindex(columns=core.ASSETS)
    attack=ind.state.eq(0)
    unbounded=core.attack_weights(prices,btc,base.index,1.,.4)
    freed=((unbounded.TQQQ+unbounded.SOXL)-(base.TQQQ+base.SOXL)).clip(lower=0).where(attack,0)
    variants={'v21':base}
    for label,weights in SCHEMES.items():
        s=score(prices,btc,weights)
        sub=s.reindex(base.index)[['BITO','QQQ','GLD']]
        winner=sub.fillna(-np.inf).idxmax(axis=1).where(sub.max(axis=1)>0,'CASH')
        variants[label+'_residual']=core.add_residual(base,freed,winner)
        absolute,relative=core.sleeves(s,base.index)
        capped,released=core.limit((absolute+relative)/2)
        t=base.copy(); t.loc[attack]=capped.loc[attack]
        variants[label+'_hybrid']=t
        variants[label+'_combined']=core.add_residual(t,released.where(attack,0),winner)
    for t in variants.values():
        assert np.isfinite(t).all().all() and t.min().min()>-1e-10
        np.testing.assert_allclose(t.sum(axis=1),1.,atol=1e-12)
        assert (t.TQQQ+t.SOXL<=.7+1e-12).all() and (t.SOXL<=.4+1e-12).all()
        np.testing.assert_array_equal(t.loc[~attack],base.loc[~attack])
    return variants, {'schemes':SCHEMES}

if __name__=='__main__':
    core.OUT=OUT
    core.build_targets=build
    core.main()
    p=OUT/'protocol.json'
    d=json.loads(p.read_text(encoding='utf-8'))
    d.update(horizons=[63,126,189,252],schemes=SCHEMES,
             absolute='Weighted arithmetic cash-excess simple returns; positive eligible assets equal-weighted',
             relative='Top2 by same weighted score among eligible assets',
             residual='Same weighted cash-excess score for BTC/QQQ/GLD; nonpositive -> cash',
             assumptions='Weights are research assumptions, not user-confirmed. 12:4:2:1, 4:3:2:1, equal. Existing defense unchanged.')
    import hashlib
    d['source_hashes']['tools/research_weighted_36912.py']=hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest()
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
