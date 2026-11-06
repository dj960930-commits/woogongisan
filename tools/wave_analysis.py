"""Causal pattern explanations and descriptive timing from completed bars."""
import math

import numpy as np
import pandas as pd

from tools.wave_grammar import complete_catalog


NAMES = {
    "impulse": "1–2–3–4–5 추진파", "truncated_impulse": "5파 미달 추진파",
    "leading_diagonal": "선행 다이아고날", "ending_diagonal": "종결 다이아고날",
    "zigzag": "A–B–C 지그재그", "regular_flat": "A–B–C 플랫",
    "expanded_flat": "A–B–C 확장 플랫", "running_flat": "A–B–C 러닝 플랫",
    "contracting_triangle": "A–B–C–D–E 수렴 삼각형",
    "barrier_triangle": "A–B–C–D–E 장벽 삼각형",
    "expanding_triangle": "A–B–C–D–E 확산 삼각형",
    "double_zigzag": "W–X–Y 이중 지그재그", "double_three": "W–X–Y 복합 조정",
    "triple_zigzag": "W–X–Y–X–Z 삼중 지그재그", "triple_three": "W–X–Y–X–Z 복합 조정",
}


def future_ends(last, interval, crypto, count):
    """Actual bar endings, including NYSE closures and shortened sessions."""
    import pandas_market_calendars as calendars

    last = pd.Timestamp(last)
    if crypto:
        frequency = {"4h": "4h", "1d": "D", "1w": "W-MON", "1mo": "MS"}[interval]
        return [stamp.isoformat() for stamp in pd.date_range(last, periods=count + 2, freq=frequency)
                if stamp > last][:count]
    # A complete final weekly/monthly session is needed to name that period.
    days = {"4h": 5, "1d": 3, "1w": 10, "1mo": 40}[interval] * count + 60
    schedule = calendars.get_calendar("NYSE").schedule(
        last.date() - pd.Timedelta(days=35), last.date() + pd.Timedelta(days=days))
    if interval == "4h":
        ends = []
        for row in schedule.itertuples():
            for start in pd.date_range(row.market_open, row.market_close, freq="4h", inclusive="left"):
                ends.append(min(start + pd.Timedelta(hours=4), row.market_close))
    elif interval == "1d":
        ends = list(schedule.market_close)
    else:
        period = "W-SUN" if interval == "1w" else "M"
        groups = list(schedule.market_close.groupby(schedule.index.to_period(period)))
        ends = [group.iloc[-1] for _, group in groups[:-1]]
    return [stamp.isoformat() for stamp in ends if stamp > last][:count]


def rejection(bars, points):
    if len(points) < 3:
        return "연장 후보를 구성할 전환점 3개가 아직 모이지 않았어요."
    a, b, c = [point[0] for point in points[-3:]]
    sign = 1 if points[-3][2] == "L" else -1
    prices = [row[2][3] for row in bars]
    length = (prices[b] - prices[a]) * sign
    if length <= 0:
        return "최근 세 전환점의 방향이 연장 구조와 맞지 않아요."
    retracement = (prices[b] - prices[c]) * sign / length
    if not 0 < retracement < 1:
        return "되돌림이 첫 움직임의 범위를 벗어나 기존 연장 후보를 접었어요."
    column = 2 if sign > 0 else 1
    boundary = bars[a][2][column]
    if any((row[2][column] - boundary) * sign <= 0 for row in bars[a + 1:]):
        return "첫 파동의 출발 고점·저점이 깨져 기존 연장 후보를 접었어요."
    target = prices[c] + (prices[b] - prices[a]) * 1.618
    if target <= 0:
        return "계산된 연장 가격이 유효한 가격 범위 밖이에요."
    return "기존 1.618배 연장 가격에 이미 닿아 그 목표는 종료됐어요."


def timing(points, last_index, direction):
    """Same scale, same direction, only already-confirmed historical legs."""
    samples = []
    active = points[-1][0] if points else last_index
    elapsed = last_index - active
    active_direction = (1 if points[-1][2] == "L" else -1) if points else None
    if direction != active_direction:
        return dict(status="waiting_turn", samples=0, elapsed=elapsed)
    for left, right in zip(points, points[1:]):
        sign = 1 if left[2] == "L" else -1
        if sign == direction and right[0] - left[0] > elapsed:
            samples.append(right[0] - left[0] - elapsed)
    if len(samples) < 5:
        return dict(status="insufficient", samples=len(samples), elapsed=elapsed)
    lower, middle, upper = np.quantile(samples, [.25, .5, .75], method="nearest")
    return dict(status="estimated", samples=len(samples), elapsed=elapsed,
                lower=int(lower), median=int(middle), upper=int(upper))


def analyze(bars, interval, threshold, pivot_fn, scenario, crypto=False):
    close = np.array([row[2][3] for row in bars])
    degrees = (threshold / 2, threshold)
    all_points = {}
    for degree in degrees:
        all_points[degree] = [(i, known, float(close[i]), kind)
                             for i, known, kind in pivot_fn(close, degree)]
    frame = pd.DataFrame([row[2] for row in bars], columns=["open", "high", "low", "close"])
    catalog = complete_catalog(frame, all_points, degrees)
    # An unconfirmed last edge is an explicit developing outer shape.
    # It never enters historical completed-leg samples.
    active_points = {degree: list(points) for degree, points in all_points.items()}
    for degree, points in active_points.items():
        if not points or points[-1][0] == len(bars) - 1:
            continue
        index, _, value, kind = points[-1]
        sign = 1 if kind == "L" else -1
        if (float(close[-1]) - value) * sign > 0:
            points.append((len(bars) - 1, len(bars) - 1, float(close[-1]), "H" if kind == "L" else "L"))
    catalog.extend(item for item in complete_catalog(frame, active_points, degrees)
                   if item["end"] == len(bars) - 1)
    # One pattern per family at the latest known endpoint, retaining ambiguity.
    catalog.sort(key=lambda item: (item["end"], item["subdivision_verified"],
                                  -len(item["children"]), item["degree"]), reverse=True)
    patterns, seen = [], set()
    for item in catalog:
        if item["family"] in seen:
            continue
        seen.add(item["family"])
        ids = item["indices"]
        developing = item["end"] == len(bars) - 1 and all(
            point[0] != item["end"] for point in all_points[item["degree"]])
        if item["family"].startswith(("double_", "triple_")):
            labels = [dict(index=item["start"], label="시작")]
            for label, child in zip(("W", "X", "Y", "X", "Z"), item["children"]):
                labels.append(dict(index=child["end"], label=label))
        else:
            alphabet = "12345" if item["family"] in {
                "impulse", "truncated_impulse", "leading_diagonal", "ending_diagonal"} else "ABCDE"
            labels = [dict(index=ids[0], label="시작")] + [
                dict(index=index, label=label) for index, label in zip(ids[1:], alphabet)]
        if developing:
            labels[-1]["label"] += "?"
        values = [float(close[i]) for i in ids]
        if item["family"].startswith(("double_", "triple_")):
            evidence = " → ".join(NAMES[child["family"]] for child in item["children"])
            evidence = "공유 전환점에서 연결된 구성 · " + evidence
        elif len(ids) == 4:
            a_length = abs(values[1] - values[0])
            retracement = abs(values[2] - values[1]) / a_length
            c_ratio = abs(values[3] - values[2]) / a_length
            evidence = f"B는 A의 {retracement:.1%}를 되돌렸고, C의 가격 폭은 A의 {c_ratio:.2f}배예요."
        elif item["family"] in {"impulse", "truncated_impulse"}:
            evidence = "2파가 출발점을 지켰고, 4파와 1파의 가격 영역이 겹치지 않았어요. 3파는 1·3·5파 중 최단이 아니에요."
        else:
            evidence = "다섯 구간의 고점·저점 순서와 가격 폭의 수렴·확산 관계를 비교했어요."
        patterns.append(dict(family=item["family"], name=NAMES[item["family"]],
                             indices=ids, start=ids[0], end=ids[-1],
                             confirmed=item["confirmed"], direction=item["direction"],
                             developing=developing,
                             degree=item["degree"], subdivision_verified=bool(item["subdivision_verified"] and not developing),
                             prices=[round(float(close[i]), 4) for i in ids],
                             durations=[b - a for a, b in zip(ids, ids[1:])], labels=labels,
                             evidence=evidence))
        if len(patterns) == 3:
            break
    points = pivot_fn(close, threshold)
    last_index = len(bars) - 1
    # Comparison is based on prior bars so the current shock cannot dilute itself.
    returns = np.diff(np.log(close))
    history = returns[max(0, len(returns) - 61):-1]
    sigma = float(np.std(history, ddof=1)) if len(history) >= 10 else 0
    center = float(np.mean(history)) if len(history) else 0
    current = float(returns[-1])
    z = (current - center) / sigma if sigma > 1e-10 else None
    shock = dict(change=round(math.expm1(current), 6),
                 z=round(z, 2) if z is not None else None,
                 rapid_drop=bool(z is not None and z <= -2 and current < 0),
                 lookback=len(history))
    if len(points) >= 2:
        low, high = sorted(float(close[p[0]]) for p in points[-2:])
    else:
        low, high = float(min(close[-21:-1])), float(max(close[-21:-1]))
    active_sign = (1 if points[-1][2] == "L" else -1) if points else (1 if current >= 0 else -1)
    primary_sign = (1 if scenario["direction"] == "up" else -1) if scenario else active_sign
    paths = []
    for sign in (primary_sign, -primary_sign):
        clock = timing(points, last_index, sign)
        boundary = high if sign > 0 else low
        if scenario and sign == primary_sign:
            target, trigger = scenario["target"], scenario["trigger"]
            invalidation = scenario["invalidation"]
            method = "first_leg_1.618"
        else:
            trigger = boundary
            # Range-width projection, distinguished from a pattern-derived target.
            target = boundary + sign * (high - low)
            invalidation = low if sign > 0 else high
            method = "range_width"
        if high <= low:
            continue
        paths.append(dict(direction="up" if sign > 0 else "down",
                          target=round(target, 4) if target > 0 else None, trigger=round(trigger, 4),
                          invalidation=round(invalidation, 4), method=method,
                          timing=clock))
    maximum = max((path["timing"].get("upper", 0) for path in paths), default=0)
    future = future_ends(bars[-1][1], interval, crypto, maximum) if maximum else []
    for path in paths:
        clock = path["timing"]
        if clock["status"] == "estimated":
            if len(future) < clock["upper"]:
                clock["status"] = "calendar_unavailable"
            else:
                for key in ("lower", "median", "upper"):
                    clock[key + "_at"] = future[clock[key] - 1]
    return dict(version="wave-explainer-v2", patterns=patterns, paths=paths,
                rejection=None if scenario else rejection(bars, points),
                shock=shock, range_low=round(low, 4), range_high=round(high, 4),
                future_ends=future,
                timing_basis="같은 종목·시간봉·전환 폭·방향의 완료 파동 중 현재 경과 봉 수보다 긴 표본의 남은 봉 수 사분위 범위")
