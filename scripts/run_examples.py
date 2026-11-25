"""Run the supplied examples in WSL and preserve real HTTP evidence."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'reports' / 'examples'
EVIDENCE.mkdir(parents=True, exist_ok=True)


def request(path, *, body=None, headers=None, method=None, port=8000):
    data = json.dumps(body).encode() if body is not None else None
    h = {'Content-Type': 'application/json', **(headers or {})}
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=data,
                                 headers=h, method=method)
    try:
        response = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        raw = response.read().decode()
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = raw
        return {'method': req.get_method(), 'path': path, 'status': response.status,
                'body': payload}


@contextmanager
def server(folder, env=None, port=8000):
    # Refuse to interfere with an unrelated service on this port.
    import socket
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1', port)) == 0:
            raise RuntimeError(f'Port {port} is already occupied')
    with tempfile.TemporaryFile(mode='w+') as log:
        process = subprocess.Popen([sys.executable, 'app.py'], cwd=ROOT / folder,
                                   env={**os.environ, **(env or {})},
                                   stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            for _ in range(100):
                if process.poll() is not None:
                    log.seek(0)
                    raise RuntimeError(log.read())
                try:
                    request('/', port=port)
                    break
                except (OSError, TimeoutError):
                    time.sleep(.15)
            else:
                raise RuntimeError('Server startup timed out')
            yield process
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()


def part1():
    with server('01-localhost-vs-production/develop'):
        develop = [request('/ask?question=Hello', method='POST'),
                   request('/ask', body={'question': 'Hello'}), request('/health')]
    with server('01-localhost-vs-production/production', {'ENVIRONMENT': 'staging'}):
        production = [request('/health'), request('/ready'),
                      request('/ask', body={'question': 'What is deployment?'}),
                      request('/ask', body={'question': ''})]
    return {'develop': develop, 'production': production}


def part4():
    key = 'local-example-key'
    with server('04-api-gateway/develop', {'AGENT_API_KEY': key}):
        api_key = [request('/ask', body={'question': 'Hello'}),
                   request('/ask', body={'question': 'Hello'},
                           headers={'X-API-Key': key})]
    with server('04-api-gateway/production'):
        login = request('/auth/token', body={'username': 'student', 'password': 'demo123'})
        token = login['body']['access_token']
        unauthorized = request('/ask', body={'question': 'Hello'})
        burst = [request('/ask', body={'question': 'Rate limit test'},
                         headers={'Authorization': f'Bearer {token}'}) for _ in range(20)]
        # JWT deliberately omitted from persisted evidence.
        return {'api_key': api_key, 'jwt_login_status': login['status'],
                'jwt_missing': unauthorized, 'burst': burst}


def part5():
    with server('05-scaling-reliability/develop') as process:
        checks = [request('/health'), request('/ready'),
                  request('/ask?question=Hello', method='POST')]
        os.kill(process.pid, signal.SIGTERM)
        code = process.wait(timeout=15)
    return {'checks': checks, 'sigterm_exit_code': code,
            'limitation': 'Idle shutdown only; in-flight shutdown tested by Part 6 checker.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('part', choices=['part1', 'part4', 'part5'])
    args = parser.parse_args()
    result = {'ran_at_utc': datetime.now(timezone.utc).isoformat(),
              'python': sys.version, 'os_name': os.name,
              **globals()[args.part]()}
    target = EVIDENCE / f'{args.part}.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
