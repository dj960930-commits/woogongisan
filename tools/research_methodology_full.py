import numpy as np
import pandas as pd
from tools.research_methodology_stage1 import build, c
from models.core_v1 import evaluate

OUT=c.ROOT/'release/model-research/studies/methodology-full'
RISK=[0,1,2,4,5]
SHOCK=np.array([[-.30,-.12,.03,0,-.35,-.20],[-.06,-.03,0,0,-.09,-.35],[-.24,-.12,-.08,0,-.30,-.25]])

def defense(p,b,base,tag):
    original,i=evaluate(p,b)
    ix=base.index
    state=i.state.to_numpy()
    regular=np.isin(state,[2,3,4])
    eligible=regular | ((state==1)&(tag=='J01'))
    price=p[['BRK.B','GLD','TQQQ','SOXL']].copy()
    price['BTC']=b.shift(1).reindex(p.index)
    r=price.pct_change(5,fill_method=None).reindex(ix)
    gold21=price.GLD.pct_change(21,fill_method=None).reindex(ix)
    gold=(original.GLD>0).to_numpy()
    has_asset=original[['BRK.B','GLD']].sum(axis=1).gt(0).to_numpy()
    ratio=p.GLD/p['BRK.B']
    shortgold=(ratio.ewm(span=5,adjust=False,min_periods=5).mean()>ratio.ewm(span=21,adjust=False,min_periods=21).mean()).reindex(ix).to_numpy()
    weakening=np.log(i.defense_fast/i.defense_slow).diff(21).lt(0).to_numpy()
    ready=np.log(ratio).diff().rolling(63).std().shift(1).reindex(ix).notna().to_numpy()
    condition=regular & gold & ~shortgold & weakening & ready
    confirm=pd.Series(condition).rolling(3).sum().eq(3).to_numpy()
    entry=condition & np.r_[True,state[:-1]==0]
    if tag=='H01': entry=condition
    if tag=='H02': entry=confirm
    both=(r['BRK.B'].lt(0)&r.GLD.lt(0)).to_numpy()
    common=both & (r[['TQQQ','SOXL','BTC']].lt(0).sum(axis=1)>=2).to_numpy() & r.notna().all(axis=1).to_numpy() & gold21.notna().to_numpy()
    weak=(p.QQQ<p.QQQ.rolling(200).mean()).reindex(ix).to_numpy()
    dd=(p[['BRK.B','GLD']]/p[['BRK.B','GLD']].rolling(21).max()-1).reindex(ix).to_numpy()
    ret=r[['BRK.B','GLD']].to_numpy()
    out=base.to_numpy(copy=True)
    active=False
    age=cool=clear=recovery=0
    damaged=False
    prior=None
    for j in range(len(ix)):
        if state[j]==0:
            age=cool=clear=recovery=0
            active=damaged=False
            prior=None
            continue
        tentative=regular[j] and gold[j] and not shortgold[j] and (active or entry[j])
        chosen=int(gold[j] and not tentative)
        ref=chosen if tag in ('G01','X04') else int(gold[j])
        raw=eligible[j] and common[j] and ret[j,ref]<=-.05 and (not ref or gold21.iloc[j]<0)
        emergency=eligible[j] and both[j] and ret[j,chosen]<=-.08
        shelter=False
        if not eligible[j]:
            age=cool=clear=0
        elif age:
            clear=0 if raw else clear+1
            keep=(clear<3 if tag=='I01' else raw and age<10)
            if age<3 or keep:
                shelter=True; age+=1
            else:
                age=0; cool=10
        elif cool and not (tag in ('I02','X04') and emergency):
            cool-=1
        elif raw or (tag in ('I02','X04') and cool and emergency):
            shelter=True; age=1; clear=cool=0
        active=bool(tentative and not shelter)
        budget=0 if shelter or not has_asset[j] else (.75 if weak[j] else 1.)
        if tag=='J02':
            if chosen!=prior: damaged=False; recovery=0
            if budget:
                if dd[j,chosen]<=-.10: damaged=True
                recovery=recovery+1 if dd[j,chosen]>-.05 else 0
                if recovery>=3: damaged=False
                if damaged: budget*=.5
            prior=chosen
        out[j]=0
        out[j,1+chosen]=budget
        out[j,3]=1-budget
    return pd.DataFrame(out,index=ix,columns=base.columns)

def scale(target, multiplier):
    result=target.copy()
    result.iloc[:,RISK]=result.iloc[:,RISK].mul(multiplier,axis=0)
    result.CASH=1-result.iloc[:,RISK].sum(axis=1)
    return result

def vol(target, returns, ceiling, attack):
    weights=target.iloc[:,RISK].to_numpy()
    matrices=returns.rolling(63).cov().to_numpy().reshape(-1,5,5)
    used=weights!=0
    relevant=used[:,:,None]&used[:,None,:]
    cov=np.where(relevant,matrices,0)
    estimate=np.sqrt(np.maximum(0,np.einsum('ij,ijk,ik->i',weights,cov,weights)*252))
    return scale(target,np.where(attack & (estimate>ceiling),ceiling/np.maximum(estimate,1e-12),1))

def stress(target, ceiling):
    loss=np.maximum(0,-target.iloc[:,:6].to_numpy()@SHOCK.T).max(axis=1)
    return scale(target,np.minimum(1,ceiling/np.maximum(loss,1e-12)))

def replay(t,cl,op,rf,div,mode,extra,guard=None):
    if guard is None:
        return c.canonical_replay(t,cl,rf,div,mode,op,extra,.125)[:2]
    h=np.eye(6)[3]; nav=[]; trades=[]; value=1.; pending=None
    fees=np.full(6,.001+extra); fees[3]=0
    for j,goal in enumerate(t):
        traded=0
        def fill(order,held,value):
            if order is None: return held,value,0
            if isinstance(order,float):
                order=held.copy()
                order[4]=min(order[4],.4)
                lever=order[0]+order[4]
                if lever>.7: order[[0,4]]*=.7/lever
                order[3]+=1-order.sum()
            if np.max(abs(order-held))<1e-12: return held,value,0
            factor=c.factor(order[None,:],held[None,:],fees)[0]
            return order,value*factor,1
        if j:
            gross=op[j]/cl[j-1]; gross[3]=1+rf[j]; gross-=div[j]*.001
            mark=h*gross; value*=mark.sum(); h=mark/mark.sum()
            if mode=='next_open': h,value,traded=fill(pending,h,value)
            mark=h*cl[j]/op[j]; value*=mark.sum(); h=mark/mark.sum()
            if mode=='next_close': h,value,traded=fill(pending,h,value)
        pending=goal if np.max(abs(goal-h))>=.125 else None
        if h[0]+h[4]>.7+guard+1e-12 or h[4]>.4+guard+1e-12:
            pending=1.
        if mode=='same_close_reference': h,value,traded=fill(pending,h,value)
        nav.append(value); trades.append(traded)
    return np.array(nav),np.array(trades)

def setup(p,b,ix,close,rf,actual):
    stage,_=build(p,b)
    base=stage['v21'].iloc[:,:6]
    anchor=stage['A01'].iloc[:,:6]
    check=defense(p,b,base,'baseline')
    np.testing.assert_allclose(check,base,atol=1e-12)
    _,i=c.load_model('woogong-v2.1').evaluate(p,b)
    out={name:t.reindex(ix).iloc[:,:6] for name,t in stage.items()}
    attack=i.state.reindex(ix).eq(0)
    returns=pd.DataFrame(close[:,RISK],index=ix).pct_change(fill_method=None)
    a=out['A01']
    for j,ceiling in enumerate([.20,.25,.30],1): out[f'D0{j}']=vol(a,returns,ceiling,attack)
    for j,ceiling in enumerate([.10,.15],1): out[f'E0{j}']=stress(a,ceiling)
    for name in ['F01','F02']: out[name]=out['v21']
    for name in ['G01','H01','H02','I01','I02','J01','J02']:
        out[name]=defense(p,b,base,name).reindex(ix)
    if actual:
        x=p[['TQQQ','SOXL']].reindex(ix).copy()
        x['BITO']=close[:,5]
        l=np.log(x)
        s=sum((l-l.shift(n))/(l.diff().rolling(n).std()*np.sqrt(n)) for n in [42,252])/2
        ex=np.exp(s.sub(s.max(axis=1),axis=0))
        w=ex.div(ex.sum(axis=1),axis=0)
        w.SOXL=w.SOXL.clip(upper=.4)
        w[['TQQQ','SOXL']]=w[['TQQQ','SOXL']].mul((.7/(w.TQQQ+w.SOXL)).clip(upper=1),axis=0)
        t=a.copy(); mask=attack & w.notna().all(axis=1)
        t.loc[mask,w.columns]=w.loc[mask]
        t.CASH=1-t.iloc[:,RISK].sum(axis=1)
        out['K01']=t
        t=a.copy()
        cash=pd.Series(np.log1p(rf),index=ix).rolling(63).sum()
        mask=attack & np.log(x.BITO/x.BITO.shift(63)).lt(cash)
        t.loc[mask,'BITO']*=.5
        t.CASH=1-t.iloc[:,RISK].sum(axis=1)
        out['K02']=t
    # Fixed, interpretable combinations from stage-1 candidates and the planned risk budgets.
    x=a.copy()
    raw=a.BITO
    ratio=out['C04'].BITO.div(raw.where(raw>0)).fillna(1.)
    x.BITO=raw.mul(ratio).clip(upper=.6)
    x.CASH=1-x.iloc[:,RISK].sum(axis=1)
    out['X01']=x
    out['X02']=vol(x,returns,.30,attack)
    out['X03']=stress(x,.15)
    out['X04']=defense(p,b,base,'X04').reindex(ix)
    out['X05']=x.where(attack,out['X04'],axis=0)
    if actual:
        x6=out['X05'].copy()
        x6.BITO*=out['K02'].BITO.div(a.BITO.where(a.BITO>0)).fillna(1.)
        x6.CASH=1-x6.iloc[:,RISK].sum(axis=1)
        out['X06']=x6
    return out

def main(only=None):
    OUT.mkdir(exist_ok=True)
    p=pd.read_csv(c.ROOT/'data/equities.csv',index_col=0,parse_dates=True)
    b=pd.read_csv(c.ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    fixtures=[]
    for tag in ['actual_BITO','long_synthetic']:
        a=np.load(c.ROOT/f'data/validation/v2/inputs_{tag}.npz')
        fixtures.append((tag,p,pd.DatetimeIndex(a['dates']),a['cl'],a['op'],a['rf'],a['div']))
    lp=pd.read_csv(c.ROOT/'data/validation/long2010/reconstructed_inputs.csv.gz',index_col=0,parse_dates=True).loc[:p.index[-1]]
    ix=lp.loc['2010-02-11':].index
    for drag in [0,-.05338828097800662,-.10]:
        cl=lp.reindex(ix)[['TQQQ','BRK.B','GLD','cash_return','SOXL','BITO']].copy()
        cl.cash_return=1.
        proxy=b.shift(1).reindex(ix)
        cl.BITO=proxy*np.exp(drag*(ix-proxy.first_valid_index()).days/365.25)
        cl=cl.ffill().fillna(1.).to_numpy()
        fixtures.append((f'long2010_{drag:.6f}',lp,ix,cl,cl,lp.cash_return.reindex(ix).fillna(0).to_numpy(),np.zeros_like(cl)))
    rows=[]; seg=[]; annual=[]
    for tag,prices,ix,cl,op,rf,div in fixtures:
        print('Replay',tag,flush=True)
        targets=setup(prices,b,ix,cl,rf,tag=='actual_BITO')
        for name,t in targets.items():
            if only is not None and name not in only: continue
            np.testing.assert_allclose(t.sum(axis=1),1,atol=1e-12)
            assert np.isfinite(t).all().all() and t.min().min()>-1e-10
            assert (t.TQQQ+t.SOXL<=.7+1e-10).all() and (t.SOXL<=.4+1e-10).all()
            guard={'F01':0.,'F02':.02,'X06':.02}.get(name)
            for mode in ['same_close_reference','next_close']+(['next_open'] if tag=='actual_BITO' else []):
                for extra in [0.,.003]:
                    nav,tr=replay(t.to_numpy(),cl,op,rf,div,mode,extra,guard)
                    daily=nav/np.r_[1.,nav[:-1]]-1
                    worst3=(nav/np.r_[np.ones(3),nav[:-3]]-1).min()
                    rows.append(dict(period=tag,name=name,mode=mode,extra=extra,worst_day=daily.min(),worst_3day=worst3,**c.metrics(nav,ix,tr)))
                    primary='next_open' if tag=='actual_BITO' else 'same_close_reference'
                    if mode==primary and extra==0:
                        for year in sorted(set(ix.year)):
                            idx=np.flatnonzero(ix.year==year)
                            annual.append(dict(period=tag,name=name,year=year,total_return=nav[idx[-1]]/(nav[idx[0]-1] if idx[0] else 1)-1))
                        for start,end in [(2010,2014),(2015,2019),(2020,2023),(2024,2026)]:
                            idx=np.flatnonzero((ix.year>=start)&(ix.year<=end))
                            if len(idx)<2: continue
                            nv,tx=replay(t.to_numpy()[idx],cl[idx],op[idx],rf[idx],div[idx],mode,0.,guard)
                            seg.append(dict(period=tag,name=name,start=str(ix[idx[0]].date()),end=str(ix[idx[-1]].date()),**c.metrics(nv,ix[idx],tx)))
        pd.DataFrame(rows).to_csv(OUT/'metrics.csv',index=False)
        pd.DataFrame(seg).to_csv(OUT/'segments.csv',index=False)
        pd.DataFrame(annual).to_csv(OUT/'annual.csv',index=False)

if __name__=='__main__':
    main()


