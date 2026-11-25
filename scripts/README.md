# Chạy lại các bước LAB

Các script `.sh` chạy trong Ubuntu WSL2 từ repo hiện tại. Chúng lưu bằng chứng HTTP/JSON/CSV thật và dừng các stack demo khi phù hợp. Không sửa checker hoặc golden dataset.

| Script | Công việc |
|---|---|
| `bash scripts/check_lab.sh` | Một lệnh kiểm tra Part 6 + quality gate + artifacts, in tổng kết PASS/FAIL và giữ log mới riêng. Cloud kiểm tra riêng. |
| `bash scripts/check_environment.sh` | Kiểm tra Python/WSL/Docker. |
| `bash scripts/install_lab_dependencies.sh` | Cài dependencies vào `.venv` WSL có sẵn. |
| `bash scripts/run_part1.sh` | Chạy hai bản Part 1, lưu HTTP response. |
| `bash scripts/run_part2.sh` | Build hai image, chạy container và Compose qua Nginx, đo size. |
| `bash scripts/run_part4.sh` | Tạo môi trường riêng, test API key/JWT/20 request. |
| `bash scripts/capture_part4_http.sh` | Lưu raw `curl -i` 401/200/429, không ghi JWT. |
| `bash scripts/run_part5.sh` | Health/shutdown và stateless 3 instance; tự dừng stack. |
| `bash scripts/run_part6.sh` | Chạy checker đầy đủ có Docker; lưu output. |
| `bash scripts/run_part7a.sh baseline` | Load tests và eval v1/v2. Lưu ý baseline ban đầu đã đo trước sửa KB; code hiện tại đã sửa nên không tái tạo 21/23 bằng lệnh này. |
| `bash scripts/run_part7a.sh fixed` | Eval v2 100%, so với baseline đã lưu. |
| `bash scripts/check_question_metric.sh` | Kiểm chứng histogram question length theo Exercise 7.1. |
| `bash scripts/run_part7b.sh boot` | Build/start stack và test alert rules. |
| `bash scripts/run_part7b.sh scaling` | Locust 100 users, 2 phút với 1 và 3 instance. |
| `bash scripts/run_part7b.sh chaos` | Inject lỗi/chậm, đo thời gian hai alert cùng firing. |
| `bash scripts/run_part7b.sh traces` | Lấy trace theo log bằng Jaeger API v3; lưu wire OTLP và summary. |
| `bash scripts/run_part7b.sh experiments` | Thí nghiệm A–E riêng lẻ; tự unpause và khôi phục config. |
| `bash scripts/run_part7b.sh dashboard` | 2 instance, 30 users, ramp 5; snapshot các câu trả lời 7.4. |
| `bash scripts/run_part7b.sh live` | Giữ tải 30 users để chụp Grafana đang có traffic; dừng bằng stop khi chụp xong. |
| `bash scripts/run_part7b.sh stop` | Dừng headless load và stack của bài. |
| `bash scripts/finish_local_reports.sh` | Tạo bảng báo cáo từ raw JSON/CSV. |
| `.venv/bin/python scripts/verify_artifacts.py` | Kiểm tra bằng chứng và ghi rõ phần cloud còn thiếu. |
| `bash scripts/check_ci_gate.sh` | Chạy local đúng script của job CI, 100% và không regression. |
| `bash scripts/finalize_local.sh` | Tổng hợp, kiểm tra artifacts và dừng observability stack. |

Script ghi đè file report cùng tên khi chạy lại. Nếu muốn giữ nguyên bài nộp, thử nghiệm trong bản sao khác và giữ baseline cũ.

## Chụp giao diện thật trên Windows

Native Computer Use không kết nối được trong phiên làm bài này. Bằng chứng được chụp bằng Edge headless có sẵn, không vẽ lại dashboard.

PowerShell tại gốc repo:

```powershell
npm.cmd install --prefix .tools/browser playwright-core@1.65.1
node scripts/capture-ui.cjs all
node scripts/capture-ui.cjs error 'chat mock-llm-small' Details
.\scripts\capture-evidence.ps1 -Url 'http://localhost:3000/d/day14-agent-overview?from=now-5m&to=now&refresh=5s&kiosk' -Name 'grafana-dashboard.png'
```

Chụp khi service đang chạy và đã có tải. Nếu lấy trace mới, chụp lại ảnh để trace ID trong ảnh và báo cáo khớp nhau. `.tools/` chứa dependencies/profile local và được Git/Docker ignore.

## Railway

CLI được cài local bằng `npm.cmd install --prefix .tools/railway @railway/cli`. Học viên tự đăng nhập bằng `.\.tools\railway\node_modules\.bin\railway.cmd login --browserless`; không gửi password/token vào chat. Sau đó triển khai agent Part 6 và Redis theo `DEPLOYMENT.md`.
