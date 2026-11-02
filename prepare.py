"""Generate selected model's historical app assets without external research files."""
from pathlib import Path
import json
import shutil
import pandas as pd
from models.registry import load_model
from pipeline import snapshot, write
ROOT = Path(__file__).parent

def main():
    model = load_model()
    evidence = json.loads((ROOT/'models/evidence'/f'{model.id}.backtest.json').read_text(encoding='utf-8'))
    if evidence['model_fingerprint'] != model.fingerprint:
        raise ValueError('모델이 검증 자료와 다릅니다. 새 버전의 기준 원장과 회귀 검증을 먼저 등록하세요.')
    p = pd.read_csv(ROOT/'data/equities.csv', index_col=0, parse_dates=True)
    btc = pd.read_csv(ROOT/'data/btc.csv', parse_dates=['date_utc']).set_index('date_utc').close
    data, _ = snapshot(p, btc, 'historical_demo', model=model)
    site = ROOT/'site'
    write(site/'backtest.json', evidence)
    write(site/'snapshot.json', data)
    write(site/'model.json', model.metadata())
    write(site/'status.json', {**model.metadata(), 'state':'demo', 'market_date':data['market_date'], 'message':data['market_date']+' 기준 과거 검증 자료. 현재 매매 신호가 아닙니다.'})
    ext = site/'extended_backtest.json'
    if ext.exists() and json.loads(ext.read_text(encoding='utf-8')).get('model_fingerprint') != model.fingerprint:
        ext.unlink()
    assets = ROOT/'android/app/src/main/assets'
    assets.mkdir(parents=True, exist_ok=True)
    for name in ['snapshot','status','backtest','model']:
        shutil.copy2(site/f'{name}.json', assets/f'{name}.json')
    # Release seeds are independently dated; never advance the frozen research CSVs.
    seed = ROOT/'data/offline'
    if (seed/'snapshot.json').exists():
        offline = json.loads((seed/'snapshot.json').read_text(encoding='utf-8'))
        if offline.get('model_fingerprint') == model.fingerprint:
            for name in ['snapshot','status','extended_backtest']:
                source = seed/f'{name}.json'
                if source.exists():
                    value = json.loads(source.read_text(encoding='utf-8'))
                    if value.get('model_fingerprint') != model.fingerprint:
                        raise ValueError('Offline seed model mismatch')
                    shutil.copy2(source, assets/source.name)
    print(model.version, 'historical site and Android assets prepared')

if __name__=='__main__':main()
