import json
import pytest
from tools.build_signal_bundle import build


def documents(tmp_path):
    for name in ('model', 'snapshot', 'status'):
        value = dict(schema_version=1, model_id='test', model_fingerprint='a'*64,
                     market_date='2026-10-30', state='ready')
        (tmp_path / (name+'.json')).write_text(json.dumps(value))


def test_one_generation_changes_with_status_and_rejects_mixed_dates(tmp_path):
    documents(tmp_path)
    a = build(tmp_path)
    path = tmp_path/'status.json'
    value = json.loads(path.read_text());value['market_date']='2026-11-02'
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):build(tmp_path)
    value['state']='error';path.write_text(json.dumps(value))
    b = build(tmp_path)
    assert b['generation'] != a['generation']
    assert b['documents']['status.json']['state']=='error'


def test_rejects_other_model_and_excludes_unrelated_history(tmp_path):
    documents(tmp_path)
    (tmp_path/'backtest.json').write_text('{"model_id":"other"}')
    assert 'backtest.json' not in build(tmp_path)['documents']
    (tmp_path/'model.json').write_text('{"model_id":"other"}')
    with pytest.raises(ValueError):build(tmp_path)
