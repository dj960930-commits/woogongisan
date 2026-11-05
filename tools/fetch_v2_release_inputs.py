"""Isolated public feed check. Never alters frozen data or broker credentials."""
from pathlib import Path
import shutil,sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from market_data import fetch

def main():
    stage=ROOT/'runtime/v2-feed';(stage/'data').mkdir(parents=True,exist_ok=True)
    for name in ['equities.csv','btc.csv']:shutil.copy2(ROOT/'data'/name,stage/'data'/name)
    p,b,raw=fetch('2026-11-04',stage)
    p.to_csv(stage/'verified-prices.csv');b.to_csv(stage/'verified-btc.csv',header=['close'])
    (stage/'raw.json').write_text(json.dumps(raw),encoding='utf-8')
    print('Verified prices',p.index[-1],'BTC',b.index[-1])

if __name__=='__main__':main()
