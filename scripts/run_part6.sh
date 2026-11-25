#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p reports/examples
cd 06-lab-complete
../.venv/bin/python check_production_ready.py "$@" 2>&1 | tee ../reports/examples/part6-readiness.log
