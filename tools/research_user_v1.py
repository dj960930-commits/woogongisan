"""Exact user V1 thresholds, predeclared exits, ablations and separate 2008 sleeve.
No threshold fitting. Never changes production model or orders.
"""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from research_defense_redesign import ROOT,AUDIT,replay,metrics
from models.registry import load_model

OUT=ROOT/'release/user-v1'
RAW=ROOT.parent/'bito_bitx_cases_20261023/inputs'
CONFIGS=[('v1_daily','daily',None),('v1_sticky','sticky',None),('v1_armed','armed',None),
 ('v1_symmetric','symmetric',None),('v1_clp','clp',None),('v1_confirm2','confirm2',None),
 *[(f'drop_{s}','sticky',s) for s in ['r5','r20','ratio_ma','gold_ma','brk_ma']],('v1_cash_proxy','cash',None)]
PROTOCOL=dict(thresholds=dict(r5=.02,r20=.05,ratio_ma=.01,gold_ma=-.01,brk_ma=0),configs=CONFIGS,
 primary='exact user entry, no threshold search',
 daily='original baseline whenever full entry condition absent',
 sticky='retain alternate until relative5 return<=0 AND ratio<SMA10; attack/state1 or baseline changes reset',
 symmetric='retain selected alternate until reverse full V1 entry; baseline changes reset',
 armed='sticky recommendation tracked during attack, no attack trading',
 clp='sticky entry plus CLP alternate>0.5 and current<0.5; data2020+',
 cash='separate proxy: selected asset20day return must beat cash20day; otherwise other eligible asset, otherwisecash; preserve legacy cash; no BIL claim',
 frozen_selection='select highest pre2025 net log NAV expert separately within each data/execution scope; deploy from2025 only',
 standalone='2008 onward standalone GLD/BRK ratio EMA84/378 baseline, NOT the full app',
 caveat='2025-2026 already viewed; chronological retrospective check, NOT untouched holdout')

def signals(p,raw):
    f=pd.DataFrame(index=p.index)
    for label,current,alt in [('gold','GLD','BRK.B'),('brk','BRK.B','GLD')]:
        r=p[alt]/p[current]
        f[label+'_r5_value']=r.pct_change(5,fill_method=None)
        f[label+'_r20_value']=r.pct_change(20,fill_method=None)
        f[label+'_ratio_ma_value']=r/r.rolling(10,min_periods=10).mean()-1
        f[label+'_gold_ma_value']=p[current]/p[current].rolling(10,min_periods=10).mean()-1
        f[label+'_brk_ma_value']=p[alt]/p[alt].rolling(5,min_periods=5).mean()-1
        for key,threshold,greater in [('r5',.02,True),('r20',.05,True),('ratio_ma',.01,True),('gold_ma',-.01,False),('brk_ma',0,True)]:
            f[label+'_'+key]=f[label+'_'+key+'_value']>threshold if greater else f[label+'_'+key+'_value']<threshold
        f[label+'_full']=f[[label+'_'+k for k in ['r5','r20','ratio_ma','gold_ma','brk_ma']]].all(axis=1)
        def clp(x):return ((x.close-x.low)/(x.high-x.low).where(lambda v:v>0)).reindex(p.index)
        f[label+'_clp']=(clp(raw[alt])>.5)&(clp(raw[current])<.5)
        f[label+'_exit']=(f[label+'_r5_value']<=0)&(r<r.rolling(10,min_periods=10).mean())
    cash=(1+p.cash_return).cumprod();cr=cash/cash.shift(20)-1
    excess=p[['BRK.B','GLD']].pct_change(20,fill_method=None).sub(cr,axis=0)
    f['both_cash_inferior']=(excess<0).all(axis=1)&excess.notna().all(axis=1)
    f['brk_cash_eligible']=excess['BRK.B']>=0;f['gold_cash_eligible']=excess.GLD>=0
    return f

def build(p,base,ind,raw):
    ix=base.index;b=base.to_numpy();f=signals(p,raw).reindex(ix);state=ind.state.to_numpy()
    long=np.where(b[:,2]>0,2,np.where(b[:,1]>0,1,3));normal=np.where(ind.defense_fast>ind.defense_slow,2,1)
    out={'baseline':b}
    for name,kind,drop in CONFIGS:
        full={}
        for label in ['gold','brk']:
            full[label]=f[[label+'_'+k for k in ['r5','r20','ratio_ma','gold_ma','brk_ma'] if k!=drop]].all(axis=1).to_numpy(copy=True)
            if kind=='clp':full[label]&=f[label+'_clp'].to_numpy()
            if kind=='confirm2':full[label]=pd.Series(full[label]).rolling(2,min_periods=2).min().fillna(0).to_numpy(bool)
        t=b.copy();active=None;last_ref=None
        for i in range(len(ix)):
            if state[i]==1 or (state[i]==0 and kind!='armed'):active=None;last_ref=None;continue
            ref=int(normal[i]) if state[i]==0 else int(long[i])
            if ref==3:active=None;last_ref=None;continue
            if last_ref is not None and ref!=last_ref:active=None
            last_ref=ref
            if kind=='daily':active=1 if ref==2 and full['gold'][i] else None
            else:
                if active is not None:
                    if kind=='symmetric':
                        reverse='brk' if active==1 else 'gold'
                        if full[reverse][i]:active=3-active
                        if active==ref:active=None
                    elif active==3:
                        if not f.both_cash_inferior.iloc[i]:active=None
                    elif f[('gold' if active==1 else 'brk')+'_exit'].iloc[i]:active=None
                if active is None and ref==2 and full['gold'][i]:active=1
                elif active is None and kind=='symmetric' and ref==1 and full['brk'][i]:active=2
                if kind=='cash':
                    if f.both_cash_inferior.iloc[i]:active=3
                    else:
                        chosen=ref if active is None else active
                        eligible=f['brk_cash_eligible' if chosen==1 else 'gold_cash_eligible'].iloc[i]
                        if not eligible:
                            other=3-chosen;other_ok=f['brk_cash_eligible' if other==1 else 'gold_cash_eligible'].iloc[i]
                            active=other if other_ok else 3
            if active is not None and state[i]!=0:
                budget=b[i,1]+b[i,2];t[i,1:3]=0;t[i,active]+=budget
        assert np.isfinite(t).all() and t.min()>-1e-12 and np.allclose(t.sum(axis=1),1)
        np.testing.assert_array_equal(t[state==0],b[state==0]);out[name]=t
    return out,f

def standalone(p):
    ix=p.index[p.index>='2008-01-01'];r=p.GLD/p['BRK.B'];fast=r.ewm(span=84,adjust=False,min_periods=84).mean();slow=r.ewm(span=378,adjust=False,min_periods=378).mean()
    assert fast.reindex(ix).notna().all() and slow.reindex(ix).notna().all()
    gold=(fast>slow).reindex(ix);b=pd.DataFrame(0.,index=ix,columns=['TQQQ','BRK.B','GLD','CASH','SOXL','BITO']);b['GLD']=gold.astype(float);b['BRK.B']=(~gold).astype(float)
    ind=pd.DataFrame(dict(state=2,defense_fast=fast.reindex(ix),defense_slow=slow.reindex(ix)),index=ix)
    return b,ind

def main():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'protocol.json').write_text(json.dumps(PROTOCOL,indent=2),encoding='utf-8')
    p=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True)
    btc=pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    raw={s:pd.read_csv(RAW/f'{t}_prices.csv',index_col=0,parse_dates=True) for s,t in [('BRK.B','BRK-B'),('GLD','GLD')]}
    base,ind=load_model('woogong-1.3-d').evaluate(p,btc);app,f=build(p,base,ind,raw);sb,si=standalone(p);sleeve,sf=build(p,sb,si,raw)
    assert f.loc['2026-10-02','gold_full']
    timeline=f.loc['2026-09-01':].join(ind[['state']])
    for name,t in app.items():
        for j,asset in [(1,'brk'),(2,'gold'),(3,'cash')]:timeline[name+'_'+asset]=pd.Series(t[:,j],index=base.index).reindex(timeline.index)
    timeline.to_csv(OUT/'case_signals.csv')
    for cut in ['2020-12-31','2024-12-31']:
        bp,ip=load_model('woogong-1.3-d').evaluate(p.loc[:cut],btc.loc[:cut]);t,_=build(p.loc[:cut],bp,ip,{s:z.loc[:cut] for s,z in raw.items()})
        for name in app:np.testing.assert_allclose(app[name][base.index<=cut],t[name],atol=1e-12,rtol=0)
    altered=p.copy();altered.loc[altered.index>'2024-12-31',['QQQ','TQQQ','SOXL','BRK.B','GLD']]*=2
    ab,ai=load_model('woogong-1.3-d').evaluate(altered,btc);at,_=build(altered,ab,ai,raw)
    for name in app:np.testing.assert_allclose(app[name][base.index<='2024-12-31'],at[name][base.index<='2024-12-31'],atol=1e-12,rtol=0)
    sp=p.loc[:'2024-12-31'];spb,spi=standalone(sp);spt,_=build(sp,spb,spi,{s:z.loc[:'2024-12-31'] for s,z in raw.items()})
    for name in sleeve:np.testing.assert_allclose(sleeve[name][sb.index<='2024-12-31'],spt[name],atol=1e-12,rtol=0)
    cases=[]
    for label,source,start in [('app_actual','actual_BITO','2021-10-20'),('app_long','long_synthetic','2015-07-01'),('app_ohlc2020','long_synthetic','2020-01-31')]:
        a=np.load(AUDIT/f'inputs_{source}.npz');di=pd.DatetimeIndex(a['dates']);sel=di>=start
        cases.append((label,di[sel],a['op'][sel],a['cl'][sel],a['rf'][sel],a['div'][sel],base.index,app))
    sx=sb.index;close=np.ones((len(sx),6));close[:,1:3]=p.loc[sx,['BRK.B','GLD']].to_numpy()
    cases.append(('standalone2008',sx,close,close,p.cash_return.reindex(sx).to_numpy(),np.zeros_like(close),sb.index,sleeve))
    rows=[];selections=[];events=[]
    for label,ix,op,cl,rf,div,sourceix,targets in cases:
        names=[n for n in targets if n!='v1_clp' or label in ['app_actual','app_ohlc2020']]
        pos=sourceix.get_indexer(ix);arr=np.stack([targets[n][pos] for n in names]);mode='next_open' if label=='app_actual' else 'next_close'
        nav,*_=replay(arr,op,cl,rf,div,mode,0,1);train=np.flatnonzero(ix<'2025-01-01');last=train[-1]
        score=np.log(nav[:,last]/nav[:,0]);win=int(np.argmax(score));pick=names[win]
        routed=arr[0].copy();routed[ix>='2025-01-01']=arr[win,ix>='2025-01-01']
        selections.append(dict(case=label,pick=pick,train_end=str(ix[last].date()),training_log_excess=float(score[win]-score[0])))
        allnames=names+['frozen2024_router'];alltargets=np.concatenate([arr,routed[None]])
        for timing,slip,delay in [(mode,0,1),(mode,.003,1),(mode,.003,3)]+([('next_close',0,1)] if label=='app_actual' else []):
            nv,tr,turn,fees=replay(alltargets,op,cl,rf,div,timing,slip,delay)
            if label=='app_actual' and timing=='next_open' and slip==0:
                old=np.load(AUDIT/'nav_next_open_s0_d1_f1_cash00.npz');np.testing.assert_allclose(nv[0],old['nav'][list(old['names']).index('V1.3-D')],atol=1e-10,rtol=1e-10)
            for k,name in enumerate(allnames):
                for window,start,end in [('full',ix[0],ix[-1]),('through2024',ix[0],pd.Timestamp('2024-12-31')),('2025on',pd.Timestamp('2025-01-01'),ix[-1])]:
                    use=np.flatnonzero((ix>=start)&(ix<=end));lo=max(0,use[0]-1);hi=use[-1]+1
                    rows.append(dict(case=label,model=name,mode=timing,slippage=slip,delay=delay,window=window,start=str(ix[lo].date()),end=str(ix[hi-1].date()),**metrics(nv[k,lo:hi],ix[lo:hi],tr[k,lo:hi],turn[k,lo:hi],fees[k,lo:hi])))
            if slip==0 and delay==1:pd.DataFrame(nv.T,index=ix,columns=allnames).to_csv(OUT/f'nav_{label}_{timing}.csv')
        # Declared-policy target overrides; not independent realised trades.
        for k,name in enumerate(names[1:],1):
            changed=np.max(abs(arr[k]-arr[0]),axis=1)>1e-9
            for i in np.flatnonzero(changed&~np.r_[False,changed[:-1]]):
                ends=np.flatnonzero(~changed[i+1:]);end=i+1+ends[0] if len(ends) else len(ix)-1
                if end+1>=len(ix):continue
                entry=i+1;exit_=end+1
                br=cl[exit_,1]/cl[entry,1]*(1-.001)/(1+.001)-1;gold=cl[exit_,2]/cl[entry,2]*(1-.001)/(1+.001)-1
                events.append(dict(case=label,model=name,signal=str(ix[i].date()),entry=str(ix[entry].date()),exit=str(ix[exit_].date()),brk_return=br,gold_return=gold,brk_beats_gold=br>gold))
    result=pd.DataFrame(rows);result.to_csv(OUT/'metrics.csv',index=False);pd.DataFrame(selections).to_csv(OUT/'frozen_selections.csv',index=False);pd.DataFrame(events).to_csv(OUT/'override_windows.csv',index=False)
    info=dict(protocol=PROTOCOL,fingerprint=load_model('woogong-1.3-d').fingerprint,checks=['2020/2024 app prefix equality','standalone2024 prefix equality','future perturbation past equality','October2 exact full signal true','attack parity','weight constraints','baseline actual NAV parity'],
        limitations=['entry thresholds chosen after seeing2026','standalone2008 is not app and no risk assets','CLP unavailable pre2020 excluded, not imputed','cash_proxy is not BIL ETF total return','raw override window returns not full-policy win rates','2025on retrospective already viewed'],
        hashes={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in [Path(__file__),ROOT/'tools/research_defense_redesign.py',ROOT/'tools/research_defense_whipsaw.py',ROOT/'data/equities.csv',ROOT/'data/btc.csv',AUDIT/'inputs_actual_BITO.npz',AUDIT/'inputs_long_synthetic.npz',RAW/'BRK-B_prices.csv',RAW/'GLD_prices.csv']})
    (OUT/'manifest.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    print(result[(result['case']=='app_actual')&(result['mode']=='next_open')&(result.slippage==0)&(result.window=='full')][['model','cagr','mdd','trade_days']].to_string(index=False))
    print(pd.DataFrame(selections).to_string(index=False))

if __name__=='__main__':main()
