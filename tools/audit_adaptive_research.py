"""Independent interval reconstruction and leave-one-intervention-out audit."""
import json,hashlib
import numpy as np
import pandas as pd
from research_bounded_intervention import ROOT,combine
from research_defense_redesign import AUDIT,replay,metrics
from portable_replay import run
from models.registry import load_model

OUT=ROOT/'release/adaptive-audit'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    p=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True);btc=pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    alltargets,ind=combine(p,btc);base=alltargets['baseline'];candidate=alltargets['entry_only'];ix=base.index
    ratio=p.GLD/p['BRK.B'];gold=(ratio.ewm(span=5,adjust=False,min_periods=5).mean()>ratio.ewm(span=21,adjust=False,min_periods=21).mean()).reindex(ix)
    gap=np.log(ind.defense_fast/ind.defense_slow);start=(ind.state.isin([2,3,4])&ind.state.shift(1).eq(0)&base.GLD.gt(0)&~gold&gap.diff(21).lt(0))
    exit_condition=ind.state.isin([0,1])|base.GLD.le(1e-9)|gold
    reconstructed=base.copy();intervals=[]
    for i in np.flatnonzero(start.to_numpy()):
        ends=np.flatnonzero(exit_condition.to_numpy()[i+1:]);j=i+1+ends[0] if len(ends) else len(ix)
        reconstructed.iloc[i:j,1]=base.iloc[i:j,1]+base.iloc[i:j,2];reconstructed.iloc[i:j,2]=0
        intervals.append(dict(start=str(ix[i].date()),end=str(ix[j].date()) if j<len(ix) else None,i=i,j=int(j),ongoing=j==len(ix)))
    np.testing.assert_allclose(reconstructed,candidate,atol=1e-12,rtol=0)
    names=['baseline','entry_only'];ts=[base,candidate]
    for interval in intervals:
        t=candidate.copy();t.iloc[interval['i']:interval['j']]=base.iloc[interval['i']:interval['j']]
        names.append('omit_'+interval['start']);ts.append(t)
    rows=[];annual=[];checks=[]
    for period in ['actual_BITO','long_synthetic']:
        a=np.load(AUDIT/f'inputs_{period}.npz');di=pd.DatetimeIndex(a['dates']);arr=np.stack([t.reindex(di).to_numpy() for t in ts])
        modes=['next_open','next_close'] if period=='actual_BITO' else ['next_close']
        for mode in modes:
            for slip,delay in [(0,1),(.003,1),(.003,3)]:
                nv,tr,turn,fee=replay(arr,a['op'],a['cl'],a['rf'],a['div'],mode,slip,delay)
                independent=run(arr,np.full(len(arr),.125),a['op'],a['cl'],a['rf'],a['div'],mode,slip,delay,1)
                err=float(np.max(abs(nv-independent)/np.maximum(1,abs(nv))));assert err<1e-11
                checks.append(dict(period=period,mode=mode,slippage=slip,delay=delay,max_relative_error=err))
                for k,name in enumerate(names):
                    for window,end in [('full',di[-1]),('before_oct2026',pd.Timestamp('2026-09-30')),('before2026',pd.Timestamp('2025-12-31'))]:
                        hi=np.flatnonzero(di<=end)[-1]+1
                        rows.append(dict(period=period,model=name,mode=mode,slippage=slip,delay=delay,window=window,
                            relative_final=float(nv[k,hi-1]/nv[0,hi-1]-1),**metrics(nv[k,:hi],di[:hi],tr[k,:hi],turn[k,:hi],fee[k,:hi])))
                if slip==0 and delay==1:
                    for year in sorted(set(di.year)):
                        pos=np.flatnonzero(di.year==year);lo=max(0,pos[0]-1);hi=pos[-1]
                        annual.append(dict(period=period,mode=mode,year=int(year),baseline_return=nv[0,hi]/nv[0,lo]-1,candidate_return=nv[1,hi]/nv[1,lo]-1))
    pd.DataFrame(intervals).to_csv(OUT/'intervention_intervals.csv',index=False)
    pd.DataFrame(rows).to_csv(OUT/'leave_one_out_metrics.csv',index=False);pd.DataFrame(annual).to_csv(OUT/'annual.csv',index=False)
    info=dict(checks=checks,independent_interval_reconstruction='PASS',fingerprint=load_model().fingerprint,
        caveat='leave-one-out tests concentration only; NOT independent statistical cross-validation',
        hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [__import__('pathlib').Path(__file__),ROOT/'tools/research_bounded_intervention.py',ROOT/'tools/research_defense_whipsaw.py',AUDIT/'portable_replay.py']})
    (OUT/'audit.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    f=pd.DataFrame(rows);print(f[(f.period=='actual_BITO')&(f['mode']=='next_open')&(f.slippage==0)&f.model.isin(['baseline','entry_only'])][['model','window','cagr','mdd','relative_final']].to_string(index=False))
    print('PASS independent interval logic and9 full saved-ledger scenarios; intervals:',len(intervals))

if __name__=='__main__':main()
