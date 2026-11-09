import copy
import pandas as pd
import pandas_market_calendars as calendars
from tools.wave_forecast_ledger import update


def bar(date, high, low, close):
    return [date, date+"T21:00:00+00:00", 100, high, low, close, None]


def feed(bars, generated):
    return dict(generated_at=generated, analysis_version="v1", symbols={
        "GLD": {"series": {"1d": dict(as_of=bars[-1][1], bars=bars, freshness={"status":"current"},
            analysis={"paths":[dict(direction="up",status="conditional",target=110,trigger=95,
                                     invalidation=90,method="range_width")]})}}})


def test_first_published_signal_is_immutable_and_target_is_scored_afterward():
    schedule=calendars.get_calendar("NYSE").schedule("2026-10-01","2026-11-30")
    one=feed([bar("2026-11-02",101,99,100)],"2026-11-02T21:10:00+00:00")
    ledger=update({},one,schedule)
    assert len(ledger["records"])==1
    old=copy.deepcopy(ledger["records"][0])
    assert update(ledger,one,schedule)["records"][0]==old
    two=feed([bar("2026-11-02",101,99,100),bar("2026-11-03",111,99,105)],
             "2026-11-03T21:10:00+00:00")
    ledger=update(ledger,two,schedule)
    assert ledger["records"][0]["outcome"]=="target_first"
    assert ledger["records"][0]["generated_at"]==old["generated_at"]


def test_same_bar_collision_is_not_counted_as_a_win():
    schedule=calendars.get_calendar("NYSE").schedule("2026-10-01","2026-11-30")
    ledger=update({},feed([bar("2026-11-02",101,99,100)],"2026-11-02T21:10:00+00:00"),schedule)
    two=feed([bar("2026-11-02",101,99,100),bar("2026-11-03",111,89,100)],
             "2026-11-03T21:10:00+00:00")
    assert update(ledger,two,schedule)["records"][0]["outcome"]=="same_bar_ambiguous"


def test_stale_series_cannot_issue_a_forecast():
    schedule=calendars.get_calendar("NYSE").schedule("2026-10-01","2026-11-30")
    value=feed([bar("2026-11-02",101,99,100)],"2026-11-02T21:10:00+00:00")
    value["symbols"]["GLD"]["series"]["1d"]["freshness"]["status"]="delayed"
    assert update({},value,schedule)["records"]==[]


def test_missing_prior_bar_is_never_scored_as_a_win():
    schedule=calendars.get_calendar("NYSE").schedule("2026-10-01","2026-11-30")
    ledger=update({},feed([bar("2026-11-02",101,99,100)],"2026-11-02T21:10:00+00:00"),schedule)
    replacement=feed([bar("2026-11-03",111,99,105)],"2026-11-03T21:10:00+00:00")
    assert update(ledger,replacement,schedule)["records"][0]["outcome"]=="missing_bars"
