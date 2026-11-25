#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
.venv/bin/python - <<'PY'
import json
from pathlib import Path
import subprocess
rows = [json.loads(line) for line in subprocess.check_output(
    ['docker', 'image', 'ls', 'my-agent', '--format', '{{json .}}'], text=True).splitlines()]
Path('reports/examples/part2-image-list.json').write_text(json.dumps(rows, indent=2) + '\n')
PY
.venv/bin/python scripts/update_benchmark_report.py
