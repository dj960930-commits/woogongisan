from datetime import datetime,timezone
from types import SimpleNamespace
import pytest
from tools.close_gate import decide

MODEL=SimpleNamespace(fingerprint='a'*64)


def ready():
    s={'mode':'live','market_date':'2026-11-02','model_fingerprint':MODEL.fingerprint,
       'data_contract_id':'audited-mixed-close-v1','performance':{'version':'model-tqqq-brkb-v1'}}
    h={'state':'ready','market_date':s['market_date'],'model_fingerprint':MODEL.fingerprint}
    return s,h


def test_external_retry_skips_already_completed_close():
    s,h=ready()
    assert decide(datetime(2026,11,2,21,6,tzinfo=timezone.utc),s,h,MODEL,'2026-11-02')==(False,'already_calculated')


def test_manual_force_still_supported():
    s,h=ready()
    assert decide(datetime(2026,11,2,21,6,tzinfo=timezone.utc),s,h,MODEL,force=True)[0]


def test_pending_or_failed_date_is_retried():
    s,h=ready();h['state']='error'
    assert decide(datetime(2026,11,2,21,6,tzinfo=timezone.utc),s,h,MODEL,'2026-11-02')[0]


def test_future_or_old_requested_session_never_publishes_as_current():
    s,h=ready()
    assert decide(datetime(2026,11,2,21,4,tzinfo=timezone.utc),s,h,MODEL,'2026-11-02')==(False,'requested_session_not_current')
    assert decide(datetime(2026,11,2,21,6,tzinfo=timezone.utc),s,h,MODEL,'2026-10-30')==(False,'requested_session_not_current')


def test_bad_input_is_rejected_before_execution():
    s,h=ready()
    with pytest.raises(ValueError):decide(datetime(2026,11,2,21,6,tzinfo=timezone.utc),s,h,MODEL,'$(not-a-date)')


def test_model_change_recalculates_same_date():
    s,h=ready();h['model_fingerprint']='b'*64
    assert decide(datetime(2026,11,2,21,6,tzinfo=timezone.utc),s,h,MODEL,'2026-11-02')[0]
