#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../06-lab-complete/benchmark-observability/develop"
ci_log=$(mktemp "${RUNNER_TEMP:-/tmp}/day14-ci-agent.XXXXXX.log")
AGENT_VERSION=v2 MOCK_ERROR_RATE=0 MOCK_SLOW_RATE=0 PORT=8002 python app.py > "$ci_log" 2>&1 &
server_pid=$!
trap 'kill -TERM "$server_pid" 2>/dev/null || true; wait "$server_pid" 2>/dev/null || true' EXIT
for attempt in {1..50}; do
  if ! kill -0 "$server_pid" 2>/dev/null; then
    cat "$ci_log"
    exit 1
  fi
  if curl --fail --silent http://localhost:8002/health > /dev/null; then
    break
  fi
  sleep 0.2
done
curl --fail --silent http://localhost:8002/health > /dev/null
python eval/run_eval.py --url http://localhost:8002 --min-accuracy 1.0 \
  --baseline ../../../reports/eval_v2_fixed.json --out ../../../reports/ci-eval.json
