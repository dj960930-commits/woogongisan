"""Historical return scenarios; not a validated price-prediction trading model."""
from datetime import datetime,timezone
import numpy as np
import pandas as pd
import pandas_market_calendars as calendars

VERSION='historical-return-scenarios-v1'
HORIZONS=(5,21,63)


def distribution(series,horizon):
    values=series.tail(1261)
    returns=np.log(values/values.shift(horizon)).dropna()
    if len(returns)<252 or not np.isfinite(returns).all():
        raise ValueError('insufficient scenario history')
    return np.quantile(returns,[.1,.5,.9])


def build(prices,raw):
    end=prices.index[-1]
    future=calendars.get_calendar('NYSE').schedule(start_date=(end+pd.Timedelta(days=1)).date(),end_date=(end+pd.Timedelta(days=130)).date()).index
    assets=[]
    for symbol in ('TQQQ','BRK.B','GLD'):
        series=prices[symbol].astype(float)
        series=series.loc[series.first_valid_index():]
        if series.isna().any() or not np.isfinite(series).all() or (series<=0).any():
            raise ValueError('invalid scenario prices')
        anchor=float(raw[symbol])
        if not np.isfinite(anchor) or anchor<=0:raise ValueError('invalid current close')
        windows=[]
        for h in HORIZONS:
            q=distribution(series,h)
            # Fixed rolling origins, each fitted solely on then-available history.
            errors=[];baseline=[];covered=[]
            for i in range(max(400,len(series)-504),len(series)-h,21):
                past=series.iloc[:i+1];actual=float(series.iloc[i+h]/series.iloc[i]-1)
                try:old=distribution(past,h)
                except ValueError:continue
                estimates=np.expm1(old)
                errors.append(abs(estimates[1]-actual));baseline.append(abs(actual))
                covered.append(bool(estimates[0]<=actual<=estimates[2]))
            windows.append(dict(sessions=h,target_date=str(future[h-1].date()),
                lower=float(anchor*np.exp(q[0])),median=float(anchor*np.exp(q[1])),upper=float(anchor*np.exp(q[2])),
                evaluation=dict(origins=len(errors),mae_return=float(np.mean(errors)) if errors else None,
                    unchanged_mae_return=float(np.mean(baseline)) if baseline else None,
                    historical_coverage=float(np.mean(covered)) if covered else None)))
        assets.append(dict(symbol=symbol,close=anchor,windows=windows))
    return dict(version=VERSION,issued_at=datetime.now(timezone.utc).isoformat(),as_of=str(end.date()),currency='USD',assets=assets,
        method='최근 최대 5년의 5·21·63거래일 누적 수익률 분포를 현재 종가에 적용. 하단·중앙·상단은 과거 10·50·90백분위.',
        limitation='과거 분포 시나리오이며 미래 적중확률 80%를 보장하지 않습니다. 배당·세금·비용·새로운 시장 충격은 반영하지 않습니다. 매매 신호와 별도입니다.')
