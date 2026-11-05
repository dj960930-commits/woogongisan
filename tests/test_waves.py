import pandas as pd

from tools.build_waves import OHLC, four_hours, periods, pivots, series


def test_session_boundaries_and_shortened_four_hour_bar():
    opening = pd.Timestamp("2026-11-27T14:30:00Z")
    closing = pd.Timestamp("2026-11-27T18:00:00Z")
    schedule = pd.DataFrame({"market_open": [opening], "market_close": [closing]})
    hours = pd.date_range(opening, closing, freq="h", inclusive="left")
    quotes = pd.DataFrame([[100, 105, 99, 104]] * len(hours), index=hours, columns=OHLC)
    assert four_hours(quotes, schedule, closing - pd.Timedelta(seconds=1), False) == []
    bar, = four_hours(quotes, schedule, closing, False)
    assert bar[1:] == (closing, [100.0, 105.0, 99.0, 104.0], 210)
    assert four_hours(quotes.drop(hours[2]), schedule, closing, False) == []


def test_weekly_requires_final_scheduled_session_and_full_coverage():
    dates = pd.date_range("2026-11-02", periods=5, freq="D")
    closes = dates.tz_localize("UTC") + pd.Timedelta(hours=21)
    schedule = pd.DataFrame({"market_close": closes}, index=dates)
    raw = pd.DataFrame([[100, 105, 99, 104]] * 5, index=closes, columns=OHLC)
    assert periods(raw, schedule, closes[-2], False)["1w"] == []
    assert periods(raw.drop(closes[2]), schedule, closes[-1], False)["1w"] == []
    assert len(periods(raw, schedule, closes[-1], False)["1w"]) == 1


def test_pivot_confirmation_is_causal_and_projection_expires():
    prices = [90, 95, 100, 105, 110, 120, 114, 105, 111, 112, 113, 114]
    complete = pivots(prices, .04)
    for cut in range(1, len(prices)):
        assert pivots(prices[:cut], .04) == [p for p in complete if p[1] < cut]

    def bars(values):
        dates = pd.date_range("2026-01-01", periods=len(values), tz="UTC")
        return [(date, date, [p, p, p, p], None) for date, p in zip(dates, values)]

    data = series(bars(prices), "1d")
    assert data["scenario"]["direction"] == "up"
    assert not data["scenario"]["triggered"]
    assert data["scenario"]["confirmed"] > data["scenario"]["anchors"][-1]
    assert series(bars(prices + [155]), "1d")["scenario"] is None
