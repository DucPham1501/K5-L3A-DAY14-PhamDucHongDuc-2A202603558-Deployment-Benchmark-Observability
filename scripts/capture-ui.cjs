// Screenshots of the real local services, using an isolated headless Edge.
const { chromium } = require('../.tools/browser/node_modules/playwright-core');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');

(async () => {
  const kind = process.argv[2];
  const selected = ['slow', 'error', 'all'].includes(kind)
    ? JSON.parse(fs.readFileSync(path.join(root, 'reports/observability/selected-traces.json'), 'utf8'))
    : null;
  const targets = {
    slow: {url: selected && `http://localhost:16686/trace/${selected.slow.traceID}`, file: 'jaeger-slow-trace.png'},
    error: {url: selected && `http://localhost:16686/trace/${selected.error.traceID}`, file: 'jaeger-error-trace.png'},
    alerts: {url: 'http://localhost:9090/alerts', file: 'prometheus-alert-firing.png'},
  };
  const kinds = kind === 'all' ? ['alerts', 'slow', 'error'] : [kind];
  if (kinds.some(key => !targets[key]?.url)) throw new Error('Choose slow, error, alerts or all');
  const browser = await chromium.launch({
    executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true,
  });
  try {
    for (const key of kinds) {
    const page = await browser.newPage({viewport: {width: 1700, height: 1300}});
    await page.goto(targets[key].url, {waitUntil: 'domcontentloaded'});
    await page.waitForTimeout(3000);
    for (const text of process.argv.slice(3)) {
      const target = page.getByText(text, {exact: true});
      console.log('Matching text elements:', await target.count());
      if (await target.count() !== 1) throw new Error('Click target is ambiguous; inspect body text first');
      await target.click();
      await page.waitForTimeout(1000);
    }
    console.log(key, (await page.locator('body').innerText()).slice(0, 9000));
    fs.mkdirSync(path.join(root, 'screenshots'), {recursive: true});
    await page.screenshot({path: path.join(root, 'screenshots', targets[key].file), fullPage: true});
    console.log('Saved', targets[key].file);
    await page.close();
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
