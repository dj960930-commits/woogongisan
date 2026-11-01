"""Always-on, model-only publisher. No brokerage keys, orders, or GitHub jobs.

One process owns the scheduler and persistent disk. Readers see only a completely
validated generation. A failed calculation keeps the last good generation and
overlays an unavailable status; it never relabels old positions as today's signal.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import argparse
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid

from models.registry import load_model
from pipeline import session

ROOT = Path(__file__).resolve().parent
FILES = ('model.json', 'snapshot.json', 'status.json', 'backtest.json',
         'extended_backtest.json', 'data-validation.json')


def utcnow():
    return datetime.now(timezone.utc)


def validate(documents, expected, metadata, now):
    s, h, m = (documents[name] for name in ('snapshot.json', 'status.json', 'model.json'))
    for doc in (s, h, m):
        for key in ('schema_version', 'model_id', 'model_fingerprint', 'rebalance_band'):
            if doc.get(key) != metadata[key]:
                raise ValueError('model identity mismatch')
        if doc.get('orders_enabled') is not False or doc.get('live_approved') is not False:
            raise ValueError('order lock mismatch')
    if s.get('mode') != 'live' or h.get('state') != 'ready':
        raise ValueError('calculation not ready')
    if s.get('market_date') != expected or h.get('market_date') != expected:
        raise ValueError('incomplete market date')
    if s.get('data_contract_id') != 'audited-mixed-close-v1':
        raise ValueError('price contract mismatch')
    expires = datetime.fromisoformat(s['valid_until'].replace('Z', '+00:00'))
    if expires.tzinfo is None or now >= expires:
        raise ValueError('expired result')
    weights = s['target']
    if set(weights) != {'TQQQ', 'SOXL', 'BITO', 'BRK.B', 'GLD', 'CASH'}:
        raise ValueError('asset mismatch')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0
           for v in weights.values()) or abs(sum(weights.values()) - 1) > 1e-8:
        raise ValueError('invalid allocation')
    for name in ('backtest.json', 'extended_backtest.json'):
        if name in documents and documents[name].get('model_fingerprint') != metadata['model_fingerprint']:
            raise ValueError('backtest identity mismatch')
    if documents.get('extended_backtest.json', {}).get('data_end') != expected:
        raise ValueError('extended result date mismatch')


class Publisher:
    def __init__(self, directory, runner=subprocess.run, clock=utcnow):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.runner, self.clock = runner, clock
        self.metadata = load_model().metadata()
        self.lock = threading.RLock()
        self.current = None
        self.last_attempt_at = None
        self.last_success_at = None
        self.error_type = None
        self.push_state = 'not_configured'
        self.pushed_generation = None
        self.last_push_attempt = 0.0
        self._session_cache = None
        try:
            saved = json.loads((self.directory/'current.json').read_text(encoding='utf-8'))
            # Even after downtime the old generation may be retained, but is never
            # promoted as fresh without today's checks in effective_status().
            validate(saved['documents'], saved['market_date'], self.metadata,
                     datetime.fromisoformat(saved['published_at']))
            self.current = saved
            self.last_success_at = saved['published_at']
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def expected(self, now):
        bucket = int(now.timestamp()) // 15
        with self.lock:
            if self._session_cache and self._session_cache[0] == bucket:
                return self._session_cache[1]
        found = session(now)
        value = None if found is None else (str(found[0].date()), found[1].to_pydatetime())
        with self.lock:
            self._session_cache = (bucket, value)
        return value

    def effective_status(self, now=None):
        now = now or self.clock()
        found = self.expected(now)
        with self.lock:
            if self.current is None:
                h = {**self.metadata, 'state': 'error', 'message': '첫 확정 종가 계산 대기'}
            else:
                h = dict(self.current['documents']['status.json'])
                if not found or h.get('market_date') != found[0] or self.error_type:
                    h.update(state='error', message='새 종가 확인 중 · 이전 목표를 새 신호로 사용하지 마세요')
                elif datetime.fromisoformat(self.current['documents']['snapshot.json']['valid_until'].replace('Z', '+00:00')) <= now:
                    h.update(state='error', message='이전 결과 만료 · 새 종가 확인 중')
            if found:
                h['expected_date'] = found[0]
            h['publication'] = {'source': 'dedicated-model-server',
                                'last_attempt_at': self.last_attempt_at,
                                'last_success_at': self.last_success_at,
                                'push_state': self.push_state,
                                'error_type': self.error_type}
            return h

    def bundle(self):
        with self.lock:
            if self.current is None:
                return None
            result = dict(self.current)
            result['documents'] = dict(result['documents'])
            result['documents']['status.json'] = self.effective_status()
            return result

    def calculate(self, force=False):
        now = self.clock()
        found = self.expected(now)
        if not found:
            return False
        expected, close = found
        with self.lock:
            if not force and self.current and self.effective_status(now)['state'] == 'ready':
                return False
            self.last_attempt_at = now.isoformat()
        try:
            with tempfile.TemporaryDirectory(prefix='candidate-', dir=self.directory) as temp:
                staging = Path(temp)
                env = dict(os.environ, WOOGONG_SITE_DIR=str(staging))
                result = self.runner([sys.executable, str(ROOT/'pipeline.py'), '--live', '--force-refresh'],
                                     cwd=ROOT, env=env, timeout=300, capture_output=True, text=True)
                if result.returncode:
                    raise RuntimeError('calculation process failed')
                docs = {name: json.loads((staging/name).read_text(encoding='utf-8'))
                        for name in FILES if (staging/name).is_file()}
                validate(docs, expected, self.metadata, self.clock())
                published = self.clock()
                candidate = {'schema_version': 1, 'generation': uuid.uuid4().hex,
                             'market_date': expected, 'published_at': published.isoformat(),
                             'close_to_publish_seconds': max(0, (published-close).total_seconds()),
                             'documents': docs}
                encoded = json.dumps(candidate, ensure_ascii=False, allow_nan=False).encode('utf-8')
                pending = self.directory/('current-'+candidate['generation']+'.tmp')
                with pending.open('wb') as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
                with self.lock:
                    pending.replace(self.directory/'current.json')
                    self.current = candidate
                    self.last_success_at = published.isoformat()
                    self.error_type = None
            return True
        except Exception as exc:
            with self.lock:
                self.error_type = type(exc).__name__
            # Never print exception text: upstream responses and environment can
            # contain operational information. Public diagnostics use types only.
            print('model calculation unavailable:', self.error_type, flush=True)
            return False

    def push(self):
        try:
            tokens = json.loads(os.environ.get('FCM_TOKENS') or '[]')
        except ValueError:
            tokens = None
        if (not os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON') or not isinstance(tokens, list)
                or not tokens or any(not isinstance(t, str) or not t.strip() for t in tokens)):
            self.push_state = 'not_configured'
            return
        with self.lock:
            current = self.current
            if not current or self.effective_status()['state'] != 'ready':
                return
            if self.pushed_generation == current['generation'] or (self.last_push_attempt and time.monotonic()-self.last_push_attempt < 60):
                return
            self.last_push_attempt = time.monotonic()
        try:
            with tempfile.TemporaryDirectory(prefix='push-', dir=self.directory) as temp:
                for name in ('snapshot.json', 'status.json'):
                    (Path(temp)/name).write_text(json.dumps(current['documents'][name], ensure_ascii=False), encoding='utf-8')
                env = dict(os.environ, WOOGONG_SITE_DIR=temp,
                           WOOGONG_OUTBOX_DIR=str(self.directory/'outbox'))
                result = self.runner([sys.executable, str(ROOT/'notify.py')], cwd=ROOT, env=env,
                                     timeout=60, capture_output=True, text=True)
                self.push_state = 'sent' if result.returncode == 0 else 'failed'
                if result.returncode == 0:
                    self.pushed_generation = current['generation']
        except Exception:
            self.push_state = 'failed'


class ModelService:
    def __init__(self, publisher, interval=30):
        self.publisher, self.interval = publisher, max(15, interval)
        self.stop_event = threading.Event()
        self.thread = None
        self.file_lock = None

    def start(self):
        # Render disk services run one instance. A process lock also prevents a
        # mistaken second scheduler on the same disk during manual restarts.
        self.file_lock = (self.publisher.directory/'scheduler.lock').open('a+b')
        if os.name == 'nt':
            import msvcrt
            self.file_lock.write(b'0');self.file_lock.flush();self.file_lock.seek(0)
            msvcrt.locking(self.file_lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.file_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.thread = threading.Thread(target=self.loop, name='model-scheduler', daemon=True)
        self.thread.start()

    def loop(self):
        while not self.stop_event.is_set():
            try:
                self.publisher.calculate()
                self.publisher.push()
            except Exception as exc:
                self.publisher.error_type = type(exc).__name__
            self.stop_event.wait(self.interval)

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=365)
        if self.file_lock:
            self.file_lock.close()


def handler(service):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *_):
            pass  # Paths from public callers must not enter operational logs.

        def do_GET(self):
            path = urlsplit(self.path).path
            code = 200
            if path == '/healthz':
                healthy = service.thread is not None and service.thread.is_alive()
                code = 200 if healthy else 503
                data = {'service': 'woogong-model', 'scheduler_running': healthy}
            elif path == '/status.json':
                data = service.publisher.effective_status()
            elif path == '/bundle.json' or path[1:] in FILES:
                bundle = service.publisher.bundle()
                data = bundle if path == '/bundle.json' else (bundle or {}).get('documents', {}).get(path[1:])
                if data is None:
                    code, data = 503, {'state': 'error', 'message': '확정 종가 계산 대기'}
            else:
                code, data = 404, {'error': 'not_found'}
            body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store, max-age=0')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def do_HEAD(self):
            self.send_response(405);self.end_headers()
    return Handler


class ModelHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, *args, **kwargs):
        self.slots = threading.BoundedSemaphore(16)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '8780')))
    parser.add_argument('--state', default=os.environ.get('WOOGONG_STATE_DIR', str(ROOT/'runtime/model-server')))
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    publisher = Publisher(args.state)
    if args.once:
        publisher.calculate(force=True)
        if publisher.effective_status()['state'] != 'ready':
            raise SystemExit(1)
        print('validated publication:', publisher.current['market_date'])
        return
    service = ModelService(publisher)
    service.start()
    server = ModelHTTPServer((args.host, args.port), handler(service))
    def shutdown(*_):
        service.stop_event.set()
        threading.Thread(target=server.shutdown, daemon=True).start()
    for event in (signal.SIGINT, signal.SIGTERM):
        signal.signal(event, shutdown)
    try:
        server.serve_forever()
    finally:
        server.server_close();service.stop()


if __name__ == '__main__':
    main()
