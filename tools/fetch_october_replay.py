"""Read public market feed into an isolated research folder, never production."""
from pathlib import Path
import sys,shutil,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from market_data import fetch

def main():
    out=ROOT/'release/model-research/studies/october-replay';stage=out/'feed-root';(stage/'data').mkdir(parents=True,exist_ok=True)
    for name in ['equities.csv','btc.csv']:shutil.copy2(ROOT/'data'/name,stage/'data'/name)
    p,btc,raw=fetch('2026-11-04',root=stage)
    p.to_csv(out/'equities_verified.csv');btc.to_csv(out/'btc_verified.csv',header=['close'])
    (out/'raw_market_summary.json').write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Verified public feed',p.index[-1].date(),'BTC',btc.index[-1].date(),'rows',len(p))

if __name__=='__main__':main()
