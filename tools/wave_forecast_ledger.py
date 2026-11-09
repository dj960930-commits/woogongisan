"""Prospective wave-price observations. No historical forecasts are invented."""
from datetime import timedelta
from bisect import bisect_right
import hashlib
import json
import os

import pandas as pd

HORIZON = {"4h": 30, "1d": 21, "1w": 13, "1mo": 12}


def market_endpoints(schedule):
    intraday = []
    for opening, closing in zip(schedule.market_open, schedule.market_close):
        for start in pd.date_range(opening, closing, freq="4h", inclusive="left"):
            intraday.append(min(start + pd.Timedelta(hours=4), closing))
    return {
        "4h": intraday,
        "1d": list(schedule.market_close),
        "1w": [group.iloc[-1] for _, group in schedule.market_close.groupby(schedule.index.to_period("W-SUN"))],
        "1mo": [group.iloc[-1] for _, group in schedule.market_close.groupby(schedule.index.to_period("M"))],
    }


def next_end(last, interval, crypto, endpoints):
    if crypto:
        if interval == "4h":
            return last + pd.Timedelta(hours=4)
        if interval == "1d":
            return last + pd.Timedelta(days=1)
        if interval == "1w":
            return last + pd.Timedelta(days=7)
        return last + pd.DateOffset(months=1)
    times = endpoints[interval]
    index = bisect_right(times, last)
    if index >= len(times):
        raise ValueError("Session calendar unavailable")
    return times[index]


def bar_start(row, interval, crypto, schedule):
    end = pd.Timestamp(row[1])
    date = pd.Timestamp(row[0])
    if interval == "4h":
        minutes = int(row[6] or 0)
        if minutes <= 0:
            raise ValueError("Missing intraday duration")
        return end - pd.Timedelta(minutes=minutes)
    if crypto:
        if interval == "1d":
            return end - pd.Timedelta(days=1)
        period = date.to_period("W-SUN" if interval == "1w" else "M")
        return period.start_time.tz_localize("UTC")
    if interval == "1d":
        return schedule.loc[date, "market_open"]
    period = date.to_period("W-SUN" if interval == "1w" else "M")
    group = schedule[schedule.index.to_period(period.freqstr) == period]
    if group.empty:
        raise ValueError("Missing session calendar")
    return group.market_open.iloc[0]


def update(ledger, feed, schedule):
    if not ledger:
        ledger = dict(schema_version=1, records=[], methodology=(
            "Forward observations only. Fixed horizons in completed bars; same-bar collisions are ambiguous. "
            "The generated timestamp is not a verified public deployment timestamp; a 30-minute buffer is used."))
    if ledger.get("schema_version") != 1:
        raise ValueError("Unknown wave forecast ledger")
    generated = pd.Timestamp(feed["generated_at"])
    records = ledger["records"]
    symbols = feed["symbols"]
    endpoints = market_endpoints(schedule)
    for record in records:
        if record["outcome"] != "pending":
            continue
        series = symbols.get(record["symbol"], {}).get("series", {}).get(record["interval"])
        if not series or series.get("freshness", {}).get("status") != "current":
            continue
        bars = series["bars"]
        last = pd.Timestamp(record["last_bar"])
        if not any(pd.Timestamp(bar[1]) == last for bar in bars):
            record["outcome"] = "missing_bars"
            continue
        cutoff = pd.Timestamp(record["generated_at"]) + timedelta(minutes=30)
        for bar in bars:
            end = pd.Timestamp(bar[1])
            if end <= last:
                continue
            if end != next_end(last, record["interval"], record["symbol"] == "BTC/USD", endpoints):
                record["outcome"] = "missing_bars"
                break
            start = bar_start(bar, record["interval"], record["symbol"] == "BTC/USD", schedule)
            high, low, close = float(bar[3]), float(bar[4]), float(bar[5])
            sign = 1 if record["direction"] == "up" else -1
            target_hit = high >= record["target"] if sign > 0 else low <= record["target"]
            invalid_hit = low <= record["invalidation"] if sign > 0 else high >= record["invalidation"]
            record["last_bar"] = end.isoformat()
            last = end
            if start < cutoff or not record["confirmed"]:
                if target_hit or invalid_hit:
                    record["outcome"] = "unscorable_before_entry"
                    record["resolved_at"] = end.isoformat()
                    break
                record["confirmed"] = (close - record["trigger"]) * sign > 0
                continue
            record["bars_observed"] += 1
            if target_hit and invalid_hit:
                record["outcome"] = "same_bar_ambiguous"
            elif target_hit:
                record["outcome"] = "target_first"
            elif invalid_hit:
                record["outcome"] = "invalidation_first"
            elif record["bars_observed"] >= HORIZON[record["interval"]]:
                record["outcome"] = "expired"
            else:
                record["confirmed"] = (close - record["trigger"]) * sign > 0
            if record["outcome"] != "pending":
                record["resolved_at"] = end.isoformat()
                break
    seen = {r["id"] for r in records}
    for symbol, asset in symbols.items():
        for interval, series in asset.get("series", {}).items():
            if interval not in HORIZON or series.get("freshness", {}).get("status") != "current":
                continue
            bars = series.get("bars", [])
            if not bars:
                continue
            current = float(bars[-1][5])
            for path in series.get("analysis", {}).get("paths", []):
                if path.get("status") != "conditional" or path.get("target") is None:
                    continue
                sign = 1 if path["direction"] == "up" else -1
                target, trigger, invalid = (float(path[k]) for k in ("target", "trigger", "invalidation"))
                if not ((current-trigger)*sign > 0 and (target-current)*sign > 0 and (current-invalid)*sign > 0):
                    continue
                ident = hashlib.sha256(("\0".join((symbol,interval,series["as_of"],
                    feed.get("analysis_version",""),path["direction"]))).encode()).hexdigest()[:24]
                if ident in seen:
                    continue
                records.append(dict(id=ident,symbol=symbol,interval=interval,
                    direction=path["direction"],generated_at=generated.isoformat(),
                    as_of=series["as_of"],last_bar=series["as_of"],issued_close=current,
                    target=target,trigger=trigger,invalidation=invalid,
                    method=path.get("method"),analysis_version=feed.get("analysis_version"),
                    code_revision=os.environ.get("GITHUB_SHA","local"),confirmed=True,
                    bars_observed=0,outcome="pending"))
                seen.add(ident)
    return ledger
