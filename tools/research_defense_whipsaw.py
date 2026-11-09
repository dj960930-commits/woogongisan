"""Offline candidate comparison. Never imports/modifies live model profiles."""
from pathlib import Path
import sys,json,hashlib,os
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
AUDIT=Path(os.environ.get('WOOGONG_AUDIT_DATA_DIR',str(ROOT.parent/'all_versions_validation_20261026')))
sys.path[:0]=[str(ROOT),str(AUDIT)]
from models.core_v1 import evaluate as core
from models.registry import load_model
from portable_replay import factor

# Fixed, small family before reading outcomes. No exhaustive parameter search.
CANDIDATES=[
 dict(name='baseline'),
 dict(name='confirm2',confirm=2),dict(name='confirm3',confirm=3),dict(name='confirm5',confirm=5),
 dict(name='hysteresis025',hysteresis=.0025),dict(name='hysteresis050',hysteresis=.005),
 dict(name='minimum_hold5',hold=5),
 dict(name='forced_selector',forced='selector'),dict(name='forced_keep_defense',forced='keep'),
 dict(name='forced_mix50',forced='mix'),dict(name='forced_cash',forced='cash'),
 dict(name='forced_mix_confirm2',forced='mix',confirm=2)]


def targets(p,btc,config):
    target,ind=core(p,btc);profile=load_model('woogong-1.3-d').profile
    gap=np.log(ind.defense_fast/ind.defense_slow).to_numpy()
    gold=np.zeros(len(ind),bool);selected=None;pending=None;count=0;age=0
    for i,g in enumerate(gap):
        if not np.isfinite(g):continue
        raw=g>0
        if selected is None:selected=raw
        wanted=True if g>config.get('hysteresis',0) else False if g<-config.get('hysteresis',0) else selected
        if wanted!=selected:
            count=count+1 if pending==wanted else 1;pending=wanted
            if count>=config.get('confirm',1) and age>=config.get('hold',0):
                selected=wanted;count=0;pending=None;age=0
        else:count=0;pending=None
        gold[i]=selected;age+=1
    valid=ind.defense_fast.notna()&ind.defense_slow.notna()
    regular=ind.state.isin([2,3,4])&valid
    target.loc[regular,:]=0
    target.loc[regular,'GLD']=gold[regular].astype(float)
    target.loc[regular,'BRK.B']=(~gold[regular]).astype(float)
    last=None
    for i in range(len(ind)):
        state=int(ind.state.iloc[i])
        if state in (2,3,4) and valid.iloc[i]:last=bool(gold[i])
        if state!=1:continue
        forced=config.get('forced','brk')
        if forced=='brk':continue
        target.iloc[i]=0
        if forced=='cash':target.iloc[i,target.columns.get_loc('CASH')]=1
        elif forced=='mix':
            target.iloc[i,target.columns.get_loc('GLD')]=.5
            target.iloc[i,target.columns.get_loc('BRK.B')]=.5
        else:
            use_gold=(last if last is not None else gold[i]) if forced=='keep' else gold[i]
            target.iloc[i,target.columns.get_loc('GLD' if use_gold else 'BRK.B')]=1
    # Recompute Cross using the candidate's actual selected defense asset.
    c=profile['cross'];prices=p[['TQQQ','SOXL','BRK.B','GLD']].copy();prices['BTC']=btc.shift(1).reindex(p.index)
    ret=prices.pct_change(c['look'],fill_method=None).reindex(target.index)
    gr=prices.GLD.pct_change(c['gold'],fill_method=None).reindex(target.index)
    cross_regular=ind.state.isin([2,3,4]).to_numpy(copy=True)
    cross_gold=gold.copy()
    # Stage-two hypothesis, absent from all original candidates. If state1 is
    # included, evaluate its actual destination, not the regular selector.
    if config.get('cross_lock',False):
        locked=ind.state.eq(1).to_numpy();cross_regular|=locked
        if config.get('forced','brk')=='brk':cross_gold[locked]=False
        else:assert config['forced']=='selector'
    selected_return=np.where(cross_gold,ret.GLD,ret['BRK.B'])
    raw=(cross_regular&(ret['BRK.B'].to_numpy()<0)&(ret.GLD.to_numpy()<0)
         &((ret[['TQQQ','SOXL','BTC']]<0).sum(axis=1).to_numpy()>=c['riskmin'])
         &(selected_return<=c['loss'])&(~cross_gold|(gr.to_numpy()<0)))
    raw &= ret.notna().all(axis=1).to_numpy()&gr.notna().to_numpy()
    cash=np.zeros(len(target),bool);age=cool=0
    for i in range(len(target)):
        if not cross_regular[i]:age=cool=0;continue
        if age:
            if age<c['minhold'] or(raw[i] and age<c['maxhold']):cash[i]=True;age+=1
            else:age=0;cool=c['cooldown']
        elif cool:cool-=1
        elif raw[i]:cash[i]=True;age=1
    target.loc[cash,:]=[0,0,0,1,0,0]
    d=profile['defense'];weak=p.QQQ.reindex(target.index)<p.QQQ.rolling(d['qqq_sma']).mean().reindex(target.index)
    defense=target[['BRK.B','GLD']].sum(axis=1);mask=weak&(defense>1e-9)
    moved=defense.loc[mask]*d['cash_fraction'];target.loc[mask,['BRK.B','GLD']]*=1-d['cash_fraction'];target.loc[mask,'CASH']+=moved
    assert np.isfinite(target).all().all() and target.min().min()>-1e-10 and np.allclose(target.sum(axis=1),1)
    return target,ind,gold


def replay(t,op,cl,rf,div,mode='next_open',slip=0,delay=1):
    m,n,_=t.shape;held=np.zeros((m,6));held[:,3]=1;value=np.ones(m);nav=np.ones((m,n));goal=t[:,0].copy()
    bands=np.full(m,.125);due=np.where(np.max(abs(goal-held),axis=1)>=bands,delay,-1)
    rate=np.full(6,.001+slip);rate[3]=0;trades=np.zeros((m,n),int);turn=np.zeros((m,n));fees=np.zeros((m,n))
    for i in range(1,n):
        g=op[i]/cl[i-1];g[3]=1+rf[i];g-=div[i]*.001;a=held*g;value*=a.sum(axis=1);held=a/a.sum(axis=1)[:,None]
        for timing in ['next_open','next_close']:
            if timing=='next_close':
                g=cl[i]/op[i];g[3]=1;a=held*g;value*=a.sum(axis=1);held=a/a.sum(axis=1)[:,None]
            if timing==mode:
                use=due==i
                if use.any():
                    k=factor(goal[use],held[use],rate);delta=abs(k[:,None]*goal[use]-held[use])
                    trades[use,i]=1;turn[use,i]=delta[:,[0,1,2,4,5]].sum(axis=1);fees[use,i]=(delta*rate).sum(axis=1)
                    value[use]*=k;held[use]=goal[use];due[use]=-1
        fire=(due<0)&(np.max(abs(t[:,i]-held),axis=1)>=bands);due[fire]=i+delay;goal[fire]=t[fire,i];nav[:,i]=value
    return nav,trades,turn,fees


def metrics(v,dates,trade,turn,fee):
    years=(dates[-1]-dates[0]).days/365.25;cg=(v[-1]/v[0])**(1/years)-1;dd=v/np.maximum.accumulate(v)-1
    returns=v[1:]/v[:-1]-1;under=0;longest=0
    for x in dd:
        under=under+1 if x<-1e-12 else 0;longest=max(longest,under)
    return dict(cagr=float(cg),mdd=float(dd.min()),calmar=float(cg/-dd.min()),worst_day=float(returns.min()),
        worst3=float((v[3:]/v[:-3]-1).min()),underwater_sessions=longest,trade_days=int(trade.sum()),
        turnover_year=float(turn.sum()/years),sum_fee_fractions=float(fee.sum()))


def main(candidates=CANDIDATES,output=None):
    out=output or ROOT/'release/whipsaw-research';out.mkdir(parents=True,exist_ok=True)
    p=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True)
    btc=pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    baseline=load_model('woogong-1.3-d').evaluate(p,btc)[0]
    alltargets={};allgold={};checks=[]
    for config in candidates:
        t,ind,gold=targets(p,btc,config);alltargets[config['name']]=t;allgold[config['name']]=gold
    np.testing.assert_allclose(alltargets['baseline'],baseline,atol=1e-12,rtol=0)
    # Prefix and future-perturbation checks cover every candidate's sequential state.
    cutoff='2024-05-31';short=p.loc[:cutoff];changed=p.copy();changed.loc[changed.index>cutoff]*=2
    changed_btc=btc.copy();changed_btc.loc[changed_btc.index>cutoff]*=3
    for config in candidates:
        a=alltargets[config['name']].loc[:cutoff]
        np.testing.assert_allclose(a,targets(short,btc,config)[0],atol=1e-12,rtol=0)
        np.testing.assert_allclose(a,targets(changed,changed_btc,config)[0].loc[:cutoff],atol=1e-12,rtol=0)
    frozen=np.load(AUDIT/'targets.npz');refidx=pd.DatetimeIndex(frozen['dates']);which=list(frozen['names']).index('V1.3-D')
    np.testing.assert_allclose(baseline.reindex(refidx),frozen['targets'][which],atol=1e-12,rtol=0)
    rows=[];eventrows=[]
    for period in ['actual_BITO','long_synthetic']:
        a=np.load(AUDIT/f'inputs_{period}.npz');ix=pd.DatetimeIndex(a['dates'])
        arr=np.stack([t.reindex(ix).to_numpy() for t in alltargets.values()]);assert np.isfinite(arr).all()
        configs=[('next_open',0,1),('next_open',.001,1),('next_open',.003,1),('next_close',0,1),('next_open',.003,2),('next_open',.003,3)] if period=='actual_BITO' else [('next_close',0,1),('next_close',.003,1)]
        for mode,slip,delay in configs:
            nav,tr,turn,fees=replay(arr,a['op'],a['cl'],a['rf'],a['div'],mode,slip,delay)
            if period=='actual_BITO' and mode=='next_open' and slip==0:
                expected=np.load(AUDIT/'nav_next_open_s0_d1_f1_cash00.npz')
                np.testing.assert_allclose(nav[0],expected['nav'][list(expected['names']).index('V1.3-D')],atol=1e-10,rtol=1e-10)
            for k,name in enumerate(alltargets):
                for window,start,end in [('full',str(ix[0].date()),str(ix[-1].date())),('development','2021-10-20','2023-12-31'),('confirmation','2024-01-01','2026-10-20')]:
                    if period=='long_synthetic' and window!='full':continue
                    pos=np.flatnonzero((ix>=start)&(ix<=end));lo=max(0,pos[0]-1);hi=pos[-1]+1
                    rows.append(dict(period=period,model=name,mode=mode,slippage=slip,delay=delay,window=window,
                        **metrics(nav[k,lo:hi],ix[lo:hi],tr[k,lo:hi],turn[k,lo:hi],fees[k,lo:hi])))
            if slip==0 and delay==1:
                pd.DataFrame(nav.T,index=ix,columns=alltargets.keys()).to_csv(out/f'nav_{period}_{mode}.csv')
        # Baseline event taxonomy: causal selector change vs forced state1 entry.
        t=baseline.reindex(ix);states=ind.state.reindex(ix)
        for i in range(1,len(t)):
            if t.GLD.iloc[i-1]>0 and t['BRK.B'].iloc[i]>0 and t['BRK.B'].iloc[i-1]<1e-9 and t.GLD.iloc[i]<1e-9:
                eventrows.append(dict(date=str(ix[i].date()),period=period,previous_state=int(states.iloc[i-1]),state=int(states.iloc[i]),kind='forced' if states.iloc[i]==1 else 'defense_selector'))
    frame=pd.DataFrame(rows);frame.to_csv(out/'metrics.csv',index=False);pd.DataFrame(eventrows).to_csv(out/'event_taxonomy.csv',index=False)
    manifest=dict(candidates=candidates,cutoff=str(p.index[-1].date()),baseline_fingerprint=load_model('woogong-1.3-d').fingerprint,
        inputs={str(f.relative_to(ROOT.parent)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [ROOT/'data/equities.csv',ROOT/'data/btc.csv',AUDIT/'inputs_actual_BITO.npz',AUDIT/'inputs_long_synthetic.npz']},
        checks=['baseline targets match 2843 frozen sessions','baseline NAV matches archived next-open ledger','all candidate prefix checks','all candidate future perturbation checks'],
        caveat='Retrospective time split; confirmation data already viewed. Long synthetic uses BTC proxy and next-close, not actual BITO pre-inception. Not independent out-of-sample proof.')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(frame[(frame.period=='actual_BITO')&(frame['mode']=='next_open')&(frame.slippage==0)&(frame.window=='full')][['model','cagr','mdd','calmar','trade_days','worst3']].to_string(index=False))
    print('PASS baseline parity and causality; saved',out)


if __name__=='__main__':main()
