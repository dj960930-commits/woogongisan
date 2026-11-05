"""Common-calendar, zero-based performance windows. Never uses personal accounts."""
import numpy as np
import pandas as pd

VERSION = 'model-tqqq-brkb-v1'


def build(model_nav, benchmark_payload):
    end = model_nav.index[-1]
    if benchmark_payload.get('market_date') != str(end.date()) or benchmark_payload.get('basis') != 'dividend_and_split_adjusted_close':
        raise ValueError('comparison benchmark date/basis mismatch')
    frame = pd.DataFrame({'model':model_nav})
    for symbol, key in [('TQQQ','tqqq'),('BRK.B','brkb')]:
        series = pd.Series(benchmark_payload['prices'][symbol], dtype=float)
        series.index = pd.to_datetime(series.index)
        if series.index.has_duplicates or end not in series.index:
            raise ValueError('comparison benchmark coverage missing')
        # Never hide a missing benchmark session by intersecting/dropping rows.
        frame[key] = series.reindex(frame.index)
    if frame.isna().any().any() or not np.isfinite(frame.to_numpy()).all() or (frame <= 0).any().any():
        raise ValueError('comparison needs complete positive daily series')
    windows = {}
    for key, offset in [('1m',pd.DateOffset(months=1)),('3m',pd.DateOffset(months=3)),('1y',pd.DateOffset(years=1)),('all',None)]:
        cutoff = end-offset if offset else frame.index[0]
        eligible = frame.index[frame.index <= cutoff]
        start = eligible[-1] if len(eligible) else frame.index[0]
        selected = frame.loc[start:]
        if len(selected)<2:
            raise ValueError('comparison window too short')
        returns = selected.div(selected.iloc[0])-1
        windows[key] = {'start':str(start.date()), 'end':str(end.date()), 'sessions':len(selected),
            'returns':{c:float(returns[c].iloc[-1]) for c in returns},
            'points':[{'date':str(d.date()), **{c:float(v) for c,v in row.items()}} for d,row in returns.iterrows()]}
    return {'version':VERSION, 'available':True, 'currency':'USD', 'market_date':str(end.date()),
        'kind':'model_simulation_vs_buy_and_hold', 'windows':windows,
        'labels':{'model':'우공이산','tqqq':'TQQQ','brkb':'버크셔 B'},
        'basis':model_nav.attrs.get('basis','모델: 원본 혼합 가격기준·다음 종가·편도0.1%·현금금리0 / USD·세전')+' / 비교종목: 배당·분할 반영 수정종가·매수보유',
        'note':'동일 거래일·시작점 0%. 모델 시뮬레이션이며 실계좌 수익률이 아닙니다.'}
