"""Stage2: context at ENTRY and continuous efficiency sizing, not daily routing."""
import numpy as np
import pandas as pd
from research_adaptive_defense import ROOT,combine as phase1,features
from research_defense_redesign import main as run_research

OUT=ROOT/'release/model-research/studies/adaptive-context'
CONFIGS=[('roc_full','full','any',False),('er_mix','er','any',False),('er_qqq','er','qqq',False),
 ('er_calm','er','calm',False),('er_state4','er','state4',False),('er_forecast63','er','forecast',False),
 ('er_armed_qqq','er','qqq',True),('roc_full_qqq','full','qqq',False),('roc_forecast63','full','forecast',False)]
NAMES=['baseline','efficiency_gold','confluence3_gold']+[c[0] for c in CONFIGS]
PROTOCOL=dict(stage='after phase1 outcomes; exploratory context hypotheses, no independent discovery',configs=CONFIGS,
    short='GLD/BRK log ratio5 and21 day changes both negative; exit both positive',
    entry_context='QQQ>SMA200 / vol21<=vol126 / state4 / projected long crossover<=63sessions / any',
    forecast='current positive long logEMA84/378 gap divided by negative mean21day gap change; linear extrapolation, not future observation',
    sizing='ER21 continuously0..1 or full; ER is NOT a probability',
    lifecycle='context checked on entry; hold through normal2/3/4 until short reversal, baseline change/cash or state1/attack; armed variant monitors during attack',
    legacy='attack and original cash unchanged; Gold->BRK only',
    caveat='all periods already viewed; parameters fixed here, not tuned to maximize reported results')

def combine(p,btc):
    old,ind=phase1(p,btc);base=old['baseline'];ix=base.index;b=base.to_numpy();state=ind.state.to_numpy()
    f=features(p).reindex(ix);x=f.log_ratio
    want=((x-x.shift(5)<0)&(x-x.shift(21)<0)).to_numpy()
    revert=((x-x.shift(5)>0)&(x-x.shift(21)>0)).to_numpy()
    er=f.efficiency.fillna(0).clip(0,1).to_numpy()
    long=np.where(b[:,2]>0,2,np.where(b[:,1]>0,1,3));normal=np.where(ind.defense_fast>ind.defense_slow,2,1)
    gap=np.log(ind.defense_fast/ind.defense_slow);slope=gap.diff(21)/21
    crossing=gap/(-slope.where(slope<0));forecast=((crossing>0)&(crossing<=63)).to_numpy()
    q=(p.QQQ>p.QQQ.rolling(200).mean()).reindex(ix).to_numpy()
    v=np.log(p.QQQ).diff();calm=(v.rolling(21).std()<=v.rolling(126).std()).reindex(ix).to_numpy()
    contexts={'any':np.ones(len(ix),bool),'qqq':q,'calm':calm,'state4':state==4,'forecast':forecast}
    out={name:old[name] for name in NAMES[:3]}
    for name,size,context,armed in CONFIGS:
        t=b.copy();active=False
        for i in range(len(ix)):
            ref=normal[i] if state[i]==0 and armed else long[i]
            if state[i]==1 or (state[i]==0 and not armed) or ref!=2:active=False;continue
            if active and revert[i]:active=False
            if not active and want[i] and contexts[context][i]:active=True
            if active and state[i]!=0:
                fraction=er[i] if size=='er' else 1.;budget=(b[i,1]+b[i,2])*fraction
                t[i,1:3]*=1-fraction;t[i,1]+=budget
        assert np.isfinite(t).all() and t.min()>-1e-12 and np.allclose(t.sum(axis=1),1)
        np.testing.assert_array_equal(t[state==0],b[state==0]);out[name]=pd.DataFrame(t,index=ix,columns=base.columns)
    return out,ind

if __name__=='__main__':run_research(NAMES,combine,OUT,PROTOCOL)
