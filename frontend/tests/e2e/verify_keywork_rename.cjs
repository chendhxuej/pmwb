/**
 * 重点工作分类「专题工作」→「每人一件事（专题工作）」更名验证
 *
 * 覆盖：
 *  1) 分类 Tab 显示「每人一件事」，不再出现「专题工作」Tab
 *  2) 页头副标题含「每人一件事」
 *  3) 列表/详情的分类标签渲染为「每人一件事（专题工作）」
 *  4) 新建对话框分类下拉含新名
 *  5) 无 console error / pageerror
 *
 * 运行：cd frontend && node tests/e2e/verify_keywork_rename.cjs
 */
const puppeteer = require('puppeteer-core');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const TIMEOUT = Number(process.env.TIMEOUT) || 25000;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const log = (...a) => console.log(...a);
let failures = 0;
function assert(cond, msg) {
  if (cond) log(`  [PASS] ${msg}`);
  else { log(`  [FAIL] ${msg}`); failures++; }
}

async function run() {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  page.setDefaultTimeout(TIMEOUT);
  await page.setViewport({ width: 1600, height: 1000 });

  const errors = [];
  page.on('pageerror', (e) => errors.push(`[pageerror] ${e.message}`));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(`[console.error] ${m.text()}`); });

  log(`==> 打开 ${BASE}/key-works`);
  await page.goto(`${BASE}/key-works`, { waitUntil: 'networkidle2', timeout: 40000 }).catch(() => {});
  await sleep(3000);

  const isLogin = await page.evaluate(() => document.body.innerText.includes('登录') && !!document.querySelector('input[type=password]'));
  if (isLogin) {
    log('!! 需要登录，无法验证（请先在浏览器登录后再跑）');
    await browser.close();
    process.exit(2);
  }

  // ---- 1) Tab 标签 ----
  const tabTexts = await page.$$eval('.el-tabs__item', (els) => els.map((e) => e.innerText.trim()));
  log('  Tab 列表:', JSON.stringify(tabTexts));
  assert(tabTexts.some((t) => t === '每人一件事'), 'Tab 含「每人一件事」');
  assert(!tabTexts.some((t) => t === '专题工作'), 'Tab 不再含纯「专题工作」');

  // ---- 2) 页头副标题 ----
  const sub = await page.$eval('.page-sub', (e) => e.innerText.trim()).catch(() => '');
  log('  页头副标题:', sub);
  assert(sub.includes('每人一件事'), '页头副标题含「每人一件事」');

  // ---- 3) 切到该分类，看分类标签 ----
  const idx = tabTexts.findIndex((t) => t === '每人一件事');
  if (idx >= 0) {
    const tabs = await page.$$('.el-tabs__item');
    await tabs[idx].click();
    await sleep(2500);
    const tags = await page.$$eval('.pm-tag', (els) => els.map((e) => e.innerText.trim()).filter(Boolean));
    log('  该分类下标签样本:', JSON.stringify([...new Set(tags)].slice(0, 6)));
    const hasFull = tags.some((t) => t.includes('每人一件事'));
    assert(hasFull || tags.length === 0, '列表分类标签渲染为「每人一件事（专题工作）」（或无数据）');
    const rowCount = await page.$$eval('tbody tr', (els) => els.length).catch(() => 0);
    log('  该分类行数:', rowCount);
  }

  // ---- 4) 新建对话框分类下拉 ----
  const createBtn = await page.evaluateHandle(() => {
    const btns = [...document.querySelectorAll('.page-actions button')];
    return btns.find((b) => b.innerText.includes('新建')) || null;
  });
  const btnEl = createBtn.asElement();
  if (btnEl) {
    await btnEl.click();
    await sleep(1800);
    const dlgTabs = await page.$$eval('.el-dialog .el-select', (els) => els.length).catch(() => 0);
    // 打开分类下拉
    const opened = await page.evaluate(() => {
      const sel = [...document.querySelectorAll('.el-dialog .el-select')].find((s) => s.innerText.includes('总部试点') || s.innerText.includes('年度任务') || s.innerText.includes('每人一件事'));
      if (!sel) return false;
      const inp = sel.querySelector('input');
      if (inp) inp.click();
      return true;
    });
    await sleep(1500);
    const opts = await page.$$eval('.el-select-dropdown__item', (els) => els.map((e) => e.innerText.trim()));
    log('  分类下拉选项:', JSON.stringify(opts.filter((o) => o && !o.includes('P0') && !o.includes('规划') && !o.includes('进行')).slice(0, 8)));
    assert(opened && opts.some((o) => o.includes('每人一件事')), '新建分类下拉含「每人一件事（专题工作）」');
    // 关闭
    await page.keyboard.press('Escape').catch(() => {});
    await sleep(500);
    await page.evaluate(() => {
      const btns = [...document.querySelectorAll('.el-dialog__footer button, .el-dialog button')];
      const c = btns.find((b) => b.innerText.trim() === '取消');
      if (c) c.click();
    });
    await sleep(800);
  } else {
    log('  !! 未找到「新建重点工作」按钮');
  }

  // ---- 5) 报错 ----
  const realErrors = errors.filter((e) => !/favicon|ResizeObserver|Download the Vue Devtools/i.test(e));
  assert(realErrors.length === 0, `无 console/page 错误（实际 ${realErrors.length} 条）`);
  if (realErrors.length) realErrors.slice(0, 8).forEach((e) => log('    ', e));

  await browser.close();
  log(`\n===== 结果: ${failures === 0 ? '全部通过' : failures + ' 项失败'} =====`);
  process.exit(failures === 0 ? 0 : 1);
}

run().catch((e) => { console.error('脚本异常:', e); process.exit(3); });
