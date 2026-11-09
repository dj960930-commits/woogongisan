"""Read-only structural diagnostics, not another strategy optimization."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from models.registry import load_model

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'release/model-research/studies/methodology-final-audit'

def main():
    p=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True)
    b=pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    model=load_model('woogong-v2.1'); t,ind=model.evaluate(p,b)
    risk=p[['TQQQ','SOXL']].copy(); risk['BITO']=b.shift(1).reindex(p.index)
    log=np.log(risk); daily=log.diff()
    score=sum((log-log.shift(n))/(daily.rolling(n,min_periods=n).std(ddof=1)*np.sqrt(n)) for n in [42,252])/2
    ex=np.exp(score.sub(score.max(axis=1),axis=0)); raw=ex.div(ex.sum(axis=1),axis=0)
    mask=ind.state.eq(0)&(ind.index>='2021-10-20')&(ind.index<='2026-10-20')
    ix=ind.index[mask]; a=t.loc[ix]; s=score.reindex(ix); r=raw.reindex(ix)
    delta=a.BITO-r.BITO; day=delta.idxmax()
    active=ind.defense_entry_active & (ind.index>='2021-10-20') & (ind.index<='2026-10-20')
    sources=['models/allocation_v21.py','models/core_v1.py','models/overlays.py',
             'models/defense_v2.py','models/performance.py','models/profiles/woogong-v2.1.json',
             'data/equities.csv','data/btc.csv']
    result=dict(model_fingerprint=model.fingerprint,start='2021-10-20',end='2026-10-20',
        basis='Signal target allocations, not verified broker holdings. No production changes.',
        attack_days=len(ix),btc_target_quantiles={str(k):float(v) for k,v in a.BITO.quantile([0,.25,.5,.75,.95,1]).items()},
        btc_max_date=str(a.BITO.idxmax().date()),btc_over40_days=int(a.BITO.gt(.4).sum()),
        btc_over70_days=int(a.BITO.gt(.7).sum()),btc_negative_score_days=int(s.BITO.lt(0).sum()),
        all_attack_scores_negative_days=int(s.lt(0).all(axis=1).sum()),
        soxl_cap_increases_btc_days=int(delta.gt(1e-8).sum()),max_btc_increase_pp=float(delta.max()*100),
        redistribution_example=dict(date=str(day.date()),raw_weights=r.loc[day].to_dict(),
                                    final_target=a.loc[day].to_dict(),scores=s.loc[day].to_dict()),
        zero_attack_cash_days=int(a.CASH.lt(1e-10).sum()),
        defense_short_redirect_days=int(active.sum()),
        forced_brk_days=int((ind.state.eq(1)&(ind.index>='2021-10-20')&(ind.index<='2026-10-20')).sum()),
        hypothetical_drift=dict(initial_tqqq=.7,initial_cash=.3,tqqq_price_return=.1,
                               after_weight=.7*1.1/(.7*1.1+.3),band=.125),
        source_hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in sources})
    OUT.mkdir(exist_ok=True)
    (OUT/'diagnostics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    detail=a.copy(); detail['BTC_score']=s.BITO; detail['BTC_raw_weight']=r.BITO
    detail['BTC_increase_from_SOXL_cap']=delta
    detail.to_csv(OUT/'attack_allocation_audit.csv')
    print(json.dumps({k:result[k] for k in ['attack_days','btc_target_quantiles','soxl_cap_increases_btc_days','max_btc_increase_pp']},ensure_ascii=False))

if __name__=='__main__':
    main()
