"""Bound incorrect fast intervention while preserving long policy/risk timing."""
import numpy as np
import pandas as pd
from research_defense_redesign import ROOT,main as run_research
from models.registry import load_model
from research_policy_router import experts

OUT=ROOT/'release/bounded-intervention'
CONFIGS=[('fast_reference',None,None,0,False,False),('loss_stop1',1.,False,0,False,False),
 ('loss_stop2',2.,False,0,False,False),('trailing_stop2',2.,True,0,False,False),
 ('dwell3',None,None,3,False,False),('dwell5',None,None,5,False,False),
 ('entry_only',None,None,0,True,False),('entry_commit',None,None,0,True,True)]
NAMES=['baseline']+[c[0] for c in CONFIGS]
PROTOCOL=dict(configs=CONFIGS,signal='same existing price-ratio EMA5/21 fast expert, Gold->BRK only, long advantage declining21days on entry',
 stop='relative log(BRK/GLD) loss or trailing loss from SIGNAL close; width k*prior63day daily relative vol*sqrt5 frozen on entry',
 execution='stop is close decision and fills next opportunity, NOT assumed intraday stop fill',
 rearm='after stop, require short to agree Gold at least once before entering again',
 dwell='3 or5 actual signal holding sessions; attack/cash/state1 always override dwell',
 entry='entry_only/commit allow initial normal defense entry from attack only; commit ignores fast reversal until baseline/risk exit',
 scope='no threshold fit, overlays preserve existing cash/risk/forced lock',
 caveat='after other research outcomes, all history viewed; exploratory')

def combine(p,btc):
    base,ind=load_model('woogong-1.3-d').evaluate(p,btc);ix=base.index;b=base.to_numpy();state=ind.state.to_numpy()
    ratio=p.GLD/p['BRK.B'];fast=(ratio.ewm(span=5,adjust=False,min_periods=5).mean()>ratio.ewm(span=21,adjust=False,min_periods=21).mean()).reindex(ix).to_numpy()
    gap=np.log(ind.defense_fast/ind.defense_slow);weak=(gap.diff(21)<0).to_numpy()
    y=np.log(p['BRK.B']/p.GLD).reindex(ix).to_numpy()
    vol=(np.log(p['BRK.B']/p.GLD).diff().rolling(63,min_periods=63).std().shift(1)*np.sqrt(5)).reindex(ix).to_numpy()
    out={'baseline':base}
    for name,k,trailing,dwell,only_entry,commit in CONFIGS:
        t=b.copy();active=False;blocked=False;age=0;start=peak=width=np.nan
        for i in range(len(ix)):
            if state[i] in [0,1] or b[i,2]<=1e-9:active=False;blocked=False;age=0;continue
            if fast[i]:blocked=False
            stop=False
            if active:
                age+=1;peak=max(peak,y[i])
                stop=k is not None and y[i]<(peak if trailing else start)-width
                if stop:active=False;blocked=True;age=0
                elif fast[i] and age>=dwell and not commit:active=False;age=0
            entry=not fast[i] and weak[i] and not blocked
            if only_entry:entry &= i==0 or state[i-1]==0
            if not active and entry and np.isfinite(vol[i]):
                active=True;age=0;start=peak=y[i];width=float(k)*vol[i] if k is not None else np.inf
            if active:
                budget=b[i,1]+b[i,2];t[i,1:3]=0;t[i,1]+=budget
        assert np.isfinite(t).all() and t.min()>-1e-12 and np.allclose(t.sum(axis=1),1)
        np.testing.assert_array_equal(t[state==0],b[state==0]);out[name]=pd.DataFrame(t,index=ix,columns=base.columns)
    _,reference,_,_=experts(p,btc)
    np.testing.assert_allclose(out['fast_reference'],reference['ema5_21_from2_w1.0'],atol=1e-12,rtol=0)
    return out,ind

if __name__=='__main__':run_research(NAMES,combine,OUT,PROTOCOL)
