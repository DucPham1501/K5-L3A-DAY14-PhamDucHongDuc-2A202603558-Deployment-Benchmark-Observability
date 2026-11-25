# Day 14 — Mission Answers

> Trạng thái: đang thực hiện theo CHECKPOINTS.md của lớp K5. Chỉ ghi nhận số đo sau khi chạy; các phần chưa chạy được đánh dấu rõ.

## Part 1: Localhost vs Production

### Exercise 1.1 — Anti-patterns trong develop/app.py

| Code/vị trí | Vấn đề | Hậu quả và hướng sửa |
|---|---|---|
| `OPENAI_API_KEY = ...` | API key được viết trực tiếp trong source | Dễ lộ qua Git; lấy secret từ môi trường. Key trong ví dụ là giả. |
| `DATABASE_URL = ...` | Hardcode cả mật khẩu, host database và cấu hình kết nối | Không dùng chung được giữa local/staging/cloud; cấu hình qua env và quản lý secret riêng. |
| `DEBUG = True`, `MAX_TOKENS = 500` | Cấu hình cố định trong source | Phải sửa code khi đổi môi trường; đưa các giá trị cần thay đổi sang config. |
| `print(... OPENAI_API_KEY ...)` | Ghi secret vào log | Người có quyền đọc log có thể lấy credential; bỏ secret khỏi log. |
| Các câu `print()` trong `ask_agent` | Log không có cấu trúc, level, timestamp hay request ID | Khó tìm và tổng hợp sự cố; dùng logging với JSON formatter. |
| Không khai báo `/health`, `/ready` | Thiếu liveness/readiness | Platform không có endpoint kiểm tra sống và sẵn sàng; bổ sung hai endpoint riêng. |
| `host="localhost"` | Chỉ bind loopback | Reverse proxy/container network không truy cập được; bind `0.0.0.0`. |
| `port=8000` | Cổng cố định | Không nhận cổng cloud cấp; đọc `PORT`. |
| `reload=True` | Bật theo dõi và nạp lại source | Tạo process phụ, không phù hợp production; tắt reload ở production. |
| Không có lifecycle cleanup | Không chỉ rõ cách đóng tài nguyên lúc shutdown | Dùng lifespan và phối hợp cơ chế chờ request của Uvicorn. |

### Exercise 1.2 — Kết quả chạy

Đã chạy thật trong Ubuntu WSL2, Python 3.12.3 (`os.name=posix`). Bằng chứng: [part1.json](reports/examples/part1.json).

| Phiên bản | Request | HTTP thực tế | Kết luận |
|---|---|---:|---|
| Develop | `POST /ask?question=Hello` | 200 | question phải truyền qua query. |
| Develop | `POST /ask` với JSON question | 422 | JSON không đáp ứng tham số query bắt buộc. |
| Develop | `GET /health` | 404 | Chưa có health endpoint. |
| Production | `GET /health` | 200 | Có status/uptime/version/environment. |
| Production | `GET /ready` | 200 | Hoàn tất khởi tạo. |
| Production | `POST /ask` với JSON hợp lệ | 200 | Nhận JSON và trả lời mock LLM. |
| Production | `POST /ask` với question rỗng | 422 | Có xử lý input rỗng. |

### Exercise 1.3 — So sánh code

| Feature | Develop | Production | Vì sao quan trọng |
|---|---|---|---|
| Config | Giá trị trong `app.py` | `Settings` trong `config.py`, đọc `os.getenv` | Đổi môi trường không cần sửa source. |
| Network | localhost:8000 | HOST mặc định 0.0.0.0, PORT từ env | Container/cloud truy cập được và dùng đúng cổng. |
| Reload | Luôn bật | Theo `DEBUG`, mặc định false | Chỉ bật reload khi phát triển. |
| Secret trong log | In API key | Chỉ log độ dài câu hỏi và câu trả lời | Tránh lộ credential qua log. |
| Logging | print | logging và thông tin sự kiện | Dễ thu thập; tuy nhiên JSON formatter mẫu còn hạn chế, xem ghi chú dưới. |
| Liveness | Không có `/health` | `/health` trả status, uptime, version, environment | Kiểm tra process hoạt động. |
| Readiness | Không có `/ready` | `/ready` kiểm cờ `is_ready` | Có thể tách trạng thái khởi tạo khỏi trạng thái process sống. |
| Lifecycle | Không có cleanup rõ ràng | lifespan startup/shutdown | Có điểm khởi tạo và đóng tài nguyên. |
| Input | question qua query | Đọc JSON và từ chối question rỗng bằng 422 | Giao diện request và lỗi rõ hơn. |

**Giới hạn của mẫu production:** `/ready` mới kiểm cờ trong process, chưa ping Redis. Formatter nhúng `%(message)s` vào JSON bằng nối chuỗi; khi message chứa JSON/dấu nháy, dòng log có thể không còn là JSON hợp lệ. Part 6 sẽ dùng `json.dumps` cho toàn bộ record và kiểm readiness thật. Việc có handler SIGTERM/lifespan trong source chưa tự chứng minh request đang xử lý được hoàn tất; cần test runtime.

## Part 2: Docker

### Exercise 2.1 — Dockerfile develop

1. Base image: `python:3.11`.
2. Working directory: `/app`.
3. Copy requirements trước source để Docker tái sử dụng layer cài dependencies khi chỉ đổi code. Khi requirements đổi, layer cài lại và các layer sau bị invalidated.
4. `CMD` là lệnh/tham số mặc định, có thể thay khi `docker run`. `ENTRYPOINT` xác định executable chính; đối số sau tên image thường bổ sung/thay CMD. Exec form truyền signal trực tiếp, shell form cần `exec` để process ứng dụng nhận signal đúng.

### Exercise 2.2–2.3 — Build và dung lượng đo thực tế

Đã build từ gốc repo bằng `docker build -f ... .`, chạy container develop và gọi `/ask?question=...` nhận 200.

| Image | Size theo `docker image inspect`, bytes | MB thập phân |
|---|---:|---:|
| `my-agent:develop` | 426320021 | 426.32 |
| `my-agent:advanced` | 57409069 | 57.41 |

Theo trường Size của image inspect, giảm **86.53%**, tính bằng `(426320021 - 57409069) / 426320021 * 100`.

Đối chiếu thêm đúng lệnh `docker images` mà đề yêu cầu: develop hiển thị **1.67 GB**, advanced **240 MB** (VirtualSize chi tiết tương ứng 1.668 GB và 239.8 MB). Dựa trên VirtualSize đã làm tròn, mức giảm khoảng **85.62%**. Docker Desktop image store báo hai cách tính khác nhau giữa image inspect và image list; không dùng lẫn hai cách tính trong cùng phép so sánh. Bằng chứng lệnh image list: [part2-image-list.json](reports/examples/part2-image-list.json). Các số đều là kết quả máy báo, không lấy từ README.

Builder dùng base slim, cài gcc/libpq-dev và dependencies. Runtime dùng base slim, chỉ copy packages đã cài và source cần chạy; không mang build tools sang. User non-root giảm quyền của process trong container. Multi-stage hữu ích khi tách được build artifacts khỏi build toolchain; mức giảm trong bài còn đến từ việc đổi full image sang slim.

### Exercise 2.4 — Compose stack

```text
Client → Nginx :80 → agent :8000
                       ├── REDIS_URL → Redis :6379
                       └── QDRANT_URL → Qdrant :6333
```

Compose khởi động agent, Redis, Qdrant và Nginx trong mạng internal. Chỉ Nginx publish cổng host; agent dùng tên service để định vị dependencies. Redis dành cho cache/state, Qdrant dành cho vector search. App mock ở Part 2 chỉ nhận các URL qua env, chưa thực hiện truy vấn Redis/Qdrant; không suy diễn rằng request demo đã đi qua hai database này.

Kết quả thật qua Nginx: `GET /health` **200**, `POST /ask` với JSON **200**. Bằng chứng: [part2.json](reports/examples/part2.json), [service status](reports/examples/part2-services.jsonl), các log build và compose trong `reports/examples/`. Stack đã được dừng sau khi thu bằng chứng.

## Part 3: Cloud Deployment

### Exercise 3.1 / 3.2 — Triển khai chính

Đã đổi sang tài khoản Railway mới do học viên xác nhận và deploy thành công agent Part 6 cùng Redis cloud ngày 25/11/2026. URL: https://agent-production-36599cd4.up.railway.app. Bốn kiểm tra public đạt `/health` 200, `/ready` 200, `POST /ask` thiếu key 401, đúng key 200. Bằng chứng thật ở [railway-deployment.json](reports/railway-deployment.json) và [railway-http.json](reports/railway-http.json). Không kích hoạt gói trả phí.

Đã upload `06-lab-complete/` bằng `--path-as-root`, dùng Dockerfile Part 6. Agent dùng reference Redis private; domain trỏ cổng 8080 đúng với PORT runtime. Chi tiết và lệnh test trong [DEPLOYMENT.md](DEPLOYMENT.md).

### So sánh railway.toml và render.yaml

| Nội dung | Railway | Render |
|---|---|---|
| Định dạng | TOML, các bảng build/deploy | YAML, danh sách services và envVars |
| Build | builder DOCKERFILE, Dockerfile path | runtime docker, rootDir/dockerfilePath/dockerContext |
| Health | healthcheckPath=/health | healthCheckPath=/health |
| Secret | Đặt Variables/reference trên project service | generateValue cho API key; sync:false yêu cầu nhập Redis URL |
| Redis | Service Redis riêng, nối bằng reference variable | Provision Redis riêng và điền REDIS_URL |
| Build context repo này | Upload riêng Part 6 bằng path-as-root hoặc cấu hình root directory | rootDir=06-lab-complete, Blueprint path trỏ file trong thư mục đó |

Hai cấu hình mô tả cùng ứng dụng nhưng schema khác nhau. Chọn một nền tảng để deploy; không cần triển khai cả hai để hoàn thành bài.

### Exercise 3.3 — Đọc pipeline Cloud Run

1. `cloudbuild.yaml` mô tả stage test: cài requirements/pytest rồi chạy `pytest tests/`.
2. Build Docker image, gắn tag theo COMMIT_SHA và latest, dùng cache từ image trước.
3. Push các tag lên registry rồi dùng gcloud deploy image commit lên Cloud Run ở asia-southeast1.
4. Deploy đặt tài nguyên, min/max instances, timeout, ENVIRONMENT và đọc secret từ Secret Manager; `service.yaml` mô tả cấu hình service tương ứng để tham khảo.
5. Đây là đọc cấu hình mẫu, chưa chạy pipeline hoặc deploy GCP. Bước test mẫu chưa bật `set -e`; khi tái sử dụng cần bảo đảm pytest thất bại thực sự làm stage thất bại, không bị lệnh echo phía sau che exit code.

## Part 4: API Security

### Exercise 4.1–4.3 — Kết quả HTTP thực tế

Đã chạy hai app mẫu trong WSL2. Part 4 production được cài trong môi trường riêng vì requirements yêu cầu Pydantic mới hơn Part 6. Bằng chứng đầy đủ: [part4.json](reports/examples/part4.json); output đúng định dạng `curl -i`: [part4-curl.txt](reports/examples/part4-curl.txt). Token chỉ giữ trong bộ nhớ runner, không ghi vào report.

```text
API key: POST /ask, thiếu key → HTTP 401
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

API key: POST /ask, đúng key → HTTP 200, có answer
JWT: POST /auth/token, student/demo123 → HTTP 200
JWT: POST /ask, thiếu bearer token → HTTP 401
JWT: 20 request liên tiếp với cùng token → 10 lần HTTP 200, sau đó 10 lần HTTP 429
429 detail: Rate limit exceeded; limit=10; window_seconds=60
```

JWT flow: đăng nhập → server ký token có subject, role, issued-at, expiry → client gửi Bearer token → server xác minh chữ ký và thời hạn. Key rotation của API key thực hiện bằng đổi biến môi trường và restart/redeploy; đổi JWT signing secret khiến token ký bằng secret cũ không xác minh được nếu không triển khai cơ chế chuyển tiếp.

Rate limiter dùng deque timestamp, loại request ngoài 60 giây rồi đếm số còn lại (sliding-window log). User tối đa 10 req/phút, admin 100 req/phút; admin được quota cao hơn chứ không được bỏ qua giới hạn hoàn toàn. State hiện ở RAM, nên mỗi worker có bộ đếm riêng và restart làm mất bộ đếm.

### Exercise 4.4 — Cost guard

Mẫu hiện tại dùng budget **$1/ngày/user**, **$10/ngày toàn cục**, không phải $10/tháng như đoạn minh hoạ cũ trong CODE_LAB. Trước gọi LLM, `check_budget` kiểm tổng đã dùng; sau gọi, `record_usage` cộng input/output token và chi phí. Vượt user budget trả 402, vượt global budget của mẫu trả 503.

Muốn dùng Redis và reset hàng tháng: key gồm user và tháng UTC (`budget:<user>:YYYY-MM`), lưu chi phí tập trung, đặt TTL tới kỳ mới. Khi nhiều request đồng thời, thao tác kiểm tra/reserve phải nguyên tử nếu cần chặn tuyệt đối việc vượt budget. Part 6 dùng daily budget theo hợp đồng, không cần đổi thành monthly.

Hai lớp giải quyết hai vấn đề khác nhau: rate limit giới hạn tốc độ gọi, cost guard giới hạn chi phí tích luỹ. Request ít nhưng nhiều token vẫn có thể đắt; request rẻ nhưng quá nhanh vẫn có thể làm quá tải.

**Nhận xét code mẫu:** response `usage.budget_remaining_usd` đang gán `usage.total_cost_usd`, nên tên field không khớp ý nghĩa. Không dùng field đó để kết luận ngân sách còn lại; endpoint usage mới tính remaining bằng budget trừ cost. Mẫu cũng chỉ kiểm chi phí đã ghi, chưa reserve cho các request đang chạy.

## Part 5: Scaling & Reliability

### Exercise 5.1–5.2 — Health và shutdown

Đã chạy bản develop trong WSL2: `GET /health` 200, `GET /ready` 200, `POST /ask?question=Hello` 200. Gửi SIGTERM lúc idle, process thoát code 0. Đây là test idle shutdown; test request đang chạy nằm trong checker Part 6. Bằng chứng: [part5.json](reports/examples/part5.json).

Liveness cho biết process sống, readiness cho biết có nên nhận traffic. Readiness fail nên rút instance khỏi routing; không đồng nghĩa phải restart process. Graceful shutdown cho server ngừng nhận request mới, drain request đang chạy, sau đó đóng tài nguyên và thoát.

### Exercise 5.3–5.5 — Stateless và scaling

Chạy `docker compose -p k5-day14-scaling up -d --build --scale agent=3`, sau đó chạy nguyên bản `python test_stateless.py`. Kết quả: 5 câu hỏi được chia cho **3 instance** `instance-9a5a7b`, `instance-42784f`, `instance-57b390`; đọc lại session có đủ **10 message** (5 user + 5 assistant).

```text
Request 1 → instance-9a5a7b
Request 2 → instance-42784f
Request 3 → instance-57b390
Request 4 → instance-9a5a7b
Request 5 → instance-42784f
Total messages: 10
Session history preserved across all instances via Redis!
```

Nginx là điểm vào `localhost:8080`, chuyển request tới các agent; lịch sử nằm ở Redis chung nên không cần request quay lại đúng instance cũ. Nếu lưu lịch sử trong dict của process thì request chuyển instance sẽ không thấy cùng dữ liệu. Bằng chứng đầy đủ: [part5-stateless.log](reports/examples/part5-stateless.log).

Không tắt instance nào trong lần demo này; không khẳng định đã kiểm thử failover. Stack đã dừng sau khi ghi bằng chứng.

## Part 6: Production Readiness

Đã triển khai ngay trong `06-lab-complete/` và chạy **bản đầy đủ có Docker** trên Ubuntu WSL2. Kết quả: **PASS 12/12 — 43/43 checks passed**. Toàn bộ output: [part6-readiness.log](reports/examples/part6-readiness.log).

```text
📋 Checklist Deliverable
✅ Dockerfile (multi-stage, < 500 MB)
✅ docker-compose.yml (agent + redis)
✅ .dockerignore
✅ Health check endpoint (GET /health)
✅ Readiness endpoint (GET /ready)
✅ API Key authentication
✅ Rate limiting
✅ Cost guard
✅ Config từ environment variables
✅ Structured logging
✅ Graceful shutdown
✅ Public URL ready (Railway / Render config)
Result: 12/12 tiêu chí đạt · 43/43 checks passed
PASS 12/12 — PRODUCTION READY!
```

### Thiết kế và bằng chứng runtime

- Config từ env; API key không có giá trị mặc định dùng chung. Thiếu/sai key trả 401.
- Redis client kết nối lazy và có timeout; app khởi động được khi Redis chưa sẵn sàng.
- `/health` luôn 200 khi process sống; `/ready` trả 503 nếu Redis không ping được. Checker đã xác nhận cả hai khi mất Redis.
- Rate limiter dùng Redis sorted set, UUID làm member, Redis TIME làm đồng hồ và Lua để kiểm tra/cập nhật nguyên tử. Checker đặt giới hạn 5 và thấy 429 sau 5 request, vẫn 429 sau restart.
- Cost guard dùng tổng chi phí toàn service theo ngày UTC, lưu Redis và tăng nguyên tử, hết budget trả 402. Token của mock là ước lượng `max(1, len(text)//4)`. Đây là kiểm tra chi phí đã ghi; nhiều request đã được nhận trước khi ghi cost có thể làm tổng vượt budget một lượng nhỏ. Muốn hard cap cần reserve trước rồi reconcile.
- Mỗi dòng log ứng dụng do formatter `json.dumps` tạo; checker đọc được 17 dòng JSON hợp lệ. Không log nội dung credential.
- Route sync chạy mock blocking trong thread pool; Uvicorn drain request trước lifespan shutdown đóng Redis. Checker xác nhận request đang chạy vẫn 200, process thoát code 0.
- Docker multi-stage, slim, non-root, healthcheck; checker đo image 56 MB. `docker stop` kết thúc code 0 trong 0.9 giây.
- Compose có Redis AOF + volume và agent dùng service DNS. Restart agent không làm mất state; mất toàn bộ dữ liệu Redis vẫn làm mất state.

**Phân biệt:** tiêu chí 12 của checker xác nhận cấu hình deploy sẵn sàng. Part 3 đã được kiểm chứng riêng bằng URL public và bốn kết quả HTTP thật trong `reports/railway-http.json`.

## AI log

| Yêu cầu | AI hỗ trợ | Tự kiểm tra / việc cần học viên xác nhận |
|---|---|---|
| Đọc repo và giải thích việc cần làm | Đối chiếu README, CHECKPOINTS, SUBMISSION, RULES và code; chỉ ra TODO và các đính chính K5 | Đọc lại yêu cầu nộp và giải thích được các tiêu chí. |
| Hướng dẫn từng phần | Soạn lệnh WSL, thứ tự thực hiện và các bằng chứng cần lưu | Chưa coi hướng dẫn là bằng chứng đã chạy. |
| Thực hiện lần lượt LAB | Kiểm tra WSL/Docker, chuẩn bị dependencies, viết runner lưu HTTP thật và soạn câu trả lời theo source | Kết quả chạy lưu trong reports; học viên cần đọc diff và tự giải thích trước khi nộp. Không bịa số đo hay ảnh. |
| Triển khai Part 6 | Viết config/auth, Redis client, atomic Lua rate limiter, daily cost guard, JSON logger, lifecycle, Docker và cloud configs | Đã chạy checker nguyên bản đầy đủ trong WSL: PASS 12/12, 43/43 checks; học viên cần giải thích thiết kế và giới hạn concurrent budget. |
| Benchmark và cải thiện v2 | Chạy load test/eval thật; bổ sung KB JWT/HPA sau khi đọc câu sai; giữ nguyên golden dataset | Lưu đầy đủ baseline, v2 và v2_fixed: 1/23 → 21/23 → 23/23, không regression ở bản sửa. |
| Observability | Sửa PYTHONUSERBASE trong Dockerfile mẫu; chạy Locust, Prometheus/Grafana/Jaeger; thu trace qua API v3 và chụp UI bằng Edge headless | CSV/JSON và ảnh là dữ liệu thật từ stack local. Hai alert lỗi/chậm cùng firing đã được quan sát và lưu snapshot. |
| Railway | Học viên tự xác nhận tài khoản mới; tạo project, Redis, cấu hình secret/reference và deploy Part 6 | Đã kiểm chứng URL public cùng HTTP 200/200/401/200; key không ghi vào báo cáo. |
