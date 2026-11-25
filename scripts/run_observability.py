"""CP8 operations with repeatable configuration and raw evidence."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.parse
import urllib.request

from run_examples import ROOT
from run_part2 import command, wait, service_snapshot

FOLDER = ROOT / '06-lab-complete/benchmark-observability/production'
OUT = ROOT / 'reports/observability'
OUT.mkdir(parents=True, exist_ok=True)
COMPOSE = ['docker', 'compose', '-p', 'k5-day14-observability']
DEFAULT = {'AGENT_VERSION': 'v2', 'LLM_MODEL': 'mock-llm-small',
           'MOCK_ERROR_RATE': '0.01', 'MOCK_SLOW_RATE': '0.03'}


def get_json(url):
    with urllib.request.urlopen(url, timeout=15) as response:
        return json.load(response)


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def configure(overrides=None, replicas=3, build=False):
    env = {**os.environ, **DEFAULT, **(overrides or {})}
    args = COMPOSE + ['up', '-d', '--scale', f'agent={replicas}']
    if build:
        args += ['--build']
    result = subprocess.run(args, cwd=FOLDER, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (OUT / 'latest-up.log').write_text(result.stdout, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(result.stdout[-5000:])
    wait('/health', 8080)
    # Both Nginx and Prometheus discover changed replicas through DNS.
    time.sleep(15)


def locust(users, duration, name, background=False, ramp=10):
    args = COMPOSE + ['run', '--rm', '--no-deps', 'locust', '-f', '/mnt/locust/locustfile.py',
                      '--host', 'http://nginx', '--headless', '-u', str(users), '-r', str(ramp),
                      '-t', duration, '--csv', f'/mnt/results/{name}']
    target = (OUT / f'{name}.log').open('w')
    process = subprocess.Popen(args, cwd=FOLDER, stdout=target, stderr=subprocess.STDOUT)
    target.close()
    if background:
        return process
    code = process.wait()
    if code not in (0, 1):
        raise RuntimeError(f'Locust exited {code}; inspect {name}.log')
    print(f'Locust {name} finished, exit={code}', flush=True)


def boot():
    print('Building and starting observability stack', flush=True)
    configure(replicas=1, build=True)
    save('services.json', service_snapshot(COMPOSE, FOLDER))
    command(['docker', 'run', '--rm', '-v', f'{FOLDER}/prometheus:/p',
             '--entrypoint', 'promtool', 'prom/prometheus:v3.16.0',
             'test', 'rules', '/p/alert_rules_test.yml'], log='part7-alert-unit-tests.log')
    print('Stack and alert-rule tests ready', flush=True)


def scaling():
    (ROOT / 'benchmark-results').mkdir(exist_ok=True)
    for replicas in (1, 3):
        print(f'Scaling measurement: {replicas} instance(s)', flush=True)
        configure(replicas=replicas)
        locust(100, '2m', f'scale_{replicas}')
    for path in (FOLDER / 'benchmark-results').glob('scale_*'):
        shutil.copy2(path, ROOT / 'benchmark-results' / path.name)
    save('scaling-config.json', {'configuration': DEFAULT, 'users': 100, 'ramp_up': 10,
                                'duration_per_run': '2m', 'ran_at_utc': datetime.now(timezone.utc).isoformat()})


def traces():
    logs = command(COMPOSE + ['logs', '--no-color', '--no-log-prefix', 'agent'], FOLDER)
    events = []
    for line in logs.splitlines()[-5000:]:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get('trace_id'):
            events.append(event)
    slow_calls = sorted([e for e in events if e.get('event') == 'llm_call'],
                        key=lambda e: e.get('llm_ms', 0), reverse=True)
    error_calls = [e for e in reversed(events) if e.get('event') == 'llm_error']
    time.sleep(6)  # allow the OTel batch exporter to flush the newest traces
    selected = {}
    for kind, candidates in [('slow', slow_calls), ('error', error_calls)]:
        for candidate in candidates[:20]:
            trace_id = candidate['trace_id']
            try:
                wire = get_json(f'http://localhost:16686/api/v3/traces/{trace_id}')
            except urllib.error.HTTPError:
                continue
            spans = []
            for resource in wire.get('result', wire).get('resourceSpans', []):
                for scope in resource.get('scopeSpans', []):
                    for span in scope.get('spans', []):
                        spans.append({
                            'spanID': span['spanId'], 'operationName': span['name'],
                            'duration': (int(span['endTimeUnixNano']) - int(span['startTimeUnixNano'])) / 1000,
                            'references': [{'spanID': span['parentSpanId']}] if span.get('parentSpanId') else [],
                            'status': span.get('status'), 'attributes': span.get('attributes', []),
                            'events': span.get('events', []),
                        })
            if spans:
                save(f'{kind}-trace-otlp.json', wire)
                selected[kind] = {'traceID': trace_id, 'spans': spans}
                break
        else:
            raise RuntimeError(f'No {kind} trace could be fetched through Jaeger v3')
    save('selected-traces.json', selected)
    matches = {}
    for kind, trace in selected.items():
        if trace:
            matches[kind] = [line for line in logs.splitlines() if trace['traceID'] in line]
    save('trace-log-matches.json', matches)
    print('Selected traces:', {k: t['traceID'] if t else None for k, t in selected.items()}, flush=True)


def chaos():
    overrides = {'MOCK_ERROR_RATE': '0.2', 'MOCK_SLOW_RATE': '0.3'}
    started = time.monotonic()
    start_utc = datetime.now(timezone.utc).isoformat()
    configure(overrides)
    process = locust(30, '10m', 'chaos', background=True)
    history = []
    first = {}
    wanted = {'AgentHighErrorRate', 'AgentHighLatencyP95'}
    for _ in range(72):
        time.sleep(5)
        alerts = get_json('http://localhost:9090/api/v1/alerts')
        seconds = round(time.monotonic() - started, 1)
        history.append({'elapsed_s': seconds, 'response': alerts})
        firing = set()
        for alert in alerts['data']['alerts']:
            name = alert['labels']['alertname']
            if alert['state'] == 'firing':
                firing.add(name)
                first.setdefault(name, seconds)
        save('chaos-alerts.json', {'changed_at_utc': start_utc, 'configuration': overrides,
                                 'first_firing_s': first, 'polls': history})
        print(f'Chaos elapsed={seconds}s firing={sorted(firing)}', flush=True)
        if wanted <= firing:
            save('both-alerts-firing.json', alerts)
            traces()
            # Keep this run alive for actual UI screenshots; its own 10m deadline cleans up the job.
            save('chaos-load-process.json', {'pid': process.pid, 'duration': '10m'})
            print('Both alerts firing; capture UI screenshots now.', flush=True)
            return
    raise RuntimeError('Both alerts did not fire together within the observation window')


def stop():
    ids = command(['docker', 'ps', '-q', '--filter', 'label=com.docker.compose.project=k5-day14-observability',
                   '--filter', 'label=com.docker.compose.oneoff=True']).split()
    if ids:
        command(['docker', 'stop', *ids])
    command(COMPOSE + ['down'], FOLDER)


def experiments():
    # End our previous headless run before starting the isolated experiments.
    ids = command(['docker', 'ps', '-q', '--filter', 'label=com.docker.compose.project=k5-day14-observability',
                   '--filter', 'label=com.docker.compose.oneoff=True']).split()
    if ids:
        command(['docker', 'stop', *ids])
    process = locust(30, '20m', 'isolated-experiments', background=True)
    measurements = []
    cases = [
        ('A', {'MOCK_ERROR_RATE': '0.2'}, 'AgentHighErrorRate', 150),
        ('B', {'MOCK_SLOW_RATE': '0.3'}, 'AgentHighLatencyP95', 210),
        ('C', {'LLM_MODEL': 'mock-llm-large'}, 'LLMCostBurnRateHigh', 210),
        ('D', {}, 'AgentInstanceDown', 100),
        ('E', {'AGENT_VERSION': 'v1'}, None, 70),
    ]
    for label, overrides, wanted, timeout in cases:
        print(f'Experiment {label}: {overrides}', flush=True)
        configure(overrides)
        started = time.monotonic()
        paused = None
        if label == 'D':
            paused = command(COMPOSE + ['ps', '-q', 'agent'], FOLDER).splitlines()[0]
            command(['docker', 'pause', paused])
        observations = []
        first = {}
        try:
            while time.monotonic() - started < timeout:
                time.sleep(5)
                alerts = get_json('http://localhost:9090/api/v1/alerts')
                elapsed = round(time.monotonic() - started, 1)
                firing = []
                for item in alerts['data']['alerts']:
                    if item['state'] == 'firing':
                        name = item['labels']['alertname']
                        firing.append(name)
                        first.setdefault(name, elapsed)
                observations.append({'elapsed_s': elapsed, 'alerts': alerts})
                print(f'Experiment {label}: {elapsed}s, firing={firing}', flush=True)
                if wanted and wanted in first:
                    break
            metrics = {}
            queries = {
                'p95_s': 'histogram_quantile(0.95,sum by(le)(rate(http_request_duration_seconds_bucket{job="agent",route="/ask"}[1m])))',
                'error_rate': 'sum(rate(http_requests_total{job="agent",route="/ask",status=~"5.."}[1m])) / sum(rate(http_requests_total{job="agent",route="/ask"}[1m]))',
                'cost_usd_per_hour': 'sum(rate(llm_cost_usd_total{job="agent"}[5m]))*3600',
                'versions': 'agent_info',
            }
            for name, query in queries.items():
                metrics[name] = get_json('http://localhost:9090/api/v1/query?' + urllib.parse.urlencode({'query': query}))
            entry = {'experiment': label, 'configuration': {**DEFAULT, **overrides},
                     'first_firing_s': first, 'observation_seconds': round(time.monotonic() - started, 1),
                     'observations': observations, 'metrics': metrics,
                     'timing_origin': 'after configure and 15s DNS settling; D: immediately before pause'}
            if label == 'E':
                eval_folder = ROOT / '06-lab-complete/benchmark-observability/develop'
                evaluation = subprocess.run([str(ROOT / '.venv/bin/python'), 'eval/run_eval.py',
                    '--url', 'http://localhost:8080', '--api-key', 'day14-lab-key',
                    '--out', str(OUT / 'experiment-E-eval.json')], cwd=eval_folder,
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                (OUT / 'experiment-E-eval.log').write_text(evaluation.stdout, encoding='utf-8')
                entry['eval_exit_code'] = evaluation.returncode
            measurements.append(entry)
            save('isolated-experiments.json', measurements)
        finally:
            if paused:
                command(['docker', 'unpause', paused])
    ids = command(['docker', 'ps', '-q', '--filter', 'label=com.docker.compose.project=k5-day14-observability',
                   '--filter', 'label=com.docker.compose.oneoff=True']).split()
    if ids:
        command(['docker', 'stop', *ids])
    configure()
    print('Isolated experiments complete; normal configuration restored.', flush=True)


def dashboard():
    from run_examples import request
    configure(replicas=2)
    locust(30, '3m', 'dashboard', background=True, ramp=5)
    for second in range(0, 60, 10):
        time.sleep(10)
        print(f'Dashboard warmup: {second + 10}s', flush=True)
    queries = {
        'p95_s': 'histogram_quantile(0.95,sum by(le)(rate(http_request_duration_seconds_bucket{job="agent",route="/ask"}[1m])))',
        'avg_s': 'sum(rate(http_request_duration_seconds_sum{job="agent",route="/ask"}[1m]))/sum(rate(http_request_duration_seconds_count{job="agent",route="/ask"}[1m]))',
        'requests_per_instance': 'sum by(instance)(rate(http_requests_total{job="agent",route="/ask"}[1m]))',
        'tokens_per_second': 'sum by(type)(rate(llm_tokens_total{job="agent"}[1m]))',
    }
    data = {'observed_at_utc': datetime.now(timezone.utc).isoformat(),
            'replicas': 2, 'users': 30, 'ramp': 5,
            'public_metrics': request('/metrics', port=8080), 'queries': {}}
    for name, query in queries.items():
        data['queries'][name] = get_json('http://localhost:9090/api/v1/query?' + urllib.parse.urlencode({'query': query}))
    save('dashboard-observations.json', data)
    print('Exercise 7.4 snapshot ready; capture Grafana within the next two minutes.', flush=True)


def live():
    configure(replicas=2)
    locust(30, '15m', 'dashboard-live', background=True, ramp=5)
    for _ in range(3):
        time.sleep(10)
        print('Keeping real load active for screenshot capture', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['boot', 'scaling', 'chaos', 'traces', 'experiments', 'dashboard', 'live', 'stop'])
    args = parser.parse_args()
    globals()[args.stage]()
