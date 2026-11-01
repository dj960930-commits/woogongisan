from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import threading
from types import SimpleNamespace
from urllib.request import urlopen
from urllib.error import HTTPError

import pytest
from model_server import Publisher, ModelHTTPServer, handler, validate

NOW = datetime(2026, 10, 30, 21, tzinfo=timezone.utc)
CLOSE = datetime(2026, 10, 30, 20, tzinfo=timezone.utc)


def documents(metadata, date='2026-10-30'):
    snapshot = {**metadata, 'mode': 'live', 'market_date': date,
                'valid_until': '2026-11-02T21:05:00+00:00',
                'data_contract_id': 'audited-mixed-close-v1',
                'target': dict(TQQQ=0., SOXL=0., BITO=0., **{'BRK.B': 0., 'GLD': 1., 'CASH': 0.})}
    return {'snapshot.json': snapshot, 'model.json': dict(metadata),
            'status.json': {**metadata, 'state': 'ready', 'market_date': date},
            'extended_backtest.json': {**metadata, 'data_end': date}}


@pytest.fixture
def publisher(tmp_path):
    p = Publisher(tmp_path, clock=lambda: NOW)
    p.expected = lambda now: ('2026-10-30', CLOSE)
    def run(command, **kwargs):
        for name, doc in documents(p.metadata).items():
            (Path(kwargs['env']['WOOGONG_SITE_DIR'])/name).write_text(json.dumps(doc), encoding='utf-8')
        return SimpleNamespace(returncode=0)
    p.runner = run
    return p


def test_atomic_publication_and_restart(publisher):
    p = publisher
    assert p.bundle() is None
    assert p.calculate()
    bundle = p.bundle()
    assert bundle['market_date'] == bundle['documents']['snapshot.json']['market_date']
    assert bundle['documents']['status.json']['state'] == 'ready'
    assert p.last_success_at == NOW.isoformat()
    assert not p.calculate()  # No repeated network work after a successful close.
    restored = Publisher(p.directory, clock=lambda: NOW)
    restored.expected = p.expected
    assert restored.bundle()['generation'] == bundle['generation']


def test_bad_calculation_does_not_replace_good_generation(publisher):
    p = publisher
    assert p.calculate()
    generation = p.current['generation']
    def corrupt(command, **kwargs):
        docs = documents(p.metadata)
        docs['snapshot.json']['model_fingerprint'] = 'f'*64
        for name, doc in docs.items():
            (Path(kwargs['env']['WOOGONG_SITE_DIR'])/name).write_text(json.dumps(doc), encoding='utf-8')
        return SimpleNamespace(returncode=0)
    p.runner = corrupt
    assert not p.calculate(force=True)
    assert p.current['generation'] == generation
    assert p.effective_status()['state'] == 'error'
    assert json.loads((p.directory/'current.json').read_text(encoding='utf-8'))['generation'] == generation


def test_new_session_invalidates_previous_result_without_relabeling_it(publisher):
    p = publisher
    assert p.calculate()
    p.expected = lambda now: ('2026-11-02', datetime(2026,11,2,21,tzinfo=timezone.utc))
    assert p.bundle()['documents']['status.json']['state'] == 'error'
    assert p.bundle()['documents']['snapshot.json']['market_date'] == '2026-10-30'
    assert p.effective_status()['expected_date'] == '2026-11-02'


@pytest.mark.parametrize('change', [
    lambda d: d['status.json'].update(state='error'),
    lambda d: d['snapshot.json'].update(market_date='2026-10-29'),
    lambda d: d['model.json'].update(orders_enabled=True),
    lambda d: d['snapshot.json']['target'].update(GLD=float('nan')),
    lambda d: d['snapshot.json'].update(valid_until='2026-10-30T20:59:59+00:00'),
    lambda d: d['extended_backtest.json'].update(data_end='2026-10-29'),
])
def test_rejects_unsafe_or_incomplete_results(publisher, change):
    docs = documents(publisher.metadata)
    change(docs)
    with pytest.raises(ValueError):
        validate(docs, '2026-10-30', publisher.metadata, NOW)


def test_timeout_exposes_only_error_type(publisher):
    def fail(*args, **kwargs):
        raise subprocess.TimeoutExpired('do-not-disclose-token', 300)
    publisher.runner = fail
    assert not publisher.calculate()
    status = json.dumps(publisher.effective_status())
    assert 'TimeoutExpired' in status
    assert 'do-not-disclose-token' not in status


def test_public_api_is_model_only_and_uncached(publisher):
    assert publisher.calculate()
    service = SimpleNamespace(publisher=publisher, thread=SimpleNamespace(is_alive=lambda: True))
    server = ModelHTTPServer(('127.0.0.1', 0), handler(service))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = 'http://127.0.0.1:'+str(server.server_port)
    try:
        with urlopen(base+'/bundle.json', timeout=5) as response:
            assert response.headers['Cache-Control'] == 'no-store, max-age=0'
            assert json.load(response)['documents']['status.json']['state'] == 'ready'
        for path in ['/runtime/delivery.json', '/.env', '/trading/account', '/%2e%2e/current.json']:
            with pytest.raises(HTTPError) as error:
                urlopen(base+path, timeout=5)
            assert error.value.code == 404
        with urlopen(base+'/healthz', timeout=5) as response:
            assert json.load(response)['scheduler_running']
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)


def test_push_runs_after_publication_and_is_deduplicated(publisher, monkeypatch):
    monkeypatch.setenv('FIREBASE_SERVICE_ACCOUNT_JSON', '{}')
    monkeypatch.setenv('FCM_TOKENS', '["fake-device"]')
    calls = []
    def push(command, **kwargs):
        assert publisher.current is not None
        docs = Path(kwargs['env']['WOOGONG_SITE_DIR'])
        assert json.loads((docs/'status.json').read_text(encoding='utf-8'))['state'] == 'ready'
        assert kwargs['env']['WOOGONG_OUTBOX_DIR'] == str(publisher.directory/'outbox')
        calls.append(command)
        return SimpleNamespace(returncode=0)
    publisher.push()
    assert calls == []
    assert publisher.calculate()
    publisher.runner = push
    publisher.push();publisher.push()
    assert len(calls) == 1
    assert publisher.push_state == 'sent'


@pytest.mark.parametrize('tokens', ['[]', '{}', '[null]', 'invalid'])
def test_empty_or_invalid_push_config_is_not_reported_as_sent(publisher, monkeypatch, tokens):
    monkeypatch.setenv('FIREBASE_SERVICE_ACCOUNT_JSON', '{}')
    monkeypatch.setenv('FCM_TOKENS', tokens)
    publisher.push()
    assert publisher.push_state == 'not_configured'
