#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/../06-lab-complete/benchmark-observability/production"
docker compose -p k5-day14-observability ps --all
docker compose -p k5-day14-observability logs --tail 65 agent
