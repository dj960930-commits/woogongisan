"""Build the independent, read-only wave chart feed from completed OHLC bars."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pandas as pd
import pandas_market_calendars as calendars
from tools.wave_analysis import analyze

ROOT = Path(__file__).resolve().parents[1]
SYMBOLS = {"QQQ": "QQQ", "TQQQ": "TQQQ", "SOXX": "SOXX", "SOXL": "SOXL",
           "BRK.B": "BRK-B", "GLD": "GLD", "BITO": "BITO", "BTC/USD": "BTC-USD"}
THRESHOLDS = {"4h": .025, "1d": .04, "1w": .07, "1mo": .12}
LIMITS = {"4h": 440, "1d": 760, "1w": 525, "1mo": 126}
OHLC = ("open", "high", "low", "close")


def quote(client, ticker, interval, span, now):
    response = client.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
                          params={"interval": interval, "range": span, "includePrePost": "false"})
    response.raise_for_status()
    result = response.json()["chart"]["result"][0]
    if result["meta"]["symbol"] != ticker or result["meta"]["currency"] != "USD":
        raise ValueError("Unexpected quote identity")
    raw = result["indicators"]["quote"][0]
    if any(len(raw[key]) != len(result["timestamp"]) for key in OHLC):
        raise ValueError("Incomplete provider quote")
    frame = pd.DataFrame({key: raw[key] for key in OHLC},
                         index=pd.to_datetime(result["timestamp"], unit="s", utc=True))
    frame = frame.dropna().sort_index()
    if frame.empty or frame.index.has_duplicates or not all(
        all(math.isfinite(x) and x > 0 for x in row)
        and row[2] <= min(row[0], row[3]) <= max(row[0], row[3]) <= row[1]
        for row in frame.itertuples(index=False, name=None)
    ):
        raise ValueError("Invalid OHLC")
    return frame.loc[frame.index < now]


def aggregate(rows):
    return [float(rows.open.iloc[0]), float(rows.high.max()), float(rows.low.min()), float(rows.close.iloc[-1])]


def periods(frame, schedule, now, crypto):
    local = frame.index.tz_convert("UTC" if crypto else "America/New_York")
    frame = frame.set_axis(local.tz_localize(None).normalize())
    if frame.index.has_duplicates:
        raise ValueError("Duplicate daily session")
    if crypto:
        dates = pd.date_range(frame.index.min(), now.tz_localize(None).normalize(), freq="D")
        end = pd.Series(dates.tz_localize("UTC") + pd.Timedelta(days=1), index=dates)
    else:
        end = schedule.market_close
    frame = frame.loc[frame.index.intersection(end.index)]
    frame = frame.loc[end.reindex(frame.index) <= now]
    daily = [(date, end[date], list(row), None) for date, row in zip(frame.index, frame.to_numpy())]
    out = {"1d": daily}
    for key, period in [("1w", "W-SUN"), ("1mo", "M")]:
        bars = []
        for _, days in end.groupby(end.index.to_period(period)):
            if days.iloc[-1] > now or not days.index.isin(frame.index).all():
                continue
            last = days.index[-1]
            bars.append((last, days.iloc[-1], aggregate(frame.loc[days.index]), None))
        out[key] = bars
    return out


def four_hours(frame, schedule, now, crypto):
    if crypto:
        days = pd.date_range(frame.index.min().normalize(), now.normalize(), freq="D")
        sessions = ((day, day + pd.Timedelta(days=1)) for day in days)
    else:
        sessions = zip(schedule.market_open, schedule.market_close)
    bars = []
    hour = pd.Timedelta(hours=1)
    for opening, closing in sessions:
        if closing < frame.index[0] or opening > now:
            continue
        for start in pd.date_range(opening, closing, freq="4h", inclusive="left"):
            end = min(start + pd.Timedelta(hours=4), closing)
            if end > now:
                continue
            expected = pd.date_range(start, end, freq="1h", inclusive="left")
            if expected.isin(frame.index).all():
                minutes = int((end - start) / pd.Timedelta(minutes=1))
                date = start.tz_convert("UTC" if crypto else "America/New_York").date()
                bars.append((date, end, aggregate(frame.loc[expected]), minutes))
    return bars


def expected_as_of(interval, schedule, now, crypto):
    """Latest calendar-complete bar endpoint, independent of provider availability."""
    now = pd.Timestamp(now)
    if crypto:
        utc_now = now.tz_convert("UTC")
        if interval == "1d":
            return utc_now.floor("D")
        if interval == "4h":
            return utc_now.floor("4h")
        period = "W-SUN" if interval == "1w" else "M"
        dates = pd.date_range(utc_now.tz_localize(None).normalize() - pd.Timedelta(days=45),
                              utc_now.tz_localize(None).normalize(), freq="D")
        ends = pd.Series(dates + pd.Timedelta(days=1), index=dates)
        current_period = utc_now.tz_localize(None).to_period(period)
        complete = [days.iloc[-1] for key, days in ends.groupby(ends.index.to_period(period))
                    if key < current_period]
        return complete[-1].tz_localize("UTC") if complete else None
    if interval == "1d":
        closes = schedule.market_close[schedule.market_close <= now]
        return closes.iloc[-1] if not closes.empty else None
    if interval == "4h":
        ends = []
        for opening, closing in zip(schedule.market_open, schedule.market_close):
            for start in pd.date_range(opening, closing, freq="4h", inclusive="left"):
                end = min(start + pd.Timedelta(hours=4), closing)
                if end <= now:
                    ends.append(end)
        return max(ends) if ends else None
    period = "W-SUN" if interval == "1w" else "M"
    complete = [days.iloc[-1] for _, days in schedule.market_close.groupby(schedule.index.to_period(period))
                if days.iloc[-1] <= now]
    return complete[-1] if complete else None


def freshness(series_data, expected):
    actual = pd.Timestamp(series_data["as_of"])
    if expected is None:
        return dict(status="unknown", actual_as_of=actual.isoformat(), expected_as_of=None, lag_minutes=None)
    expected = pd.Timestamp(expected)
    lag = max(0.0, (expected - actual).total_seconds() / 60)
    return dict(status="delayed" if actual < expected else "current",
                actual_as_of=actual.isoformat(), expected_as_of=expected.isoformat(),
                lag_minutes=round(lag, 1))


def pivots(prices, threshold):
    """Causal reversal detector adapted from analysis_app/models/causal_engine.py."""
    direction = 0
    low = high = 0
    points = []
    for index, price in enumerate(prices):
        if direction >= 0 and price >= prices[high]:
            high = index
        if direction <= 0 and price <= prices[low]:
            low = index
        if direction <= 0 and price >= prices[low] * (1 + threshold):
            points.append((low, index, "L"))
            direction, high = 1, index
        elif direction >= 0 and price <= prices[high] * (1 - threshold):
            points.append((high, index, "H"))
            direction, low = -1, index
    return points


def series(bars, interval, volatility=1, crypto=False):
    bars = bars[-LIMITS[interval]:]
    if len(bars) < 12:
        raise ValueError("Insufficient completed bars")
    threshold = THRESHOLDS[interval] * volatility
    prices = [row[2][3] for row in bars]
    points = pivots(prices, threshold)
    scenario = None
    if len(points) >= 3:
        (a, _, kind), (b, _, _), (c, confirmed, _) = points[-3:]
        p0, p1, p2 = (prices[i] for i in (a, b, c))
        sign = 1 if kind == "L" else -1
        leg = (p1 - p0) * sign
        retracement = (p1 - p2) * sign / leg if leg > 0 else 0
        target = p2 + (p1 - p0) * 1.618
        # Guard the scenario using observed highs/lows after its anchor.
        barrier_column = 2 if sign > 0 else 1
        anchor = bars[a][2][barrier_column]
        valid = all((bar[2][barrier_column] - anchor) * sign > 0 for bar in bars[a + 1:])
        touched = any((bar[2][1 if sign > 0 else 2] - target) * sign >= 0 for bar in bars[c:])
        if valid and 0 < retracement < 1 and target > 0 and not touched:
            scenario = dict(direction="up" if sign > 0 else "down",
                            anchors=[a, b, c], confirmed=confirmed, trigger=round(p1, 4),
                            invalidation=round(anchor, 4), target=round(target, 4),
                            retracement=round(retracement, 4),
                            triggered=bool((prices[-1] - p1) * sign > 0))
    return {
        "as_of": bars[-1][1].isoformat(),
        "threshold": threshold,
        "bars": [[str(day)[:10], end.isoformat(), *[round(x, 4) for x in row], minutes]
                 for day, end, row, minutes in bars],
        "pivots": points, "scenario": scenario,
        "analysis": analyze(bars, interval, threshold, pivots, scenario, crypto),
    }


def main():
    now = pd.Timestamp(datetime.now(timezone.utc))
    schedule = calendars.get_calendar("NYSE").schedule(now.date() - pd.Timedelta(days=3655),
                                                       now.date() + pd.Timedelta(days=45))
    destination = ROOT / "site" / "waves.json"
    old = json.loads(destination.read_text(encoding="utf-8")) if destination.exists() else {}

    def build(pair):
        symbol, ticker = pair
        previous = old.get("symbols", {}).get(symbol, {}).get("series", {})
        crypto = ticker == "BTC-USD"
        volatility = 1.5 if symbol in {"TQQQ", "SOXL", "BITO", "BTC/USD"} else 1
        result = {}
        with httpx.Client(timeout=20, headers={"User-Agent": "Mozilla/5.0"}) as client:
            for interval, group in (("1d", ("1d", "1w", "1mo")), ("60m", ("4h",))):
                try:
                    raw = quote(client, ticker, interval, "10y" if interval == "1d" else "6mo", now)
                    bars = periods(raw, schedule, now, crypto) if interval == "1d" else {
                        "4h": four_hours(raw, schedule, now, crypto)}
                    for key in group:
                        current = series(bars[key], key, volatility, crypto)
                        if current["as_of"] < previous.get(key, {}).get("as_of", ""):
                            raise ValueError(f"Quote regressed for {key}")
                        result[key] = current
                except (ValueError, IndexError, KeyError, TypeError, httpx.HTTPError) as exc:
                    print(symbol, interval, type(exc).__name__, str(exc)[:200])
                    for key in group:
                        if key not in result and key in previous:
                            result[key] = {**previous[key], "cached": True}
                for key in group:
                    if key in result:
                        result[key]["freshness"] = freshness(
                            result[key], expected_as_of(key, schedule, now, crypto))
        return symbol, {"series": result}

    with ThreadPoolExecutor(max_workers=4) as workers:
        assets = dict(workers.map(build, SYMBOLS.items()))
    if not any(a["series"] for a in assets.values()):
        raise SystemExit("No verified wave data")
    payload = dict(schema_version=1, engine="causal-pattern-v2", analysis_version="wave-explainer-v2", source="Yahoo Finance",
                   generated_at=now.isoformat(), symbols=assets)
    tmp = destination.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    tmp.replace(destination)
    print({key: list(item["series"]) for key, item in assets.items()})


if __name__ == "__main__":
    main()
