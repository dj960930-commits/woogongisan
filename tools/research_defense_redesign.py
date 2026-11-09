"""Predeclared defense-policy research. Never mutates production models.

Same attack/defense timing, new GLD/BRK/CASH policy in ALL defensive states.
Cash is an explicit asset. Original Cross/D25 apply only to the baseline.
"""
from pathlib import Path
import sys,json,hashlib,inspect
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from research_defense_whipsaw import ROOT,AUDIT,replay,metrics as ledger_metrics
from models.core_v1 import evaluate as core,ASSETS
from models.registry import load_model

OUT=ROOT/'release/model-research/studies/defense-redesign'
NAMES=['baseline','cash','static50','dual63','dual126','dual_ensemble',
       'momentum_blend','breadth','breadth_slow','sma_breadth','invvol_trend','breadth_entry3']
PROTOCOL=dict(names=NAMES,scope='all defensive states 1/2/3/4; attack unchanged; no legacy overlay stacking',
    lookbacks=dict(dual=[63,126],blend=[21,63,126],breadth=[21,63,126],breadth_slow=[42,126,252],sma=[63,126,252]),
    inverse_vol=dict(eligibility='above SMA126 and positive cash excess63',vol=63,cap=2/3),
    entry3='each asset/horizon positive for 3 consecutive closes before entry; exit immediately on nonpositive',
    selection='no parameter fit or October winner selection; chronological splits are retrospective, not independent OOS')

def metrics(*args):
    with np.errstate(divide='ignore',invalid='ignore'):
        result=ledger_metrics(*args)
    if abs(result['mdd'])<1e-12:result['calmar']=float('nan')
    return result

def allocations(p):
    x=p[['BRK.B','GLD']];cash=(1+p.cash_return).cumprod()
    ex={n:np.log(x/x.shift(n)).sub(np.log(cash/cash.shift(n)),axis=0) for n in [21,42,63,126,252]}
    n=len(x);a={}
    def pack(w):
        w=np.asarray(w,float);z=np.zeros((n,6));z[:,1:3]=w;z[:,3]=1-w.sum(axis=1)
        assert np.isfinite(z).all() and z.min()>-1e-12 and np.allclose(z.sum(axis=1),1)
        return pd.DataFrame(z,index=p.index,columns=ASSETS)
    a['cash']=pack(np.zeros((n,2)));a['static50']=pack(np.full((n,2),.5))
    def winner(score):
        s=score.to_numpy();ok=np.isfinite(s).all(axis=1);w=np.zeros_like(s)
        best=np.argmax(np.where(np.isfinite(s),s,-np.inf),axis=1)
        use=ok&(np.max(s,axis=1)>0);w[np.flatnonzero(use),best[use]]=1
        return w
    for h in [63,126]:a[f'dual{h}']=pack(winner(ex[h]))
    a['dual_ensemble']=pack((winner(ex[63])+winner(ex[126]))/2)
    a['momentum_blend']=pack(winner(sum(ex[h]*(252/h) for h in [21,63,126])/3))
    for name,hs in [('breadth',[21,63,126]),('breadth_slow',[42,126,252])]:
        a[name]=pack(sum((ex[h]>0).astype(float) for h in hs)/len(hs)*.5)
    a['sma_breadth']=pack(sum((x>x.rolling(h,min_periods=h).mean()).astype(float) for h in [63,126,252])/6)
    eligible=(x>x.rolling(126,min_periods=126).mean())&(ex[63]>0)
    vol=np.log(x).diff().rolling(63,min_periods=63).std()*np.sqrt(252)
    iv=(1/vol.where(vol>1e-8)).where(eligible,0).fillna(0)
    w=iv.div(iv.sum(axis=1).where(lambda s:s>0),axis=0).fillna(0).clip(upper=2/3)
    a['invvol_trend']=pack(w)
    # Independently confirmed sub-budgets; no delay on exits or attack timing.
    a['breadth_entry3']=pack(sum((ex[h]>0).rolling(3,min_periods=3).min().fillna(0) for h in [21,63,126])/6)
    return a

def combine(p,btc):
    base,ind=load_model('woogong-1.3-d').evaluate(p,btc);a=allocations(p);defense=ind.state.ne(0)
    out={'baseline':base}
    for name in NAMES[1:]:
        t=base.copy();t.loc[defense,:]=a[name].reindex(t.index).loc[defense,:]
        np.testing.assert_allclose(t.loc[~defense],base.loc[~defense],atol=0,rtol=0)
        out[name]=t
    return out,ind

def windows(ix):
    return [('full',ix[0],ix[-1]),('pre2024',ix[0],pd.Timestamp('2023-12-31')),
            ('post2024',pd.Timestamp('2024-01-01'),ix[-1]),('pre_BITO',ix[0],pd.Timestamp('2021-10-19')),
            ('oct2026',pd.Timestamp('2026-10-01'),pd.Timestamp('2026-10-20'))]

def main(names=NAMES,builder=combine,out=OUT,protocol=PROTOCOL):
    NAMES=names;OUT=out;PROTOCOL=protocol
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'protocol.json').write_text(json.dumps(dict(recorded_at=datetime.now(timezone.utc).isoformat(),**PROTOCOL),indent=2),encoding='utf-8')
    p=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True)
    btc=pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    ts,ind=builder(p,btc)
    for cut in ['2016-12-30','2023-12-29']:
        short,_=builder(p.loc[:cut],btc.loc[:cut])
        for name in NAMES:np.testing.assert_allclose(ts[name].loc[:cut],short[name],atol=1e-12,rtol=0)
    changed=p.copy();changed.loc[changed.index>'2023-12-29',['QQQ','TQQQ','SOXL','GLD','BRK.B']]*=2
    changed_btc=btc.copy();changed_btc.loc[changed_btc.index>'2023-12-29']*=3
    future,_=builder(changed,changed_btc)
    for name in NAMES:np.testing.assert_allclose(ts[name].loc[:'2023-12-29'],future[name].loc[:'2023-12-29'],atol=1e-12,rtol=0)
    frozen=np.load(AUDIT/'targets.npz');fi=pd.DatetimeIndex(frozen['dates'])
    np.testing.assert_allclose(ts['baseline'].reindex(fi),frozen['targets'][list(frozen['names']).index('V1.3-D')],atol=1e-12,rtol=0)
    rows=[];annual=[];ep=[];coverage=[];defnavs={}
    cases=[]
    for label in ['actual_BITO','long_synthetic']:
        a=np.load(AUDIT/f'inputs_{label}.npz');cases.append((label,pd.DatetimeIndex(a['dates']),a['op'],a['cl'],a['rf'],a['div']))
    ix=p.index[(p.index>='2012-01-01')&(p.index<='2026-10-20')]
    px=p[['TQQQ','BRK.B','GLD','SOXL']].reindex(ix).copy();px['CASH']=1.;px['BITO']=btc.shift(1).reindex(ix)*np.exp(-.05338828097800662*(ix-ix[0]).days.to_numpy()/365.25)
    close=px[ASSETS].to_numpy();assert np.isfinite(close).all() and (close>0).all()
    cases.append(('conditional_2012',ix,close,close,p.cash_return.reindex(ix).to_numpy(),np.zeros_like(close)))
    for period,ix,op,cl,rf,div in cases:
        attack=ind.state.reindex(ix).eq(0).to_numpy();arr=np.stack([ts[name].reindex(ix).to_numpy() for name in NAMES])
        assert np.isfinite(arr).all()
        sleeve=arr.copy();sleeve[:,attack,:]=0;sleeve[:,attack,3]=1
        for k,name in enumerate(NAMES):
            d=arr[k,~attack]
            coverage.append(dict(period=period,model=name,defense_days=len(d),mean_target_cash=d[:,3].mean(),mean_target_brk=d[:,1].mean(),mean_target_gold=d[:,2].mean(),full_cash_days=int((d[:,3]>.999).sum())))
        scenarios=[('next_open',0,1,False),('next_open',.001,1,False),('next_open',.003,1,False),('next_close',0,1,False),('next_close',.003,1,False),('next_open',.003,2,False),('next_open',.003,3,False),('next_open',.003,1,True)] if period=='actual_BITO' else [('next_close',0,1,False),('next_close',.003,1,False),('next_close',.003,3,False)]
        for mode,slip,delay,zero in scenarios:
            rr=np.zeros_like(rf) if zero else rf
            for scope,t in [('portfolio',arr),('defense_sleeve',sleeve)]:
                nav,tr,turn,fee=replay(t,op,cl,rr,div,mode,slip,delay)
                if scope=='portfolio' and period=='actual_BITO' and mode=='next_open' and slip==0:
                    old=np.load(AUDIT/'nav_next_open_s0_d1_f1_cash00.npz')
                    np.testing.assert_allclose(nav[0],old['nav'][list(old['names']).index('V1.3-D')],atol=1e-10,rtol=1e-10)
                if scope=='portfolio' and period=='long_synthetic' and slip==0:
                    old=pd.read_csv(ROOT/'release/model-research/studies/whipsaw-research/nav_long_synthetic_next_close.csv',index_col=0,parse_dates=True)
                    np.testing.assert_allclose(nav[0],old.baseline.to_numpy(),atol=1e-9,rtol=1e-10)
                for k,name in enumerate(NAMES):
                    for window,start,end in windows(ix):
                        pos=np.flatnonzero((ix>=start)&(ix<=end))
                        if len(pos)<5:continue
                        lo=max(0,pos[0]-1);hi=pos[-1]+1
                        rows.append(dict(period=period,scope=scope,model=name,mode=mode,slippage=slip,delay=delay,cash_zero=zero,window=window,start=str(ix[lo].date()),end=str(ix[hi-1].date()),total_return=nav[k,hi-1]/nav[k,lo]-1,
                            **metrics(nav[k,lo:hi],ix[lo:hi],tr[k,lo:hi],turn[k,lo:hi],fee[k,lo:hi])))
                if slip==0 and delay==1:
                    pd.DataFrame(nav.T,index=ix,columns=NAMES).to_csv(OUT/f'nav_{period}_{mode}_{scope}.csv')
                    for k,name in enumerate(NAMES):
                        for year in sorted(set(ix.year)):
                            pos=np.flatnonzero(ix.year==year);lo=max(0,pos[0]-1);hi=pos[-1]+1;v=nav[k,lo:hi]
                            annual.append(dict(period=period,scope=scope,mode=mode,model=name,year=year,return_=v[-1]/v[0]-1,mdd=(v/np.maximum.accumulate(v)-1).min()))
                    if scope=='defense_sleeve':
                        # Consecutive defensive signal episodes; same slice for every
                        # policy, includes next-day exit. Not independent trades.
                        cashnav=np.cumprod(1+rr);starts=np.flatnonzero(~attack&np.r_[True,attack[:-1]])
                        for st in starts:
                            ends=np.flatnonzero(attack[st:]);end=min(len(ix)-1,st+ends[0]+1) if len(ends) else len(ix)-1
                            for k,name in enumerate(NAMES):
                                ep.append(dict(period=period,mode=mode,model=name,start=str(ix[st].date()),end=str(ix[end].date()),ongoing=not len(ends),return_=nav[k,end]/nav[k,st]-1,cash_return=cashnav[end]/cashnav[st]-1,baseline_return=nav[0,end]/nav[0,st]-1))
    pd.DataFrame(rows).to_csv(OUT/'metrics.csv',index=False)
    pd.DataFrame(annual).to_csv(OUT/'annual.csv',index=False)
    pd.DataFrame(ep).to_csv(OUT/'episodes.csv',index=False)
    pd.DataFrame(coverage).to_csv(OUT/'allocation_coverage.csv',index=False)
    latest=pd.concat({name:t[['BRK.B','GLD','CASH']].loc['2026-09-30':] for name,t in ts.items()},names=['model','date'])
    latest.to_csv(OUT/'october_targets.csv')
    manifest=dict(protocol=PROTOCOL,model_fingerprint=load_model('woogong-1.3-d').fingerprint,
        hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),Path(inspect.getfile(builder)),ROOT/'tools/research_defense_whipsaw.py',ROOT/'data/equities.csv',ROOT/'data/btc.csv',AUDIT/'inputs_actual_BITO.npz',AUDIT/'inputs_long_synthetic.npz']},
        checks=['2016 and 2023 prefix parity','future perturbation unchanged past','attack target parity','2843 frozen baseline target parity','actual and long baseline NAV parity','finite nonnegative fully invested weights'],
        caveats=['Retrospective comparisons, not independent OOS','2015 BITO synthetic BTC proxy','2012 conditional signal-price/previous UTC BTC execution proxy, retrospective drag','Daily-close drawdowns not intraday','Taxes, FX and market impact excluded','No live changes'])
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    f=pd.DataFrame(rows);print(f[(f.period=='actual_BITO')&(f.scope=='portfolio')&(f.window=='full')&(f['mode']=='next_open')&(f.slippage==0)][['model','cagr','mdd','calmar','trade_days']].to_string(index=False))
    print('PASS causal checks, frozen target/NAV parity, attack invariance; saved',OUT)

if __name__=='__main__':main()
