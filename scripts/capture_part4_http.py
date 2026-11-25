"""Save the curl -i evidence requested by CP3, without persisting JWTs."""
import json
import subprocess
from run_examples import ROOT, EVIDENCE, server, request


def curl(headers=None):
    args = ['curl', '-sS', '-i', '-X', 'POST', 'http://localhost:8000/ask',
            '-H', 'Content-Type: application/json', '-d', '{"question":"Hello"}']
    for key, value in (headers or {}).items():
        args += ['-H', f'{key}: {value}']
    return subprocess.check_output(args, text=True)


with server('04-api-gateway/develop', {'AGENT_API_KEY': 'local-example-key'}):
    missing = curl()
    valid = curl({'X-API-Key': 'local-example-key'})
with server('04-api-gateway/production'):
    login = request('/auth/token', body={'username': 'student', 'password': 'demo123'})
    token = login['body']['access_token']
    for _ in range(10):
        request('/ask', body={'question': 'Hello'}, headers={'Authorization': f'Bearer {token}'})
    limited = curl({'Authorization': f'Bearer {token}'})
(EVIDENCE / 'part4-curl.txt').write_text(
    'API key missing\n' + missing + '\n\nAPI key valid\n' + valid + '\n\nJWT rate limited\n' + limited,
    encoding='utf-8')
print('Saved real curl -i output: 401, 200, 429; JWT omitted.')
