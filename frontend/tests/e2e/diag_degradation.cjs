/** 退化测试：反复开关选人弹窗，观察交互耗时与 DOM/popper 是否单调增长（泄漏签名） */
const puppeteer = require('puppeteer-core');
const BASE = process.env.BASE_URL || 'http://localhost:5173';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function run() {
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  await page.goto(`${BASE}/meeting/list`, { waitUntil: 'networkidle2' });
  await sleep(2000);
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find((x) => x.textContent.includes('新增会议'));
    b && b.click();
  });
  await sleep(1200);

  const stats = () => page.evaluate(() => ({
    nodes: document.querySelectorAll('*').length,
    poppers: document.querySelectorAll('.el-select-dropdown').length,
    popperItems: document.querySelectorAll('.el-select-dropdown__item').length,
    dialogs: document.querySelectorAll('.el-dialog').length,
    overlays: document.querySelectorAll('.el-overlay').length,
  }));

  for (let i = 1; i <= 10; i++) {
    // 打开弹窗
    await page.click('.staff-select');
    await sleep(500);
    // 打开组织下拉并选一个
    const t0 = Date.now();
    await page.click('.staff-picker-filters .el-select:nth-child(1) .el-select__wrapper, .staff-picker-filters .el-select:nth-child(1) input');
    await page.evaluate(() => {
      const p = [...document.querySelectorAll('.el-select-dropdown')].find((x) => x.getBoundingClientRect().height > 0);
      p?.querySelector('.el-select-dropdown__item')?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    const openMs = Date.now() - t0;
    await sleep(400);
    // 关弹窗（点弹窗自己的 X）
    await page.evaluate(() => {
      const dlgs = [...document.querySelectorAll('.el-dialog')].filter((d) => d.offsetParent);
      const picker = dlgs.find((d) => d.querySelector('.staff-picker'));
      picker?.querySelector('.el-dialog__headerbtn')?.click();
    });
    await sleep(500);
    const s = await stats();
    console.log(`第${String(i).padStart(2)}轮: 下拉打开+选项=${openMs}ms | nodes=${s.nodes} poppers=${s.poppers} popperItems=${s.popperItems} dialogs=${s.dialogs} overlays=${s.overlays}`);
  }
  await browser.close();
}
run().catch((e) => { console.error('[FATAL]', e); process.exit(1); });
