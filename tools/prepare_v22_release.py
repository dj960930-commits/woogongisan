"""Register V2.2 evidence and prepare dated, local display assets."""
from pathlib import Path
from datetime import datetime, timezone
import json
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from comparison import build as comparison
from model import activate
from models.performance import replay
from models.registry import load_model
from pipeline import latest_backtest, snapshot, write, session
from market_data import fetch, CONTRACT_ID, BASIS
from price_outlook import build as outlook
from tools.build_signal_bundle import build as bundle
from tools.research_dual_sleeve import metrics


def live_documents(model):
    completed = session(datetime.now(timezone.utc))
    if completed is None:
        raise ValueError('No completed session available for online publication')
    expected = completed[0]
    prices, btc, raw = fetch(expected, ROOT)
    data, targets = snapshot(prices, btc, 'live', raw, model)
    if data['market_date'] != str(expected.date()):
        raise ValueError('Online publication is behind the completed session')
    extension = latest_backtest(prices, targets, model, return_daily=True)
    benchmark = json.loads((ROOT/'runtime/benchmark-prices.json').read_text(encoding='utf-8'))
    data['performance'] = comparison(extension.pop('_daily_nav'), benchmark)
    data['price_outlook'] = outlook(prices, raw)
    data.update(data_contract_id=CONTRACT_ID, price_basis=BASIS,
                data_sources={'equities': 'Yahoo Finance', 'btc': 'Bitstamp'})
    status = dict(**model.metadata(), state='ready', market_date=data['market_date'],
                  data_contract_id=CONTRACT_ID, data_sources=data['data_sources'],
                  message='확정 종가 계산 완료', updated_at=datetime.now(timezone.utc).isoformat())
    return {'snapshot': data, 'extended_backtest': extension, 'status': status}


def main():
    model = load_model('woogong-v2.2')
    prices = pd.read_csv(ROOT/'data/equities.csv', index_col=0, parse_dates=True)
    btc = pd.read_csv(ROOT/'data/btc.csv', parse_dates=['date_utc']).set_index('date_utc').close
    targets, _ = model.evaluate(prices, btc)
    with np.load(ROOT/'data/validation/v2/inputs_actual_BITO.npz') as data:
        dates = pd.DatetimeIndex(data['dates'])
        scenarios = []
        for mode in ('next_open', 'same_close_reference', 'next_close'):
            for extra in (0., .003):
                nav, trades, *_ = replay(targets.reindex(dates).to_numpy(), data['cl'], data['rf'],
                                          data['div'], mode, data['op'], extra, model.band)
                scenarios.append(dict(period='actual_BITO', mode=mode, extra=extra, **metrics(nav, dates, trades)))
                if mode == 'next_open' and extra == 0:
                    dd = nav / np.maximum.accumulate(np.r_[1., nav])[1:] - 1
                    curve = [dict(date=str(dates[j].date()), nav=float(nav[j]), drawdown=float(dd[j]))
                             for j in sorted(set(range(0, len(dates), 5)) | {len(dates)-1})]
    primary = scenarios[0]
    expected = pd.read_csv(ROOT/'release/model-research/studies/bito-weighted-reduction/metrics.csv')
    expected = expected.query("name=='50_fixed' and period=='actual_BITO' and mode=='next_open' and extra==0").iloc[0]
    np.testing.assert_allclose([primary[k] for k in ('cagr','mdd','final')], expected[['cagr','mdd','final']].astype(float), atol=1e-12, rtol=0)
    long = pd.read_csv(ROOT/'release/model-research/studies/bito-weighted-reduction/metrics.csv')
    long = long.query("name=='50_fixed' and period=='long2010_-0.053388' and mode=='same_close_reference' and extra==0").iloc[0]
    evidence = dict(**model.metadata(), **primary, scenarios=scenarios, data_start=str(dates[0].date()),
                    data_end=str(dates[-1].date()), kind='observed_BITO_backtest', curve=curve,
                    execution='next_open',
                    validation=dict(actual_after_hours_fills_verified=False,
                                    live_broker_fills_verified=False, independent_oos=False),
                    label='실제 BITO 가격 · 다음 거래일 시가 가정 · 편도 0.1% · USD 세전',
                    synthetic_cagr=float(long.cagr),
                    synthetic_label='2010년 이후 BTC 대용 · 로그 추적비용 연 5.34% · 동일 종가 체결 가정')
    write(ROOT/f'models/evidence/{model.id}.backtest.json', evidence)

    # The dated preview uses the already verified archived feed.
    feed = ROOT/'runtime/v21-feed'
    day = '2026-10-30'
    p = pd.read_csv(feed/'verified-prices.csv', index_col=0, parse_dates=True).loc[:day]
    b = pd.read_csv(feed/'verified-btc.csv', index_col=0, parse_dates=True).close.loc[:day]
    seed = ROOT/'data/offline'
    raw = json.loads((seed/'snapshot.json').read_text(encoding='utf-8'))['raw_close']
    benchmark = json.loads((feed/'runtime/benchmark-prices.json').read_text(encoding='utf-8'))
    benchmark['market_date'] = day
    benchmark['prices'] = {k:{d:v for d,v in x.items() if d<=day} for k,x in benchmark['prices'].items()}
    offline, weights = snapshot(p,b,'historical_demo',raw,model)
    assert offline['market_date'] == day
    extension = latest_backtest(p,weights,model,return_daily=True)
    offline['performance'] = comparison(extension.pop('_daily_nav'),benchmark)
    offline['price_outlook'] = outlook(p,raw)
    status = dict(**model.metadata(),state='demo',market_date=day,
                  message=f'{day} 기준 {model.version} 오프라인 미리보기')
    # Obtain current online data before activation changes any displayed model.
    online = live_documents(model)
    for name,value in [('snapshot',offline),('extended_backtest',extension),('status',status)]:
        write(seed/f'{name}.json',value)
    activate(model.id)
    site = ROOT/'site'
    for name,value in online.items():
        write(site/f'{name}.json',value)
    write(site/'bundle.json',bundle(site))
    print(model.version, model.fingerprint, day, primary['cagr'], primary['mdd'])


if __name__ == '__main__':
    main()
