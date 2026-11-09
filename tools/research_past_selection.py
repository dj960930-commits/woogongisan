"""Past-only selector study; pair and family controls, identical dynamic policies."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from adaptive_family import ROOT,build_family,saved_nav
from research_defense_redesign import AUDIT,replay,metrics
from research_execution_refresh import latest

OUT=ROOT/'release/model-research/studies/past-selection'
PRIMARY='bounded::entry_only'
SELECTORS=[('annual_all','YS','all',None,0),('monthly_all','MS','all',None,0),
 ('quarterly36_all','QS','all',36,0),('monthly_pair','MS','pair',None,0),('monthly_pair_closed3','MS','pair',None,3)]
PROTOCOL=dict(selectors=SELECTORS,primary=PRIMARY,min_completed_months=24,
 score='mean realised complete-month log NAV excess over baseline; canonical execution, not fixed21day asset labels',
 decision='at period start use only earlier complete months; choose only score>1e-10, otherwise baseline',
 pair='baseline and fixed candidate selected after prior research, NOT an independent discovery',
 closed3='require3 completed signal intervention intervals fully within price scope before decision date',
 entrygate='strict pair controls freeze monthly approval at actual intervention entry; later approvals do not join existing intervention',
 caveat='all policy design used previously viewed history; walk-forward execution does not erase prior selection bias')

def routes(nav,targets,di,intervals):
    monthly=nav.resample('ME').last();monthly=monthly[monthly.index<=di[-1]]
    lr=np.log(monthly/monthly.shift(1)).dropna();ex=lr.sub(lr.baseline,axis=0)
    names=list(targets);base=targets['baseline'].reindex(di).to_numpy();out={};logs=[];schedules={}
    for policy,freq,pool,window,min_events in SELECTORS:
        target=base.copy();schedule=np.full(len(di),None,dtype=object)
        for period in pd.period_range(di[0],di[-1],freq={'YS':'Y','MS':'M','QS':'Q'}[freq]):
            start=period.start_time;end=period.end_time
            history=ex[ex.index<start]
            if window:history=history.tail(window)
            eligible=[PRIMARY] if pool=='pair' else [n for n in names if n!='baseline']
            closed=intervals[(intervals.start>=di[0])&(intervals.end<start)].shape[0]
            scores=history[eligible].mean();pick=None
            if len(history)>=24 and closed>=min_events:
                best=scores.idxmax()
                if scores[best]>1e-10:pick=best
            pos=np.flatnonzero((di>=start)&(di<=end))
            schedule[pos]=pick
            if len(pos) and pick is not None:target[pos]=targets[pick].reindex(di).to_numpy()[pos]
            assert len(history)==0 or history.index[-1]<start
            logs.append(dict(selector=policy,decision=str(start.date()),months=len(history),closed_events=int(closed),pick=pick,
                last_training_month=str(history.index[-1].date()) if len(history) else None,score=float(scores[pick]) if pick else 0))
        out[policy]=target
        schedules[policy]=schedule
    # Freeze approval at intervention entry. Later monthly approvals cannot
    # begin an intervention halfway through a defensive signal episode.
    for source,dest in [('monthly_pair','monthly_pair_entrygate'),('monthly_pair_closed3','monthly_pair_entrygate_closed3')]:
        target=base.copy()
        for interval in intervals.itertuples():
            if interval.start<di[0] or interval.start>di[-1]:continue
            i=di.get_indexer([interval.start])[0]
            if i<0 or schedules[source][i]!=PRIMARY:continue
            use=(di>=interval.start)&((di<interval.end) if pd.notna(interval.end) else True)
            target[use]=targets[PRIMARY].reindex(di).to_numpy()[use]
        out[dest]=target
    return out,logs

def main():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'protocol.json').write_text(json.dumps(PROTOCOL,indent=2),encoding='utf-8')
    p=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True);btc=pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    ts,ind=build_family(p,btc);intervals=pd.read_csv(ROOT/'release/model-research/studies/adaptive-audit/intervention_intervals.csv',parse_dates=['start','end'])
    allrows=[];alllogs=[]
    for period,mode in [('actual_BITO','next_open'),('long_synthetic','next_close')]:
        a=np.load(AUDIT/f'inputs_{period}.npz');di=pd.DatetimeIndex(a['dates']);nav=saved_nav(period,mode)
        np.testing.assert_array_equal(nav.index,di);assert list(nav)==list(ts)
        arr=np.stack([t.reindex(di).to_numpy() for t in ts.values()])
        generated=replay(arr,a['op'],a['cl'],a['rf'],a['div'],mode,0,1)[0]
        np.testing.assert_allclose(generated.T,nav.to_numpy(),atol=1e-9,rtol=1e-10)
        chosen,logs=routes(nav,ts,di,intervals)
        # A materially altered future expert path cannot affect past routing.
        changed=nav.copy();cut=pd.Timestamp('2025-12-31');changed.loc[changed.index>cut,changed.columns!='baseline']*=1.5
        check,_=routes(changed,ts,di,intervals)
        for n in chosen:np.testing.assert_allclose(chosen[n][di<=cut],check[n][di<=cut],atol=1e-12,rtol=0)
        names=['baseline','fixed_candidate']+list(chosen)
        final=np.stack([ts['baseline'].reindex(di).to_numpy(),ts[PRIMARY].reindex(di).to_numpy(),*chosen.values()])
        for log in logs:alllogs.append(dict(period=period,**log))
        scenarios=[(mode,0,1),(mode,.003,1),(mode,.003,3)]+([('next_close',0,1)] if period=='actual_BITO' else [])
        for execution,slip,delay in scenarios:
            nv,tr,turn,fee=replay(final,a['op'],a['cl'],a['rf'],a['div'],execution,slip,delay)
            for k,name in enumerate(names):
                for window,end in [('full',di[-1]),('before2026',pd.Timestamp('2025-12-31')),('before_oct2026',pd.Timestamp('2026-09-30'))]:
                    hi=np.flatnonzero(di<=end)[-1]+1
                    allrows.append(dict(period=period,model=name,mode=execution,slippage=slip,delay=delay,window=window,
                        relative_final=nv[k,hi-1]/nv[0,hi-1]-1,**metrics(nv[k,:hi],di[:hi],tr[k,:hi],turn[k,:hi],fee[k,:hi])))
            if slip==0 and delay==1:pd.DataFrame(nv.T,index=di,columns=names).to_csv(OUT/f'nav_{period}_{execution}.csv')
    pd.DataFrame(allrows).to_csv(OUT/'metrics.csv',index=False);pd.DataFrame(alllogs).to_csv(OUT/'selection_log.csv',index=False)
    (OUT/'audit.json').write_text(json.dumps(dict(protocol=PROTOCOL,checks=['all expert target ledgers match saved NAV','past-only complete month selection','future expert NAV perturbation unchanged past routing'],
        hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),ROOT/'tools/adaptive_family.py',ROOT/'tools/research_adaptive_defense.py',ROOT/'tools/research_adaptive_context.py',ROOT/'tools/research_bounded_intervention.py']},
        caveats=['family32new policies plus existing fast reference','single-pair candidate was selected after seeing2026','expert states tracked while inactive; final router turnover repriced','entrygate variants freeze entry approval instead of joining later']),indent=2),encoding='utf-8')
    f=pd.DataFrame(allrows);print(f[(f.period=='actual_BITO')&(f['mode']=='next_open')&(f.slippage==0)&(f.window=='full')][['model','cagr','mdd','relative_final']].to_string(index=False))
    print(pd.DataFrame(alllogs)[lambda x:(x.period=='actual_BITO')&x.selector.eq('monthly_pair')&x.pick.notna()].to_string(index=False))

if __name__=='__main__':main()
