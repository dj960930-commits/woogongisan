from pathlib import Path
import sys,json,hashlib
import pandas as pd,numpy as np
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from pathlib import Path
import sys,json
import numpy as np,pandas as pd
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from models.registry import load_model
from models.performance import replay
from models import core_v1
p=pd.read_csv(R/'data/equities.csv',index_col=0,parse_dates=True)
b=pd.read_csv(R/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
m=load_model('woogong-v2');base,ind=m.evaluate(p,b)
# Reconstruct the exact pre-leverage-cap BTC allocation, preserving SOXL cap.
src=(R/'models/core_v1.py').read_text(encoding="utf-8");src=src.replace(' clipped[:,2]+=np.where',' native=clipped[:,2].copy()\n clipped[:,2]+=np.where').replace(' return targets,indicators',' indicators["native_btc"]=native\n return targets,indicators')
ns=dict(core_v1.__dict__);exec(compile(src,str(R/'models/core_v1.py'),'exec'),ns)
_,rawind=ns['evaluate'](p,b)
lag=b.shift(1).reindex(p.index);sma=lag.rolling(126).mean();on=False;eligible=[]
for v,a in zip(lag,sma):
 if pd.notna(a):
  if v>a*1.02:on=True
  elif v<a*.98:on=False
 eligible.append(on)
gate=pd.Series(eligible,index=p.index).reindex(base.index)

from tools.portable_replay import factor
OUT=R/'release/model-research/studies/allocation-combination-study';OUT.mkdir(exist_ok=True)
CAPS=[0,.2,.4,.5,.6,.7,.8,1.];DEST=['BTC','CASH','QQQ','GLD','QQQ_GLD50','mom63','mom126','mom63_126'];FILTERS=['off','trend','trend_cap40']
attack=ind.state.eq(0);xx=pd.DataFrame({'BITO':lag,'QQQ':p.QQQ,'GLD':p.GLD});selector={}
for label,looks in [('mom63',[63]),('mom126',[126]),('mom63_126',[63,126])]:
 scores=sum(np.log(xx/xx.shift(n)) for n in looks)/len(looks);scores=scores.reindex(base.index)
 selector[label]=scores.fillna(-np.inf).idxmax(axis=1).where(scores.max(axis=1)>0,'CASH')
variants={'current':base.assign(QQQ=0.)};meta=[]
for cap in CAPS:
 modified=src.replace('.6/np.maximum(lever',f'{cap}/np.maximum(lever');scope=dict(core_v1.__dict__);exec(compile(modified,str(R/'models/core_v1.py'),'exec'),scope);capped,ci=scope['evaluate'](p,b)
 for dest in DEST:
  t=base.assign(QQQ=0.);t.loc[attack,base.columns]=capped.loc[attack];excess=(capped.BITO-ci.native_btc).clip(lower=0).where(attack,0);t.BITO-=excess
  if dest=='QQQ_GLD50':t.QQQ+=excess*.5;t.GLD+=excess*.5
  elif dest in selector:
   for asset in ['BITO','QQQ','GLD','CASH']:t[asset]+=excess.where(selector[dest].eq(asset),0)
  else:t['BITO' if dest=='BTC' else dest]+=excess
  for filt in FILTERS:
   u=t.copy()
   if filt!='off':
    cut=u.BITO.where(attack&~gate,0)
    if filt=='trend_cap40':cut=np.maximum(cut,(u.BITO-.4).clip(lower=0).where(attack,0))
    u.BITO-=cut;u.CASH+=cut
   name=f'L{int(cap*100)}_{dest}_{filt}';np.testing.assert_allclose(u.sum(axis=1),1);assert u.min().min()>-1e-10
   np.testing.assert_array_equal(u.loc[~attack,base.columns],base.loc[~attack]);variants[name]=u;meta.append(dict(name=name,cap=cap,destination=dest,btc_filter=filt))
np.testing.assert_allclose(variants['L60_BTC_off'][base.columns],base,atol=1e-12)
names=list(variants)
def batch(t,cl,op,rf,div,extra,mode):
 m,n,k=t.shape;held=np.zeros((m,k));held[:,3]=1;v=np.ones(m);nav=np.ones((m,n));tr=np.zeros(m,int);rate=np.full(k,.001+extra);rate[3]=0;goal=t[:,0];pending=np.max(abs(goal-held),axis=1)>=.125
 for i in range(n):
  if i:
   g=op[i]/cl[i-1];g[3]=1+rf[i];g-=div[i]*.001;mark=held*g;v*=mark.sum(axis=1);held=mark/mark.sum(axis=1)[:,None];g=cl[i]/op[i];g[3]=1;mark=held*g;v*=mark.sum(axis=1);held=mark/mark.sum(axis=1)[:,None]
  use=(np.max(abs(t[:,i]-held),axis=1)>=.125) if mode=='same_close_reference' else (pending if i else np.zeros(m,bool))
  if use.any():
   target=t[use,i] if mode=='same_close_reference' else goal[use];f=factor(target,held[use],rate);v[use]*=f;held[use]=target;tr[use]+=1
  goal=t[:,i];pending=np.max(abs(goal-held),axis=1)>=.125;nav[:,i]=v
 return nav,tr
metrics=[];annual=[];navs={}
for period in ['actual_BITO','long_synthetic']:
 a=np.load(R/f'data/validation/v2/inputs_{period}.npz');ix=pd.DatetimeIndex(a['dates']);cl=np.column_stack([a['cl'],p.QQQ.reindex(ix)]);div=np.column_stack([a['div'],np.zeros(len(ix))]);t=np.stack([v.reindex(ix).to_numpy() for v in variants.values()])
 for mode in ['same_close_reference','next_close']:
  for extra in [0,.003]:
   nv,tr=batch(t,cl,np.column_stack([a['op'],p.QQQ.reindex(ix)]),a['rf'],div,extra,mode)
   # Compare independent six-asset reference, including delayed-close execution.
   ref=replay(base.reindex(ix),a['cl'],a['rf'],a['div'],mode,a['op'],extra,.125)[0];np.testing.assert_allclose(nv[0],ref,rtol=1e-10)
   dd=nv/np.maximum.accumulate(np.column_stack([np.ones(len(names)),nv]),axis=1)[:,1:]-1
   for k,name in enumerate(names):
    metrics.append(dict(period=period,start=str(ix[0].date()),end=str(ix[-1].date()),mode=mode,extra=extra,name=name,final=nv[k,-1],total_return=nv[k,-1]-1,cagr=nv[k,-1]**(365.25/(ix[-1]-ix[0]).days)-1,mdd=dd[k].min(),trades=tr[k]))
   if mode=='same_close_reference' and extra==0:
    navs[period]=nv
    for year in sorted(set(ix.year)):
     ids=np.flatnonzero(ix.year==year);prior=nv[:,ids[0]-1] if ids[0] else np.ones(len(names))
     for k,name in enumerate(names):annual.append(dict(period=period,year=int(year),name=name,return_=nv[k,ids[-1]]/prior[k]-1))
    pd.DataFrame(nv.T,index=ix,columns=names).to_csv(OUT/f'nav_{period}.csv.gz',compression='gzip')
f=pd.DataFrame(metrics);y=pd.DataFrame(annual);f.to_csv(OUT/'metrics.csv',index=False);y.to_csv(OUT/'annual.csv',index=False);pd.DataFrame(meta).to_csv(OUT/'candidates.csv',index=False)
# Equal-weight annualised log growth across actual history and pre-BITO history;
# avoid counting the overlapping 2021+ period twice in the score.
long=np.load(R/'data/validation/v2/inputs_long_synthetic.npz');li=pd.DatetimeIndex(long['dates']);cut=np.flatnonzero(li<pd.Timestamp('2021-10-20'))[-1]
pre=navs['long_synthetic'][:,cut];years=(li[cut]-li[0]).days/365.25
actual=f.query('period=="actual_BITO" and mode=="same_close_reference" and extra==0').set_index('name').reindex(names)
score=.5*np.log(pre)/years+.5*np.log1p(actual.cagr.to_numpy())
ranks=pd.DataFrame({'name':names,'balanced_log_score':score,'pre_BITO_multiple':pre,'actual_multiple':actual.final.to_numpy()}).sort_values('balanced_log_score',ascending=False);ranks.to_csv(OUT/'ranking.csv',index=False)
print('CANDIDATES',len(names),'PARITY PASSED');print('RECENT TOP');print(actual.sort_values('final',ascending=False).head(10)[['final','cagr','mdd']].to_string());print('BALANCED TOP');print(ranks.head(12).to_string(index=False));print('NO LEVER TOP');print(actual.loc[[n for n in names if n.startswith('L0_')]].sort_values('final',ascending=False).head(5)[['final','cagr','mdd']].to_string())
