"""Load profiles; fingerprint binds every output to its rules and code."""
from pathlib import Path
import hashlib
import json
from . import core_v1
from .overlays import cross_defense

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = {"frozen_core_v1": core_v1.evaluate, "cross_defense_v1": cross_defense}

class Model:
    def __init__(self, profile):
        self.profile = profile
        self.id = profile['model_id']
        self.version = profile['version']
        self.band = profile['rebalance_band']
        rules = json.dumps(profile, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        implementation = b''.join((ROOT / p).read_text(encoding='utf-8-sig').encode('utf-8') for p in ['strategy_parameters.json', 'models/core_v1.py', 'models/overlays.py', 'models/registry.py'])
        self.fingerprint = hashlib.sha256(rules + implementation).hexdigest()

    def metadata(self):
        return dict(schema_version=1, model_id=self.id, version=self.version,
                    strategy_id=self.profile['strategy_id'], model_fingerprint=self.fingerprint,
                    rebalance_band=self.band, approval=self.profile['approval'],
                    research_note=self.profile['research_note'], live_approved=False, orders_enabled=False)

    def evaluate(self, prices, btc):
        adapter = ADAPTERS[self.profile['adapter']]
        if self.profile['adapter'] == 'frozen_core_v1':
            return adapter(prices, btc)
        return adapter(prices, btc, self.profile)

def load_model(model_id=None):
    if model_id is None:
        model_id = json.loads((ROOT / 'active_model.json').read_text(encoding='utf-8'))['model_id']
    if not isinstance(model_id, str) or not model_id or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-.' for c in model_id):
        raise ValueError('잘못된 모델 ID')
    profile = json.loads((ROOT / 'models/profiles' / (model_id + '.json')).read_text(encoding='utf-8'))
    if profile['schema_version'] != 1 or profile['model_id'] != model_id or profile['adapter'] not in ADAPTERS:
        raise ValueError('지원하지 않는 모델 계약')
    if profile['parent'] != 'frozen_3661' or not 0 < profile['rebalance_band'] <= 1:
        raise ValueError('잘못된 모델 설정')
    if profile.get('live_approved') or profile.get('orders_enabled'):
        raise ValueError('이 앱은 연구·조회 전용입니다')
    return Model(profile)
