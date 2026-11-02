"""Validate an external scheduler's requested session before doing any writes."""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pipeline import session
from models.registry import load_model


def decide(now, snapshot, status, model, requested='', force=False):
    if requested and not re.fullmatch(r'\d{4}-\d{2}-\d{2}',requested):
        raise ValueError('invalid requested market date')
    found=session(now)
    if found is None:
        return False,'no_completed_session'
    expected=str(found[0].date())
    if requested and requested!=expected:
        return False,'requested_session_not_current'
    ready=(snapshot.get('mode')=='live' and status.get('state')=='ready'
           and snapshot.get('market_date')==status.get('market_date')==expected
           and snapshot.get('model_fingerprint')==status.get('model_fingerprint')==model.fingerprint
           and snapshot.get('data_contract_id')=='audited-mixed-close-v1'
           and snapshot.get('performance',{}).get('version')=='model-tqqq-brkb-v1')
    if ready and not force:
        return False,'already_calculated'
    return True,'calculation_needed'


def main():
    def read(name):
        try:return json.loads((ROOT/'site'/f'{name}.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):return {}
    requested=os.environ.get('REQUESTED_CLOSE','')
    force=os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch' and not requested
    proceed,reason=decide(datetime.now(timezone.utc),read('snapshot'),read('status'),load_model(),requested,force)
    output=f'proceed={str(proceed).lower()}\nreason={reason}\n'
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as stream:stream.write(output)
    print(output,end='')


if __name__=='__main__':main()
