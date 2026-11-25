#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
.venv/bin/python --version
.venv/bin/python - <<'PY'
import importlib
import os
print('os.name:', os.name)
for name in ('fastapi', 'uvicorn', 'httpx', 'redis', 'jwt', 'prometheus_client'):
    try:
        module = importlib.import_module(name)
        print(name, getattr(module, '__version__', 'installed'))
    except ImportError:
        print(name, 'NOT INSTALLED')
PY
docker compose version
docker ps
