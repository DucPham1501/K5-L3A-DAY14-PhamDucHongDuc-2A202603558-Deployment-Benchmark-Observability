#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
.venv/bin/python scripts/check_question_metric.py
