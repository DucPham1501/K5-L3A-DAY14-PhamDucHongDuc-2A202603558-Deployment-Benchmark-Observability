#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
trap '.venv/bin/python scripts/run_observability.py stop' EXIT
bash scripts/finish_local_reports.sh
.venv/bin/python scripts/verify_artifacts.py
