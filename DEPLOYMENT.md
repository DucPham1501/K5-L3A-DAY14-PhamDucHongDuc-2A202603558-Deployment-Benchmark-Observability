# Deployment Information

## Trạng thái

**Đã deploy thành công lên Railway ngày 25/11/2026.** Sau khi học viên đổi tài khoản và xác nhận đăng nhập, đã tạo project `day14-agent-observability`, service `agent` và `Redis`. Cả hai service triển khai thành công trên trial; không kích hoạt gói trả phí.

Bốn kiểm tra public đạt **200 / 200 / 401 / 200**. `/ready` xác nhận Redis cloud truy cập được. Bằng chứng: `reports/railway-deployment.json`, `reports/railway-http.json` và `reports/railway-http.log`. API key chỉ lưu trong `.env.railway` được Git ignore và biến môi trường Railway.

## Public URL

https://agent-production-36599cd4.up.railway.app

- Health: https://agent-production-36599cd4.up.railway.app/health
- API docs: https://agent-production-36599cd4.up.railway.app/docs
- Dashboard: https://railway.com/project/670dfe1d-cca8-4898-8380-c0c34c15f7e9

## Code được deploy

Thư mục `06-lab-complete/`, không dùng Dockerfile ở gốc repo hoặc app mẫu Part 3.

## Environment variables cần đặt trên service agent

| Biến | Cách đặt |
|---|---|
| PORT | Dùng cổng nền tảng cấp; Docker CMD đọc biến này. |
| ENVIRONMENT | production |
| AGENT_API_KEY | Secret riêng, không ghi giá trị vào repo. |
| REDIS_URL | Connection URL của Redis cloud, đặt bằng secret/reference variable. |
| RATE_LIMIT_PER_MINUTE | 10 |
| DAILY_BUDGET_USD | 1 (budget ngày UTC được chọn cho triển khai này) |
| LOG_LEVEL | INFO |

## Railway

Tạo project/service agent và Redis trong cùng project, cấu hình biến môi trường. Nếu service Redis tên `Redis`, dùng reference `${{Redis.REDIS_URL}}` cho biến REDIS_URL của agent. Từ gốc repo đã link đúng service:

```bash
railway up ./06-lab-complete --path-as-root
railway domain
```

Runtime hiện nhận `PORT=8080` từ Railway. Domain phải trỏ tới cổng **8080**; trỏ 8000 sẽ trả 502. Đã kiểm chứng cổng qua Uvicorn logs và sửa domain bằng `railway domain update agent-production-36599cd4.up.railway.app --service agent --port 8080`. Agent dùng `REDIS_URL=${{Redis.REDIS_URL}}` qua private network.

Chỉ `cd` vào thư mục con không bảo đảm CLI upload đúng build context; kiểm tra Dockerfile/build logs và dùng path-as-root hoặc root directory phù hợp.

## Render

Blueprint path: `06-lab-complete/render.yaml`. Root directory của service là `06-lab-complete`; Dockerfile và build context tương ứng là `./Dockerfile` và `.`. Blueprint hiện yêu cầu điền REDIS_URL; cần tạo Redis riêng trước khi xác nhận `/ready` 200.

## Test commands sau khi có URL

Trong WSL:

```bash
BASE="https://YOUR-PUBLIC-DOMAIN"
read -rsp "API key cloud: " AGENT_API_KEY
printf '\n'
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
unset AGENT_API_KEY
```

Đã kiểm chứng theo thứ tự: **200 / 200 / 401 / 200**. Chạy lại từ gốc repo bằng `node scripts/verify-railway.cjs https://agent-production-36599cd4.up.railway.app`; script đọc key local và lưu bằng chứng không chứa key.

## Ảnh bằng chứng triển khai

- Project Railway hiển thị agent và Redis đều Online. [dashboard.png](screenshots/dashboard.png)
- Deployment Active, có log `Uvicorn running` và `Application startup complete`. [running.png](screenshots/running.png)
- Bốn kiểm tra HTTP public đạt **200 / 200 / 401 / 200**. [test.png](screenshots/test.png)

## Tài liệu nền tảng được đối chiếu

- [Railway CLI deployment/path-as-root](https://docs.railway.com/cli/deploying)
- [Railway Redis](https://railway.com/deploy/redis-1)
- [Render Blueprint specification](https://render.com/docs/blueprint-spec)
