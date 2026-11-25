#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
04-api-gateway/production/.venv/bin/python scripts/capture_part4_http.py
