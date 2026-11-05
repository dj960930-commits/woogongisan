"""Make dated offline seeds and a verified live v2 publication, separately."""
from pathlib import Path
from datetime import datetime,timezone
import sys,json
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from models.registry import load_model
from pipeline import snapshot,latest_backtest,write
from comparison import build as comparison
from price_outlook import build as outlook
from model import activate
from build_signal_bundle import build,archive

def derive(p,b,raw,bench,model,mode):
    data,t=snapshot(p,b,mode,raw,model)
    ext=latest_backtest(p,t,model,return_daily=True);nav=ext.pop('_daily_nav')
    data['performance']=comparison(nav,bench)
    data['price_outlook']=outlook(p,raw)
    data.update(data_contract_id='audited-mixed-close-v1',data_sources={'equities':'Yahoo Finance','btc':'Bitstamp'},
                price_basis={'QQQ':'close','TQQQ':'close','BRK.B':'close','GLD':'close','SOXL':'adjclose','BITO':'adjclose'})
    return data,ext

def main():
    stage=ROOT/'runtime/v2-feed';m=load_model('woogong-v2')
    p=pd.read_csv(stage/'verified-prices.csv',index_col=0,parse_dates=True)
    b=pd.read_csv(stage/'verified-btc.csv',index_col=0,parse_dates=True).close
    raw=json.loads((stage/'raw.json').read_text(encoding='utf-8'))
    bench=json.loads((stage/'runtime/benchmark-prices.json').read_text(encoding='utf-8'))
    seed=ROOT/'data/offline';day='2026-10-30'
    seedraw=json.loads((seed/'snapshot.json').read_text(encoding='utf-8'))['raw_close']
    seedbench={**bench,'market_date':day,'prices':{s:{d:v for d,v in prices.items() if d<=day} for s,prices in bench['prices'].items()}}
    offline,seedext=derive(p.loc[:day],b.loc[:day],seedraw,seedbench,m,'historical_demo')
    assert offline['market_date']==day
    write(seed/'snapshot.json',offline);write(seed/'extended_backtest.json',seedext)
    write(seed/'status.json',{**m.metadata(),'state':'demo','market_date':day,'message':day+' 기준 v2 오프라인 미리보기. 최신 매매 신호가 아닙니다.'})
    # Activation checks new evidence, then prepare() copies matching offline seed.
    activate(m.id)
    live,ext=derive(p,b,raw,bench,m,'live')
    assert live['market_date']=='2026-11-04'
    site=ROOT/'site'
    write(site/'snapshot.json',live);write(site/'extended_backtest.json',ext)
    write(site/'model.json',m.metadata())
    write(site/'status.json',{**m.metadata(),'state':'ready','market_date':live['market_date'],
        'message':'v2 · 원본 가격기준 대조 · 확정 종가 계산 완료','data_contract_id':'audited-mixed-close-v1',
        'data_sources':live['data_sources'],'updated_at':datetime.now(timezone.utc).isoformat()})
    proof=json.loads((stage/'runtime/market-data-validation.json').read_text(encoding='utf-8'))
    write(site/'data-validation.json',proof)
    bundle=build(site);archive(site,bundle);write(site/'bundle.json',bundle)
    print('Prepared v2',m.fingerprint,'offline',day,'live',live['market_date'],'target',live['target'])

if __name__=='__main__':main()
