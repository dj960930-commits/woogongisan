"""Causal chart-hint ablations and same-policy past-only router; research only."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from research_defense_redesign import ROOT,AUDIT,replay,metrics
from models.registry import load_model

OUT=ROOT/'release/model-research/studies/chart-hints'
RAW=ROOT.parent/'bito_bitx_cases_20261023/inputs'
CONFIGS=[('relative','R',1,False),('relative_weak','RG',1,False),('relative_shock','RS',1,False),('shock_base','RSB',1,False),('relative_base','RB',1,False),
 ('relative_flow','RF',1,False),('weak_base','RGB',1,False),('weak_flow','RGF',1,False),
 ('weak_flow1','WF1',1,False),('weak_flow3','WF3',1,False),('all_hints1','AF1',1,False),('all_hints3','AF3',1,False),
 ('weak_flow_armed','RGF',1,False),('all_hints_armed','RGBF',1,False),
 ('all_hints','RGBF',1,False),('vote2','V',1,False),('vote2_confirm3','V3',1,False),
 ('weak_base_half','RGB',.5,False),('symmetric_vote2','V',1,True),('vote2_cash','VC',1,False)]
PROTOCOL=dict(configs=CONFIGS,
 R='alternate/current ratio EMA5>EMA21 AND 5day log ratio return>0',
 G='current below EMA10 AND 5day logreturn<0',
 S='5day logreturn/(63day daily vol*sqrt5)<-1; separate shock ablation',
 B='alternate above EMA10 AND 5day return>0 AND rolling5 low > previous5 rolling low, all past-only',
 F='alternate 5day mean close/open logreturn>0, current<0, and alternate mean CLV5>current',
 V='R plus at least2 of G/B/F; V3 requires entry condition3 consecutive closes',
 cash='optional both weak: each below EMA10 and 5day return negative',
 lifecycle='normal defense2/3/4 only; invested defensive budget redirected; exit on R false3 closes OR new asset own weakness; existing cash and attack retained',
 router='annual expanding and rolling36; minimum24 completed monthly returns; highest positive net log NAV excess over baseline',
 scope='chart definitions chosen after viewing October; retrospective, not independent OOS; no threshold optimization',
 sensitivity='after initial 5day flow results, compare1/3day flow for weak_flow and all_hints only; explicitly post-result hypothesis',
 armed='post-result mechanism check: track 5day weak_flow/all_hints defensive preference during attack without trading; apply only on normal defense entry')

def features(p,raw):
    out=pd.DataFrame(index=p.index)
    for direction,current,alt in [('gold','GLD','BRK.B'),('brk','BRK.B','GLD')]:
        r=p[alt]/p[current];cr=np.log(p[current]).diff(5);ar=np.log(p[alt]).diff(5)
        vol=np.log(p[current]).diff().rolling(63,min_periods=63).std()
        out[direction+'_relative']=np.log(r/r.shift(5))
        out[direction+'_shock']=cr/(vol*np.sqrt(5))
        out[direction+'_R']=(r.ewm(span=5,adjust=False,min_periods=5).mean()>r.ewm(span=21,adjust=False,min_periods=21).mean())&(out[direction+'_relative']>0)
        out[direction+'_G']=(p[current]<p[current].ewm(span=10,adjust=False,min_periods=10).mean())&(cr<0)
        out[direction+'_S']=out[direction+'_shock']<-1
        # Close-based past lows permit a consistent 2015 price-only comparison.
        lo=p[alt].rolling(5,min_periods=5).min()
        out[direction+'_B']=(p[alt]>p[alt].ewm(span=10,adjust=False,min_periods=10).mean())&(ar>0)&(lo>lo.shift(5))
        a=raw[alt];c=raw[current]
        af=np.log(a.close/a.open).rolling(5,min_periods=5).mean().reindex(p.index)
        cf=np.log(c.close/c.open).rolling(5,min_periods=5).mean().reindex(p.index)
        def clv(z):return ((2*z.close-z.high-z.low)/(z.high-z.low).where(lambda x:x>0)).rolling(5,min_periods=5).mean()
        ac=clv(a).reindex(p.index);cc=clv(c).reindex(p.index)
        out[direction+'_flow_diff']=af-cf;out[direction+'_clv_diff']=ac-cc
        out[direction+'_flow_available']=af.notna()&cf.notna()&ac.notna()&cc.notna()
        out[direction+'_F']=out[direction+'_flow_available']&(af>0)&(cf<0)&(ac>cc)
        for h in [1,3]:
            def cv(z):return (2*z.close-z.high-z.low)/(z.high-z.low).where(lambda v:v>0)
            af_h=np.log(a.close/a.open).rolling(h,min_periods=h).mean().reindex(p.index)
            cf_h=np.log(c.close/c.open).rolling(h,min_periods=h).mean().reindex(p.index)
            clv_diff=(cv(a).rolling(h,min_periods=h).mean()-cv(c).rolling(h,min_periods=h).mean()).reindex(p.index)
            out[direction+f'_F{h}']=(af_h>0)&(cf_h<0)&(clv_diff>0)
    return out

def build(p,btc,raw):
    base,ind=load_model('woogong-1.3-d').evaluate(p,btc);f=features(p,raw).reindex(base.index);b=base.to_numpy()
    long=np.where(b[:,2]>0,2,np.where(b[:,1]>0,1,3));state=ind.state.to_numpy();ts={'baseline':b};flow_names=[]
    for name,rule,fraction,symmetric in CONFIGS:
        t=b.copy()
        if 'F' in rule or rule.startswith('V'):flow_names.append(name)
        for d,label in [(2,'gold'),(1,'brk')]:
            if d==1 and not symmetric:continue
            R=f[label+'_R'].to_numpy();G=f[label+'_G'].to_numpy();B=f[label+'_B'].to_numpy();F=f[label+'_F'].to_numpy();S=f[label+'_S'].to_numpy()
            if rule.startswith(('WF','AF')):
                flow=f[label+'_F'+rule[-1]].to_numpy();mask=R&G&flow
                if rule.startswith('AF'):mask&=B
            else:
                mask=R&((G.astype(int)+B.astype(int)+F.astype(int))>=2) if rule.startswith('V') else np.logical_and.reduce([{'R':R,'G':G,'B':B,'F':F,'S':S}[c] for c in rule])
            if rule=='V3':mask=pd.Series(mask).rolling(3,min_periods=3).min().fillna(0).to_numpy(bool)
            active=None;off=0;armed=name.endswith('_armed')
            for i in range(len(t)):
                reference=long[i]
                if armed and state[i]==0:reference=2 if ind.defense_fast.iloc[i]>ind.defense_slow.iloc[i] else 1
                if state[i]==1 or (state[i]==0 and not armed) or reference!=d:active=None;off=0;continue
                own=f[('brk' if d==2 else 'gold')+'_G'].iloc[i]
                both=G[i] and own
                if active is not None:
                    off=off+1 if not R[i] else 0
                    if off>=3 or (active!=3 and own) or(active==3 and not both):active=None;off=0
                if rule=='VC' and both:active=3
                elif active is None and mask[i]:active=3-d
                if active is not None and state[i]!=0:
                    budget=(b[i,1]+b[i,2])*fraction;t[i,1:3]*=1-fraction;t[i,active]+=budget
        assert np.isfinite(t).all() and t.min()>-1e-12 and np.allclose(t.sum(axis=1),1)
        np.testing.assert_array_equal(t[state==0],b[state==0]);ts[name]=t
    return base.index,ts,f,ind,flow_names

def main():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'protocol.json').write_text(json.dumps(PROTOCOL,indent=2),encoding='utf-8')
    p=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True)
    btc=pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    raw={s:pd.read_csv(RAW/f'{ticker}_prices.csv',index_col=0,parse_dates=True) for s,ticker in [('BRK.B','BRK-B'),('GLD','GLD')]}
    for z in raw.values():
        complete=z[['open','high','low','close']].notna().all(axis=1)
        assert ((z.loc[complete].high>=z.loc[complete,['open','close','low']].max(axis=1))&(z.loc[complete].low<=z.loc[complete,['open','close','high']].min(axis=1))).all()
    bi,ts,f,ind,flow_names=build(p,btc,raw)
    cut='2023-12-29';_,st,_,_,_=build(p.loc[:cut],btc.loc[:cut],{s:z.loc[:cut] for s,z in raw.items()})
    for name in ts:np.testing.assert_allclose(ts[name][bi<=cut],st[name],atol=1e-12,rtol=0)
    changed=p.copy();changed.loc[changed.index>cut,['GLD','BRK.B','QQQ','TQQQ','SOXL']]*=2
    changedraw={s:z.copy() for s,z in raw.items()}
    for z in changedraw.values():z.loc[z.index>cut,['open','high','low','close']]*=3
    _,ft,_,_,_=build(changed,btc,changedraw)
    for name in ts:np.testing.assert_allclose(ts[name][bi<=cut],ft[name][bi<=cut],atol=1e-12,rtol=0)
    # October2 is attack, not a defensively invested day. Save every raw hint.
    timeline=f.join(ind[['state']]);timeline['baseline_asset']=np.where(ts['baseline'][:,2]>0,'GLD',np.where(ts['baseline'][:,1]>0,'BRK','CASH/ATTACK'))
    for name,t in ts.items():timeline[name+'_brk']=t[:,1];timeline[name+'_cash']=t[:,3]
    timeline.loc['2026-09-15':].to_csv(OUT/'october_timeline.csv')
    old=pd.read_csv(ROOT/'release/model-research/studies/failure-overlay/original_choice_windows.csv',parse_dates=['start'])
    ef=old.merge(f.reset_index().rename(columns={f.index.name or 'index':'start'}),on='start',how='left');ef.to_csv(OUT/'failure_features.csv',index=False)
    groups=[]
    for asset in ['GLD','BRK.B']:
        prefix='gold' if asset=='GLD' else 'brk'
        for outcome in [False,True]:
            group=ef[(ef.asset==asset)&(ef.wrong==outcome)]
            for h in ['R','G','B','F','S']:
                g=group[group[prefix+'_flow_available'].fillna(False)] if h=='F' else group
                groups.append(dict(asset=asset,wrong=outcome,hint=h,n=len(g),frequency=g[prefix+'_'+h].mean()))
    pd.DataFrame(groups).to_csv(OUT/'feature_associations.csv',index=False)
    rows=[];logs=[]
    for period in ['actual_BITO','common_2020','price_only_2015']:
        source='actual_BITO' if period=='actual_BITO' else 'long_synthetic';a=np.load(AUDIT/f'inputs_{source}.npz')
        dates=pd.DatetimeIndex(a['dates']);sel=dates>='2020-01-31' if period=='common_2020' else np.ones(len(dates),bool)
        ix=dates[sel];pos=bi.get_indexer(ix);names=[n for n in ts if period!='price_only_2015' or n not in flow_names]
        arr=np.stack([ts[n][pos] for n in names]);op=a['op'][sel];cl=a['cl'][sel];rf=a['rf'][sel];div=a['div'][sel]
        mode='next_open' if period=='actual_BITO' else 'next_close'
        nav,*_=replay(arr,op,cl,rf,div,mode,0,1)
        monthly=pd.DataFrame(nav.T,index=ix,columns=names).resample('ME').last();monthly=monthly[monthly.index<=ix[-1]]
        lr=np.log(monthly/monthly.shift(1)).dropna();ex=lr.sub(lr.baseline,axis=0)
        routes=[]
        for policy in ['expanding','recent36']:
            target=arr[0].copy()
            for year in sorted(set(ix.year)):
                h=ex[ex.index<pd.Timestamp(year=year,month=1,day=1)]
                if policy=='recent36':h=h.tail(36)
                scores=h.mean().drop('baseline');pick=scores.idxmax() if len(h)>=24 else None
                if pick is not None and scores[pick]<=0:pick=None
                if pick is not None:target[ix.year==year]=arr[names.index(pick),ix.year==year]
                assert len(h)==0 or h.index[-1]<pd.Timestamp(year=year,month=1,day=1)
                logs.append(dict(period=period,router=policy,year=int(year),months=len(h),pick=pick,last_month=str(h.index[-1].date()) if len(h) else None))
            routes.append(target)
        alltargets=np.concatenate([arr,np.stack(routes)]);allnames=names+['router_expanding','router_recent36']
        scenarios=[(mode,0,1),(mode,.003,1),(mode,.003,3)]
        if period=='actual_BITO':scenarios.append(('next_close',0,1))
        for timing,slip,delay in scenarios:
            nv,tr,turn,fee=replay(alltargets,op,cl,rf,div,timing,slip,delay)
            if period=='actual_BITO' and timing=='next_open' and slip==0:
                ref=np.load(AUDIT/'nav_next_open_s0_d1_f1_cash00.npz');np.testing.assert_allclose(nv[0],ref['nav'][list(ref['names']).index('V1.3-D')],atol=1e-10,rtol=1e-10)
            for k,name in enumerate(allnames):
                for window,start in [('full',ix[0]),('pre2024',ix[0]),('post2024',pd.Timestamp('2024-01-01'))]:
                    use=(ix>=start)&(ix<=pd.Timestamp('2023-12-31')) if window=='pre2024' else ix>=start
                    where=np.flatnonzero(use);lo=max(0,where[0]-1);hi=where[-1]+1
                    rows.append(dict(period=period,model=name,window=window,mode=timing,slippage=slip,delay=delay,**metrics(nv[k,lo:hi],ix[lo:hi],tr[k,lo:hi],turn[k,lo:hi],fee[k,lo:hi])))
            if slip==0 and delay==1:pd.DataFrame(nv.T,index=ix,columns=allnames).to_csv(OUT/f'nav_{period}_{timing}.csv')
    result=pd.DataFrame(rows);result.to_csv(OUT/'metrics.csv',index=False);pd.DataFrame(logs).to_csv(OUT/'router_log.csv',index=False)
    files=[Path(__file__),ROOT/'data/equities.csv',ROOT/'data/btc.csv',ROOT/'tools/research_defense_redesign.py',ROOT/'tools/research_defense_whipsaw.py',RAW/'GLD_prices.csv',RAW/'BRK-B_prices.csv',AUDIT/'inputs_actual_BITO.npz',AUDIT/'inputs_long_synthetic.npz']
    info=dict(protocol=PROTOCOL,fingerprint=load_model('woogong-1.3-d').fingerprint,checks=['OHLC range consistency','2023 prefix parity','future prices perturbation past unchanged','attack parity','weight constraints','baseline actual NAV parity','annual past-only complete-month fit'],
        coverage={s:[str(z.index[0].date()),str(z.index[-1].date())] for s,z in raw.items()},hashes={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in files},
        limitations=['OHLC cannot prove buying pressure or intraday sequence','basing uses close-based rolling lows, not hindsight pivot','flow unavailable pre2020, omitted from 2015 comparison','all hypotheses designed after seeing October and old studies','associations are small-sample exploratory, not significance tests','synthetic BITO in long periods','router expert counterfactual states tracked while not selected'])
    (OUT/'manifest.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    print(result[(result.period=='actual_BITO')&(result['mode']=='next_open')&(result.slippage==0)&(result.window=='full')][['model','cagr','mdd','trade_days']].to_string(index=False))
    print(timeline.loc['2026-10-02':'2026-10-16',['state','gold_R','gold_G','gold_B','gold_F','gold_relative','gold_shock']].to_string())

if __name__=='__main__':main()
