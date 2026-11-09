import pandas as pd
import pytest

from tools import prepare_v22_release as release


@pytest.fixture
def archived_inputs(monkeypatch):
    # Exercise publication routing using repository fixtures on developer PCs and CI.
    read_csv = pd.read_csv
    read_text = type(release.ROOT).read_text
    def fixture_csv(path, *args, **kwargs):
        path = str(path).replace('\\', '/')
        if path.endswith('bito-weighted-reduction/metrics.csv'):
            path = release.ROOT/'site/research/bito-weighted-reduction.csv'
        elif path.endswith('verified-prices.csv'):
            path = release.ROOT/'data/equities.csv'
        elif path.endswith('verified-btc.csv'):
            return read_csv(release.ROOT/'data/btc.csv', parse_dates=['date_utc']).set_index('date_utc')
        return read_csv(path, *args, **kwargs)
    def fixture_text(path, *args, **kwargs):
        if str(path).replace('\\', '/').endswith('v21-feed/runtime/benchmark-prices.json'):
            return '{"prices":{}}'
        return read_text(path, *args, **kwargs)
    monkeypatch.setattr(release.pd, 'read_csv', fixture_csv)
    monkeypatch.setattr(type(release.ROOT), 'read_text', fixture_text)
    monkeypatch.setattr(release, 'snapshot', lambda *args: ({'mode': 'historical_demo', 'market_date': '2026-10-30'}, None))
    monkeypatch.setattr(release, 'latest_backtest', lambda *args, **kwargs: {'_daily_nav': None})
    monkeypatch.setattr(release, 'comparison', lambda *args: {})
    monkeypatch.setattr(release, 'outlook', lambda *args: {})


def test_release_publishes_live_online_and_keeps_dated_android_seed(monkeypatch, archived_inputs):
    written = {}
    activated = []
    live = {
        'snapshot': {'mode': 'live', 'market_date': '2026-11-06'},
        'extended_backtest': {'data_end': '2026-11-06'},
        'status': {'state': 'ready', 'market_date': '2026-11-06'},
    }
    monkeypatch.setattr(release, 'live_documents', lambda model: live)
    monkeypatch.setattr(release, 'write', lambda path, value: written.update({path.relative_to(release.ROOT).as_posix(): value}))
    monkeypatch.setattr(release, 'activate', lambda model_id: activated.append(model_id))
    monkeypatch.setattr(release, 'bundle', lambda site: {})
    release.main()
    assert activated == ['woogong-v2.2']
    assert written['site/snapshot.json'] == live['snapshot']
    assert written['site/status.json']['state'] == 'ready'
    seed = written['data/offline/snapshot.json']
    assert seed['market_date'] == '2026-10-30'
    assert seed['mode'] == 'historical_demo'


def test_release_refuses_to_activate_when_current_feed_fails(monkeypatch, archived_inputs):
    monkeypatch.setattr(release, 'write', lambda *args: None)
    def fail(model):
        raise ValueError('current feed unavailable')
    monkeypatch.setattr(release, 'live_documents', fail)
    activated = []
    monkeypatch.setattr(release, 'activate', lambda model_id: activated.append(model_id))
    with pytest.raises(ValueError, match='current feed unavailable'):
        release.main()
    assert not activated


def test_online_publication_rejects_an_old_feed(monkeypatch):
    monkeypatch.setattr(release, 'session', lambda now: (pd.Timestamp('2026-11-06'), None))
    monkeypatch.setattr(release, 'fetch', lambda expected, root: (None, None, {}))
    monkeypatch.setattr(release, 'snapshot', lambda *args: ({'market_date': '2026-10-30'}, None))
    with pytest.raises(ValueError, match='behind the completed session'):
        release.live_documents(release.load_model('woogong-v2.2'))
