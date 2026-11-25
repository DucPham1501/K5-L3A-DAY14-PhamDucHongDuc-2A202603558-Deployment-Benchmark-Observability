#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
PATH="$PWD/.venv/bin:$PATH" bash scripts/ci_quality_gate.sh
