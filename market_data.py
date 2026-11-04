"""Keyless EOD feed, preserving the audited price-column contract and frozen prefix.

QQQ/TQQQ/BRK.B/GLD: split-adjusted close (cash distributions NOT reinvested).
SOXL/BITO: split-and-distribution-adjusted close. BTC: completed Bitstamp UTC days.
Never substitute one price basis for another or rewrite the frozen research fixtures.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import pandas_market_calendars as calendars
import httpx

ROOT = Path(__file__).resolve().parent
CONTRACT_ID = 'audited-mixed-close-v1'
BASIS = {'QQQ': 'close', 'TQQQ': 'close', 'BRK.B': 'close', 'GLD': 'close',
         'SOXL': 'adjclose', 'BITO': 'adjclose'}
SYMBOLS = {s: ('BRK-B' if s == 'BRK.B' else s) for s in BASIS}
# Different decimal serialization of provider floats is below 1e-6 in daily return.
# A 0.0001% return difference rejects a wrong price column or material handoff revision.
RETURN_TOLERANCE = 1e-6
HANDOFF_RETURNS = 60


def timestamp(day):
    return int(pd.Timestamp(day).tz_localize('UTC').timestamp())


def parse_chart(obj, symbol, expected, price_field=None):
    chart = obj.get('chart', {})
    if chart.get('error') or not chart.get('result') or len(chart['result']) != 1:
        raise ValueError(f'{symbol}: missing price result')
    result = chart['result'][0]
    meta = result['meta']
    if meta.get('symbol') != SYMBOLS[symbol] or meta.get('currency') != 'USD':
        raise ValueError(f'{symbol}: wrong instrument/currency')
    if meta.get('exchangeTimezoneName') != 'America/New_York':
        raise ValueError(f'{symbol}: unexpected exchange timezone')
    dates = pd.to_datetime(result['timestamp'], unit='s', utc=True).tz_convert(
        meta['exchangeTimezoneName']).tz_localize(None).normalize()
    close = result['indicators']['quote'][0]['close']
    field = price_field or BASIS[symbol]
    if field not in ('close', 'adjclose'):
        raise ValueError('unsupported price field')
    values = close if field == 'close' else result['indicators']['adjclose'][0]['adjclose']
    if not len(dates) == len(values) == len(close) or dates.has_duplicates:
        raise ValueError(f'{symbol}: duplicate/unequal candles')
    selected, raw = {}, {}
    for day, value, price in zip(dates, values, close):
        if day > expected:
            continue  # Never use the current intraday US candle.
        if value is None or price is None:
            continue  # Required-session validation below rejects actual missing closes.
        if not np.isfinite([value, price]).all() or min(value, price) <= 0:
            raise ValueError(f'{symbol}: invalid close')
        selected[day], raw[day] = float(value), float(price)
    selected = pd.Series(selected, dtype=float).sort_index()
    if expected not in selected.index:
        raise ValueError(f'{symbol}: completed close not available')
    return selected, raw[expected]


def append_verified(old, incoming, expected, symbol):
    old = old.dropna().sort_index()
    if old.index.has_duplicates or incoming.index.has_duplicates or old.empty:
        raise ValueError(f'{symbol}: invalid history')
    anchor = old.index[-1]
    overlap = old.index.intersection(incoming.index)
    if len(overlap) < HANDOFF_RETURNS + 1 or anchor not in overlap:
        raise ValueError(f'{symbol}: insufficient handoff overlap')
    differences = (old.loc[overlap].pct_change(fill_method=None)
                   - incoming.loc[overlap].pct_change(fill_method=None)).abs().dropna()
    recent_gap = float(differences.tail(HANDOFF_RETURNS).max())
    if recent_gap > RETURN_TOLERANCE:
        raise ValueError(f'{symbol}: price basis/handoff mismatch')
    # Validate every session in the handoff and extension, not just the latest row.
    required = calendars.get_calendar('NYSE').schedule(
        start_date=overlap[-(HANDOFF_RETURNS + 1)].date(), end_date=expected.date()).index
    if incoming.reindex(required).isna().any():
        raise ValueError(f'{symbol}: missing exchange session')
    extension = incoming.loc[(incoming.index > anchor) & (incoming.index <= expected)]
    # New split/dividend back-adjustments may change historical LEVELS. Scale at the
    # frozen anchor; preserve all old returns/levels and append only causal new returns.
    extension = extension * (old.loc[anchor] / incoming.loc[anchor])
    combined = pd.concat([old, extension])
    return combined, {'symbol': symbol, 'price_field': BASIS[symbol], 'anchor': str(anchor.date()),
        'overlap_sessions': len(overlap), 'handoff_returns': HANDOFF_RETURNS,
        'handoff_max_daily_return_gap': recent_gap,
        'full_overlap_max_daily_return_gap': float(differences.max()),
        'historical_revisions_preserved': int((differences > RETURN_TOLERANCE).sum()),
        'appended_sessions': len(extension), 'frozen_prefix_unchanged': combined.loc[old.index].equals(old)}


def restore_known_distribution(obj, incoming, old, expected, symbol):
    """Repair a confirmed missing Yahoo event, then retain the strict handoff test.

    ProShares BITO 2026-10-01 distribution is $0.017381. The frozen Yahoo
    adjclose uses its three-decimal event representation ($0.017). This repair
    is accepted only if ALL existing handoff checks pass afterwards.
    """
    if symbol!='BITO' or BASIS[symbol]!='adjclose':return incoming,None
    ex_date=pd.Timestamp('2026-10-01')
    events=obj['chart']['result'][0].get('events',{}).get('dividends',{})
    dates={pd.Timestamp(v['date'],unit='s',tz='UTC').tz_convert('America/New_York').tz_localize(None).normalize() for v in events.values()}
    if ex_date in dates or expected<ex_date:return incoming,None
    # A correct feed with omitted event metadata needs no correction.
    try:
        append_verified(old,incoming,expected,symbol)
        return incoming,None
    except ValueError as error:
        if str(error)!=f'{symbol}: price basis/handoff mismatch':raise
    closes,_=parse_chart(obj,symbol,expected,'close')
    previous=closes.loc[closes.index<ex_date]
    if previous.empty or ex_date not in closes.index:raise ValueError('BITO: correction coverage missing')
    factor=1-round(.017381,3)/float(previous.iloc[-1])
    repaired=incoming.copy();repaired.loc[repaired.index<ex_date]*=factor
    append_verified(old,repaired,expected,symbol)  # Never waive the tolerance.
    return repaired,dict(ex_date='2026-10-01',official_distribution=.017381,
        source_precision_distribution=.017,adjustment_factor=factor,
        source='https://www.proshares.com/our-etfs/find-proshares-etfs',
        reason='provider omitted known dividend; frozen handoff revalidated')


def parse_btc(obj, expected):
    result = {}
    for row in obj['data']['ohlc']:
        day = pd.Timestamp(int(row['timestamp']), unit='s')
        if day != day.normalize():
            raise ValueError('BTC: not a UTC daily candle')
        if day >= expected:
            continue  # US day t uses only completed UTC days through t-1.
        value = float(row['close'])
        if not np.isfinite(value) or value <= 0 or (day in result and result[day] != value):
            raise ValueError('BTC: invalid/duplicate daily candle')
        result[day] = value
    return pd.Series(result, dtype=float).sort_index()


def fetch(expected, root=None, client=None):
    root = Path(root or ROOT)
    expected = pd.Timestamp(expected).normalize()
    frozen = pd.read_csv(root/'data/equities.csv', index_col=0, parse_dates=True)
    prices = frozen.copy()
    btc = pd.read_csv(root/'data/btc.csv', parse_dates=['date_utc']).set_index('date_utc').close.sort_index()
    owned = client is None
    client = client or httpx.Client(timeout=45, headers={'User-Agent': 'Mozilla/5.0'})
    reports, raw, benchmarks = [], {}, {}
    try:
        # Anchor-relative start continues working after many years; the research
        # fixtures stay frozen, and GitHub runners need no private data/cache/key.
        anchor = frozen.index[-1]
        start = min(anchor - pd.Timedelta(days=550), pd.Timestamp('2021-10-20'))
        for symbol, provider in SYMBOLS.items():
            response = client.get('https://query1.finance.yahoo.com/v8/finance/chart/'+provider,
                params={'period1': timestamp(start), 'period2': timestamp(expected+pd.Timedelta(days=1)),
                        'interval': '1d', 'events': 'div,splits'})
            response.raise_for_status()
            payload = response.json()
            series, raw[symbol] = parse_chart(payload, symbol, expected)
            if symbol in ('TQQQ', 'BRK.B'):
                adjusted, _ = parse_chart(payload, symbol, expected, 'adjclose')
                benchmarks[symbol] = {str(d.date()): float(v) for d, v in adjusted.items()}
            series,correction=restore_known_distribution(payload,series,frozen[symbol],expected,symbol)
            combined, report = append_verified(frozen[symbol], series, expected, symbol)
            if correction:report['restored_distribution']=correction
            prices = prices.reindex(prices.index.union(combined.index))
            prices[symbol] = combined
            reports.append(report)
        # Fetch completed UTC candles in bounded windows. The endpoint's `end`
        # wins over `start`, so validate coverage and retain the immutable prefix.
        cursor = btc.index.max() - pd.Timedelta(days=7)
        incoming = pd.Series(dtype=float)
        while cursor < expected:
            end = min(cursor+pd.Timedelta(days=899), expected-pd.Timedelta(days=1))
            response = client.get('https://www.bitstamp.net/api/v2/ohlc/btcusd/', params={
                'step': 86400, 'limit': 900, 'end': timestamp(end), 'exclude_current_candle': 'true'})
            response.raise_for_status()
            part = parse_btc(response.json(), expected)
            incoming = pd.concat([incoming, part])
            incoming = incoming[~incoming.index.duplicated(keep='last')].sort_index()
            cursor = end + pd.Timedelta(days=1)
        overlap = btc.index.intersection(incoming.index)
        if len(overlap) < 7 or not np.allclose(btc.loc[overlap], incoming.loc[overlap], rtol=1e-8, atol=.01):
            raise ValueError('BTC: reference/source mismatch')
        btc = pd.concat([btc, incoming.loc[incoming.index > btc.index.max()]]).sort_index()
    finally:
        if owned:
            client.close()
    prices = prices.loc[:expected].sort_index()
    sessions = calendars.get_calendar('NYSE').schedule(start_date='2021-10-20', end_date=expected.date()).index
    if prices.reindex(sessions)[list(BASIS)].isna().any().any():
        raise ValueError('equity session coverage incomplete')
    if btc.reindex(pd.date_range('2021-01-01', expected-pd.Timedelta(days=1))).isna().any():
        raise ValueError('BTC calendar coverage incomplete')
    # The full audited input prefix must remain byte-for-value identical.
    prices.index.name = frozen.index.name
    pd.testing.assert_frame_equal(prices.loc[frozen.index, frozen.columns], frozen, check_freq=False)
    quality = {'contract_id': CONTRACT_ID, 'expected_date': str(expected.date()),
        'sources': {'equities': 'Yahoo Finance', 'btc': 'Bitstamp'}, 'price_fields': BASIS,
        'history_policy': 'immutable audited prefix; scale at anchor and append new completed sessions',
        'return_tolerance': RETURN_TOLERANCE, 'equities': reports,
        'btc_last_utc_day': str(btc.index.max().date()),
        'frozen_equities_sha256': hashlib.sha256((root/'data/equities.csv').read_bytes()).hexdigest()}
    directory = root/'runtime'
    directory.mkdir(exist_ok=True)
    (directory/'market-data-validation.json').write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding='utf-8')
    (directory/'benchmark-prices.json').write_text(json.dumps({'market_date':str(expected.date()),
        'basis':'dividend_and_split_adjusted_close', 'prices':benchmarks}), encoding='utf-8')
    return prices, btc, raw
