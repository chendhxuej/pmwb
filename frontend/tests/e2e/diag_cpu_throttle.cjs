/** 高保真复现：CPU 4x 降速 + 多路由漫游后，测选人弹窗组织/身份操作 */
const puppeteer = require('puppeteer-core');
const BASE = process.env.BASE_URL || 'http://localhost:5173';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const ROUTES = ['/dashboard', '/key-works', '/knowledge-center/hub', '/task-center', '/meeting/list'];

async function run() {
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  // CPU 4x 降速（逼近繁忙真实机）
  const client = await page.createCDPSession();
  await client.send('Emulation.setCPUThrottlingRate', { rate: 4 });

  for (const r of ROUTES) {
    await page.goto(`${BASE}${r}`, { waitUntil: 'networkidle2', timeout: 30000 }).catch(() => {});
    await sleep(1800);
    console.log(`漫游: ${r} 完成`);
  }

  // 回会议页，开选人弹窗
  await page.goto(`${BASE}/meeting/list`, { waitUntil: 'networkidle2' });
  await sleep(2000);
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find((x) => x.textContent.includes('新增会议'));
    b && b.click();
  });
  await sleep(1500);
  await page.click('.staff-select');
  await sleep(1500);

  async function timed(label, fn) {
    const t0 = Date.now();
    await fn();
    console.log(`[${label}] wall=${Date.now() - t0}ms`);
  }

  await timed('打开组织下拉', async () => {
    await page.click('.staff-picker-filters .el-select:nth-child(1) .el-select__wrapper, .staff-picker-filters .el-select:nth-child(1) input');
    await sleep(400);
  });
  await timed('选择组织', async () => {
    await page.evaluate(() => {
      const p = [...document.querySelectorAll('.el-select-dropdown')].find((x) => x.getBoundingClientRect().height > 0);
      p?.querySelector('.el-select-dropdown__item')?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    await sleep(400);
  });
  await timed('打开身份下拉', async () => {
    await page.click('.staff-picker-filters .el-select:nth-child(2) .el-select__wrapper, .staff-picker-filters .el-select:nth-child(2) input');
    await sleep(400);
  });
  await timed('选择身份', async () => {
    await page.evaluate(() => {
      const p = [...document.querySelectorAll('.el-select-dropdown')].find((x) => x.getBoundingClientRect().height > 0);
      p?.querySelector('.el-select-dropdown__item')?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    await sleep(400);
  });
  await timed('搜索键入「大海」', async () => {
    await page.type('.staff-picker-search input', '大海', { delay: 120 });
    await sleep(400);
  });
  const nodes = await page.evaluate(() => document.querySelectorAll('*').length);
  console.log('DOM 节点数:', nodes);
  await browser.close();
}
run().catch((e) => { console.error('[FATAL]', e); process.exit(1); });
