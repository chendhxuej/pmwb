/**
 * 验证「邮件自动抄送规则——收件人含吴雨霜自动带出抄送尹学永」（2026-10-28）
 *
 * 覆盖（真实 DOM 断言，只读真实库，绝不点击「发送」）：
 *   1. /mail-dispatch/auto-cc-rules 端点下发规则 + 触发人邮箱（唯一真相源在后端）
 *   2. 工单页（BUG管理）打开行内「催办」→ MailComposeDialog 弹窗出现
 *   3. 收件人清空后通过人员选择器加入「吴雨霜」→ 抄送框自动出现「尹学永」标签
 *   4. 删掉自动带出的抄送标签后，不再强制回填（尊重人工修改）
 *   5. 取消关闭弹窗（不落库不发送）
 *
 * 运行：node tests/e2e/verify_mail_auto_cc.cjs
 * 前置：前端 5173 + 后端 8000 已启动；BUG管理页至少 1 条工单；人员中台含吴雨霜/尹学永。
 */
const puppeteer = require('puppeteer-core');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const TIMEOUT = Number(process.env.TIMEOUT) || 20000;
const RENDER_WAIT = Number(process.env.RENDER_WAIT) || 2500;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let pass = 0;
let fail = 0;

function check(name, ok, extra = '') {
  if (ok) { pass++; console.log(`  [OK]   ${name}${extra ? ' -> ' + extra : ''}`); }
  else { fail++; console.log(`  [FAIL] ${name}${extra ? ' -> ' + extra : ''}`); }
}

async function run() {
  // ── 0. 后端规则端点直查 ──
  const rulesRes = await fetch(`${BASE.replace('5173', '8000')}/api/v1/mail-dispatch/auto-cc-rules`);
  const rulesJson = await rulesRes.json();
  const rules = rulesJson?.data?.rules || {};
  const trigEmails = rulesJson?.data?.trigger_emails || {};
  check('auto-cc-rules 端点返回规则', rules['吴雨霜'] === '尹学永', JSON.stringify(rules));
  check('端点附带触发人邮箱（供邮箱形态收件人命中）', /@/.test(trigEmails['吴雨霜'] || ''), trigEmails['吴雨霜'] || '缺失');

  let browser;
  try {
    browser = await puppeteer.launch({
      executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    });
  } catch (err) {
    console.error(`[FATAL] 浏览器启动失败: ${err.message}`);
    process.exit(2);
  }

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1600, height: 1000 });
    const pageErrors = [];
    page.on('pageerror', (e) => pageErrors.push(e.message));

    await page.goto(`${BASE}/operation/bug`, { waitUntil: 'networkidle2', timeout: TIMEOUT });
    await sleep(RENDER_WAIT);

    // ── 1. 打开首行的督办下拉（精确找触发按钮文案为「督办」的 el-dropdown）──
    const rowDropdown = await page.evaluateHandle(() => {
      const dds = [...document.querySelectorAll('.el-table__body .el-table__row .el-dropdown')];
      return dds.find((d) => [...d.querySelectorAll('button')].some((b) => b.textContent.includes('督办'))) || null;
    });
    const dropdownEl = rowDropdown.asElement();
    check('工单表格有行且含督办下拉', !!dropdownEl);
    if (!dropdownEl) throw new Error('工单表格无督办下拉');
    await dropdownEl.hover();
    await sleep(600);

    await page.evaluate(() => {
      // el-dropdown 菜单 teleport 到 body，DOM 里有多份隐藏实例；必须先锁定可见菜单再点项
      const visibleMenu = [...document.querySelectorAll('.el-dropdown-menu')]
        .find((m) => m.offsetParent !== null && m.textContent.includes('催办'));
      const item = visibleMenu
        ? [...visibleMenu.querySelectorAll('.el-dropdown-menu__item')]
            .find((x) => x.textContent.includes('催办'))
        : null;
      if (item) item.click();
    });
    await sleep(1200);

    // ── 2. 撰写弹窗出现 ──
    const dlgOpen = await page.evaluate(() => {
      const dialogs = [...document.querySelectorAll('.el-dialog')];
      const d = dialogs.find((x) => x.textContent.includes('撰写邮件') || x.textContent.includes('发送催办邮件'));
      if (!d) return false;
      const overlay = d.closest('.el-overlay');
      return !overlay || getComputedStyle(overlay).display !== 'none';
    });
    check('催办打开撰写弹窗', dlgOpen);
    if (!dlgOpen) throw new Error('撰写弹窗未打开');

    // ── 3. 清空收件人 → 通过人员选择器加入吴雨霜 ──
    // 3a. 清空：点收件人行 staff-select 的 clear 图标
    await page.evaluate(() => {
      const rows = [...document.querySelectorAll('.mail-compose-dialog .compose-row')];
      const toRow = rows.find((r) => r.querySelector('.compose-label')?.textContent.includes('收件人'));
      const clear = toRow?.querySelector('.staff-select-clear');
      if (clear) clear.click();
    });
    await sleep(400);

    // 3b. 点收件人 staff-select → 「选择人员」弹窗
    await page.evaluate(() => {
      const rows = [...document.querySelectorAll('.mail-compose-dialog .compose-row')];
      const toRow = rows.find((r) => r.querySelector('.compose-label')?.textContent.includes('收件人'));
      const sel = toRow?.querySelector('.staff-select');
      if (sel) sel.click();
    });
    await sleep(1000);

    const pickerOpen = await page.evaluate(() => {
      const dialogs = [...document.querySelectorAll('.el-dialog')];
      const d = dialogs.find((x) => x.textContent.includes('选择人员'));
      if (!d) return false;
      const overlay = d.closest('.el-overlay');
      return overlay && getComputedStyle(overlay).display !== 'none';
    });
    check('人员选择器弹窗打开', pickerOpen);

    // 3c. 搜索吴雨霜并点选
    await page.type('.staff-picker-search input', '吴雨霜', { delay: 50 });
    await sleep(1200);
    await page.evaluate(() => {
      const opt = [...document.querySelectorAll('.staff-picker-option')]
        .find((x) => x.querySelector('.staff-picker-name')?.textContent.trim() === '吴雨霜');
      if (opt) opt.click();
    });
    await sleep(300);
    await page.evaluate(() => {
      const dialogs = [...document.querySelectorAll('.el-dialog')];
      const d = dialogs.find((x) => x.textContent.includes('选择人员'));
      const btn = [...d.querySelectorAll('button')].find((b) => b.textContent.trim() === '确认');
      if (btn) btn.click();
    });
    await sleep(1200);

    // ── 4. 断言：收件人含吴雨霜，抄送自动带出尹学永 ──
    const state = await page.evaluate(() => {
      const rows = [...document.querySelectorAll('.mail-compose-dialog .compose-row')];
      const toRow = rows.find((r) => r.querySelector('.compose-label')?.textContent.includes('收件人'));
      const ccRow = rows.find((r) => r.querySelector('.compose-label')?.textContent.includes('抄送'));
      const tags = (row) => [...(row?.querySelectorAll('.staff-select-trigger .el-tag') || [])]
        .map((t) => t.textContent.trim());
      return { to: tags(toRow), cc: tags(ccRow) };
    });
    check('收件人已加入吴雨霜', state.to.some((t) => t.includes('吴雨霜')), JSON.stringify(state.to));
    check('抄送自动带出尹学永', state.cc.some((t) => t.includes('尹学永')), JSON.stringify(state.cc));

    // ── 5. 手动删除抄送标签 → 不强制回填（尊重人工修改）──
    await page.evaluate(() => {
      const rows = [...document.querySelectorAll('.mail-compose-dialog .compose-row')];
      const ccRow = rows.find((r) => r.querySelector('.compose-label')?.textContent.includes('抄送'));
      const tag = [...(ccRow?.querySelectorAll('.staff-select-trigger .el-tag') || [])]
        .find((t) => t.textContent.includes('尹学永'));
      const close = tag?.querySelector('.el-tag__close');
      if (close) close.click();
    });
    await sleep(1000);
    const ccAfterRemove = await page.evaluate(() => {
      const rows = [...document.querySelectorAll('.mail-compose-dialog .compose-row')];
      const ccRow = rows.find((r) => r.querySelector('.compose-label')?.textContent.includes('抄送'));
      return [...(ccRow?.querySelectorAll('.staff-select-trigger .el-tag') || [])]
        .map((t) => t.textContent.trim());
    });
    check('手动删除抄送后不回填', !ccAfterRemove.some((t) => t.includes('尹学永')), JSON.stringify(ccAfterRemove));

    // ── 6. 取消关闭（不发送、不落库）──
    await page.evaluate(() => {
      const dialogs = [...document.querySelectorAll('.el-dialog')];
      const d = dialogs.find((x) => x.textContent.includes('撰写邮件') || x.textContent.includes('发送催办邮件'));
      const btn = [...(d?.querySelectorAll('button') || [])].find((b) => b.textContent.trim() === '取消');
      if (btn) btn.click();
    });
    await sleep(600);

    check('无页面 JS 错误', pageErrors.length === 0, pageErrors.slice(0, 2).join(' | '));

    console.log(`\n结果：${pass} passed, ${fail} failed`);
  } finally {
    await browser.close();
  }
  process.exit(fail > 0 ? 1 : 0);
}

run();
