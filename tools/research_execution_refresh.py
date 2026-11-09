"""Execution ablation, SAME rules for baseline and candidates, no production edits."""
import json
import numpy as np
import pandas as pd
from research_bounded_intervention import combine,ROOT
from research_defense_redesign import AUDIT,replay,metrics
from portable_replay import factor

OUT=ROOT/'release/model-research/studies/execution-refresh'

def latest(t,op,cl,rf,div,mode,slip,delay):
    m,n,_=t.shape;held=np.zeros((m,6));held[:,3]=1;value=np.ones(m);nav=np.ones((m,n));goal=t[:,0].copy()
    due=np.where(np.max(abs(goal-held),axis=1)>=.125,delay,-1)
    rate=np.full(6,.001+slip);rate[3]=0;tr=np.zeros((m,n),int);turn=np.zeros((m,n));fee=np.zeros((m,n));cancel=np.zeros(m,int);refresh=cancel.copy()
    for i in range(1,n):
        g=op[i]/cl[i-1];g[3]=1+rf[i];g-=div[i]*.001;a=held*g;value*=a.sum(axis=1);held=a/a.sum(axis=1)[:,None]
        for timing in ['next_open','next_close']:
            if timing=='next_close':
                g=cl[i]/op[i];g[3]=1;a=held*g;value*=a.sum(axis=1);held=a/a.sum(axis=1)[:,None]
            if timing==mode:
                use=due==i
                if use.any():
                    k=factor(goal[use],held[use],rate);delta=abs(k[:,None]*goal[use]-held[use])
                    tr[use,i]=1;turn[use,i]=delta[:,[0,1,2,4,5]].sum(axis=1);fee[use,i]=(delta*rate).sum(axis=1)
                    value[use]*=k;held[use]=goal[use];due[use]=-1
        # This occurs AFTER today's open/close fill. Therefore the next fill
        # only knows signals from the preceding close, never same-day future.
        desired=t[:,i];needed=np.max(abs(desired-held),axis=1)>=.125
        pending=due>i;stop=pending&~needed;cancel+=stop.astype(int);due[stop]=-1
        update=pending&needed;refresh+=(update&(np.max(abs(goal-desired),axis=1)>1e-12)).astype(int);goal[update]=desired[update]
        fire=(due<0)&needed;due[fire]=i+delay;goal[fire]=desired[fire];nav[:,i]=value
    return nav,tr,turn,fee,cancel,refresh

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    p=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True);btc=pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    targets,_=combine(p,btc);names=list(targets);rows=[];changes=[]
    for period in ['actual_BITO','long_synthetic']:
        z=np.load(AUDIT/f'inputs_{period}.npz');ix=pd.DatetimeIndex(z['dates']);arr=np.stack([targets[n].reindex(ix).to_numpy() for n in names])
        modes=['next_open','next_close'] if period=='actual_BITO' else ['next_close']
        for mode in modes:
            for slip,delay in [(0,1),(.003,1),(.003,3)]:
                original=replay(arr,z['op'],z['cl'],z['rf'],z['div'],mode,slip,delay)
                current=latest(arr,z['op'],z['cl'],z['rf'],z['div'],mode,slip,delay)
                if delay==1:np.testing.assert_allclose(original[0],current[0],atol=1e-11,rtol=1e-11)
                # Change all FUTURE targets to cash and verify past NAV unchanged.
                cut=np.flatnonzero(ix<='2023-12-29')[-1];altered=arr.copy();altered[:,cut+1:,:]=0;altered[:,cut+1:,3]=1
                changed=latest(altered,z['op'],z['cl'],z['rf'],z['div'],mode,slip,delay)[0]
                np.testing.assert_allclose(changed[:,:cut+1],current[0][:,:cut+1],atol=1e-12,rtol=0)
                for execution,values in [('saved_target',original),('latest_target',current)]:
                    nav,tr,turn,fee=values[:4]
                    for k,name in enumerate(names):rows.append(dict(period=period,model=name,execution=execution,mode=mode,slippage=slip,delay=delay,**metrics(nav[k],ix,tr[k],turn[k],fee[k])))
                for k,name in enumerate(names):changes.append(dict(period=period,model=name,mode=mode,slippage=slip,delay=delay,cancel=int(current[4][k]),refresh=int(current[5][k])))
    pd.DataFrame(rows).to_csv(OUT/'metrics.csv',index=False);pd.DataFrame(changes).to_csv(OUT/'pending_changes.csv',index=False)
    (OUT/'protocol.json').write_text(json.dumps(dict(rule='fixed first scheduled opportunity; each earlier close updates pending target or cancels when within band; no pushing due date',
        fairness='same execution semantics for baseline and every candidate',checks=['delay1 exact saved ledger parity all experts both price scopes','future target perturbation unchanged historical NAV'],
        caveat='execution hypothesis only, actual app order endpoints not modified'),indent=2),encoding='utf-8')
    f=pd.DataFrame(rows);print(f[(f.period=='actual_BITO')&(f['mode']=='next_open')&(f.delay==3)&f.model.isin(['baseline','fast_reference','entry_only'])][['execution','model','cagr','mdd']].to_string(index=False))

if __name__=='__main__':main()
