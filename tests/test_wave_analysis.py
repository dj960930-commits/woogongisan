import pandas as pd

from tools.build_waves import series
from tools.wave_analysis import future_ends, timing
from tools.wave_grammar import complete_catalog, geometry


def test_timing_uses_only_same_direction_completed_legs_and_elapsed_time():
    points = [(index, index + 1, "L" if i % 2 == 0 else "H")
              for i, index in enumerate(range(0, 121, 10))]
    result = timing(points, 123, 1)
    assert result == dict(status="estimated", samples=6, elapsed=3, lower=7, median=7, upper=7)
    assert timing(points, 131, 1)["status"] == "insufficient"


def test_future_calendar_skips_holiday_and_handles_short_session():
    # Thanksgiving is closed and Friday ends at 18:00 UTC.
    assert future_ends("2026-11-25T21:00:00Z", "1d", False, 2) == [
        "2026-11-27T18:00:00+00:00", "2026-11-30T21:00:00+00:00"]
    assert future_ends("2026-11-25T21:00:00Z", "4h", False, 1) == [
        "2026-11-27T18:00:00+00:00"]
    assert future_ends("2026-11-25T00:00:00Z", "4h", True, 1) == [
        "2026-11-25T04:00:00+00:00"]


def test_pattern_geometry_keeps_ambiguity_and_rejects_non_alternating_shape():
    assert "zigzag" in geometry([100, 120, 110, 130])
    assert "zigzag" in geometry([130, 110, 120, 100])
    assert geometry([100, 120, 125, 130]) == []
    assert "impulse" in geometry([100, 120, 110, 145, 125, 160])
    assert "impulse" not in geometry([100, 120, 110, 145, 119, 160])


def test_no_extension_still_yields_explanation_and_no_fabricated_timing():
    prices = [100 + i for i in range(20)]
    dates = pd.date_range("2026-01-01", periods=len(prices), tz="UTC")
    bars = [(date, date, [p, p, p, p], None) for date, p in zip(dates, prices)]
    result = series(bars, "1d")
    assert result["scenario"] is None
    assert result["analysis"]["rejection"]
    assert len(result["analysis"]["paths"]) == 2
    assert result["analysis"]["future_ends"] == []
    assert all(p["timing"]["status"] in {"insufficient", "waiting_turn"}
               for p in result["analysis"]["paths"])


def test_shock_is_compared_to_prior_bars_and_reports_direction():
    prices = [100 * (1.002 if i % 2 else .998) for i in range(30)] + [80]
    dates = pd.date_range("2026-01-01", periods=len(prices), tz="UTC")
    bars = [(date, date, [p, p, p, p], None) for date, p in zip(dates, prices)]
    result = series(bars, "1d")["analysis"]["shock"]
    assert result["rapid_drop"]
    assert result["change"] < -.19
    assert result["z"] < -2


def test_combination_requires_connected_corrective_children():
    values = [100, 120, 110, 130, 115, 122, 108, 128, 118, 138]
    data = pd.DataFrame({key: values for key in ("open", "high", "low", "close")})
    points = [(i, i, value, "L" if i % 2 == 0 else "H") for i, value in enumerate(values)]
    catalog = complete_catalog(data, {.02: points}, (.02,))
    combinations = [item for item in catalog
                    if item["family"] == "double_zigzag" and item["start"] == 0 and item["end"] == 9]
    assert combinations
    assert [child["end"] for child in combinations[0]["children"]] == [3, 6, 9]
    assert not combinations[0]["subdivision_verified"]
