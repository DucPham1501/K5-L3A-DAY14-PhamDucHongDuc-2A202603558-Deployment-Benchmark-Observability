"""Check submission evidence and report missing cloud work explicitly."""
import csv
import json
from pathlib import Path
import re
import struct
import subprocess
from run_examples import ROOT

names = ([f'load_v2_c{c}.json' for c in (1, 10, 50, 100)] +
         [f'load_v2_slow_{s}.json' for s in ('0', '0.03', '0.1')] +
         ['eval_v1.json', 'eval_v2.json', 'eval_v2_fixed.json'])
for name in names:
    root = ROOT / 'reports' / name
    original = ROOT / '06-lab-complete/benchmark-observability/develop/reports' / name
    assert root.read_bytes() == original.read_bytes(), f'Report copy differs: {name}'
    data = json.loads(root.read_text())
    if name.startswith('eval'):
        assert sum(item['passed'] for item in data['results']) == data['passed']
fixed = json.loads((ROOT / 'reports/eval_v2_fixed.json').read_text())
assert fixed['passed'] == fixed['total'] == 23
assert fixed['quality_gate']['passed'] and not fixed['quality_gate']['regressions']
for replicas in (1, 3):
    with (ROOT / f'benchmark-results/scale_{replicas}_stats.csv').open(newline='') as stream:
        aggregate = next(row for row in csv.DictReader(stream) if row['Name'] == 'Aggregated')
    assert int(aggregate['Request Count']) > 0 and float(aggregate['Requests/s']) > 0
for name in ('grafana-dashboard.png', 'jaeger-slow-trace.png', 'jaeger-error-trace.png',
             'prometheus-alert-firing.png'):
    raw = (ROOT / 'screenshots' / name).read_bytes()
    assert raw.startswith(b'\x89PNG\r\n\x1a\n')
    width, height = struct.unpack('>II', raw[16:24])
    assert width >= 800 and height >= 500
assert 'PASS 12/12' in (ROOT / 'reports/examples/part6-readiness.log').read_text()
protected = ['06-lab-complete/check_production_ready.py',
             '06-lab-complete/benchmark-observability/develop/eval/golden_dataset.jsonl']
for name in protected:
    original = subprocess.check_output(['git', '-c', f'safe.directory={ROOT}', 'show', f'HEAD:{name}'], cwd=ROOT)
    current = (ROOT / name).read_bytes().replace(b'\r\n', b'\n')
    assert original.replace(b'\r\n', b'\n') == current, f'Protected file modified: {name}'
patterns = [re.compile(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b'),
            re.compile(r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+'),
            re.compile(r'(?:sk-|ghp_)[A-Za-z0-9_-]{20,}')]
files = [ROOT / name for name in ('MISSION_ANSWERS.md', 'DEPLOYMENT.md', 'BENCHMARK_REPORT.md')]
files += [p for p in (ROOT / 'reports').rglob('*') if p.suffix in ('.json', '.log', '.txt', '.csv')]
findings = [str(p.relative_to(ROOT)) for p in files
            if any(pattern.search(p.read_text(encoding='utf-8', errors='replace')) for pattern in patterns)]
assert not findings, f'Review possible private data in artifacts: {findings}'
cloud_status = 'PENDING Railway authentication, deployment and public HTTP verification'
cloud_evidence = ROOT / 'reports/railway-deployment.json'
if cloud_evidence.exists():
    deployment = json.loads(cloud_evidence.read_text(encoding='utf-8'))
    cloud_status = deployment.get('status', 'PENDING') + ': ' + deployment.get('detail', '')
summary = {'local_evidence_valid': True, 'benchmark_json_count': len(names),
           'eval_fixed': '23/23, no regression', 'readiness': 'PASS 12/12',
           'observability_screenshots': 4, 'protected_files_unchanged': True,
           'credential_or_email_patterns_in_generated_text': False,
           'cloud_deployment': cloud_status,
           'missing_cloud_screenshots': [name for name in ('dashboard.png', 'running.png', 'test.png')
                                         if not (ROOT / 'screenshots' / name).exists()]}
(ROOT / 'reports/artifact-validation.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
