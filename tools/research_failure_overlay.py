"""Find ex-post wrong defense choices, fit short overlays, test causal combinations.

Failure labels are research targets only. Never gate a historical trade by its
future wrong/right label. Annual walk-forward selects from matured past labels.
"""
import json,hashlib
import numpy as np
import pandas as pd
from research_defense_redesign import ROOT,AUDIT,replay,metrics
from models.registry import load_model

OUT=ROOT/'release/model-research/studies/failure-overlay'
PAIRS=[(f,s) for f in [5,10,21,42] for s in [21,42,63,84,126,189] if f<s]
GATES=['disagree','own_weak','long_weakening']

def policies(p,base,ind):
    ix=base.index;ratio=p.GLD/p['BRK.B'];b=base.to_numpy()
    long=np.where(b[:,2]>0,2,np.where(b[:,1]>0,1,3));defense=ind.state.ne(0).to_numpy()
    cash=(1+p.cash_return).cumprod();x=p[['BRK.B','GLD']]
    ex=np.log(x/x.shift(21)).sub(np.log(cash/cash.shift(21)),axis=0).reindex(ix).to_numpy()
    below=(x<x.rolling(63,min_periods=63).mean()).reindex(ix).to_numpy()
    own=np.zeros(len(ix),bool)
    for j in [1,2]:own|=(long==j)&below[:,j-1]&(ex[:,j-1]<0)
    gap=np.log(ind.defense_fast/ind.defense_slow);dg=gap.diff(21).to_numpy()
    weakening=np.where(long==2,dg<0,dg>0)
    choices=[];names=[]
    for f,s in PAIRS:
        fast=ratio.ewm(span=f,adjust=False,min_periods=f).mean();slow=ratio.ewm(span=s,adjust=False,min_periods=s).mean()
        short=pd.Series(np.where(fast>slow,2,1),index=p.index).reindex(ix).to_numpy()
        for gate in GATES:
            use=defense&(long!=3)&(short!=long)
            if gate=='own_weak':use&=own
            if gate=='long_weakening':use&=weakening
            choices.append(np.where(use,short,long));names.append(f'ema{f}_{s}_{gate}')
    return names,np.array(choices),long

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    protocol=dict(pairs=PAIRS,gates=GATES,horizon=21,min_training_events=20,refit='yearly using labels exited strictly before Jan1',
        failure='original held asset loses to other asset over fixed next-close evaluation window',
        objective='failure corrections AND damage on correct periods; mean net excess on all training events',
        frozen_fit='train to 2023 end, examine 2024 onward retrospectively',
        caveat='grid and gates designed after viewing history; no independent OOS; oracle failure-only result is NOT executable')
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    p=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True)
    btc=pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    base,ind=load_model('woogong-1.3-d').evaluate(p,btc);names,choice,long=policies(p,base,ind);bi=base.index
    # Meaningful causality check on signals and state, before fitting labels.
    cut='2023-12-29';small,si=load_model('woogong-1.3-d').evaluate(p.loc[:cut],btc.loc[:cut]);sn,sc,sl=policies(p.loc[:cut],small,si)
    np.testing.assert_array_equal(choice[:,bi<=cut],sc)
    a=np.load(AUDIT/'inputs_long_synthetic.npz');ix=pd.DatetimeIndex(a['dates']);loc=bi.get_indexer(ix)
    c=choice[:,loc];l=long[loc];b=base.reindex(ix).to_numpy();n=len(ix)
    events=[];excess=[];fastreturns=[];i=0
    while i<n-2:
        if l[i]==3:i+=1;continue
        # End at first different original asset/cash/attack target; preserve
        # next-day execution. Do not silently truncate unfinished tail events.
        breaks=np.flatnonzero(l[i+1:]!=l[i]);end=min(i+22,i+int(breaks[0])+2 if len(breaks) else n)
        if end>=n:break
        entry=i+1;asset=int(l[i]);other=3-asset
        ret=a['cl'][end]/a['cl'][entry]*(1-.001)/(1+.001)-1
        lr=float(ret[asset]);ar=float(ret[other]);fr=ret[c[:,i]]
        events.append(dict(start=str(ix[i].date()),entry=str(ix[entry].date()),exit=str(ix[end].date()),i=i,end=end,
            asset='GLD' if asset==2 else 'BRK.B',state=int(ind.state.reindex(ix).iloc[i]),original_return=lr,alternative_return=ar,
            missed_return=ar-lr,wrong=bool(ar>lr)))
        excess.append(fr-lr);fastreturns.append(fr);i=end+1
    ev=pd.DataFrame(events);E=np.array(excess).T;F=np.array(fastreturns).T
    assert all(ev.i.to_numpy()[1:]>ev.end.to_numpy()[:-1])
    ev.to_csv(OUT/'original_choice_windows.csv',index=False)
    ev[ev.wrong].to_csv(OUT/'wrong_choice_windows.csv',index=False)
    def rank(mask):
        wrong=ev.wrong.to_numpy()&mask;right=~ev.wrong.to_numpy()&mask
        rows=[]
        for k,name in enumerate(names):
            rows.append(dict(policy=name,n=int(mask.sum()),failures=int(wrong.sum()),
                corrected=int((E[k,wrong]>1e-12).sum()),damaged=int((E[k,right]<-1e-12).sum()),
                failure_mean_excess=float(E[k,wrong].mean()) if wrong.any() else 0,
                all_mean_excess=float(E[k,mask].mean()) if mask.any() else 0))
        return pd.DataFrame(rows)
    allrank=rank(np.ones(len(ev),bool));allrank.to_csv(OUT/'all_candidate_scores.csv',index=False)
    oracle=allrank.sort_values(['failure_mean_excess','all_mean_excess'],ascending=False).iloc[0].policy
    train=ev.exit<'2024-01-01';r=rank(train.to_numpy());r.to_csv(OUT/'training_scores.csv',index=False)
    fitted=r.sort_values(['all_mean_excess','policy'],ascending=[False,True]).iloc[0]
    fixed=str(fitted.policy) if fitted.n>=20 and fitted.all_mean_excess>0 else None
    selected={};logs=[]
    for year in sorted(set(ix.year)):
        mask=(ev.exit<f'{year}-01-01').to_numpy();rr=rank(mask)
        winner=rr.sort_values(['all_mean_excess','policy'],ascending=[False,True]).iloc[0]
        pick=str(winner.policy) if winner.n>=20 and winner.all_mean_excess>0 else None
        selected[year]=pick;logs.append(dict(year=int(year),policy=pick,n=int(winner.n),mean_excess=float(winner.all_mean_excess)))
    pd.DataFrame(logs).to_csv(OUT/'walkforward_selections.csv',index=False)
    metricsrows=[]
    for period in ['actual_BITO','long_synthetic']:
        z=np.load(AUDIT/f'inputs_{period}.npz');dates=pd.DatetimeIndex(z['dates']);pos=bi.get_indexer(dates)
        original=base.reindex(dates).to_numpy();cc=choice[:,pos];ll=long[pos]
        def overlay(picks):
            t=original.copy()
            for j,pick in enumerate(picks):
                if pick is None:continue
                asset=int(cc[names.index(pick),j])
                if ll[j]==3 or asset==ll[j]:continue
                budget=t[j,1]+t[j,2];t[j,1:3]=0;t[j,asset]+=budget
            assert np.allclose(t.sum(axis=1),1)
            return t
        labels=['baseline','failure_only_oracle_fit','frozen_2023_fit','annual_walkforward']
        targets=[original,overlay([oracle]*len(dates)),overlay([fixed]*len(dates)),overlay([selected.get(y) for y in dates.year])]
        # Audit every grid member in the full ledger as well; event ranking is
        # not a substitute for dynamic portfolio costs and turnover.
        labels+=names
        targets += [overlay([name]*len(dates)) for name in names]
        for mode,slip,delay in ([('next_open',0,1),('next_open',.003,1),('next_close',0,1),('next_open',.003,3)] if period=='actual_BITO' else [('next_close',0,1),('next_close',.003,1)]):
            nav,tr,turn,fee=replay(np.stack(targets),z['op'],z['cl'],z['rf'],z['div'],mode,slip,delay)
            if period=='actual_BITO' and mode=='next_open' and slip==0:
                old=np.load(AUDIT/'nav_next_open_s0_d1_f1_cash00.npz');np.testing.assert_allclose(nav[0],old['nav'][list(old['names']).index('V1.3-D')],atol=1e-10,rtol=1e-10)
            for k,name in enumerate(labels):
                for window,start,end in [('full',dates[0],dates[-1]),('post2024',pd.Timestamp('2024-01-01'),dates[-1])]:
                    use=np.flatnonzero((dates>=start)&(dates<=end));lo=max(0,use[0]-1);hi=use[-1]+1
                    metricsrows.append(dict(period=period,model=name,window=window,mode=mode,slippage=slip,delay=delay,**metrics(nav[k,lo:hi],dates[lo:hi],tr[k,lo:hi],turn[k,lo:hi],fee[k,lo:hi])))
            if slip==0 and delay==1:pd.DataFrame(nav.T,index=dates,columns=labels).to_csv(OUT/f'nav_{period}_{mode}.csv')
    result=pd.DataFrame(metricsrows);result.to_csv(OUT/'metrics.csv',index=False)
    info=dict(protocol=protocol,oracle_fit=oracle,frozen_fit=fixed,event_count=len(ev),wrong_count=int(ev.wrong.sum()),
        fingerprint=load_model('woogong-1.3-d').fingerprint,hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [__import__('pathlib').Path(__file__),ROOT/'data/equities.csv',ROOT/'data/btc.csv',AUDIT/'inputs_long_synthetic.npz']},
        checks=['signal prefix parity 2023','events do not overlap','annual fit labels strictly before Jan1','baseline actual NAV parity','weights sum1'],
        limitations=['oracle fitted on full future labels, forbidden for live use','event labels use initial selected asset, not dynamic policy returns','annual WF is retrospective and 20-event minimum is study choice','2015 BITO synthetic; no independent OOS'])
    (OUT/'manifest.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in info.items() if k in ['oracle_fit','frozen_fit','event_count','wrong_count']},indent=2))
    print(allrank.sort_values('failure_mean_excess',ascending=False).head(5).to_string(index=False))
    print(result[(result.period=='actual_BITO')&(result['mode']=='next_open')&(result.slippage==0)&result.model.isin(['baseline','failure_only_oracle_fit','frozen_2023_fit','annual_walkforward'])][['model','window','cagr','mdd']].to_string(index=False))

if __name__=='__main__':main()
