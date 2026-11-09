"""Fixed-rule 2010 extension and explicit post-close official-close fills.
Research outputs only. No production configuration or trading changes.
"""
import json,hashlib,os
from pathlib import Path
import numpy as np
import pandas as pd
LOCAL_ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('WOOGONG_AUDIT_DATA_DIR',str(LOCAL_ROOT/'data/validation/v2'))
from research_bounded_intervention import ROOT,combine
from research_defense_whipsaw import AUDIT,replay
from portable_replay import factor

OUT=ROOT/'release/long-close-2010'
ASSETS=['TQQQ','BRK.B','GLD','CASH','SOXL','BITO']
PRIMARY='bounded::entry_only'

def literal(p,base,ind):
    q=p['BRK.B']/p.GLD
    signal=(q.pct_change(5,fill_method=None)>.02)&(q.pct_change(20,fill_method=None)>.05)&(q>q.rolling(10).mean()*1.01)&(p.GLD<p.GLD.rolling(10).mean()*.99)&(p['BRK.B']>p['BRK.B'].rolling(5).mean())
    t=base.copy();active=False
    for d in t.index:
        if ind.loc[d,'state'] not in [2,3,4] or base.loc[d,'GLD']<=1e-9:active=False
        elif not active and signal.loc[d]:active=True
        if active:t.loc[d,'BRK.B']+=t.loc[d,'GLD'];t.loc[d,'GLD']=0
    return t

def same_close(t,cl,rf,div,slip=0):
    """Mark prior holdings first; fill TODAY'S target only AFTER today's move."""
    m,n,_=t.shape;held=np.zeros((m,6));held[:,3]=1;value=np.ones(m)
    nav=np.ones((m,n));tr=np.zeros((m,n),int);turn=np.zeros((m,n));fee=np.zeros((m,n))
    rate=np.full(6,.001+slip);rate[3]=0
    for i in range(n):
        if i:
            g=cl[i]/cl[i-1];g[3]=1+rf[i];g-=div[i]*.001
            dollars=held*g;value*=dollars.sum(axis=1);held=dollars/dollars.sum(axis=1)[:,None]
        use=np.max(abs(t[:,i]-held),axis=1)>=.125
        if use.any():
            k=factor(t[use,i],held[use],rate);delta=abs(k[:,None]*t[use,i]-held[use])
            tr[use,i]=1;turn[use,i]=delta[:,[0,1,2,4,5]].sum(axis=1);fee[use,i]=(delta*rate).sum(axis=1)
            value[use]*=k;held[use]=t[use,i]
        nav[:,i]=value
    return nav,tr,turn,fee

def scalar_check(t,cl,rf,div,slip):
    """Separate dollar-book implementation, bisection self-financing costs."""
    rate=np.full(6,.001+slip);rate[3]=0;dollars=np.array([0.,0.,0.,1.,0.,0.]);out=[]
    for i,w in enumerate(t):
        if i:
            g=cl[i]/cl[i-1];g[3]=1+rf[i];g-=div[i]*.001;dollars*=g
        value=dollars.sum()
        if max(abs(w-dollars/value))>=.125:
            lo,hi=0.,value
            for _ in range(55):
                mid=(lo+hi)/2
                if mid+np.sum(abs(mid*w-dollars)*rate)>value:hi=mid
                else:lo=mid
            dollars=((lo+hi)/2)*w
        out.append(dollars.sum())
    return np.array(out)

def intervals(candidate,base):
    different=(abs(candidate-base).max(axis=1)>1e-9).to_numpy();ix=base.index;out=[]
    for i in np.flatnonzero(different&~np.r_[False,different[:-1]]):
        ends=np.flatnonzero(~different[i+1:]);j=i+1+ends[0] if len(ends) else len(ix)
        out.append((ix[i],ix[j] if j<len(ix) else pd.NaT))
    return out

def approve(nav,base,candidate,ix,min_events=0):
    monthly=nav.resample('ME').last();monthly=monthly[monthly.index<=ix[-1]]
    lr=np.log(monthly/monthly.shift(1)).dropna();ex=lr.candidate-lr.baseline
    events=intervals(candidate,base);approved={};logs=[]
    for month in pd.period_range(ix[0],ix[-1],freq='M'):
        start=month.start_time;history=ex[ex.index<start]
        closed=sum(a>=ix[0] and pd.notna(b) and b<start for a,b in events)
        ok=len(history)>=24 and closed>=min_events and history.mean()>1e-10
        approved[month]=bool(ok)
        logs.append(dict(month=str(month),history_months=len(history),closed_events=closed,approved=bool(ok),score=float(history.mean()) if len(history) else None))
    result=base.copy()
    for start,end in events:
        if approved[start.to_period('M')]:
            sel=(ix>=start)&((ix<end) if pd.notna(end) else True);result.loc[sel]=candidate.loc[sel]
    return result,logs

def stats(v,ix,tr):
    years=(ix[-1]-ix[0]).days/365.25;dd=v/np.maximum.accumulate(np.r_[1.,v])[1:]-1
    return dict(start=str(ix[0].date()),end=str(ix[-1].date()),cagr=float(v[-1]**(1/years)-1),mdd=float(dd.min()),final_multiple=float(v[-1]),total_return=float(v[-1]-1),trade_days=int(tr.sum()))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    p=pd.read_csv(ROOT/'data/validation/long2010/reconstructed_inputs.csv.gz',index_col=0,parse_dates=True)
    frozen=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True)
    pd.testing.assert_frame_equal(p.loc[frozen.index],frozen,check_freq=False)
    btc=pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    ts,ind=combine(p,btc);base=ts['baseline'];candidate=ts['entry_only'];v1=literal(p,base,ind)
    # New construction is causal under truncation, including exact V1 latch.
    for cut in ['2014-12-31','2024-12-31']:
        short,si=combine(p.loc[:cut],btc.loc[:cut])
        np.testing.assert_allclose(candidate.loc[:cut],short['entry_only'],atol=1e-12)
        np.testing.assert_allclose(v1.loc[:cut],literal(p.loc[:cut],short['baseline'],si),atol=1e-12)
    # Tiny timing trap: buying after a doubling must NOT receive that doubling.
    toy=np.zeros((1,3,6));toy[:,:,3]=1;toy[:,1:,3]=0;toy[:,1:,1]=1
    px=np.ones((3,6));px[:,1]=[1,2,2]
    nv=same_close(toy,px,np.zeros(3),np.zeros_like(px))[0]
    np.testing.assert_allclose(nv[0],[1,1/1.001,1/1.001],rtol=1e-12)
    a=np.load(AUDIT/'inputs_actual_BITO.npz');ai=pd.DatetimeIndex(a['dates'])
    cases=[]
    for drag in [0.,-.05338828097800662,-.10]:
        ix=base.index
        close=pd.DataFrame(1.,index=ix,columns=ASSETS)
        for s in ['TQQQ','BRK.B','GLD','SOXL']:close[s]=p[s].reindex(ix)
        proxy=btc.shift(1).reindex(ix);valid=proxy.notna()
        close.loc[valid,'BITO']=proxy.loc[valid]*np.exp(drag*(ix[valid]-ix[valid][0]).days.to_numpy()/365.25)
        for s in ['SOXL','BITO']:
            missing=~p[s].reindex(ix).notna() if s=='SOXL' else ~valid
            assert base.loc[missing,s].abs().max()<1e-12
        # All late incomplete fields have zero exposure before/after trades.
        late=ix>frozen.index[-1]
        for t in [base,candidate,v1]:
            assert t.loc[late,['TQQQ','SOXL','BITO','CASH']].abs().max().max()<1e-12
            assert t.shift(1).loc[late,['TQQQ','SOXL','BITO','CASH']].abs().max().max()<1e-12
        close=close.ffill().fillna(1.)
        cases.append((f'conditional_2010_btc_drag{drag:.6f}',ix,close.to_numpy(),close.to_numpy(),p.cash_return.reindex(ix).fillna(0).to_numpy(),np.zeros(close.shape)))
    # Actual ETF ledger through Oct20, extended only while all risk exposure=0.
    ix=base.index[base.index>=ai[0]];cl=np.ones((len(ix),6));op=cl.copy();rf=np.zeros(len(ix));div=np.zeros_like(cl)
    cl[:len(ai)]=a['cl'];op[:len(ai)]=a['op'];rf[:len(ai)]=a['rf'];div[:len(ai)]=a['div']
    for i in range(len(ai),len(ix)):
        cl[i]=cl[i-1]
        for j,s in [(1,'BRK.B'),(2,'GLD')]:cl[i,j]*=p.loc[ix[i],s]/p.loc[ix[i-1],s]
        op[i]=cl[i] # never used for an open fill in this extension; asserted below
    cases.append(('actual_BITO',ix,op,cl,rf,div))
    rows=[];annual=[];logs=[];checks=[]
    for label,ix,op,cl,rf,div in cases:
        b=base.reindex(ix);c=candidate.reindex(ix);u=v1.reindex(ix)
        modes=['same_close','next_close']+(['next_open'] if label=='actual_BITO' else [])
        for mode in modes:
            expert=np.stack([b.to_numpy(),c.to_numpy()])
            expert_nav=(same_close(expert,cl,rf,div) if mode=='same_close' else replay(expert,op,cl,rf,div,mode))[0]
            routed,log=approve(pd.DataFrame(expert_nav.T,index=ix,columns=['baseline','candidate']),b,c,ix)
            strict,_=approve(pd.DataFrame(expert_nav.T,index=ix,columns=['baseline','candidate']),b,c,ix,3)
            for l in log:logs.append(dict(case=label,mode=mode,**l))
            names=['baseline','user_v1_latch','monthly_entrygate','monthly_entrygate_closed3','fixed_entry_only']
            arr=np.stack([b,u,routed,strict,c])
            for slip in [0.,.003]:
                nv,tr,turn,fee=(same_close(arr,cl,rf,div,slip) if mode=='same_close' else replay(arr,op,cl,rf,div,mode,slip))
                if label=='actual_BITO' and mode=='next_open':
                    assert tr[:,len(ai):].sum()==0,'Would need genuine new opening prices'
                    if slip==0:
                        expected=pd.read_csv(ROOT/'data/validation/long2010/nav_actual_BITO_next_open.csv.gz',index_col=0,parse_dates=True)
                        np.testing.assert_allclose(nv[0,:len(ai)],expected.baseline,rtol=1e-10)
                        np.testing.assert_allclose(nv[2,:len(ai)],expected.monthly_pair_entrygate,rtol=1e-10)
                if mode=='same_close' and slip==0:
                    for k in range(len(names)):
                        scalar=scalar_check(arr[k],cl,rf,div,slip)
                        error=float(np.max(abs(nv[k]-scalar)/np.maximum(1,abs(scalar))))
                        assert error<1e-10;checks.append(dict(case=label,model=names[k],independent_error=error))
                for k,name in enumerate(names):
                    rows.append(dict(case=label,mode=mode,slippage=slip,model=name,**stats(nv[k],ix,tr[k])))
                    if slip==0:
                        for year in sorted(set(ix.year)):
                            pos=np.flatnonzero(ix.year==year);prior=nv[k,pos[0]-1] if pos[0] else 1.
                            annual.append(dict(case=label,mode=mode,model=name,year=int(year),return_=float(nv[k,pos[-1]]/prior-1)))
                if slip==0:pd.DataFrame(nv.T,index=ix,columns=names).to_csv(OUT/f'nav_{label}_{mode}.csv')
    pd.DataFrame(rows).to_csv(OUT/'metrics.csv',index=False);pd.DataFrame(annual).to_csv(OUT/'annual.csv',index=False)
    pd.DataFrame(logs).to_csv(OUT/'monthly_approval.csv',index=False)
    manifest=dict(fingerprint=__import__('models.registry',fromlist=['load_model']).load_model('woogong-1.3-d').fingerprint,
        checks=checks,other_checks=['fixed price history prefix preserved','2014/2024 target truncation invariance','same-close timing trap passed','actual next-open baseline and approved-combination canonical NAV parity','no late open executions or missing risk exposure'],
        scope='Research only; no production app, broker or execution policy changed',
        same_close='Observe final close, then hypothetical full after-hours fill at identical official close, today target. Not a guaranteed executable closing-auction or after-hours return.',
        long_proxy='2010-02-11 onward signal-close equity series; BITO replaced throughout by previous UTC BTC close from2011-08-19, annual log drag0/-5.3388%/-10%; no BTC holding before readiness, no fabricated pre-inception ETF returns. Not the audited2015 NY-close proxy.',
        literal_user_rule='Five entry thresholds unchanged; one-way latch until attack/forced state or baseline no longer GLD, as preceding October answer. No symmetric reverse or daily reset has been invented.',
        price_limitations='Long equity series is frozen signal-price basis, not verified all-asset dividend-reinvested execution ledger. Actual scope uses audited adjusted prices/distribution fee inputs throughOct20. Nov4 cached extension only BRK/GLD; prices not independently refreshed.',
        costs='12.5percentage-point rebalance band; fee0.1% each side; sensitivity extra0.3% each side; cash return where known; no taxes,FX,market impact,partial fills or borrowing.',
        selection='At least24 complete prior months, positive mean net log excess, approval frozen at intervention entry; closed3 variant requires3 prior completed intervals. Each execution convention trains its own approval. Rules chosen after seeing2026, no independent OOS.',
        hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),ROOT/'data/equities.csv',ROOT/'data/btc.csv',ROOT/'data/validation/long2010/reconstructed_inputs.csv.gz',ROOT/'data/validation/long2010/nav_actual_BITO_next_open.csv.gz',AUDIT/'inputs_actual_BITO.npz']})
    (OUT/'audit.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    f=pd.DataFrame(rows);print(f[(f['mode']=='same_close')&(f.slippage==0)][['case','model','cagr','mdd','final_multiple','trade_days']].to_string(index=False))
    print('PASS independent same-close ledgers and causal/timing/canonical checks')

if __name__=='__main__':main()
