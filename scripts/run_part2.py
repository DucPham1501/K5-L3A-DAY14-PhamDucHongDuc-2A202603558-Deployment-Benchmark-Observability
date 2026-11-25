"""Build the supplied Docker examples and record sizes and real HTTP results."""
from datetime import datetime, timezone
import json
import subprocess
import time

from run_examples import ROOT, EVIDENCE, request


def command(args, cwd=ROOT, log=None):
    result = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    if log:
        (EVIDENCE / log).write_text(result.stdout, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(f'{args}:\n{result.stdout[-5000:]}')
    return result.stdout


def wait(path, port, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = request(path, port=port)
            if result['status'] == 200:
                return result
        except OSError:
            pass
        time.sleep(2)
    raise RuntimeError(f'Service not ready: {port}{path}')


def service_snapshot(compose, folder):
    raw = command(compose + ['ps', '--format', 'json'], folder)
    fields = ('Name', 'Image', 'State', 'Health', 'Ports', 'Service')
    return [{key: item.get(key) for key in fields}
            for item in (json.loads(line) for line in raw.splitlines() if line.strip())]


def main():
    sizes = {}
    for variant, folder in [('develop', 'develop'), ('advanced', 'production')]:
        print(f'Building my-agent:{variant}', flush=True)
        command(['docker', 'build', '-f', f'02-docker/{folder}/Dockerfile',
                 '-t', f'my-agent:{variant}', '.'], log=f'part2-build-{variant}.log')
        details = json.loads(command(['docker', 'image', 'inspect', f'my-agent:{variant}']))[0]
        sizes[variant] = {'bytes': details['Size'], 'image_id': details['Id']}
    name = 'day14-lab-part2-develop'
    command(['docker', 'run', '-d', '--name', name, '-p', '8000:8000', 'my-agent:develop'])
    try:
        wait('/', 8000)
        develop = request('/ask?question=What%20is%20Docker', method='POST')
    finally:
        command(['docker', 'stop', name])
        command(['docker', 'rm', name])
    folder = ROOT / '02-docker/production'
    (folder / '.env.local').touch(exist_ok=True)
    compose = ['docker', 'compose', '-p', 'k5-day14-docker']
    try:
        print('Starting Part 2 Compose stack', flush=True)
        command(compose + ['up', '-d', '--build'], folder, 'part2-compose-up.log')
        health = wait('/health', 80)
        ask = request('/ask', port=80, body={'question': 'Explain microservices'})
        services = service_snapshot(compose, folder)
        (EVIDENCE / 'part2-services.jsonl').write_text(
            '\n'.join(json.dumps(item) for item in services) + '\n', encoding='utf-8')
    finally:
        command(compose + ['logs', '--no-color'], folder, 'part2-compose.log')
        command(compose + ['down'], folder)
    result = {'ran_at_utc': datetime.now(timezone.utc).isoformat(), 'images': sizes,
              'reduction_percent': (1 - sizes['advanced']['bytes'] / sizes['develop']['bytes']) * 100,
              'develop_api': develop, 'nginx_health': health, 'nginx_ask': ask}
    (EVIDENCE / 'part2.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
