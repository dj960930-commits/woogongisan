from tools import research_dual_sleeve as c
import numpy as np
import pandas as pd

def build(p,b):
    t,i=c.load_model('woogong-v2.1').evaluate(p,b)
    t['QQQ']=0.
    t=t[c.ASSETS]
    ix=t.index
    attack=i.state.eq(0)
    x=p[['TQQQ','SOXL']].copy()
    x['BITO']=b.shift(1).reindex(x.index)
    l=np.log(x.where(x>0))
    s=sum((l-l.shift(n))/(l.diff().rolling(n).std()*np.sqrt(n)) for n in [42,252])/2
    e=np.exp(s.sub(s.max(axis=1),axis=0))
    w=e.div(e.sum(axis=1),axis=0)
    w.loc[~s.notna().all(axis=1)]=[.3,.2,.5]
    w=w.reindex(ix)
    ready=p.TQQQ.reindex(ix).shift(126).notna() & p.SOXL.reindex(ix).shift(126).notna() & b.reindex(ix).shift(127).notna()
    w.loc[~ready]=[1,0,0]
    out={'v21':t}
    def add(name, weights):
        a=t.copy()
        a.loc[attack,w.columns]=weights.loc[attack]
        a.loc[attack,'CASH']=1-weights.loc[attack].sum(axis=1)
        np.testing.assert_allclose(a.sum(axis=1),1)
        assert a.min().min()>-1e-10
        out[name]=a
    for name in ['A01','A02']:
        q=w.copy()
        q.SOXL=w.SOXL.clip(upper=.4)
        if name=='A02':
            q.TQQQ+=w.SOXL-q.SOXL
        q[['TQQQ','SOXL']]=q[['TQQQ','SOXL']].mul((.7/(q.TQQQ+q.SOXL)).clip(upper=1),axis=0)
        add(name,q)
        if name=='A01':
            anchor=q.copy()
    for j,cap in enumerate([0,.2,.3,.4,.6],1):
        q=anchor.copy(); q.BITO=q.BITO.clip(upper=cap); add(f'B{j:02}',q)
    spot=b.shift(1).reindex(ix)
    ma100=b.rolling(100).mean().shift(1).reindex(ix)
    below=(spot<ma100).rolling(3).sum().eq(3)
    above=(spot>ma100).rolling(3).sum().eq(3)
    off=pd.Series(np.select([below,above],[1.,0.],default=np.nan),index=ix).ffill().fillna(0).eq(1)
    for name,mask,factor in [('C01',s.BITO.reindex(ix).le(0),0),('C02',spot.lt(b.rolling(200).mean().shift(1).reindex(ix)),0),('C03',off,0),('C04',s.BITO.reindex(ix).le(0),.5)]:
        q=anchor.copy(); q.loc[mask,'BITO']*=factor; add(name,q)
    return out,{'scope':'A01/A02 B01-B05 C01-C04'}

if __name__=='__main__':
    c.OUT=c.ROOT/'release/model-research/studies/methodology-stage1'
    c.build_targets=build
    c.main()
    p=pd.read_csv(c.ROOT/'data/equities.csv',index_col=0,parse_dates=True)
    b=pd.read_csv(c.ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    a=np.load(c.ROOT/'data/validation/v2/inputs_actual_BITO.npz')
    ix=pd.DatetimeIndex(a['dates'])
    rows=[]
    for name,t in build(p,b)[0].items():
        for extra in [0.,.003]:
            nav,tr,*_=c.canonical_replay(t.reindex(ix).to_numpy()[:,:6],a['cl'],a['rf'],a['div'],'next_open',a['op'],extra,.125)
            rows.append(dict(name=name,extra=extra,**c.metrics(nav,ix,tr)))
    result=pd.DataFrame(rows)
    result.to_csv(c.OUT/'actual_next_open.csv',index=False)
    print(result[result.extra.eq(0)].round(4).to_string(index=False))

