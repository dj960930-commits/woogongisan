"""Causal append/basis/coverage checks. No network, keys, or accounts."""
from pathlib import Path
import json
import shutil
import numpy as np
import pandas as pd
import pytest
import httpx
import market_data as feed
from engine import evaluate

ROOT=Path(__file__).resolve().parents[1]


def series():
    days=pd.bdate_range('2026-01-01',periods=100)
    return pd.Series(np.linspace(100,125,100),index=days)


def test_append_preserves_frozen_history_and_neutralizes_adjusted_level_change():
    old=series();incoming=old*.6
    expected=old.index[-1]
    combined,report=feed.append_verified(old,incoming,expected,'BITO')
    pd.testing.assert_series_equal(combined,old)
    assert report['handoff_max_daily_return_gap']<1e-14


def test_wrong_adjustment_basis_is_rejected():
    old=series();incoming=old.copy();incoming.iloc[-10:]*=.99
    with pytest.raises(ValueError,match='basis/handoff'):
        feed.append_verified(old,incoming,old.index[-1],'QQQ')


def test_known_missing_distribution_restores_frozen_basis_without_waiving_checks():
    days=feed.calendars.get_calendar('NYSE').schedule(start_date='2026-06-01',end_date='2026-11-04').index
    raw=pd.Series(np.linspace(10,12,len(days)),index=days)
    ex=pd.Timestamp('2026-10-01');factor=1-.017/raw.loc[raw.index<ex].iloc[-1]
    corrected=raw.copy();corrected.loc[corrected.index<ex]*=factor
    old=corrected.loc[:'2026-10-20']
    obj={'chart':{'result':[{'meta':{'symbol':'BITO','currency':'USD','exchangeTimezoneName':'America/New_York'},
        'timestamp':[int((d.tz_localize('America/New_York')+pd.Timedelta(hours=9,minutes=30)).timestamp()) for d in days],
        'indicators':{'quote':[{'close':raw.tolist()}],'adjclose':[{'adjclose':raw.tolist()}]}}]}}
    expected=days[-1]
    repaired,proof=feed.restore_known_distribution(obj,raw,old,expected,'BITO')
    combined,report=feed.append_verified(old,repaired,expected,'BITO')
    pd.testing.assert_series_equal(combined.loc[old.index],old)
    assert proof['official_distribution']==.017381 and report['handoff_max_daily_return_gap']<1e-10
    # Metadata-only omission with correct prices must not double-adjust.
    same,proof=feed.restore_known_distribution(obj,corrected,old,expected,'BITO')
    assert proof is None
    pd.testing.assert_series_equal(same,corrected)
    wrong=raw.copy();wrong.iloc[-20]*=1.01
    with pytest.raises(ValueError):feed.restore_known_distribution(obj,wrong,old,expected,'BITO')
    obj['chart']['result'][0]['events']={'dividends':{'known':{'date':int((ex.tz_localize('America/New_York')+pd.Timedelta(hours=9,minutes=30)).timestamp()),'amount':.017}}}
    unchanged,proof=feed.restore_known_distribution(obj,raw,old,expected,'BITO')
    assert proof is None
    with pytest.raises(ValueError):feed.append_verified(old,unchanged,expected,'BITO')


def test_old_revision_is_reported_but_never_overwrites_frozen_prefix():
    old=series();incoming=old.copy();incoming.iloc[5]*=1.01
    combined,report=feed.append_verified(old,incoming,old.index[-1],'BRK.B')
    assert report['historical_revisions_preserved']==2
    pd.testing.assert_series_equal(combined,old)


def test_missing_handoff_session_is_rejected():
    old=series();incoming=old.drop(old.index[-5])
    with pytest.raises(ValueError):feed.append_verified(old,incoming,old.index[-1],'QQQ')


def test_chart_rejects_wrong_symbol_and_incomplete_current_day():
    obj={'chart':{'result':[{'meta':{'symbol':'QQQ','currency':'USD','exchangeTimezoneName':'America/New_York'},
        'timestamp':[int(pd.Timestamp('2026-10-26T13:30Z').timestamp())],
        'indicators':{'quote':[{'close':[100]}],'adjclose':[{'adjclose':[99]}]}}]}}
    with pytest.raises(ValueError,match='instrument'):feed.parse_chart(obj,'TQQQ',pd.Timestamp('2026-10-26'))
    with pytest.raises(ValueError,match='not available'):feed.parse_chart(obj,'QQQ',pd.Timestamp('2026-10-27'))
    s,raw=feed.parse_chart(obj,'QQQ',pd.Timestamp('2026-10-26'))
    assert raw==100 and s.iloc[-1]==100


def test_btc_never_uses_utc_candle_on_or_after_us_signal_date():
    expected=pd.Timestamp('2026-10-26')
    rows=[{'timestamp':str(feed.timestamp(d)),'close':'100'} for d in ['2026-10-25','2026-10-26','2026-10-27']]
    result=feed.parse_btc({'data':{'ohlc':rows}},expected)
    assert list(result.index)==[pd.Timestamp('2026-10-25')]


def test_complete_feed_preserves_all_frozen_targets_and_needs_no_keys(tmp_path):
    (tmp_path/'data').mkdir()
    for name in ['equities.csv','btc.csv']:shutil.copy(ROOT/'data'/name,tmp_path/'data'/name)
    old=pd.read_csv(tmp_path/'data/equities.csv',index_col=0,parse_dates=True)
    btc=pd.read_csv(tmp_path/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    expected=pd.Timestamp('2026-10-26')
    sessions=feed.calendars.get_calendar('NYSE').schedule(start_date=old.index[-1]+pd.Timedelta(days=1),end_date=expected).index
    def reply(request):
        assert 'authorization' not in request.headers
        if 'bitstamp' in request.url.host:
            days=pd.date_range(btc.index[-1]-pd.Timedelta(days=30),expected)
            return httpx.Response(200,json={'data':{'ohlc':[{'timestamp':str(feed.timestamp(d)),
                'close':str(btc.loc[d] if d in btc.index else float(btc.iloc[-1]))} for d in days]}})
        symbol=next(k for k,v in feed.SYMBOLS.items() if request.url.path.endswith('/'+v))
        incoming=old[symbol].dropna().iloc[-130:]
        incoming=pd.concat([incoming,pd.Series(float(incoming.iloc[-1])*1.01,index=sessions)])
        # Include a current/intraday extra candle, which must be ignored.
        incoming.loc[expected+pd.Timedelta(days=1)]=999999
        values=list(map(float,incoming));dates=[int((d.tz_localize('America/New_York')+pd.Timedelta(hours=9,minutes=30)).timestamp()) for d in incoming.index]
        return httpx.Response(200,json={'chart':{'result':[{'meta':{'symbol':feed.SYMBOLS[symbol],
            'currency':'USD','exchangeTimezoneName':'America/New_York'},'timestamp':dates,
            'indicators':{'quote':[{'close':values}],'adjclose':[{'adjclose':values}]}}]}})
    with httpx.Client(transport=httpx.MockTransport(reply)) as client:p,b,raw=feed.fetch(expected,tmp_path,client)
    pd.testing.assert_frame_equal(p.loc[old.index],old)
    original,_=evaluate(old,btc);updated,_=evaluate(p,b)
    np.testing.assert_allclose(updated.loc[original.index],original,atol=1e-12,rtol=0)
    assert p.index[-1]==expected and b.index[-1]<expected
    quality=json.loads((tmp_path/'runtime/market-data-validation.json').read_text())
    assert all(row['frozen_prefix_unchanged'] for row in quality['equities'])
    assert quality['price_fields']['BITO']=='adjclose' and quality['price_fields']['QQQ']=='close'
