"""Different mechanisms, fixed small hypotheses; no production mutations.

Investigates geometry, path efficiency, regression slope, CUSUM, channels and
confluence rather than searching another dense EMA grid.
"""
import numpy as np
import pandas as pd
from research_defense_redesign import ROOT,main as run_research
from models.registry import load_model
from models.core_v1 import evaluate as core

OUT=ROOT/'release/adaptive-defense'
NAMES=['baseline','log_selector','clipped_log_selector','efficiency_gold','efficiency_both','efficiency_blend25',
       'regression_gold','regression_both','cusum5_gold','cusum5_both','cusum3_gold',
       'channel21_gold','channel21_both','channel63_gold','trailing_vol_gold','confluence2_gold','confluence3_gold']
PROTOCOL=dict(names=NAMES,priority='long-term net growth; preserve attack timing and state1 forced lock',
 geometry='EMA84/378 of log(GLD/BRK), plus separate daily3*prior63vol winsorization',
 efficiency='abs21day net log change / sum21 abs daily log changes; gate>.35 and direction agrees21return; fast logEMA21/63',
 regression='OLS21 slope indicator abs(t)>2 and agrees last5day change; t is signal, NOT inferential significance',
 cusum='prior63vol-normalized daily relative logreturn, allowance.25, thresholds5 and3; persistent state',
 channels='prior21/63day close-ratio channel breakout; exit opposing prior10day channel',
 trailing='current GLD20day log drawdown>2*vol21*sqrt5; alternative5return positive & aboveEMA10 =>BRK, elseCASH',
 confluence='efficiency-trend, regression and CUSUM5 opposing votes; 2=>half/3=>full or only3=>full',
 semantics='gold-only or both direction controls; normal defense only; log selectors recompute Cross/D25, overlays preserve legacy cash',
 caveat='parameters fixed by this protocol but all historical periods already viewed; exploratory, no independent OOS')

def ema(x,n):return x.ewm(span=n,adjust=False,min_periods=n).mean()

def features(p):
    x=np.log(p.GLD/p['BRK.B']);d=x.diff();v=d.rolling(63,min_periods=63).std().shift(1)
    fast=ema(x,21)>ema(x,63);old=ema(p.GLD/p['BRK.B'],84)>ema(p.GLD/p['BRK.B'],378)
    er=(x-x.shift(21)).abs()/d.abs().rolling(21,min_periods=21).sum().where(lambda z:z>1e-12)
    efficient=(er>.35)&(np.sign(x-x.shift(21))==np.where(fast,1,-1))
    eff=np.where(efficient,np.where(fast,1,-1),0)
    n=21;grid=np.arange(n)-(n-1)/2;den=float((grid*grid).sum())
    slope=x.rolling(n,min_periods=n).apply(lambda a:np.dot(a,grid)/den,raw=True)
    mx=x.rolling(n,min_periods=n).mean();sse=(x*x).rolling(n).sum()-n*mx*mx-slope*slope*den
    se=np.sqrt(sse.clip(lower=0)/(n-2)/den).where(lambda z:z>1e-12);t=slope/se
    reg=np.where((t.abs()>2)&(np.sign(slope)==np.sign(x-x.shift(5))),np.sign(slope),0)
    def cusum(h):
        out=np.zeros(len(x));selected=0;plus=minus=0.
        z=(d/v.where(lambda a:a>1e-10)).to_numpy()
        for i,value in enumerate(z):
            if np.isfinite(value):
                if selected==0:selected=1 if old.iloc[i] else -1
                plus=max(0.,plus+value-.25);minus=min(0.,minus+value+.25)
                if plus>h:selected=1;plus=minus=0.
                elif minus<-h:selected=-1;plus=minus=0.
            out[i]=selected
        return out
    def channel(n):
        hi=x.rolling(n,min_periods=n).max().shift(1);lo=x.rolling(n,min_periods=n).min().shift(1)
        exit_hi=x.rolling(10,min_periods=10).max().shift(1);exit_lo=x.rolling(10,min_periods=10).min().shift(1)
        out=np.zeros(len(x));held=0
        for i in range(len(x)):
            if not np.isfinite(hi.iloc[i]):continue
            if held==0:held=1 if old.iloc[i] else -1
            if x.iloc[i]>hi.iloc[i]:held=1
            elif x.iloc[i]<lo.iloc[i]:held=-1
            elif held==-1 and x.iloc[i]>exit_hi.iloc[i]:held=1
            elif held==1 and x.iloc[i]<exit_lo.iloc[i]:held=-1
            out[i]=held
        return out
    changes=d.clip(lower=-3*v,upper=3*v).where(v.notna(),d).fillna(0)
    clipped=changes.cumsum().where(x.notna())
    return pd.DataFrame(dict(log_ratio=x,old_gold=old,fast_gold=fast,efficiency=er,eff_signal=eff,
        slope_t=t,reg_signal=reg,cusum5=cusum(5),cusum3=cusum(3),channel21=channel(21),channel63=channel(63),
        log_gold=ema(x,84)>ema(x,378),clipped_log_gold=ema(clipped,84)>ema(clipped,378)),index=p.index)

def selector_overlay(p,btc,gold):
    target,ind=core(p,btc);ix=target.index;gold=gold.reindex(ix).to_numpy(bool)
    profile=load_model('woogong-1.3-d').profile;c=profile['cross'];regular=ind.state.isin([2,3,4]).to_numpy()
    target.loc[regular,:]=0.;target.loc[regular,'GLD']=gold[regular].astype(float);target.loc[regular,'BRK.B']=(~gold[regular]).astype(float)
    prices=p[['TQQQ','SOXL','BRK.B','GLD']].copy();prices['BTC']=btc.shift(1).reindex(p.index)
    ret=prices.pct_change(c['look'],fill_method=None).reindex(ix);gr=prices.GLD.pct_change(c['gold'],fill_method=None).reindex(ix)
    selected=np.where(gold,ret.GLD,ret['BRK.B'])
    raw=regular&(ret['BRK.B'].to_numpy()<0)&(ret.GLD.to_numpy()<0)&((ret[['TQQQ','SOXL','BTC']]<0).sum(axis=1).to_numpy()>=c['riskmin'])&(selected<=c['loss'])&(~gold|(gr.to_numpy()<0))
    raw&=ret.notna().all(axis=1).to_numpy()&gr.notna().to_numpy();cash=np.zeros(len(ix),bool);age=cool=0
    for i in range(len(ix)):
        if not regular[i]:age=cool=0;continue
        if age:
            if age<c['minhold'] or(raw[i] and age<c['maxhold']):cash[i]=True;age+=1
            else:age=0;cool=c['cooldown']
        elif cool:cool-=1
        elif raw[i]:cash[i]=True;age=1
    target.loc[cash,:]=[0,0,0,1,0,0]
    d=profile['defense'];weak=p.QQQ.reindex(ix)<p.QQQ.rolling(d['qqq_sma']).mean().reindex(ix)
    defense=target[['BRK.B','GLD']].sum(axis=1);mask=weak&(defense>1e-9)
    moved=defense.loc[mask]*d['cash_fraction'];target.loc[mask,['BRK.B','GLD']]*=1-d['cash_fraction'];target.loc[mask,'CASH']+=moved
    return target

def combine(p,btc):
    base,ind=load_model('woogong-1.3-d').evaluate(p,btc);f=features(p).reindex(base.index);b=base.to_numpy();state=ind.state.to_numpy()
    gold=np.where(b[:,2]>0,True,False);regular=np.isin(state,[2,3,4]);invested=b[:,1]+b[:,2]>1e-9
    out={'baseline':base,'log_selector':selector_overlay(p,btc,features(p).log_gold),
         'clipped_log_selector':selector_overlay(p,btc,features(p).clipped_log_gold)}
    def overlay(signal,goldonly=True,fraction=1.):
        t=b.copy();signal=np.asarray(signal);opposite=(signal!=0)&(signal!=np.where(gold,1,-1))
        mask=regular&invested&opposite
        if goldonly:mask&=gold
        amount=(b[:,1]+b[:,2])*np.asarray(fraction)
        for i in np.flatnonzero(mask):
            t[i,1:3]*=1-np.asarray(fraction)[i] if np.ndim(fraction) else 1-fraction
            dest=2 if signal[i]>0 else 1;t[i,dest]+=amount[i]
        return pd.DataFrame(t,index=base.index,columns=base.columns)
    for prefix,signal in [('efficiency',f.eff_signal),('regression',f.reg_signal),('cusum5',f.cusum5),('channel21',f.channel21)]:
        out[prefix+'_gold']=overlay(signal);out[prefix+'_both']=overlay(signal,False)
    out['efficiency_blend25']=overlay(f.eff_signal,fraction=.25)
    out['cusum3_gold']=overlay(f.cusum3);out['channel63_gold']=overlay(f.channel63)
    g=p.GLD;gv=np.log(g).diff().rolling(21,min_periods=21).std();draw=np.log(g/g.rolling(20,min_periods=20).max())
    stopped=(draw<-2*gv*np.sqrt(5)).reindex(base.index).to_numpy()
    brk_ok=((p['BRK.B'].pct_change(5,fill_method=None)>0)&(p['BRK.B']>ema(p['BRK.B'],10))).reindex(base.index).to_numpy()
    t=b.copy()
    for i in np.flatnonzero(regular&gold&invested&stopped):
        amount=b[i,1]+b[i,2];t[i,1:3]=0;t[i,1 if brk_ok[i] else 3]+=amount
    out['trailing_vol_gold']=pd.DataFrame(t,index=base.index,columns=base.columns)
    votes=((f[['eff_signal','reg_signal','cusum5']].to_numpy()==-1).sum(axis=1))
    frac=np.where(votes>=3,1.,np.where(votes>=2,.5,0.))
    out['confluence2_gold']=overlay(np.full(len(f),-1),fraction=frac)
    out['confluence3_gold']=overlay(np.where(votes==3,-1,0))
    for t in out.values():
        assert np.isfinite(t).all().all() and t.min().min()>-1e-12 and np.allclose(t.sum(axis=1),1)
        np.testing.assert_array_equal(t.iloc[state==0],base.iloc[state==0])
    return {name:out[name] for name in NAMES},ind

if __name__=='__main__':
    run_research(NAMES,combine,OUT,PROTOCOL)
