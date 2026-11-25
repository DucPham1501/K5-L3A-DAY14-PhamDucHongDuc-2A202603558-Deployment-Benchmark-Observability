// Verify the public deployment without printing or saving the API key.
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');

async function main() {
  const base = process.argv[2];
  if (!base || !base.startsWith('https://')) throw new Error('Provide the HTTPS deployment URL');
  const line = fs.readFileSync(path.join(root, '.env.railway'), 'utf8')
    .split(/\r?\n/).find(line => line.startsWith('AGENT_API_KEY='));
  const key = line?.slice('AGENT_API_KEY='.length).trim().replace(/^(['"])(.*)\1$/, '$2');
  if (!key) throw new Error('Missing API key in .env.railway');
  const checks = [];
  for (const [name, endpoint, expected, authenticated] of [
    ['health', '/health', 200, false],
    ['ready', '/ready', 200, false],
    ['ask_without_key', '/ask', 401, false],
    ['ask_with_key', '/ask', 200, true],
  ]) {
    const headers = { 'Content-Type': 'application/json' };
    if (authenticated) headers['X-API-Key'] = key;
    const response = await fetch(new URL(endpoint, base), {
      method: endpoint === '/ask' ? 'POST' : 'GET', headers,
      body: endpoint === '/ask' ? JSON.stringify({ question: 'Hello' }) : undefined,
      signal: AbortSignal.timeout(30000),
    });
    const body = (await response.text()).split(key).join('[REDACTED]');
    checks.push({ name, method: endpoint === '/ask' ? 'POST' : 'GET', endpoint,
      expected_status: expected, status: response.status, passed: response.status === expected, body });
    console.log(`${name}: HTTP ${response.status} (expected ${expected})`);
  }
  const report = { checked_at_utc: new Date().toISOString(), public_url: base,
    passed: checks.every(check => check.passed), checks };
  fs.writeFileSync(path.join(root, 'reports/railway-http.json'), JSON.stringify(report, null, 2) + '\n');
  fs.writeFileSync(path.join(root, 'reports/railway-http.log'),
    `${report.checked_at_utc}\n${base}\n` + checks.map(check =>
      `${check.method} ${check.endpoint} ${check.name}: HTTP ${check.status} expected ${check.expected_status} ${check.passed ? 'PASS' : 'FAIL'}\n${check.body}`).join('\n') + '\n');
  if (!report.passed) process.exitCode = 1;
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
