"""Disagreement labels and strictly matured-history switching gates. Research only."""
import json,hashlib
import numpy as np
import pandas as pd
from research_defense_redesign import ROOT,AUDIT,replay,metrics,allocations
from models.registry import load_model

OUT=ROOT/'release/model-research/studies/conditional-defense'
SHORTS=['ema21_63','ema42_126','dual63']

def wilson(w,n):
    if not n:return 0.
    z=1.96;p=w/n
    return (p+z*z/(2*n)-z*np.sqrt(p*(1-p)/n+z*z/(4*n*n)))/(1+z*z/n)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    protocol=dict(shorts=SHORTS,horizon=21,nonoverlap='new label no sooner than 21 sessions after previous start',
        gate='at least 10 matured observations; win>=60%; mean excess>0',
        contexts='global or direction pair (long asset, short asset)',
        strict='only labels with exit index strictly before current signal may train gate',
        definition='win means short beats long after hypothetical roundtrip fees; also report absolute profits',
        scope='preserve original Cross/D25 cash; redirect only invested defense budget; attack unchanged',
        caveat='retrospective study; thresholds fixed for this study, not independent OOS')
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    p=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True)
    btc=pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    base,ind=load_model('woogong-1.3-d').evaluate(p,btc)
    ratio=p.GLD/p['BRK.B'];short={}
    for f,s in [(21,63),(42,126)]:
        fast=ratio.ewm(span=f,adjust=False,min_periods=f).mean();slow=ratio.ewm(span=s,adjust=False,min_periods=s).mean()
        short[f'ema{f}_{s}']=pd.Series(np.where(fast>slow,2,1),index=p.index).reindex(base.index).to_numpy()
    z=allocations(p)['dual63'].reindex(base.index)
    short['dual63']=np.where(z.CASH>.999,3,np.where(z.GLD>0,2,1))
    rows=[];events=[];summary=[];decisions=[]
    for period in ['actual_BITO','long_synthetic']:
        a=np.load(AUDIT/f'inputs_{period}.npz');ix=pd.DatetimeIndex(a['dates']);n=len(ix)
        b=base.reindex(ix).to_numpy();states=ind.state.reindex(ix).to_numpy();defense=states!=0
        long=np.where(b[:,2]>0,2,np.where(b[:,1]>0,1,3));cash=np.cumprod(1+a['rf'])
        names=['baseline'];ts=[b];labelmap={}
        for name in SHORTS:
            choice=pd.Series(short[name],index=base.index).reindex(ix).to_numpy(dtype=int)
            disagreement=defense&(long!=3)&(choice!=long)
            labels=[];nextstart=0
            for i in range(n-2):
                if i<nextstart or not disagreement[i]:continue
                exits=np.flatnonzero(~defense[i+1:]);end=min(n-1,i+22,i+1+int(exits[0])+1 if len(exits) else n-1)
                if i+22>=n and not len(exits):continue # unfinished outcome
                entry=i+1
                def ret(asset):
                    if asset==3:return cash[end]/cash[entry]-1
                    return a['cl'][end,asset]/a['cl'][entry,asset]*(1-.001)/(1+.001)-1
                fr,lr=ret(choice[i]),ret(long[i]);r=dict(period=period,short=name,start=str(ix[i].date()),exit=str(ix[end].date()),i=i,end=end,
                    long_asset=int(long[i]),short_asset=int(choice[i]),fast_return=float(fr),long_return=float(lr),excess=float(fr-lr),win=bool(fr>lr))
                labels.append(r);events.append(r);nextstart=max(i+21,end+1)
            labelmap[name]=labels
            for context in ['all','global','direction','wilson']:
                t=b.copy();switches=0
                for i in np.flatnonzero(disagreement):
                    history=[r for r in labels if r['end']<i]
                    if context=='direction':history=[r for r in history if r['long_asset']==long[i] and r['short_asset']==choice[i]]
                    count=len(history);wins=sum(r['win'] for r in history);mean=np.mean([r['excess'] for r in history]) if count else 0
                    use=context=='all' or (count>=10 and wins/count>=.60 and mean>0 and (context!='wilson' or wilson(wins,count)>.5))
                    if use:
                        budget=t[i,1]+t[i,2];t[i,1:3]=0;t[i,choice[i]]+=budget;switches+=1
                        decisions.append(dict(period=period,short=name,gate=context,date=str(ix[i].date()),matured_n=count,wins=wins,mean_excess=mean))
                names.append(name+'_'+context);ts.append(t)
                assert np.allclose(t[~defense],b[~defense]) and np.allclose(t.sum(axis=1),1)
                summary.append(dict(period=period,short=name,gate=context,labels=len(labels),switch_signal_days=switches))
            for direction in ['all','gold_to_brk','brk_to_gold','to_cash']:
                predicate={'all':lambda r:True,'gold_to_brk':lambda r:r['long_asset']==2 and r['short_asset']==1,
                           'brk_to_gold':lambda r:r['long_asset']==1 and r['short_asset']==2,'to_cash':lambda r:r['short_asset']==3}[direction]
                q=[r for r in labels if predicate(r)]
                count=len(q);wins=sum(r['win'] for r in q)
                summary.append(dict(period=period,short=name,gate='label_'+direction,labels=count,win_rate=wins/count if count else np.nan,wilson_low=wilson(wins,count),mean_excess=np.mean([r['excess'] for r in q]) if count else np.nan,profit_rate=np.mean([r['fast_return']>0 for r in q]) if count else np.nan))
        arr=np.stack(ts)
        scenarios=[('next_open',0,1),('next_open',.003,1),('next_close',0,1),('next_open',.003,3)] if period=='actual_BITO' else [('next_close',0,1),('next_close',.003,1)]
        for mode,slip,delay in scenarios:
            nav,tr,turn,fee=replay(arr,a['op'],a['cl'],a['rf'],a['div'],mode,slip,delay)
            for k,name in enumerate(names):
                for window,start,end in [('full',ix[0],ix[-1]),('pre2024',ix[0],pd.Timestamp('2023-12-31')),('post2024',pd.Timestamp('2024-01-01'),ix[-1])]:
                    pos=np.flatnonzero((ix>=start)&(ix<=end));lo=max(0,pos[0]-1);hi=pos[-1]+1
                    rows.append(dict(period=period,model=name,mode=mode,slippage=slip,delay=delay,window=window,**metrics(nav[k,lo:hi],ix[lo:hi],tr[k,lo:hi],turn[k,lo:hi],fee[k,lo:hi])))
            if slip==0 and delay==1:pd.DataFrame(nav.T,index=ix,columns=names).to_csv(OUT/f'nav_{period}_{mode}.csv')
    pd.DataFrame(rows).to_csv(OUT/'metrics.csv',index=False);pd.DataFrame(events).to_csv(OUT/'events.csv',index=False)
    pd.DataFrame(summary).to_csv(OUT/'summary.csv',index=False);pd.DataFrame(decisions).to_csv(OUT/'decisions.csv',index=False)
    (OUT/'manifest.json').write_text(json.dumps(dict(protocol=protocol,model_fingerprint=load_model('woogong-1.3-d').fingerprint,code_sha256=hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest(),checks=['decision uses only strictly matured labels','nonoverlap label starts','attack parity','weight sum parity'],limitations=['winner labels frozen initial asset, not full dynamic strategy','labels use next close even for next-open NAV scenario','not independent OOS; previously viewed data','nonoverlap label sampling does not make observations independent']),indent=2),encoding='utf-8')
    f=pd.DataFrame(rows);print(f[(f.period=='actual_BITO')&(f['mode']=='next_open')&(f.slippage==0)&(f.window=='full')][['model','cagr','mdd','trade_days']].to_string(index=False))
    print(pd.DataFrame(summary).query("gate=='label_all'").to_string(index=False))

if __name__=='__main__':main()
