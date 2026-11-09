import numpy as np
import pandas as pd
from tools import research_methodology_full as r

original = r.setup
diagnostics = []
def setup(p,b,ix,close,rf,actual):
    base,_=r.c.load_model('woogong-v2.2').evaluate(p,b)
    base=base.reindex(ix)
    spot=b.shift(1).reindex(p.index)
    cash=np.log1p(p.cash_return.fillna(0))
    excess={n:(spot/spot.shift(n)-1)-np.expm1(cash.rolling(n).sum()) for n in (63,126,189,252)}
    out={}
    for cap in (.6,.5):
        for weights in (None,(4,3,2,1),(12,4,2,1)):
            t=base.copy()
            weight=t.BITO.clip(upper=cap)
            if weights:
                score=sum(w*x for w,x in zip(weights,excess.values())).reindex(ix)
                short=excess[63].reindex(ix)
                weight*=np.select([score.le(0),score.gt(0)&short.le(0)],[.5,.75],default=1.)
            t.CASH+=t.BITO-weight
            t.BITO=weight
            name=str(round(cap*100))+('_'+''.join(map(str,weights)) if weights else '_fixed')
            out[name]=t
            if actual:
                shock=spot.reindex(ix).pct_change(fill_method=None).le(-.05)
                diagnostics.append(dict(name=name,max_bito=weight.max(),above40=weight.gt(.4).sum(),reduced=weight.lt(base.BITO-1e-10).sum(),mean_target_before_btc_down5=weight.shift(1)[shock].mean()))
    return out

if __name__=='__main__':
    r.setup=setup
    r.OUT=r.OUT.parent/'bito-weighted-reduction'
    r.main()
    pd.DataFrame(diagnostics).to_csv(r.OUT/'diagnostics.csv',index=False)
    m=pd.read_csv(r.OUT/'metrics.csv')
    for period,mode in [('actual_BITO','next_open'),('long2010_-0.053388','same_close_reference')]:
        print(m[(m.period==period)&(m['mode']==mode)][['name','extra','cagr','mdd','calmar','worst_day']].round(5).to_string(index=False))
    print(pd.DataFrame(diagnostics).to_string(index=False))
