"""Run Exercise 7.1 against an actual local server and save /metrics."""
import urllib.request
from run_examples import EVIDENCE, server, request

with server('06-lab-complete/benchmark-observability/develop', {
    'AGENT_VERSION': 'v2', 'PORT': '8002', 'MOCK_ERROR_RATE': '0', 'MOCK_SLOW_RATE': '0',
}, port=8002):
    for length in (10, 50, 200):
        result = request('/ask', body={'question': 'x' * length}, port=8002)
        assert result['status'] == 200, result
    with urllib.request.urlopen('http://localhost:8002/metrics') as response:
        metrics = response.read().decode()
    assert 'agent_question_length_chars_count 3.0' in metrics
    assert 'agent_question_length_chars_sum 260.0' in metrics
    (EVIDENCE / 'part7-metrics.txt').write_text(metrics, encoding='utf-8')
    print('\n'.join(line for line in metrics.splitlines() if line.startswith('agent_question_length_chars')))
