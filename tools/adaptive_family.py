"""Current-goal family, namespaced and checked against saved counterfactual NAVs."""
import numpy as np
import pandas as pd
from research_adaptive_defense import combine as mechanism
from research_adaptive_context import combine as context
from research_bounded_intervention import combine as bounded
from research_defense_redesign import ROOT

SOURCES=[('mechanism','adaptive-defense',mechanism),('context','adaptive-context',context),('bounded','bounded-intervention',bounded)]

def build_family(p,btc):
    ts={}
    for label,folder,builder in SOURCES:
        out,ind=builder(p,btc)
        if not ts:ts['baseline']=out['baseline']
        else:np.testing.assert_allclose(ts['baseline'],out['baseline'],atol=0,rtol=0)
        for name,target in out.items():
            if name=='baseline' or(label=='context' and name in ['efficiency_gold','confluence3_gold']):continue
            ts[label+'::'+name]=target
    return ts,ind

def saved_nav(period,mode):
    frames=[]
    for label,folder,builder in SOURCES:
        f=pd.read_csv(ROOT/'release'/folder/f'nav_{period}_{mode}_portfolio.csv',index_col=0,parse_dates=True)
        if not frames:frames.append(f[['baseline']])
        else:np.testing.assert_allclose(frames[0].baseline,f.baseline,atol=1e-9,rtol=1e-10)
        for name in f:
            if name=='baseline' or(label=='context' and name in ['efficiency_gold','confluence3_gold']):continue
            frames.append(f[[name]].rename(columns={name:label+'::'+name}))
    return pd.concat(frames,axis=1)
