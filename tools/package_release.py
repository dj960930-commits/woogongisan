"""Package distributable source without runtime accounts, tokens or build caches."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ['RELEASE_2_0_1.md', 'RELEASE_V2.md', 'V2_RELEASE_PLAN.md', 'V2_READINESS_REVIEW.md', 'V2_CANDIDATE.md', 'README.md', 'FREE_SCHEDULER_SETUP.md', 'ASSETS_GUIDE.md', 'TRADING_GUIDE.md', 'FINAL_REVIEW.md', 'GITHUB_SETUP.md', 'requirements.txt', 'engine.py',
         'pipeline.py', 'price_outlook.py', 'shadow_journal.py', 'market_data.py', 'comparison.py', 'notify.py', 'model_server.py', 'render.yaml', 'DEPLOY_MODEL_SERVER.md', 'prepare.py', 'model.py', 'setup_android.ps1', 'setup_android.py', 'bootstrap_android_tools.py', 'build_android.ps1',
         'trading_server.py', 'start_trading.ps1', 'check_meritz.ps1', 'active_model.json', 'strategy_parameters.json',
         '.gitignore', '.gitattributes']
DIRS = ['models', 'data', 'site', 'android', 'tests', '.github', 'tools', 'trading', 'workers']
EXCLUDE = {'build', '.gradle', '.kotlin', '__pycache__', '.pytest_cache', 'runtime', '.deps', '.tools'}


def main():
    version = re.search(r'versionName = "([^"]+)"', (ROOT/'android/app/build.gradle.kts').read_text()).group(1)
    release = ROOT/'release'
    apk = release/f'woogong-{version}-trading-debug.apk'
    assert apk.exists(), 'Build the versioned APK first'
    source = release/f'woogong-{version}-source.zip'
    paths = [ROOT/p for p in FILES if (ROOT/p).is_file()]
    for directory in DIRS:
        paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and not set(p.relative_to(ROOT).parts)&EXCLUDE
            and p.name not in ('local.properties','google-services.json') and not p.name.endswith(('.env','.keystore','.jks','.pyc')))
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(set(paths)):
            z.write(p, p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(source) as z:
        assert z.testzip() is None
        assert not any('runtime/' in p or 'trading-access-token' in p for p in z.namelist())
    counts = {'tests': 0, 'failures': 0, 'errors': 0}
    for report in (release/f'android-tests-{version}').glob('TEST-*.xml'):
        suite = ET.parse(report).getroot()
        for key in counts:
            counts[key] += int(suite.get(key, 0))
    assert counts['tests'] and not counts['failures'] and not counts['errors']
    hashes = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (apk,source)}
    verification = {'version':version,'built_at':datetime.now(timezone.utc).isoformat(),'android':counts,
        'sha256':hashes,'source_files':len(set(paths)), 'live_broker_tested':False,'live_orders_enabled':False,
        'note':'See TRADING_GUIDE.md for connection and execution limits. Python/UI checks are documented separately.'}
    (release/f'BUILD_VERIFICATION_{version}.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
    (release/'SHA256SUMS.txt').write_text(''.join(f'{sha}  {name}\n' for name,sha in hashes.items()),encoding='utf-8')
    print(json.dumps(verification,ensure_ascii=False))


if __name__ == '__main__':
    main()
