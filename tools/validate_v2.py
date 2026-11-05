"""Reproduce v2 targets and execution evidence using repo-local frozen inputs."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from models.registry import load_model
from models.performance import replay

def main():
    m=load_model('woogong-v2');folder=ROOT/'data/validation/v2'
    p=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True)
    b=pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    target,ind=m.evaluate(p,b)
    ref=pd.read_csv(folder/'reference_targets.csv.gz',index_col=0,parse_dates=True)
    np.testing.assert_allclose(target,ref,atol=1e-12,rtol=0)
    records=[];main_nav=None;main_ix=None
    for period in ['actual_BITO','long_synthetic']:
        a=np.load(folder/f'inputs_{period}.npz');ix=pd.DatetimeIndex(a['dates'])
        modes=['same_close_reference','next_close']+(['next_open'] if period=='actual_BITO' else [])
        for mode in modes:
            for slip in [0.,.003]:
                nav,tr,_,_=replay(target.reindex(ix),a['cl'],a['rf'],a['div'],mode,a['op'],slip,m.band)
                dd=nav/np.maximum.accumulate(np.r_[1.,nav])[1:]-1
                cg=float(nav[-1]**(365.25/(ix[-1]-ix[0]).days)-1)
                records.append(dict(period=period,model=m.id,mode=mode,slippage=slip,delay=0 if mode=='same_close_reference' else 1,fill=1.,cash_zero=False,cagr=cg,mdd=float(dd.min()),calmar=cg/-float(dd.min()),final=float(nav[-1]),trade_days=int(tr.sum())))
                if period=='actual_BITO' and mode=='same_close_reference' and slip==0:main_nav=nav;main_ix=ix
    primary=next(r for r in records if r['period']=='actual_BITO' and r['mode']=='same_close_reference' and r['slippage']==0)
    synth=next(r for r in records if r['period']=='long_synthetic' and r['mode']=='same_close_reference' and r['slippage']==0)
    draw=main_nav/np.maximum.accumulate(np.r_[1.,main_nav])[1:]-1
    evidence={**m.metadata(),'kind':'observed_BITO_same_close_reference','data_end':str(main_ix[-1].date()),
        'execution':'same_close_reference','label':'v2 실제 BITO 가격 · 확정 종가 후 동일 가격 체결 가정 · 편도0.1% · 현금 대용수익 · 세전',
        'cagr':primary['cagr'],'mdd':primary['mdd'],'calmar':primary['calmar'],
        'synthetic_cagr':synth['cagr'],'synthetic_label':'2015~2026 BTC 대용 · 당일 종가 가격 가정 · 미상장 BITO 실제 실적 아님',
        'scenarios':records,'curve':[dict(date=str(main_ix[i].date()),nav=float(main_nav[i]),drawdown=float(draw[i])) for i in list(range(0,len(main_ix)-1,5))+[len(main_ix)-1]],
        'validation':dict(target_rows=len(target),target_reference='data/validation/v2/reference_targets.csv.gz',
            independent_oos=False,actual_after_hours_fills_verified=False,
            note='장기 규칙 선택은 2026년 사례를 본 뒤의 사후 연구입니다. 실제 체결·미래 성과 검증이 아닙니다.',
            source_hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [folder/'reference_targets.csv.gz',folder/'inputs_actual_BITO.npz',folder/'inputs_long_synthetic.npz']})}
    out=ROOT/'models/evidence/woogong-v2.backtest.json'
    out.write_text(json.dumps(evidence,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print('PASS',len(target),'target rows; evidence',m.fingerprint,'CAGR',primary['cagr'],'MDD',primary['mdd'])

if __name__=='__main__':main()
