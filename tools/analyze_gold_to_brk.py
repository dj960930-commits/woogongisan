"""Conditional event study; not a new full-strategy backtest."""
from pathlib import Path
import sys,json
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from engine import evaluate


def main():
    p=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True)
    btc=pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    target,ind=evaluate(p,btc)
    source=ROOT.parent/'bito_bitx_cases_20261023/inputs'
    prices={s:pd.read_csv(source/(file+'_prices.csv'),index_col=0,parse_dates=True)
            for s,file in [('BRK.B','BRK-B'),('GLD','GLD')]}
    rows=[];unfinished=[]
    gold=np.isclose(target.GLD,1);brk=np.isclose(target['BRK.B'],1)
    for i in range(1,len(target)):
        if target.index[i]<pd.Timestamp("2020-01-02") or not(gold[i-1] and brk[i]):continue
        j=i+1
        while j<len(target) and brk[j]:j+=1
        # Exit at next open after first signal no longer targeting 100% BRK.
        if j+1>=len(target):unfinished.append(str(target.index[i].date()));continue
        entry,exit=target.index[i+1],target.index[j+1]
        values={s:float(frame.loc[exit,'open']/frame.loc[entry,'open']*(1-.001)/(1+.001)-1) for s,frame in prices.items()}
        if not all(np.isfinite(v) for v in values.values()):raise ValueError('missing execution price')
        row=dict(signal=str(target.index[i].date()),entry=str(entry.date()),exit=str(exit.date()),sessions=j-i,
                 brk_return=values['BRK.B'],gold_return=values['GLD'],excess=values['BRK.B']-values['GLD'],state=int(ind.iloc[i].state))
        for horizon in [5,21,63]:
            k=i+1+horizon
            if k<len(target):
                end=target.index[k]
                row[f'brk_{horizon}']=float(prices['BRK.B'].loc[end,'open']/prices['BRK.B'].loc[entry,'open']*(1-.001)/(1+.001)-1)
        rows.append(row)
    frame=pd.DataFrame(rows)
    result={}
    for name,start in [('actual_BITO','2021-10-20'),('since_2020','2020-01-02')]:
        a=frame[frame.signal>=start]
        result[name]=dict(count=len(a),wins=int((a.brk_return>0).sum()),win_rate=float((a.brk_return>0).mean()),
            beat_gold=int((a.excess>0).sum()),beat_gold_rate=float((a.excess>0).mean()),mean=float(a.brk_return.mean()),median=float(a.brk_return.median()),
            best=float(a.brk_return.max()),worst=float(a.brk_return.min()),mean_sessions=float(a.sessions.mean()),rows=a.to_dict('records'))
    directory=ROOT/'release/gold-to-brk-study';directory.mkdir(parents=True,exist_ok=True)
    frame.to_csv(directory/'events.csv',index=False)
    result['unfinished']=unfinished;result['data_end']=str(p.index[-1].date())
    (directory/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True,indent=2))


if __name__=='__main__':main()
