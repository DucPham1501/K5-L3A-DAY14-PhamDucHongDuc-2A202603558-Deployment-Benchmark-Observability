"""Run supplied reliability and stateless demos, then clean up our stack."""
from datetime import datetime, timezone
import json
import subprocess
import sys

from run_examples import ROOT, EVIDENCE, part5
from run_part2 import command, wait, service_snapshot

result = {'ran_at_utc': datetime.now(timezone.utc).isoformat(), **part5()}
folder = ROOT / '05-scaling-reliability/production'
(folder / '.env.local').touch(exist_ok=True)
compose = ['docker', 'compose', '-p', 'k5-day14-scaling']
try:
    command(compose + ['up', '-d', '--build', '--scale', 'agent=3'], folder, 'part5-compose-up.log')
    wait('/health', 8080)
    output = command([sys.executable, 'test_stateless.py'], folder, 'part5-stateless.log')
    print(output)
    result['stateless_output_file'] = 'reports/examples/part5-stateless.log'
    result['services'] = service_snapshot(compose, folder)
finally:
    command(compose + ['logs', '--no-color'], folder, 'part5-compose.log')
    command(compose + ['down'], folder)
(EVIDENCE / 'part5.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
