#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
# Part 4 requests a newer Pydantic than Part 6, so isolate its environment.
if [ ! -x 04-api-gateway/production/.venv/bin/python ]; then
  .venv/bin/python -m virtualenv --version >/dev/null 2>&1 || .venv/bin/python -m pip install virtualenv
  .venv/bin/python -m virtualenv 04-api-gateway/production/.venv
fi
04-api-gateway/production/.venv/bin/python -m pip install -r 04-api-gateway/production/requirements.txt
04-api-gateway/production/.venv/bin/python scripts/run_examples.py part4
