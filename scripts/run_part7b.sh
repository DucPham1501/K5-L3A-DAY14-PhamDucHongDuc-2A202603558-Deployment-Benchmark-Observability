#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
.venv/bin/python scripts/run_observability.py "$@"
