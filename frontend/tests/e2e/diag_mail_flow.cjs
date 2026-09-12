/** 邮件中心写邮件流程中的选人弹窗组织/身份操作耗时（嵌套弹窗场景） */
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
  const logs = [];
  page.on('console', (m) => { if (['error', 'warn'].includes(m.type())) logs.push(`[${m.type()}] ${m.text()}`); });
  page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`));

  await page.goto(`${BASE}/meeting/list`, { waitUntil: 'networkidle2' });
  await sleep(2500);

  // 打开「新增会议」表单 → 点「会议通知」打开 MailComposeDialog
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find((x) => x.textContent.includes('新增会议'));
    b && b.click();
  });
  await sleep(1200);
  const clicked = await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find((x) => /会议通知|发通知|通知$/.test(x.textContent));
    if (b) { b.click(); return b.textContent.trim(); }
    return null;
  });
  console.log('会议通知按钮:', clicked);
  await sleep(2000);

  // 打开收件人 StaffSelect（mail dialog 内的第一个 .staff-select）
  const triggers = await page.$$eval('.staff-select', (els) => els.length);
  console.log('mail 弹窗内 staff-select 数量:', triggers);
  await page.click('.staff-select');
  await sleep(1000);

  const dlg = await page.evaluate(() => {
    const d = [...document.querySelectorAll('.el-dialog')].filter((x) => x.offsetParent);
    return d.map((x) => x.querySelector('.el-dialog__title')?.textContent);
  });
  console.log('可见弹窗:', JSON.stringify(dlg));

  // 组织下拉交互计时
  async function timed(label, fn) {
    await page.evaluate(() => { window.__lt = []; window.__t0 = performance.now(); });
    await fn();
    const r = await page.evaluate(() => ({ ms: Math.round(performance.now() - window.__t0) }));
    console.log(`[${label}] wall=${r.ms}ms`);
  }

  await timed('打开组织下拉', async () => {
    await page.click('.staff-picker-filters .el-select:nth-child(1) .el-select__wrapper, .staff-picker-filters .el-select:nth-child(1) input');
    await sleep(500);
  });
  await timed('选择组织(AMS)', async () => {
    await page.evaluate(() => {
      const pops = [...document.querySelectorAll('.el-select-dropdown')].filter((p) => p.getBoundingClientRect().height > 0);
      const item = pops[0]?.querySelector('.el-select-dropdown__item');
      item && item.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    await sleep(500);
  });
  await timed('组织筛选后渲染', async () => { await sleep(300); });
  await timed('打开身份下拉', async () => {
    await page.click('.staff-picker-filters .el-select:nth-child(2) .el-select__wrapper, .staff-picker-filters .el-select:nth-child(2) input');
    await sleep(500);
  });
  await timed('选择身份', async () => {
    await page.evaluate(() => {
      const pops = [...document.querySelectorAll('.el-select-dropdown')].filter((p) => p.getBoundingClientRect().height > 0);
      const item = pops[0]?.querySelector('.el-select-dropdown__item');
      item && item.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    await sleep(500);
  });

  // 搜索框逐字输入测试（dialogQuery 重算链）
  await timed('搜索输入-陈', async () => {
    await page.type('.staff-picker-search input', '陈', { delay: 50 });
    await sleep(400);
  });
  await page.screenshot({ path: 'tests/e2e/_diag_mail_flow.png' });

  console.log('---- console ----');
  [...new Set(logs)].slice(0, 15).forEach((l) => console.log(' ' + l));
  await browser.close();
}
run().catch((e) => { console.error('[FATAL]', e); process.exit(1); });
