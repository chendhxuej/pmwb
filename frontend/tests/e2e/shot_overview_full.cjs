const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const OUT = path.resolve(__dirname, '../../tmp_uishots');

(async () => {
  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1600,1400'],
    defaultViewport: { width: 1600, height: 1400, deviceScaleFactor: 1 },
  });
  const page = await browser.newPage();
  await page.goto(BASE + '/task-center/overview', { waitUntil: 'networkidle2', timeout: 45000 });
  await new Promise((r) => setTimeout(r, 1600));
  const out = path.join(OUT, 'task_overview_full.png');
  await page.screenshot({ path: out, fullPage: true });
  console.log('saved', out);
  await browser.close();
})();
