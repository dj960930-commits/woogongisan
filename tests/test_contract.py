import sys
from pathlib import Path
import copy,json
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from engine import evaluate
from models.core_v1 import evaluate as evaluate_v1
from models.registry import load_model
from pipeline import session,snapshot,latest_backtest
def inputs():
 p=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True)
 btc=pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
 return p,btc
def test_frozen_3661_all_dates():
 p,btc=inputs();target,_=evaluate_v1(p,btc);ref=pd.read_csv(ROOT/'data/reference_targets.csv',index_col=0,parse_dates=True)
 assert np.max(abs(target.loc[ref.index].to_numpy()-ref.to_numpy()))<1e-12
def test_prefix_and_future_btc():
 p,btc=inputs();target,_=evaluate(p,btc);day=pd.Timestamp('2024-01-03');prefix,_=evaluate(p.loc[:day],btc)
 assert np.allclose(prefix.to_numpy(),target.loc[prefix.index].to_numpy(),atol=1e-12)
 altered=btc.copy();altered.loc[day:]*=3;changed,_=evaluate(p,altered)
 assert np.allclose(changed.loc[:day],target.loc[:day],atol=1e-12)
def test_early_close_dst_and_holiday():
 from datetime import datetime,timezone
 day,close=session(datetime(2025,11,28,18,7,tzinfo=timezone.utc))
 assert str(day.date())=='2025-11-28' and close.hour==18
 day,close=session(datetime(2026,7,3,22,tzinfo=timezone.utc))
 assert str(day.date())=='2026-07-02'
 day,close=session(datetime(2026,7,6,20,7,tzinfo=timezone.utc))
 assert close.hour==20
def test_snapshot_labels_and_finite():
 p,btc=inputs();data,t=snapshot(p,btc,'historical_demo')
 assert data['strategy_id']==load_model().profile['strategy_id'] and data['mode']=='historical_demo'
 assert not data['account_connected'] and data['market_date']=='2026-10-20'
 assert abs(sum(data['target'].values())-1)<1e-12
 assert data['valid_until'].startswith('2026-10-21')
 json.dumps(data,allow_nan=False)
def test_live_fetch_uses_public_feed_without_private_keys(monkeypatch):
 from pipeline import fetch
 import market_data
 monkeypatch.delenv('TIINGO_TOKEN',raising=False)
 expected=pd.Timestamp('2026-10-26');sentinel=object()
 monkeypatch.setattr(market_data,'fetch',lambda date,root:sentinel if date==expected else None)
 assert fetch(expected) is sentinel
def test_optional_push_empty_github_secrets_are_unconfigured(tmp_path,monkeypatch,capsys):
 import notify
 meta=load_model().metadata()
 (tmp_path/'status.json').write_text(json.dumps({**meta,'state':'ready','market_date':'2026-10-26'}))
 (tmp_path/'snapshot.json').write_text(json.dumps({**meta,'market_date':'2026-10-26'}))
 monkeypatch.setattr(notify,'SITE',tmp_path)
 monkeypatch.setenv('FCM_TOKENS','');monkeypatch.setenv('FIREBASE_SERVICE_ACCOUNT_JSON','')
 notify.main()
 assert 'not configured' in capsys.readouterr().out
def test_frozen_backtest_is_not_synthetic():
 b=json.loads((ROOT/'site/backtest.json').read_text(encoding='utf-8'))
 assert b['kind']=='observed_BITO_same_close_reference' and b['execution']=='same_close_reference'
 assert b['model_id']=='woogong-v2' and b['model_fingerprint']==load_model().fingerprint
 assert b['validation']['actual_after_hours_fills_verified'] is False
 assert b['synthetic_cagr']>.7 and b['model_id']==load_model().id
def test_missing_data_preserves_last_snapshot(tmp_path,monkeypatch):
 import pipeline
 from datetime import datetime,timezone
 old={'market_date':'2026-10-19','mode':'live'}
 (tmp_path/'snapshot.json').write_text(json.dumps(old))
 monkeypatch.setattr(pipeline,'SITE',tmp_path)
 monkeypatch.setattr(pipeline,'session',lambda now:(pd.Timestamp('2026-10-20'),pd.Timestamp('2026-10-20T20:00Z')))
 def broken(expected):raise ValueError('missing equity')
 monkeypatch.setattr(pipeline,'fetch',broken)
 monkeypatch.setattr(sys,'argv',['pipeline.py','--live'])
 pipeline.main()
 assert json.loads((tmp_path/'snapshot.json').read_text())==old
 assert json.loads((tmp_path/'status.json').read_text(encoding='utf-8'))['state']=='error'
def test_device_outbox_only_retries_failed(tmp_path,monkeypatch):
 import notify
 import types
 meta=load_model().metadata()
 (tmp_path/'status.json').write_text(json.dumps({**meta,'state':'ready','market_date':'2026-10-20'}))
 (tmp_path/'snapshot.json').write_text(json.dumps({**meta,'market_date':'2026-10-20','state_label':'방어'}))
 monkeypatch.setattr(notify,'SITE',tmp_path);monkeypatch.setattr(notify,'ROOT',tmp_path)
 monkeypatch.setenv('FCM_TOKENS',json.dumps(['phone1','phone2']));monkeypatch.setenv('FIREBASE_SERVICE_ACCOUNT_JSON','{}')
 calls=[];fail={'active':True}
 def send(message):
  calls.append(message['token'])
  if message['token']=='phone2' and fail['active']:raise RuntimeError('transient')
 messaging=types.SimpleNamespace(send=send,Message=lambda **kw:kw,AndroidConfig=lambda **kw:kw)
 fake=types.SimpleNamespace(initialize_app=lambda x:None,credentials=types.SimpleNamespace(Certificate=lambda x:x),messaging=messaging)
 monkeypatch.setitem(sys.modules,'firebase_admin',fake)
 import pytest
 with pytest.raises(SystemExit):notify.main()
 fail['active']=False;notify.main();notify.main()
 assert calls==['phone1','phone2','phone2']
