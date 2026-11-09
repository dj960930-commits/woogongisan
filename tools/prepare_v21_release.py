"""Prepare V2.1 with an Oct30 offline seed and independently refreshed live inputs."""
from pathlib import Path
from datetime import datetime, timezone
import json
import shutil
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from market_data import fetch
from models.registry import load_model
from pipeline import session,write
from tools.prepare_v2_release import derive
from tools.build_signal_bundle import build,archive
from model import activate


def main():
    model=load_model('woogong-v2.1')
    evidence=json.loads((ROOT/f'models/evidence/{model.id}.backtest.json').read_text(encoding='utf-8'))
    if evidence['model_fingerprint']!=model.fingerprint:
        raise ValueError('V2.1 evidence mismatch')
    stage=ROOT/'runtime/v21-feed'
    (stage/'data').mkdir(parents=True,exist_ok=True)
    for name in ['equities.csv','btc.csv']:
        shutil.copy2(ROOT/'data'/name,stage/'data'/name)
    completed=session(datetime.now(timezone.utc))
    if completed is None:
        raise ValueError('No completed market session')
    expected,_=completed
    prices,btc,raw=fetch(expected,stage)
    prices.to_csv(stage/'verified-prices.csv')
    btc.to_csv(stage/'verified-btc.csv',header=['close'])
    (stage/'raw.json').write_text(json.dumps(raw),encoding='utf-8')
    benchmark=json.loads((stage/'runtime/benchmark-prices.json').read_text(encoding='utf-8'))
    day='2026-10-30'
    seed=ROOT/'data/offline'
    seedraw=json.loads((seed/'snapshot.json').read_text(encoding='utf-8'))['raw_close']
    seedbench={**benchmark,'market_date':day,
               'prices':{symbol:{d:v for d,v in values.items() if d<=day}
                         for symbol,values in benchmark['prices'].items()}}
    offline,seedext=derive(prices.loc[:day],btc.loc[:day],seedraw,seedbench,model,'historical_demo')
    live,extension=derive(prices,btc,raw,benchmark,model,'live')
    if offline['market_date']!=day or live['market_date']!=str(expected.date()):
        raise ValueError('V2.1 release date mismatch')
    write(seed/'snapshot.json',offline)
    write(seed/'extended_backtest.json',seedext)
    write(seed/'status.json',{**model.metadata(),'state':'demo','market_date':day,
                             'message':day+' 기준 V2.1 오프라인 미리보기. 최신 매매 신호가 아닙니다.'})
    activate(model.id)
    site=ROOT/'site'
    write(site/'snapshot.json',live);write(site/'extended_backtest.json',extension)
    write(site/'model.json',model.metadata())
    write(site/'status.json',{**model.metadata(),'state':'ready','market_date':live['market_date'],
          'message':'V2.1 · 확정 종가 계산 완료','data_contract_id':'audited-mixed-close-v1',
          'data_sources':live['data_sources'],'updated_at':datetime.now(timezone.utc).isoformat()})
    write(site/'data-validation.json',json.loads((stage/'runtime/market-data-validation.json').read_text(encoding='utf-8')))
    bundle=build(site);archive(site,bundle);write(site/'bundle.json',bundle)
    print('V2.1 ready',model.fingerprint,'offline',day,'live',live['market_date'],'target',live['target'])


if __name__=='__main__':
    main()
