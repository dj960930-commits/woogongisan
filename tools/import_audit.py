"""Developer-only import of audited historical fixtures; never needed at runtime."""
import sys
from pathlib import Path
import json
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from models.registry import load_model

def main():
    audit = ROOT / 'release/model-research/early-research/all_versions_validation_20261026'
    z = np.load(audit / 'targets.npz')
    model = load_model('woogong-1.3-d')
    ref = pd.DataFrame(z['targets'][list(z['names']).index('V1.3-D')],
                       index=pd.DatetimeIndex(z['dates']), columns=['TQQQ','BRK.B','GLD','CASH','SOXL','BITO'])
    p = pd.read_csv(ROOT/'data/equities.csv', index_col=0, parse_dates=True)
    bito = pd.read_csv(ROOT.parent/'bito_bitx_cases_20261023/inputs/BITO_prices.csv',index_col=0,parse_dates=True).adjclose
    p['BITO'] = bito.reindex(p.index)
    p.to_csv(ROOT/'data/equities.csv')
    btc = pd.read_csv(ROOT/'data/btc.csv', parse_dates=['date_utc']).set_index('date_utc').close
    actual, _ = model.evaluate(p, btc)
    assert np.max(abs(actual.loc[ref.index].to_numpy() - ref.to_numpy())) < 1e-12
    ref.to_csv(ROOT/'data/reference_targets_1.3-d.csv')
    metrics = pd.read_csv(audit/'all_execution_metrics.csv')
    rows = metrics[(metrics.model == 'V1.3-D') & (metrics.period == 'actual_BITO')]
    row = rows[(rows['mode'] == 'next_open') & (rows.slippage == 0) & (rows.delay == 1) & (rows['fill'] == 1)].iloc[0]
    ledger = pd.read_csv(audit/'ledger_actual_BITO_next_open_V1.3-D.csv', index_col=0, parse_dates=True)
    nav = ledger.nav
    dd = nav/nav.cummax()-1
    history = pd.read_csv(ROOT.parent/'final_model_research_20261026/all_history_results.csv')
    synthetic = history[(history.model=='D25') & (history.period=='hybrid_drag-0.1') & (history['mode']=='next_close') & (history.slippage==0)].iloc[0]
    evidence = {**model.metadata(), 'kind':'observed_BITO_backtest', 'data_end':str(nav.index[-1].date()),
                'label':'V1.3-D · 실제 BITO · 다음 시가 · 편도0.1% · 달러 현금 대용수익 · 세전',
                'cagr':float(row.cagr), 'mdd':float(row.mdd), 'calmar':float(row.calmar),
                'synthetic_cagr':float(synthetic.cagr),
                'synthetic_label':'2015~2026 혼합 대용 · BTC 대용 연 로그 -10% 드래그 · 다음 종가 · 상장 전 BITO 실적 아님',
                'scenarios':rows.to_dict(orient='records'),
                'curve':[dict(date=str(nav.index[i].date()),nav=float(nav.iloc[i]),drawdown=float(dd.iloc[i])) for i in list(range(0,len(nav)-1,5))+[len(nav)-1]]}
    (ROOT/'models/evidence/woogong-1.3-d.backtest.json').write_text(json.dumps(evidence,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    oldpath=ROOT/'models/evidence/woogong-v1.backtest.json'
    old=json.loads(oldpath.read_text(encoding='utf-8'))
    old.update(load_model('woogong-v1').metadata())
    oldpath.write_text(json.dumps(old,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print('Audited V1.3-D full history matches; fixtures imported:',len(ref))

if __name__=='__main__':main()
