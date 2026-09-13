/**
 * UI 评估截图工具 —— 抓取关键页面首屏，供 UI 设计评估用
 * 运行： node tests/e2e/ui_shots.cjs
 */
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const OUT = path.resolve(__dirname, '../../tmp_uishots');

const PAGES = [
  ['dashboard', '/dashboard'],
  ['task-center', '/task-center'],
  ['requirement-delivery', '/requirement-delivery'],
  ['operation-overview', '/operation/overview'],
  ['meeting-list', '/meeting/list'],
  ['knowledge-hub', '/knowledge-center/hub'],
  ['mail-logs', '/mail-center/logs'],
  ['ai-qa', '/ai-center/qa'],
  ['todo', '/todo'],
  ['personnel', '/basic-data'],
];

const log = [];
function p(msg) { log.push(msg); }

(async () => {
  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1600,1000'],
    defaultViewport: { width: 1600, height: 1000, deviceScaleFactor: 1 },
  });
  for (const [name, route] of PAGES) {
    const page = await browser.newPage();
    const errs = [];
    page.on('pageerror', (e) => errs.push(String(e.message).slice(0, 160)));
    page.on('console', (m) => {
      if (m.type() === 'error') errs.push('[console] ' + m.text().slice(0, 160));
    });
    try {
      await page.goto(BASE + route, { waitUntil: 'networkidle2', timeout: 30000 });
      await new Promise((r) => setTimeout(r, 3000));
      const info = await page.evaluate(() => {
        const app = document.querySelector('#app');
        const main = document.querySelector('.main-content') || app;
        return {
          len: app ? app.innerHTML.length : 0,
          scrollH: main ? main.scrollHeight : 0,
          text: (main ? main.innerText : '').slice(0, 200),
        };
      });
      await page.screenshot({ path: path.join(OUT, name + '.png') });
      p(`${name}  ok len=${info.len} scrollH=${info.scrollH} errs=${errs.length ? errs.join(' | ') : 'none'}`);
    } catch (e) {
      p(`${name}  FAIL ${String(e.message).slice(0, 200)}`);
    }
    await page.close();
  }
  await browser.close();
  fs.writeFileSync(path.join(OUT, '_log.txt'), log.join('\n'), 'utf8');
})();
