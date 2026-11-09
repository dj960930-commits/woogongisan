"""Predetermined entry-window and starting-portfolio sensitivity, not optimisation."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from research_bounded_intervention import combine,ROOT
from research_defense_redesign import AUDIT,replay,metrics
from portable_replay import factor
from models.registry import load_model

OUT=ROOT/'release/model-research/studies/entry-boundaries'
WINDOWS=[('day1',1,1),('days1_2',1,2),('days1_3',1,3),('days1_5',1,5),('day2',2,2),('day3',3,3)]

def initial_replay(t,op,cl,rf,div,held_initial,mode='next_open',slip=0,delay=1):
    m,n,_=t.shape;held=np.broadcast_to(held_initial,(m,6)).copy();value=np.ones(m);nav=np.ones((m,n));goal=t[:,0].copy()
    due=np.where(np.max(abs(goal-held),axis=1)>=.125,delay,-1);rate=np.full(6,.001+slip);rate[3]=0
    tr=np.zeros((m,n),int);turn=np.zeros((m,n));fee=np.zeros((m,n))
    for i in range(1,n):
        g=op[i]/cl[i-1];g[3]=1+rf[i];g-=div[i]*.001;a=held*g;value*=a.sum(axis=1);held=a/a.sum(axis=1)[:,None]
        for timing in ['next_open','next_close']:
            if timing=='next_close':g=cl[i]/op[i];g[3]=1;a=held*g;value*=a.sum(axis=1);held=a/a.sum(axis=1)[:,None]
            if timing==mode:
                use=due==i
                if use.any():
                    k=factor(goal[use],held[use],rate);delta=abs(k[:,None]*goal[use]-held[use]);value[use]*=k
                    tr[use,i]=1;turn[use,i]=delta[:,[0,1,2,4,5]].sum(axis=1);fee[use,i]=(delta*rate).sum(axis=1);held[use]=goal[use];due[use]=-1
        fire=(due<0)&(np.max(abs(t[:,i]-held),axis=1)>=.125);due[fire]=i+delay;goal[fire]=t[fire,i];nav[:,i]=value
    return nav,tr,turn,fee

def build(p,btc):
    old,ind=combine(p,btc);base=old['baseline'];b=base.to_numpy();ix=base.index;state=ind.state.to_numpy()
    ratio=p.GLD/p['BRK.B'];fast=(ratio.ewm(span=5,adjust=False,min_periods=5).mean()>ratio.ewm(span=21,adjust=False,min_periods=21).mean()).reindex(ix).to_numpy()
    gap=np.log(ind.defense_fast/ind.defense_slow);weak=(gap.diff(21)<0).to_numpy();out={'baseline':b}
    for name,lo,hi in WINDOWS:
        t=b.copy();active=False;age=0;spent=False
        for i in range(len(ix)):
            if state[i]==0:active=False;age=0;spent=False;continue
            age+=1
            if state[i]==1 or b[i,2]<=1e-9:active=False;continue
            if active and fast[i]:active=False
            if not active and not spent and lo<=age<=hi and not fast[i] and weak[i]:active=True;spent=True
            if active:
                budget=b[i,1]+b[i,2];t[i,1:3]=0;t[i,1]+=budget
        assert np.allclose(t.sum(axis=1),1) and t.min()>-1e-12
        np.testing.assert_array_equal(t[state==0],b[state==0]);out[name]=t
    np.testing.assert_allclose(out['day1'],old['entry_only'],atol=1e-12,rtol=0)
    return ix,out

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    p=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True);btc=pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    bi,ts=build(p,btc);names=list(ts);sbi,short=build(p.loc[:'2024-12-31'],btc.loc[:'2024-12-31'])
    for n in ts:np.testing.assert_allclose(ts[n][bi<='2024-12-31'],short[n],atol=1e-12,rtol=0)
    rows=[];cohorts=[]
    for period,mode in [('actual_BITO','next_open'),('long_synthetic','next_close')]:
        a=np.load(AUDIT/f'inputs_{period}.npz');di=pd.DatetimeIndex(a['dates']);arr=np.stack([ts[n][bi.get_indexer(di)] for n in names])
        for slip,delay in [(0,1),(.003,1),(.003,3)]:
            nv,tr,turn,fee=replay(arr,a['op'],a['cl'],a['rf'],a['div'],mode,slip,delay)
            check=initial_replay(arr,a['op'],a['cl'],a['rf'],a['div'],[0,0,0,1,0,0],mode,slip,delay)
            np.testing.assert_allclose(nv,check[0],atol=1e-11,rtol=1e-11)
            for k,n in enumerate(names):rows.append(dict(period=period,model=n,slippage=slip,delay=delay,relative_final=nv[k,-1]/nv[0,-1]-1,**metrics(nv[k],di,tr[k],turn[k],fee[k])))
        starts=['2021-10-20','2022-01-01','2023-01-01','2024-01-01','2025-01-01'] if period=='actual_BITO' else ['2015-07-01','2017-01-01','2019-01-01','2021-01-01','2023-01-01']
        for start in starts:
            pos=np.flatnonzero(di>=start);ix=di[pos];sub=arr[[0,1]][:,pos];same_initial=arr[0,pos[0]]
            for initial,held in [('cash',np.array([0,0,0,1,0,0])),('preowned_baseline',same_initial)]:
                nv,tr,turn,fee=initial_replay(sub,a['op'][pos],a['cl'][pos],a['rf'][pos],a['div'][pos],held,mode,0,1)
                for k,n in enumerate(['baseline','day1']):cohorts.append(dict(period=period,start=str(ix[0].date()),initial=initial,model=n,relative_final=nv[k,-1]/nv[0,-1]-1,**metrics(nv[k],ix,tr[k],turn[k],fee[k])))
    pd.DataFrame(rows).to_csv(OUT/'boundary_metrics.csv',index=False);pd.DataFrame(cohorts).to_csv(OUT/'initialization_metrics.csv',index=False)
    (OUT/'protocol.json').write_text(json.dumps(dict(windows=WINDOWS,max_interventions_per_defense_episode=1,
        primary='day1 unchanged; variants sensitivity only, no best-window selection',
        initialization='cash or identical preowned baseline allocation at cohort start; signal histories stay warmed, not cold restart',
        caveat='cohorts share same2026 events and are not independent successful samples',
        checks=['day1 exactly matches primary candidate','2024 prefix equality','custom initial ledger cash parity','attack unchanged'],code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2),encoding='utf-8')
    print(pd.DataFrame(rows).query("period=='actual_BITO' and slippage==0")[['model','cagr','mdd','relative_final']].to_string(index=False))

if __name__=='__main__':main()
