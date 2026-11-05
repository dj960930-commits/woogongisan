import pytest
from trading.timing import timing, FINGERPRINT

@pytest.mark.parametrize('previous,current,phase', [(3,0,'entry'),(2,0,'entry'),(0,0,'hold'),(0,3,'exit'),(3,3,'wait'),(3,2,'wait')])
def test_transitions(previous,current,phase):
    result=timing(current,previous,FINGERPRINT)
    assert result['phase']==phase
    assert result['research_only'] and not result['borrowing_approved']

@pytest.mark.parametrize('previous,current,fingerprint', [(None,0,FINGERPRINT),(3,0,'new-model'),(3,5,FINGERPRINT),(True,0,FINGERPRINT)])
def test_unknown_or_changed_model_is_not_entry(previous,current,fingerprint):
    assert timing(current,previous,fingerprint)['phase']=='unavailable'

def test_indicator_does_not_change_strategy():
    from models.registry import load_model
    assert load_model('woogong-1.3-d').fingerprint==FINGERPRINT
    selected=load_model('woogong-v2')
    before=selected.fingerprint
    result=timing(0,3,before)
    assert result['phase']=='entry' and result['research_only'] and not result['borrowing_approved']
    assert load_model('woogong-v2').fingerprint==before
