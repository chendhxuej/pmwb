// 一线调研「淮安订单中心调研」子类端到端验证（2026-10-12）
//
// 覆盖：子类下拉含新子类 / 按新子类筛选取数一致(56条) / 列表渲染子类标签 /
//       详情抽屉出现「基本情况」区块（basic_info 由本次补齐展示）
//
// 运行：cd frontend && node tests/e2e/verify_research_subtype.cjs
const puppeteer = require('puppeteer-core');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';

const log = [];
const check = (name, cond, extra) => log.push(`${cond ? 'PASS' : 'FAIL'} ${name}${extra ? ' | ' + extra : ''}`);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1680, height: 1000 });

  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));

  await page.goto(`${BASE}/research`, { waitUntil: 'networkidle2', timeout: 60000 });
  await page.waitForSelector('.wo-table .el-table__body tbody tr', { timeout: 25000 });
  check('页面加载且表格有数据行', true);

  // ---- 1. 子类下拉含新子类 ----
  await page.evaluate(() => {
    const sels = document.querySelectorAll('.panel-toolbar .el-select');
    const target = sels[1];
    target.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    target.querySelector('input').dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    target.click();
  });
  await sleep(700);
  const opts = await page.$$eval('.el-select-dropdown__item', (els) => els.map((e) => e.textContent.trim()));
  check('子类下拉含「淮安订单中心调研」', opts.includes('淮安订单中心调研'), opts.join(' / '));

  await page.evaluate(() => {
    const items = [...document.querySelectorAll('.el-select-dropdown__item')];
    const t = items.find((e) => e.textContent.trim() === '淮安订单中心调研');
    if (t) t.click();
  });
  await sleep(500);

  // ---- 2. 触发查询 ----
  await page.evaluate(() => {
    const btns = [...document.querySelectorAll('.panel-toolbar button')];
    const b = btns.find((x) => x.textContent.includes('查询'));
    if (b) b.click();
  });
  await sleep(1800);

  const total = await page.$eval('.el-pagination__total', (el) => el.textContent.trim()).catch(() => '(未找到)');
  check('筛选后分页显示共 56 条', /56/.test(total), total);

  // ---- 3. 列表渲染子类标签 ----
  const tags = await page.$$eval('.wo-table .el-table__body tbody tr .el-tag', (els) =>
    els.map((e) => e.textContent.trim())
  );
  check('列表出现「淮安订单中心调研」标签', tags.includes('淮安订单中心调研'), `共${tags.length}个标签`);

  const firstNo = await page
    .$eval('.wo-table .el-table__body tbody tr td:first-child', (el) => el.textContent.trim())
    .catch(() => '');
  check('首行工单编号为淮安批次单号', /^RES-HA2(608|610)-/.test(firstNo), firstNo);

  // ---- 4. 详情抽屉「基本情况」 ----
  await page.evaluate(() => {
    const a = document.querySelector('.wo-table .iss-title');
    if (a) a.click();
  });
  await sleep(1800);
  const secs = await page
    .$$eval('.el-drawer .dt-sec-title', (els) => els.map((e) => e.textContent.trim()))
    .catch(() => []);
  check('详情抽屉含「基本情况」区块', secs.includes('基本情况'), secs.join(' / '));
  const basicText = await page
    .$eval('.el-drawer .dt-desc-pre', (el) => el.textContent.trim())
    .catch(() => '');
  check('基本情况内容含「调研批次」', basicText.includes('调研批次'), basicText.slice(0, 60).replace(/\n/g, '⏎'));

  check('页面无 JS 运行时报错', errors.length === 0, errors.slice(0, 2).join(' ; '));

  await browser.close();
  console.log(log.join('\n'));
  const failed = log.filter((l) => l.startsWith('FAIL')).length;
  console.log(`\n[summary] ${log.length - failed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})().catch((e) => {
  console.log(log.join('\n'));
  console.log('EXCEPTION', e && e.message);
  process.exit(1);
});
