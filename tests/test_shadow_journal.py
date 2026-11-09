from types import SimpleNamespace
import pytest
from shadow_journal import ASSETS, append
from tools.score_shadow_journal import summarize


def fixture(date, value=100):
    snapshot=dict(market_date=date, data_fingerprint="data", state=2)
    prices={key:value for key in ASSETS if key!="CASH"}
    model=SimpleNamespace(id="woogong-v2", fingerprint="v2")
    baseline=SimpleNamespace(id="woogong-1.3-d", fingerprint="v1")
    attack={key:float(key=="TQQQ") for key in ASSETS}
    cash={key:float(key=="CASH") for key in ASSETS}
    return snapshot, prices, [(model, attack),(baseline, cash)]


def test_first_publication_is_immutable_and_reference_returns_are_causal():
    journal=append({},*fixture("2026-11-02"))
    original=journal["observations"][0]
    assert append(journal,*fixture("2026-11-02",999))["observations"][0] == original
    journal=append(journal,*fixture("2026-11-03",200))
    report=summarize(journal)
    assert report["available"] and report["observations"]==2
    assert report["events_started"]==1
    # Initial 0.1% buy cost; the following day's doubling applies to holdings.
    assert report["results"][0]["final_multiple"] == pytest.approx(2/1.001)
    assert report["results"][1]["final_multiple"] == pytest.approx(1.0)


def test_missing_session_or_changed_model_suspends_scoring():
    journal=append({},*fixture("2026-11-02"))
    journal=append(journal,*fixture("2026-11-04"))
    assert summarize(journal)["available"] is False
    journal=append({},*fixture("2026-11-02"))
    snapshot,prices,candidates=fixture("2026-11-03")
    candidates[0][0].fingerprint="new-version"
    journal=append(journal,snapshot,prices,candidates)
    assert summarize(journal)["reason"]=="Collecting new model segment"
