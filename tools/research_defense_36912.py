"""Defense selection only: fixed 36912 candidates, no production changes."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from tools import research_dual_sleeve as core

OUT = core.ROOT / 'release/model-research/studies/defense-36912-study'
SCHEMES = {'w4321': (4,3,2,1), 'w12421': (12,4,2,1), 'equal': (1,1,1,1)}

def scores(prices, weights):
    x=prices[['BRK.B','GLD']]
    cash=np.log1p(prices.cash_return.fillna(0))
    return sum((x.div(x.shift(n))-1).sub(np.expm1(cash.rolling(n,min_periods=n).sum()),axis=0)*w
               for n,w in zip((63,126,189,252),weights))/sum(weights)

def short_confirm(prices):
    """Symmetric relative 5/21 >0, ratio>SMA10, asset>SMA5, three closes."""
    result={}
    for a,b in [('BRK.B','GLD'),('GLD','BRK.B')]:
        ratio=prices[a]/prices[b]
        yes=((ratio>ratio.shift(5)) & (ratio>ratio.shift(21))
             & (ratio>ratio.rolling(10,min_periods=10).mean())
             & (prices[a]>prices[a].rolling(5,min_periods=5).mean()))
        result[a]=yes.rolling(3,min_periods=3).sum().eq(3)
    return pd.DataFrame(result)

def select(score, original, confirm=None, cash_gate=False):
    valid=score.notna().all(axis=1)
    # Keep incumbent on exact ties and during score warm-up.
    chosen=original.copy()
    chosen=chosen.mask(valid & score['BRK.B'].gt(score.GLD),'BRK.B')
    chosen=chosen.mask(valid & score.GLD.gt(score['BRK.B']),'GLD')
    if confirm is not None:
        for a,b in [('BRK.B','GLD'),('GLD','BRK.B')]:
            chosen=chosen.mask(valid & chosen.eq(b) & confirm[a],a)
    if cash_gate:
        # True absolute filter: selected asset must also beat cash.
        selected=np.where(chosen.eq('BRK.B'),score['BRK.B'],score.GLD)
        chosen=chosen.mask(valid & (selected<=0),'CASH')
    return chosen

def build(prices,btc):
    base,ind=core.load_model('woogong-v2.1').evaluate(prices,btc)
    base['QQQ']=0.; base=base.reindex(columns=core.ASSETS)
    budget=base['BRK.B']+base.GLD
    eligible=ind.state.isin([2,3,4]) & budget.gt(1e-10)
    original=pd.Series(np.where(base.GLD>base['BRK.B'],'GLD','BRK.B'),index=base.index)
    confirm=short_confirm(prices).reindex(base.index)
    variants={'v21':base}
    diag={'regular_invested_defense_days':int(eligible.sum()),'choices':{}}
    for label,weights in SCHEMES.items():
        s=scores(prices,weights).reindex(base.index)
        for kind,short,cash in [('long',False,False),('cash',False,True),
                                ('hybrid',True,False),('hybrid_cash',True,True)]:
            chosen=select(s,original,confirm if short else None,cash)
            t=base.copy()
            t.loc[eligible,['BRK.B','GLD']]=0.
            for asset in ['BRK.B','GLD','CASH']:
                mask=eligible & chosen.eq(asset)
                t.loc[mask,asset]+=budget.loc[mask]
            name=label+'_'+kind
            variants[name]=t
            diag['choices'][name]={'changed_days':int((eligible & chosen.ne(original)).sum()),
                                   'additional_cash_days':int((eligible & chosen.eq('CASH')).sum())}
            np.testing.assert_array_equal(t.loc[~eligible],base.loc[~eligible])
            if not cash:
                np.testing.assert_array_equal(t.CASH,base.CASH)
    for t in variants.values():
        assert np.isfinite(t).all().all() and t.min().min()>-1e-10
        np.testing.assert_allclose(t.sum(axis=1),1.,atol=1e-12)
        np.testing.assert_array_equal(t[['TQQQ','SOXL','BITO','QQQ']],base[['TQQQ','SOXL','BITO','QQQ']])
    return variants,diag

def defense_diagnostic():
    prices=pd.read_csv(core.ROOT/'data/equities.csv',index_col=0,parse_dates=True)
    btc=pd.read_csv(core.ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    result=[]
    for period in ['actual_BITO','long2010_drag-0.053388']:
        if period=='actual_BITO':
            a=np.load(core.ROOT/'data/validation/v2/inputs_actual_BITO.npz')
            index=pd.DatetimeIndex(a['dates']); p=prices
            close=np.column_stack([a['cl'],prices.QQQ.reindex(index)])
            opening=np.column_stack([a['op'],prices.QQQ.reindex(index)])
            cash=a['rf']; div=np.column_stack([a['div'],np.zeros(len(index))])
        else:
            p=pd.read_csv(core.ROOT/'data/validation/long2010/reconstructed_inputs.csv.gz',index_col=0,parse_dates=True).loc[:prices.index[-1]]
            index=build(p,btc)[0]['v21'].index
            close=p.reindex(index)[['TQQQ','BRK.B','GLD','cash_return','SOXL','BITO','QQQ']].ffill().fillna(1.).to_numpy()
            close[:,3]=1.; opening=close.copy()
            cash=p.cash_return.reindex(index).fillna(0).to_numpy(); div=np.zeros_like(close)
        targets,_=build(p,btc)
        _,ind=core.load_model('woogong-v2.1').evaluate(p,btc)
        regular=ind.state.isin([2,3,4])
        for name,t in targets.items():
            isolated=t.copy(); isolated.loc[:,['TQQQ','SOXL','BITO','QQQ']]=0.
            isolated.loc[~regular,['BRK.B','GLD']]=0.
            isolated.CASH=1-isolated['BRK.B']-isolated.GLD
            nav,tr=core.replay(isolated.reindex(index).to_numpy(),close,opening,cash,div,'same_close_reference',0.)
            result.append(dict(period=period,name=name,**core.metrics(nav,index,tr)))
    pd.DataFrame(result).to_csv(OUT/'defense_only.csv',index=False)

def actual_next_open():
    # No candidate holds QQQ, so the verified six-asset opening fixture suffices.
    prices=pd.read_csv(core.ROOT/'data/equities.csv',index_col=0,parse_dates=True)
    btc=pd.read_csv(core.ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    targets,_=build(prices,btc)
    a=np.load(core.ROOT/'data/validation/v2/inputs_actual_BITO.npz')
    ix=pd.DatetimeIndex(a['dates']); rows=[]
    for extra in [0.,.003]:
        for name,t in targets.items():
            assert t.QQQ.eq(0).all()
            nav,tr,_,_=core.canonical_replay(t.reindex(ix).to_numpy()[:,:6],a['cl'],a['rf'],
                                              a['div'],'next_open',a['op'],extra,.125)
            rows.append(dict(period='actual_BITO',name=name,mode='next_open',extra=extra,
                             start=str(ix[0].date()),end=str(ix[-1].date()),**core.metrics(nav,ix,tr)))
    old=pd.read_csv(OUT/'metrics.csv')
    old=old.loc[~old['mode'].eq('next_open')]
    pd.concat([old,pd.DataFrame(rows)],ignore_index=True).to_csv(OUT/'metrics.csv',index=False)

if __name__=='__main__':
    core.OUT=OUT; core.build_targets=build
    core.main()
    defense_diagnostic()
    actual_next_open()
    p=OUT/'protocol.json'; d=json.loads(p.read_text(encoding='utf-8'))
    d.update(horizons=[63,126,189,252],schemes=SCHEMES,
       scope='Only regular invested defense states2/3/4. Attack, forced-BRK state1, original cross cash and original cash reserve unchanged. Missing score -> incumbent.',
       absolute='Weighted cash-excess simple returns; selected asset must be positive in cash variants',
       relative='Choose higher BRK.B/GLD score; exact tie keeps original incumbent',
       residual='Not applicable: attack allocations unchanged',
       short_rule='Symmetric ratio5/21 positive, ratio>SMA10, selected price>SMA5 for3 consecutive closes; override weighted choice; cash filter applied last',
       defense_only='Separate diagnostic portfolio: ordinary defense weights retained, all other days cash; includes waiting cash returns and entry/exit costs, not an attribution of full portfolio return.',
       next_open='Actual BITO fixture only; canonical six-asset replay, QQQ allocation zero for every candidate.',
       constraints='Original target leverage caps, cash overlays and forced-BRK preserved; cash variants may add cash.',
       checks=['sum1/nonnegative/finite','attack asset parity all dates','forced and original full-cash parity','cash reserve parity for noncash variants','prefix invariance','future perturbation','canonical V2.1 replay parity'],
       limitations='Retrospective fixed candidate comparison, no independent OOS. Long2010/BTC proxies not ETF record. Same-close reference does not establish attainable fills. Cash overlays frozen from original choices to isolate selector effect.')
    d['source_hashes'][str(Path(__file__).relative_to(core.ROOT))]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
