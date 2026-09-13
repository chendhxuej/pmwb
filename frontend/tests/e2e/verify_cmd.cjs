const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const OUT = path.resolve(__dirname, '../../tmp_uishots');

(async () => {
  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1600,1000'],
    defaultViewport: { width: 1600, height: 1000, deviceScaleFactor: 1 },
  });
  const page = await browser.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
  await page.goto(BASE + '/dashboard', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise((r) => setTimeout(r, 1500));
  // 点击 ⌘K 命令栏
  await page.click('.cmd-bar');
  await new Promise((r) => setTimeout(r, 600));
  await page.screenshot({ path: path.join(OUT, 'cmd_clicked.png') });
  // 输入搜索词"任务"
  await page.type('.cp-input', '任务', { delay: 50 });
  await new Promise((r) => setTimeout(r, 400));
  await page.screenshot({ path: path.join(OUT, 'cmd_filtered.png') });
  // ESC 关闭
  await page.keyboard.press('Escape');
  await new Promise((r) => setTimeout(r, 300));
  const overlayGone = await page.evaluate(() => !document.querySelector('.cp-overlay'));
  await page.screenshot({ path: path.join(OUT, 'cmd_closed.png') });
  fs.writeFileSync(path.join(OUT, '_cmd_log.txt'), [
    `errs=${errs.length ? errs.join(' | ') : 'none'}`,
    `overlayAfterEsc=${overlayGone}`,
  ].join('\n'), 'utf8');
  await browser.close();
})();
