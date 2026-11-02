"""Package one static deployment's model documents into a single generation."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


def build(site):
    docs = {name + '.json': json.loads((site / (name + '.json')).read_text(encoding='utf-8'))
            for name in ('model', 'snapshot', 'status')}
    model, snapshot, status = (docs[n + '.json'] for n in ('model', 'snapshot', 'status'))
    identity = lambda d: tuple(d.get(k) for k in ('schema_version', 'model_id', 'model_fingerprint'))
    if not identity(model) == identity(snapshot) == identity(status):
        raise ValueError('mixed model generation')
    if status.get('state') == 'ready' and snapshot.get('market_date') != status.get('market_date'):
        raise ValueError('mixed ready market dates')
    for name in ('backtest', 'extended_backtest'):
        path = site / (name + '.json')
        if path.exists():
            value = json.loads(path.read_text(encoding='utf-8'))
            if identity(value) == identity(model):
                docs[name + '.json'] = value
    encoded = json.dumps(docs, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return dict(schema_version=1, generation=hashlib.sha256(encoded.encode()).hexdigest()[:32],
                market_date=snapshot['market_date'], documents=docs)


if __name__ == '__main__':
    site = ROOT / 'site'
    bundle = build(site)
    temporary = site / 'bundle.tmp'
    temporary.write_text(json.dumps(bundle, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    temporary.replace(site / 'bundle.json')
