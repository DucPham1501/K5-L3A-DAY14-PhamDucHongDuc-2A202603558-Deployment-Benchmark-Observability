#!/usr/bin/env bash
set -eu
python3 --version
command -v uv || true
python3 -m pip --version || true
python3 -m ensurepip --version || true
ls /usr/bin/python* /usr/share/python-wheels/* 2>/dev/null || true
