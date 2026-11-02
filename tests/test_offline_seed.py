import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]


def test_release_seed_survives_prepare_and_keeps_research_frozen(tmp_path,monkeypatch):
    import prepare
    for name in ['data','models']:shutil.copytree(ROOT/name,tmp_path/name)
    (tmp_path/'site').mkdir()
    monkeypatch.setattr(prepare,'ROOT',tmp_path)
    prepare.main()
    asset=tmp_path/'android/app/src/main/assets'
    s=json.loads((asset/'snapshot.json').read_text(encoding='utf-8'))
    h=json.loads((asset/'status.json').read_text(encoding='utf-8'))
    assert s['market_date']==h['market_date']=='2026-10-30'
    assert s['mode']=='historical_demo' and h['state']=='demo'
    assert s['performance']['windows']['1m']['end']=='2026-10-30'
    assert (tmp_path/'data/equities.csv').read_bytes()==(ROOT/'data/equities.csv').read_bytes()
