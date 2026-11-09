"""Stage two AFTER broad families and user's long-term-growth preference.

Preserve slow prior where healthy; asset-specific weakness allows alternate/cash.
Legacy guard is explicitly a separate incremental control, not a clean redesign.
"""
import numpy as np
import pandas as pd
from research_defense_redesign import main,ROOT,ASSETS,load_model

NAMES=['baseline','prior_sma63','prior_sma126','prior_weak63','prior_weak126',
       'sticky_weak63','sticky_weak126','legacy_guard63','legacy_guard126']
PROTOCOL=dict(stage='second stage after outcomes and user preference for growth; not independent discovery',names=NAMES,
    priority='long-term net growth; recent October is diagnostic only',
    horizons=[63,126],weakness='price below own SMA AND 21-session log cash excess <0',
    alternate='above own SMA AND 21-session cash excess >0',
    prior='GLD/BRK EMA84/378 preference in regular defense; BRK preference in state1',
    sticky='follow slow prior on defense entry; retain incumbent until own weakness; if cash choose eligible prior then alternate',
    guard='preserve original Cross/D25 and forced destinations; redirect only currently invested weak asset budget',
    no_fitting=True)

def combine(p,btc):
    base,ind=load_model('woogong-1.3-d').evaluate(p,btc);ix=base.index;x=p[['BRK.B','GLD']]
    cash=(1+p.cash_return).cumprod()
    ex=np.log(x/x.shift(21)).sub(np.log(cash/cash.shift(21)),axis=0).reindex(ix).to_numpy()
    defense=ind.state.ne(0).to_numpy();gold=(ind.defense_fast>ind.defense_slow).to_numpy()
    preferred=np.where((ind.state.to_numpy()==1)|~gold,0,1)
    out={'baseline':base}
    for h in [63,126]:
        above=(x>x.rolling(h,min_periods=h).mean()).reindex(ix).to_numpy()
        below=(x<x.rolling(h,min_periods=h).mean()).reindex(ix).to_numpy()
        weak=below&(ex<0);eligible=above&(ex>0)
        for kind in ['prior_sma','prior_weak','sticky_weak','legacy_guard']:
            name=f'{kind}{h}';t=base.copy();incumbent=None;was_defense=False
            for i in range(len(t)):
                if not defense[i]:was_defense=False;incumbent=None;continue
                prior=int(preferred[i]);choice=prior
                if kind=='legacy_guard':
                    for j,col in enumerate(['BRK.B','GLD']):
                        amount=t.iloc[i,t.columns.get_loc(col)]
                        if amount<=0 or not weak[i,j]:continue
                        t.iloc[i,t.columns.get_loc(col)]-=amount
                        dest=['BRK.B','GLD'][1-j] if eligible[i,1-j] else 'CASH'
                        t.iloc[i,t.columns.get_loc(dest)]+=amount
                    continue
                if kind=='sticky_weak':
                    if not was_defense:incumbent=prior
                    if incumbent is not None and weak[i,incumbent]:
                        incumbent=1-incumbent if eligible[i,1-incumbent] else None
                    if incumbent is None:
                        incumbent=prior if eligible[i,prior] else 1-prior if eligible[i,1-prior] else None
                    choice=incumbent;was_defense=True
                else:
                    bad=not above[i,prior] if kind=='prior_sma' else weak[i,prior]
                    if bad:choice=1-prior if eligible[i,1-prior] else None
                t.iloc[i]=0
                dest='CASH' if choice is None else ['BRK.B','GLD'][choice]
                t.iloc[i,t.columns.get_loc(dest)]=1
            assert np.isfinite(t).all().all() and t.min().min()>-1e-12 and np.allclose(t.sum(axis=1),1)
            np.testing.assert_allclose(t.loc[~defense],base.loc[~defense],atol=0,rtol=0)
            out[name]=t
    return {name:out[name] for name in NAMES},ind

if __name__=='__main__':
    main(NAMES,combine,ROOT/'release/model-research/studies/defense-growth-stage2',PROTOCOL)
