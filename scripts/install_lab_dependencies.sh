#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
if ! .venv/bin/python -m pip --version; then
  curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/day14-get-pip.py
  .venv/bin/python /tmp/day14-get-pip.py
fi
.venv/bin/python -m pip install \
  -r 06-lab-complete/requirements.txt \
  -r 05-scaling-reliability/production/requirements.txt \
  -r 06-lab-complete/benchmark-observability/develop/requirements.txt
