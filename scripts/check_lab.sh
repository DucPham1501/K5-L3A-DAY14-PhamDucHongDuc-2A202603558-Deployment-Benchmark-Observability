#!/usr/bin/env bash
# Run the local acceptance checks without replacing the original lab evidence.
set -uo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  printf 'Thiếu Python WSL trong .venv. Làm bước chuẩn bị ở README.md trước.\n'
  exit 1
fi
mkdir -p reports/checks

printf '\n=== 1/3: PART 6 — PRODUCTION READINESS ===\n'
(
  cd 06-lab-complete
  ../.venv/bin/python check_production_ready.py
) 2>&1 | tee reports/checks/latest-readiness.log
readiness_code=${PIPESTATUS[0]}

printf '\n=== 2/3: PART 7 — QUALITY GATE ===\n'
bash scripts/check_ci_gate.sh 2>&1 | tee reports/checks/latest-quality-gate.log
quality_code=${PIPESTATUS[0]}

printf '\n=== 3/3: SUBMISSION EVIDENCE ===\n'
.venv/bin/python scripts/verify_artifacts.py 2>&1 | tee reports/checks/latest-artifacts.log
artifacts_code=${PIPESTATUS[0]}

printf '\n========== KẾT QUẢ KIỂM TRA LOCAL ==========\n'
result=0
for item in "Part 6:$readiness_code" "Quality gate:$quality_code" "Artifacts:$artifacts_code"; do
  label=${item%:*}
  code=${item##*:}
  if [ "$code" -eq 0 ]; then
    printf 'PASS — %s\n' "$label"
  else
    printf 'FAIL — %s (exit code %s)\n' "$label" "$code"
    result=1
  fi
done
if [ "$result" -eq 0 ]; then
  printf '\nLOCAL CHECKS PASS\n'
fi
printf '\nCloud: lệnh này không xác minh URL public. Xem trạng thái và 4 lệnh test trong DEPLOYMENT.md.\n'
printf 'Log lần kiểm tra này: reports/checks/\n'
exit "$result"
