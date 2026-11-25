"""Reproduce CP7 experiments; preserve every JSON and console report."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from run_examples import ROOT, server

FOLDER = ROOT / '06-lab-complete/benchmark-observability/develop'
REPORTS = FOLDER / 'reports'
REPORTS.mkdir(exist_ok=True)


def run_job(script, args, name):
    print(f'Running {name}', flush=True)
    result = subprocess.run([sys.executable, script, *args], cwd=FOLDER,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (REPORTS / f'{name}.log').write_text(result.stdout, encoding='utf-8')
    print(result.stdout, flush=True)
    if result.returncode not in (0, 1):
        raise RuntimeError(f'{name} exited {result.returncode}')
    if not (REPORTS / f'{name}.json').exists():
        raise RuntimeError(f'{name} did not create its JSON report')
    return result.returncode


def load(name, concurrency):
    run_job('load_test.py', ['--url', 'http://localhost:8002', '--requests', '300',
                           '--concurrency', str(concurrency), '--out', f'reports/{name}.json'], name)


def evaluate(version, baseline=None, fixed=False):
    name = f'eval_{version}' + ('_fixed' if fixed else '')
    port = 8001 if version == 'v1' else 8002
    args = ['--url', f'http://localhost:{port}', '--out', f'reports/{name}.json']
    if baseline:
        args += ['--baseline', f'reports/{baseline}.json']
    if fixed:
        args += ['--min-accuracy', '1.0']
    return run_job('eval/run_eval.py', args, name)


def baseline():
    for slow in ('0', '0.03', '0.1'):
        with server(str(FOLDER.relative_to(ROOT)), {
            'AGENT_VERSION': 'v2', 'PORT': '8002', 'MOCK_SLOW_RATE': slow,
        }, port=8002):
            if slow == '0.03':
                for concurrency in (1, 10, 50, 100):
                    load(f'load_v2_c{concurrency}', concurrency)
                evaluate('v2')
            load(f'load_v2_slow_{slow}', 20)
    with server(str(FOLDER.relative_to(ROOT)), {'AGENT_VERSION': 'v1', 'PORT': '8001'}, port=8001):
        evaluate('v1')
    # Compare the saved initial reports without overwriting the v2 baseline.
    from importlib.util import module_from_spec, spec_from_file_location
    spec = spec_from_file_location('lab_eval', FOLDER / 'eval/run_eval.py')
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    v1 = json.loads((REPORTS / 'eval_v1.json').read_text())
    v2 = json.loads((REPORTS / 'eval_v2.json').read_text())
    regressions = module.compare_with_baseline(v2, v1)
    (REPORTS / 'initial-comparison.json').write_text(json.dumps({
        'baseline': 'eval_v1.json', 'current': 'eval_v2.json', 'regressions': regressions,
    }, indent=2), encoding='utf-8')


def fixed():
    with server(str(FOLDER.relative_to(ROOT)), {'AGENT_VERSION': 'v2', 'PORT': '8002'}, port=8002):
        if evaluate('v2', 'eval_v2', fixed=True):
            raise RuntimeError('The final quality gate failed; inspect eval_v2_fixed.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['baseline', 'fixed'])
    args = parser.parse_args()
    globals()[args.stage]()
    destination = ROOT / 'reports'
    for path in REPORTS.iterdir():
        if path.is_file():
            shutil.copy2(path, destination / path.name)
    template = ROOT / '06-lab-complete/benchmark-observability/BENCHMARK_REPORT_TEMPLATE.md'
    if not (ROOT / 'BENCHMARK_REPORT.md').exists():
        shutil.copy2(template, ROOT / 'BENCHMARK_REPORT.md')
