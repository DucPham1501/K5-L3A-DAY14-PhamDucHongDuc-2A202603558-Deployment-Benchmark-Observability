# Benchmark & Observability Report — Day 14

**Họ tên:** Phạm Đức Hồng Đức  
**Ngày chạy:** 25/11/2026  
**Môi trường:** Ubuntu WSL2, Python 3.12.3; Docker Linux engine: 16 CPU, 7.36 GiB RAM. Chi tiết: reports/environment-info.json.

Mỗi cấu hình là một lần đo với mock có jitter/lỗi ngẫu nhiên. JSON/CSV là nguồn số liệu; không dùng mẫu 23 câu eval để kết luận latency production. Load test local được đo trước khi sửa KB và bổ sung histogram độ dài câu hỏi; scaling Docker dùng v2 với KB đã sửa.

## 1. SLO

| SLI | SLO | Lý do |
| --- | --- | --- |
| p95 /ask | ≤ 500 ms | Phản ánh trải nghiệm ở đuôi phân phối. |
| Error rate /ask | ≤ 2% | Mock mặc định có 1% xác suất upstream error. |
| Accuracy | 100%, không regression sau sửa KB | Mục tiêu Exercise 7.3. |

Ngưỡng load test khớp CLI mặc định. Alert stack có ngưỡng riêng: error rate >5%, p95 >1 giây và thời gian for để tránh báo động vì spike ngắn.

### Exercise 7.1 — Metric và cardinality

Counter: http_requests_total, chỉ tăng theo request. Gauge: agent_in_flight_requests, tăng khi bắt đầu và giảm khi kết thúc request. Histogram: http_request_duration_seconds và agent_question_length_chars. Đã bổ sung histogram độ dài câu hỏi trong develop/app.py với buckets 20/50/100/200/500/1000/2000 ký tự. Chạy thật ba câu dài 10, 50, 200 ký tự: count=3, sum=260, bucket ≤50 có 2; raw /metrics ở reports/examples/part7-metrics.txt.

Dùng route.path để URL lạ đều vào unmatched. Nếu lấy URL thật làm label, bot quét hàng nghìn đường dẫn sẽ tạo hàng nghìn time series; RAM/storage/query cost tăng. Độ dài câu hỏi cũng nên là giá trị observe của Histogram, không làm label length.

## 2. Benchmark hiệu năng

### 2.1. Concurrency — 300 request/mức

| Concurrency | RPS | p50 ms | p95 ms | p99 ms | Error rate | SLO |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 4.43 | 190.9 | 217.1 | 1689.0 | 1.33% | PASS |
| 10 | 39.26 | 186.6 | 218.4 | 1708.6 | 1.67% | PASS |
| 50 | 106.4 | 199.3 | 274.5 | 1705.9 | 2.00% | PASS |
| 100 | 98.48 | 350.5 | 2278.8 | 2430.7 | 2.00% | FAIL |

Nguồn: reports/load_v2_c*.json. RPS tăng tới concurrency 50 nhưng giảm ở 100 trong lần đo này, đồng thời p95 tăng mạnh. Throughput không tăng tuyến tính theo concurrency. Scheduling, giới hạn tài nguyên và tail latency có thể tác động; chưa có profiling để khẳng định một nguyên nhân duy nhất. Giữ nguyên kết quả FAIL thực tế.

### 2.2. Tail latency — 300 request, concurrency 20

| MOCK_SLOW_RATE | avg ms | p95 ms | p99 ms |
| --- | --- | --- | --- |
| 0 | 188.8 | 218.4 | 229.6 |
| 0.03 | 249.9 | 222.1 | 1683.1 |
| 0.1 | 356.3 | 1697.6 | 1720.0 |

Khi slow rate từ 0 lên 3%, p99 tăng rõ hơn p95. Ở 10%, cả p95 và p99 nằm trong nhóm chậm. Average che bớt trải nghiệm ở đuôi nên không đủ để đặt SLO. Latency trong load JSON chỉ tính response 200; error rate đếm các response khác 200.

## 3. Benchmark chất lượng

| Chỉ số | v1 | v2 ban đầu | v2 sửa KB |
| --- | --- | --- | --- |
| Accuracy | 1/23 (4.35%) | 21/23 (91.30%) | 23/23 (100.00%) |
| Avg tokens/câu | 56.7 | 109.1 | 117.6 |
| Tổng cost USD | 0.000398 | 0.000762 | 0.000825 |
| Cost/câu đúng USD | 0.00039795 | 3.627e-05 | 3.586e-05 |
| Quality gate | FAIL | PASS | PASS |

| ID sai ban đầu | Keyword thiếu | Sửa |
| --- | --- | --- |
| security-02 | token, hết hạn, chữ ký | Thêm tài liệu JWT/API key và claims/expiry/signature. |
| scaling-03 | cpu, memory, custom metrics | Thêm tài liệu HPA và metrics adapter. |

Đã sửa KNOWLEDGE_BASE của cả develop và production; không sửa golden dataset. v2 ban đầu so với v1 không regression (reports/initial-comparison.json); v2 đã sửa đạt 23/23 và không regression so với v2 ban đầu.

v2 có retrieval nên prompt dài hơn và tổng cost cao hơn v1, nhưng cost/câu đúng thấp hơn nhiều. Chỉ số cost/câu đúng tính cả tiền đã tiêu cho câu sai nên phản ánh giá trị tốt hơn cost/request. Không kết luận latency v2 tốt hơn v1 từ 23 mẫu eval.

### Quality gate trong CI

Sau khi cài requirements, khởi động agent v2 ở 8002 và chờ /health 200, CI chạy `python eval/run_eval.py --url http://localhost:8002 --min-accuracy 1.0 --baseline reports/eval_v2.json --out reports/ci-eval.json` từ develop. Exit code 1 khi accuracy thiếu hoặc có regression; không dùng `|| true`. Đặt job làm required status check trong branch protection để chặn merge. Đã viết job tại .github/workflows/quality-gate.yml và scripts/ci_quality_gate.sh. Job thực tế dùng baseline eval_v2_fixed.json, ngưỡng 100% (chặt hơn yêu cầu 85%), tắt lỗi/chậm ngẫu nhiên để gate chất lượng ổn định, poll health thay vì sleep cố định và dọn process bằng trap. Đã chạy script job local; chưa chạy trên GitHub Actions và chưa cấu hình branch protection. Action versions theo [checkout](https://github.com/actions/checkout) và [setup-python](https://github.com/actions/setup-python) được đối chiếu lúc làm bài.

## 4. Observability stack

- [x] Grafana có tải: [grafana-dashboard.png](screenshots/grafana-dashboard.png)

- [x] Trace chậm: [jaeger-slow-trace.png](screenshots/jaeger-slow-trace.png)

- [x] Trace lỗi: [jaeger-error-trace.png](screenshots/jaeger-error-trace.png)

- [x] Hai alert firing: [prometheus-alert-firing.png](screenshots/prometheus-alert-firing.png)

### Exercise 7.4 — Đọc dashboard

Đo tại 2026-11-25T10:38:47.958742+00:00, 2 instance, 30 users, ramp-up 5 users/s: p95=293.21 ms, avg=229.69 ms, chênh lệch 63.52 ms. Khoảng cách phản ánh sự khác nhau giữa mức trung bình và ngưỡng 95%; percentile có thể cao hơn hoặc thấp hơn average khi một nhóm rất nhỏ request cực chậm kéo average lên.

| Instance | Request /ask mỗi giây |
| --- | --- |
| 172.21.0.9:8000 | 8.605 |
| 172.21.0.8:8000 | 8.906 |

Traffic được chia gần đều trong cửa sổ đo. Không yêu cầu bằng tuyệt đối vì mẫu hữu hạn, connection reuse và thời gian phục vụ khác nhau. Cấu hình Nginx dùng round-robin.

| Loại token | Token/giây |
| --- | --- |
| input | 1389.664 |
| output | 751.308 |

Input gồm system prompt, câu hỏi và context retrieval; output chỉ là câu trả lời. Với bộ câu hỏi này input thường dài hơn, nhưng không phải quy luật cho mọi workload.

Gọi public GET /metrics qua Nginx trả HTTP 404. Nginx chủ động không public endpoint này; Prometheus scrape trực tiếp agent trong Docker network. Raw queries: reports/observability/dashboard-observations.json.

### 4.1. Fault injection

Đổi cấu hình lúc 2026-11-25T10:14:14.759596+00:00: MOCK_ERROR_RATE=0.2, MOCK_SLOW_RATE=0.3, Locust 30 users. Thời gian từ ngay trước lệnh áp dụng cấu hình, gồm recreate/discovery; sai số poll khoảng 5 giây.

| Alert | Lần đầu thấy firing, giây |
| --- | --- |
| LLMCostBurnRateHigh | 34.6 |
| AgentHighErrorRate | 89.7 |
| AgentHighLatencyP95 | 169.8 |

Đây là thí nghiệm phối hợp A+B để có hai alert cùng firing; chưa tách ảnh hưởng riêng của hai biến. Bằng chứng: reports/observability/chaos-alerts.json và both-alerts-firing.json. Cost alert xuất hiện ở poll đầu có thể kế thừa tải scaling trước đó; không dùng thời gian đó làm độ trễ phát hiện một fault mới.

### Thí nghiệm A–E riêng lẻ

| Thí nghiệm | Thay đổi | Firing và thời gian | Panel liên quan |
| --- | --- | --- | --- |
| A | {'MOCK_ERROR_RATE': '0.2'} | AgentHighErrorRate: 40.0s | Error rate / LLM errors |
| B | {'MOCK_SLOW_RATE': '0.3'} | AgentHighLatencyP95: 110.1s | Latency p95 / LLM p95 |
| C | {'LLM_MODEL': 'mock-llm-large'} | LLMCostBurnRateHigh: 120.1s | Cost burn rate / tokens |
| D | pause 1/3 instance | AgentInstanceDown: 45.3s | Instances up / request theo instance |
| E | {'AGENT_VERSION': 'v1'} | Không có rule đánh giá accuracy; xem eval bên dưới | Version / chất lượng eval |

Mỗi thí nghiệm khôi phục cấu hình khác về baseline, dùng 3 instance và Locust 30 users. Mốc thời gian: sau recreate và 15 giây DNS settling, riêng D ngay trước pause. Bảng ghi alert mục tiêu của từng thí nghiệm. Alert khác có thể kế thừa cửa sổ rate/for từ thí nghiệm trước; raw snapshots giữ lại cả các trạng thái đó. Không firing trong cửa sổ quan sát không chứng minh alert không thể firing nếu chạy lâu hơn. Raw API snapshots trong reports/observability/isolated-experiments.json.

Khi đổi v1, eval runtime qua Nginx đạt 1/23, accuracy 4.35%. Đây là sự cố chất lượng dù HTTP vẫn có thể 200.

### 4.2. Trace và log

Jaeger 2.23 trong stack dùng [HTTP API v3](https://www.jaegertracing.io/docs/2.dev/architecture/apis/). Script lấy trace theo trace_id có sẵn trong log, lưu response OTLP nguyên bản và summary quy đổi nanosecond sang microsecond; không sửa trace để tạo bằng chứng.

**slow:** trace_id `fee1e8565bce7338d14d7afaf32f398f`; tổng 1723.34 ms; leaf span chậm nhất `chat mock-llm-small` 1698.86 ms (98.6%).

```json
{"ts": "2026-11-25T10:18:20.128395+00:00", "level": "INFO", "service": "observable-agent", "instance": "7394878ee5bc", "event": "llm_call", "trace_id": "fee1e8565bce7338d14d7afaf32f398f", "span_id": "d4d73788d6e7a9bc", "request_id": "f93dfaa91882", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 95, "output_tokens": 58, "cost_usd": 4.9e-05, "llm_ms": 1698.8}
```

**error:** trace_id `e2af417e91429321570cbc1370096e4d`; tổng 119.48 ms; leaf span chậm nhất `chat mock-llm-small` 94.90 ms (79.4%).

```json
{"ts": "2026-11-25T10:19:47.307448+00:00", "level": "INFO", "service": "observable-agent", "instance": "b0f5bd096d03", "event": "llm_error", "trace_id": "e2af417e91429321570cbc1370096e4d", "span_id": "686c67dc95aaa748", "request_id": "15ce997340cd", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

Dashboard hạ tầng không bảo đảm câu trả lời đúng: v1 vẫn có thể trả 200 và latency thấp. Cần eval/canary quality, phản hồi người dùng và theo dõi chất lượng theo version.

## 5. Scaling — Locust headless, 100 users, 2 phút/mức

| Instances | RPS | p50 ms | p95 ms | p99 ms | Failures |
| --- | --- | --- | --- | --- | --- |
| 1 | 64.02 | 200 | 380 | 1700 | 78 |
| 3 | 63.85 | 190 | 230 | 1700 | 68 |

Trong lần đo này, RPS 64.02 → 63.85, p95 380 → 230 ms, p99 1700 → 1700 ms. Kết quả phù hợp với giảm contention ở request thông thường nhưng không loại được tail latency từ mock LLM; chưa profiling để khẳng định nút thắt duy nhất. Với 100 users có thời gian nghỉ, tăng replica không tự tăng số request phát sinh gấp ba.

Dùng hàng Aggregated (gồm /ask và /health), hai lần cùng cấu hình bình thường; không lấy chaos để đo scale. Locust nghỉ 0.5–2 giây/user nên RPS còn phụ thuộc mô hình tải. Nếu p95 gần nhau, đối chiếu span LLM để xác định phần latency không giảm khi thêm replica.

## 6. Điều học được và giới hạn

1. Xem p95/p99 cùng error rate thay vì chỉ average.
2. Chất lượng nội dung cần eval riêng, HTTP 200 chưa đủ.
3. Metrics xác định triệu chứng, trace khoanh vùng bước chậm, log cung cấp chi tiết.

Production thật cần thêm synthetic check bên ngoài Nginx, metric load balancer/Redis, quality theo version và sampling trace phù hợp. Tránh label user_id/question cardinality cao. Mock cost/token estimate không phải hoá đơn LLM thật. Cloud deployment đã kiểm chứng riêng trong DEPLOYMENT.md: Railway Part 6 + Redis, HTTP public 200/200/401/200. Các benchmark trên vẫn là số đo local.
