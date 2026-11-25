"""Generate report tables from real JSON/CSV measurements."""
import csv
import json
import os
import platform
import subprocess
from run_examples import ROOT


def read(name):
    return json.loads((ROOT / 'reports' / name).read_text(encoding='utf-8'))


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(map(str, headers)) + ' |',
                      '| ' + ' | '.join('---' for _ in headers) + ' |',
                      *['| ' + ' | '.join(map(str, row)) + ' |' for row in rows]])


def build():
    env = {'python': platform.python_version(), 'platform': platform.platform(),
           'os_name': os.name, 'logical_cpu_count': os.cpu_count()}
    for fmt, name in [('{{.NCPU}}', 'docker_cpus'), ('{{.MemTotal}}', 'docker_memory_bytes')]:
        env[name] = int(subprocess.check_output(['docker', 'info', '--format', fmt], text=True).strip())
    (ROOT / 'reports/environment-info.json').write_text(json.dumps(env, indent=2) + '\n', encoding='utf-8')
    parts = ['# Benchmark & Observability Report — Day 14',
        '**Họ tên:** Phạm Đức Hồng Đức  \n**Ngày chạy:** 25/11/2026  \n'
        f'**Môi trường:** Ubuntu WSL2, Python {env["python"]}; Docker Linux engine: '
        f'{env["docker_cpus"]} CPU, {env["docker_memory_bytes"]/1024**3:.2f} GiB RAM. '
        'Chi tiết: reports/environment-info.json.',
        'Mỗi cấu hình là một lần đo với mock có jitter/lỗi ngẫu nhiên. JSON/CSV là nguồn số liệu; '
        'không dùng mẫu 23 câu eval để kết luận latency production. Load test local được đo '
        'trước khi sửa KB và bổ sung histogram độ dài câu hỏi; scaling Docker dùng v2 với KB đã sửa.',
        '## 1. SLO', table(['SLI', 'SLO', 'Lý do'], [
            ['p95 /ask', '≤ 500 ms', 'Phản ánh trải nghiệm ở đuôi phân phối.'],
            ['Error rate /ask', '≤ 2%', 'Mock mặc định có 1% xác suất upstream error.'],
            ['Accuracy', '100%, không regression sau sửa KB', 'Mục tiêu Exercise 7.3.']]),
        'Ngưỡng load test khớp CLI mặc định. Alert stack có ngưỡng riêng: error rate >5%, '
        'p95 >1 giây và thời gian for để tránh báo động vì spike ngắn.',
        '### Exercise 7.1 — Metric và cardinality',
        'Counter: http_requests_total, chỉ tăng theo request. Gauge: agent_in_flight_requests, '
        'tăng khi bắt đầu và giảm khi kết thúc request. Histogram: http_request_duration_seconds '
        'và agent_question_length_chars. Đã bổ sung histogram độ dài câu hỏi trong develop/app.py '
        'với buckets 20/50/100/200/500/1000/2000 ký tự. Chạy thật ba câu dài 10, 50, 200 ký tự: '
        'count=3, sum=260, bucket ≤50 có 2; raw /metrics ở reports/examples/part7-metrics.txt.',
        'Dùng route.path để URL lạ đều vào unmatched. Nếu lấy URL thật làm label, bot quét '
        'hàng nghìn đường dẫn sẽ tạo hàng nghìn time series; RAM/storage/query cost tăng. '
        'Độ dài câu hỏi cũng nên là giá trị observe của Histogram, không làm label length.',
        '## 2. Benchmark hiệu năng', '### 2.1. Concurrency — 300 request/mức']
    rows = []
    for c in (1, 10, 50, 100):
        r = read(f'load_v2_c{c}.json'); lat = r['latency_ms']
        rows.append([c, r['rps'], lat['p50'], lat['p95'], lat['p99'], f'{r["error_rate"]:.2%}',
                     'PASS' if lat['p95'] <= 500 and r['error_rate'] <= .02 else 'FAIL'])
    parts += [table(['Concurrency', 'RPS', 'p50 ms', 'p95 ms', 'p99 ms', 'Error rate', 'SLO'], rows),
        'Nguồn: reports/load_v2_c*.json. RPS tăng tới concurrency 50 nhưng giảm ở 100 trong lần đo này, '
        'đồng thời p95 tăng mạnh. Throughput không tăng tuyến tính theo concurrency. Scheduling, '
        'giới hạn tài nguyên và tail latency có thể tác động; chưa có profiling để khẳng định một '
        'nguyên nhân duy nhất. Giữ nguyên kết quả FAIL thực tế.',
        '### 2.2. Tail latency — 300 request, concurrency 20']
    rows = []
    for slow in ('0', '0.03', '0.1'):
        lat = read(f'load_v2_slow_{slow}.json')['latency_ms']
        rows.append([slow, lat['avg'], lat['p95'], lat['p99']])
    parts += [table(['MOCK_SLOW_RATE', 'avg ms', 'p95 ms', 'p99 ms'], rows),
        'Khi slow rate từ 0 lên 3%, p99 tăng rõ hơn p95. Ở 10%, cả p95 và p99 nằm trong nhóm chậm. '
        'Average che bớt trải nghiệm ở đuôi nên không đủ để đặt SLO. Latency trong load JSON chỉ '
        'tính response 200; error rate đếm các response khác 200.', '## 3. Benchmark chất lượng']
    evaluations = [read(name) for name in ('eval_v1.json', 'eval_v2.json', 'eval_v2_fixed.json')]
    parts += [table(['Chỉ số', 'v1', 'v2 ban đầu', 'v2 sửa KB'], [
        ['Accuracy', *[f'{r["passed"]}/{r["total"]} ({r["accuracy"]:.2%})' for r in evaluations]],
        ['Avg tokens/câu', *[r['avg_tokens'] for r in evaluations]],
        ['Tổng cost USD', *[r['total_cost_usd'] for r in evaluations]],
        ['Cost/câu đúng USD', *[r['cost_per_correct_usd'] for r in evaluations]],
        ['Quality gate', *['PASS' if r['quality_gate']['passed'] else 'FAIL' for r in evaluations]]]),
        table(['ID sai ban đầu', 'Keyword thiếu', 'Sửa'], [
            ['security-02', 'token, hết hạn, chữ ký', 'Thêm tài liệu JWT/API key và claims/expiry/signature.'],
            ['scaling-03', 'cpu, memory, custom metrics', 'Thêm tài liệu HPA và metrics adapter.']]),
        'Đã sửa KNOWLEDGE_BASE của cả develop và production; không sửa golden dataset. '
        'v2 ban đầu so với v1 không regression (reports/initial-comparison.json); '
        'v2 đã sửa đạt 23/23 và không regression so với v2 ban đầu.',
        'v2 có retrieval nên prompt dài hơn và tổng cost cao hơn v1, nhưng cost/câu đúng thấp hơn nhiều. '
        'Chỉ số cost/câu đúng tính cả tiền đã tiêu cho câu sai nên phản ánh giá trị tốt hơn cost/request. '
        'Không kết luận latency v2 tốt hơn v1 từ 23 mẫu eval.',
        '### Quality gate trong CI',
        'Sau khi cài requirements, khởi động agent v2 ở 8002 và chờ /health 200, CI chạy '
        '`python eval/run_eval.py --url http://localhost:8002 --min-accuracy 1.0 '
        '--baseline reports/eval_v2.json --out reports/ci-eval.json` từ develop. '
        'Exit code 1 khi accuracy thiếu hoặc có regression; không dùng `|| true`. '
        'Đặt job làm required status check trong branch protection để chặn merge. '
        'Đã viết job tại .github/workflows/quality-gate.yml và scripts/ci_quality_gate.sh. '
        'Job thực tế dùng baseline eval_v2_fixed.json, ngưỡng 100% (chặt hơn yêu cầu 85%), '
        'tắt lỗi/chậm ngẫu nhiên để gate chất lượng ổn định, poll health thay vì sleep cố định '
        'và dọn process bằng trap. Đã chạy script job local; chưa chạy trên GitHub Actions '
        'và chưa cấu hình branch protection. Action versions theo '
        '[checkout](https://github.com/actions/checkout) và '
        '[setup-python](https://github.com/actions/setup-python) được đối chiếu lúc làm bài.',
        '## 4. Observability stack']
    for name, label in [('grafana-dashboard.png', 'Grafana có tải'), ('jaeger-slow-trace.png', 'Trace chậm'),
                        ('jaeger-error-trace.png', 'Trace lỗi'), ('prometheus-alert-firing.png', 'Hai alert firing')]:
        exists = (ROOT / 'screenshots' / name).exists()
        parts.append(f'- [{"x" if exists else " "}] {label}: [{name}](screenshots/{name})')
    if (ROOT / 'reports/observability/dashboard-observations.json').exists():
        d = read('observability/dashboard-observations.json')
        results = {key: value['data']['result'] for key, value in d['queries'].items()}
        p95 = float(results['p95_s'][0]['value'][1]) * 1000
        avg = float(results['avg_s'][0]['value'][1]) * 1000
        rates = [float(item['value'][1]) for item in results['requests_per_instance']]
        balance = ('gần đều trong cửa sổ đo' if rates and sum(rates) > 0
                   and (max(rates) - min(rates)) / sum(rates) < 0.1 else 'chưa thể coi là gần đều')
        parts += ['### Exercise 7.4 — Đọc dashboard',
            f'Đo tại {d["observed_at_utc"]}, 2 instance, 30 users, ramp-up 5 users/s: '
            f'p95={p95:.2f} ms, avg={avg:.2f} ms, chênh lệch {p95-avg:.2f} ms. Khoảng cách phản ánh sự khác nhau giữa '
            'mức trung bình và ngưỡng 95%; percentile có thể cao hơn hoặc thấp hơn average khi '
            'một nhóm rất nhỏ request cực chậm kéo average lên.',
            table(['Instance', 'Request /ask mỗi giây'], [
                [item['metric']['instance'], f'{float(item["value"][1]):.3f}']
                for item in results['requests_per_instance']]),
            f'Traffic được chia {balance}. Không yêu cầu bằng tuyệt đối vì mẫu hữu hạn, '
            'connection reuse và thời gian phục vụ khác nhau. Cấu hình Nginx dùng round-robin.',
            table(['Loại token', 'Token/giây'], [
                [item['metric']['type'], f'{float(item["value"][1]):.3f}']
                for item in results['tokens_per_second']]),
            'Input gồm system prompt, câu hỏi và context retrieval; output chỉ là câu trả lời. '
            'Với bộ câu hỏi này input thường dài hơn, nhưng không phải quy luật cho mọi workload.',
            f'Gọi public GET /metrics qua Nginx trả HTTP {d["public_metrics"]["status"]}. '
            'Nginx chủ động không public endpoint này; Prometheus scrape trực tiếp agent trong Docker network. '
            'Raw queries: reports/observability/dashboard-observations.json.']
    if (ROOT / 'reports/observability/chaos-alerts.json').exists():
        a = read('observability/chaos-alerts.json')
        parts += ['### 4.1. Fault injection',
            f'Đổi cấu hình lúc {a["changed_at_utc"]}: MOCK_ERROR_RATE=0.2, MOCK_SLOW_RATE=0.3, '
            'Locust 30 users. Thời gian từ ngay trước lệnh áp dụng cấu hình, gồm recreate/discovery; '
            'sai số poll khoảng 5 giây.',
            table(['Alert', 'Lần đầu thấy firing, giây'], a['first_firing_s'].items()),
            'Đây là thí nghiệm phối hợp A+B để có hai alert cùng firing; chưa tách ảnh hưởng riêng '
            'của hai biến. Bằng chứng: reports/observability/chaos-alerts.json và both-alerts-firing.json. '
            'Cost alert xuất hiện ở poll đầu có thể kế thừa tải scaling trước đó; không dùng '
            'thời gian đó làm độ trễ phát hiện một fault mới.']
    else:
        parts += ['Chưa có thời gian alert firing thực tế.']
    if (ROOT / 'reports/observability/isolated-experiments.json').exists():
        experiments = read('observability/isolated-experiments.json')
        panels = {'A': 'Error rate / LLM errors', 'B': 'Latency p95 / LLM p95',
                  'C': 'Cost burn rate / tokens', 'D': 'Instances up / request theo instance',
                  'E': 'Version / chất lượng eval'}
        rows = []
        targets = {'A': 'AgentHighErrorRate', 'B': 'AgentHighLatencyP95',
                   'C': 'LLMCostBurnRateHigh', 'D': 'AgentInstanceDown'}
        for item in experiments:
            changed = {key: value for key, value in item['configuration'].items()
                       if value != {'AGENT_VERSION': 'v2', 'LLM_MODEL': 'mock-llm-small',
                                    'MOCK_ERROR_RATE': '0.01', 'MOCK_SLOW_RATE': '0.03'}.get(key)}
            target = targets.get(item['experiment'])
            firing = (f'{target}: {item["first_firing_s"][target]}s'
                      if target in item['first_firing_s'] else '')
            if item['experiment'] == 'E':
                firing = 'Không có rule đánh giá accuracy; xem eval bên dưới'
            rows.append([item['experiment'], 'pause 1/3 instance' if item['experiment'] == 'D' else str(changed),
                         firing or f'Không firing trong {item["observation_seconds"]}s', panels[item['experiment']]])
        parts += ['### Thí nghiệm A–E riêng lẻ',
                  table(['Thí nghiệm', 'Thay đổi', 'Firing và thời gian', 'Panel liên quan'], rows),
                  'Mỗi thí nghiệm khôi phục cấu hình khác về baseline, dùng 3 instance và Locust 30 users. '
                  'Mốc thời gian: sau recreate và 15 giây DNS settling, riêng D ngay trước pause. '
                  'Bảng ghi alert mục tiêu của từng thí nghiệm. Alert khác có thể kế thừa cửa sổ rate/for '
                  'từ thí nghiệm trước; raw snapshots giữ lại cả các trạng thái đó. '
                  'Không firing trong cửa sổ quan sát không chứng minh alert không thể firing nếu chạy lâu hơn. '
                  'Raw API snapshots trong reports/observability/isolated-experiments.json.']
        if (ROOT / 'reports/observability/experiment-E-eval.json').exists():
            evaluation = read('observability/experiment-E-eval.json')
            parts += [f'Khi đổi v1, eval runtime qua Nginx đạt {evaluation["passed"]}/{evaluation["total"]}, '
                      f'accuracy {evaluation["accuracy"]:.2%}. Đây là sự cố chất lượng dù HTTP vẫn có thể 200.']
    if (ROOT / 'reports/observability/selected-traces.json').exists():
        selected = read('observability/selected-traces.json'); logs = read('observability/trace-log-matches.json')
        parts += ['### 4.2. Trace và log']
        parts += ['Jaeger 2.23 trong stack dùng [HTTP API v3](https://www.jaegertracing.io/docs/2.dev/architecture/apis/). '
                  'Script lấy trace theo trace_id có sẵn trong log, lưu response OTLP nguyên bản và '
                  'summary quy đổi nanosecond sang microsecond; không sửa trace để tạo bằng chứng.']
        for kind, trace in selected.items():
            if not trace:
                parts.append(f'Chưa tìm thấy trace {kind}.'); continue
            spans = trace['spans']; total = max(s['duration'] for s in spans)
            leaves = [s for s in spans if not any(ref.get('spanID') == s['spanID']
                      for child in spans for ref in child.get('references', []))]
            leaf = max(leaves or spans, key=lambda s: s['duration'])
            parts += [f'**{kind}:** trace_id `{trace["traceID"]}`; tổng {total/1000:.2f} ms; '
                      f'leaf span chậm nhất `{leaf["operationName"]}` {leaf["duration"]/1000:.2f} ms '
                      f'({leaf["duration"]/total:.1%}).']
            matching = [line for line in logs.get(kind, []) if line.startswith('{')]
            if matching:
                parts.append('```json\n' + matching[0] + '\n```')
    parts += ['Dashboard hạ tầng không bảo đảm câu trả lời đúng: v1 vẫn có thể trả 200 và latency thấp. '
              'Cần eval/canary quality, phản hồi người dùng và theo dõi chất lượng theo version.',
              '## 5. Scaling — Locust headless, 100 users, 2 phút/mức']
    rows = []
    for count in (1, 3):
        path = ROOT / f'benchmark-results/scale_{count}_stats.csv'
        if path.exists():
            with path.open(newline='', encoding='utf-8') as stream:
                item = next(row for row in csv.DictReader(stream) if row['Name'] == 'Aggregated')
            rows.append([count, f'{float(item["Requests/s"]):.2f}', item['50%'], item['95%'], item['99%'], item['Failure Count']])
    parts += [table(['Instances', 'RPS', 'p50 ms', 'p95 ms', 'p99 ms', 'Failures'], rows) if rows else 'Chưa có CSV scaling.',
        'Dùng hàng Aggregated (gồm /ask và /health), hai lần cùng cấu hình bình thường; không lấy chaos '
        'để đo scale. Locust nghỉ 0.5–2 giây/user nên RPS còn phụ thuộc mô hình tải. '
        'Nếu p95 gần nhau, đối chiếu span LLM để xác định phần latency không giảm khi thêm replica.',
        '## 6. Điều học được và giới hạn',
        '1. Xem p95/p99 cùng error rate thay vì chỉ average.\n'
        '2. Chất lượng nội dung cần eval riêng, HTTP 200 chưa đủ.\n'
        '3. Metrics xác định triệu chứng, trace khoanh vùng bước chậm, log cung cấp chi tiết.',
        'Production thật cần thêm synthetic check bên ngoài Nginx, metric load balancer/Redis, '
        'quality theo version và sampling trace phù hợp. Tránh label user_id/question cardinality cao. '
        'Mock cost/token estimate không phải hoá đơn LLM thật. Cloud deployment theo dõi riêng '
        'trong DEPLOYMENT.md; chưa có URL thì bài chưa hoàn tất hoàn toàn.']
    if len(rows) == 2:
        parts.insert(-4, f'Trong lần đo này, RPS {rows[0][1]} → {rows[1][1]}, '
                     f'p95 {rows[0][3]} → {rows[1][3]} ms, p99 {rows[0][4]} → {rows[1][4]} ms. '
                     'Kết quả phù hợp với giảm contention ở request thông thường nhưng không loại '
                     'được tail latency từ mock LLM; chưa profiling để khẳng định nút thắt duy nhất. '
                     'Với 100 users có thời gian nghỉ, tăng replica không tự tăng số request phát sinh gấp ba.')
    (ROOT / 'BENCHMARK_REPORT.md').write_text('\n\n'.join(parts) + '\n', encoding='utf-8')
    print('Updated BENCHMARK_REPORT.md from raw JSON/CSV')


if __name__ == '__main__':
    build()
