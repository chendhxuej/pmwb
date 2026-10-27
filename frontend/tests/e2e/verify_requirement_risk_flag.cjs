/**
 * 验证「超期风险标记 + 开发天数检索 + 敏感池移出」（2026-10-27）
 *
 * 覆盖（真实 DOM 断言）：
 *   1. 需求 tab：检索区新增「开发天数 >」输入框；表格新增多选列 +「超期风险」「开发天数」列
 *   2. API：PUT /requirements/risk-flag/batch set → 首条需求打标 → 刷新后行内出现「超期风险」红标
 *   3. API：clear → 刷新后红标消失（自清理，不在开发库留脏数据）
 *   4. GET /requirements?dev_days_gt=N 请求可达且结构正常（total/items/pages）
 *   5. 勾选首行复选框 → 出现批量「标记超期风险」按钮
 *   6. 敏感需求跟踪面板操作列出现「移出」按钮（只验证存在，**不点击**——
 *      dismiss 永不复活，点了会把真实需求永久移出跟踪池）
 *
 * 运行：node tests/e2e/verify_requirement_risk_flag.cjs
 * 前置：前端 5173 + 后端 8000 已启动（后端须含 20261027000003 迁移）。
 */
const puppeteer = require('puppeteer-core');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const API = process.env.API_BASE || 'http://127.0.0.1:8000/api/v1';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
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
  let browser;
  try {
    browser = await puppeteer.launch({
      executablePath: CHROME,
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

    // ── 前置：取需求列表第一条作为打标对象（可逆：set 后必 clear）──
    const first = await page.evaluate(async (API) => {
      const r = await fetch(`${API}/requirements?page=1&page_size=1`).then((x) => x.json());
      const item = r?.data?.items?.[0];
      return item ? { req_id: item.req_id, dev_days: item.dev_days ?? null } : null;
    }, API);
    check('需求列表接口可用且有数据', !!first, first ? first.req_id : '列表为空，无法继续');

    // ── API：dev_days_gt 参数可达 ──
    const dd = await page.evaluate(async (API) => {
      const r = await fetch(`${API}/requirements?dev_days_gt=1&page=1&page_size=5`).then((x) => x.json());
      return { code: r?.code, keys: r?.data ? Object.keys(r.data) : [] };
    }, API);
    check('GET /requirements?dev_days_gt 可用', dd.code === 0 && dd.keys.includes('total') && dd.keys.includes('items'));

    // ── 打标（set）──
    if (first) {
      const setRes = await page.evaluate(async (API, rid) => {
        const r = await fetch(`${API}/requirements/risk-flag/batch`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ req_ids: [rid], action: 'set' }),
        }).then((x) => x.json());
        return r?.data || null;
      }, API, first.req_id);
      check('PUT risk-flag/batch set 成功', !!setRes && setRes.updated === 1, JSON.stringify(setRes || {}));
    }

    // ── DOM：需求 tab ──
    await page.goto(`${BASE}/requirement-delivery`, { waitUntil: 'networkidle2', timeout: TIMEOUT });
    await sleep(RENDER_WAIT);

    const dom1 = await page.evaluate(() => {
      const bodyText = document.body.innerText;
      const hasDevDaysInput = !!document.querySelector('.table-toolbar .el-input-number');
      const headers = [...document.querySelectorAll('.req-table th')].map((t) => t.textContent.trim());
      return {
        hasDevDaysInput,
        hasRiskCol: headers.some((h) => h.includes('超期风险')),
        hasDaysCol: headers.some((h) => h.includes('开发天数')),
        hasSelectionCol: !!document.querySelector('.req-table .el-table-column--selection, .req-table th.el-table-column--selection'),
      };
    });
    check('检索区有「开发天数」输入框', dom1.hasDevDaysInput);
    check('表格有「超期风险」列', dom1.hasRiskCol);
    check('表格有「开发天数」列', dom1.hasDaysCol);
    check('表格有多选列', dom1.hasSelectionCol);

    // 行内红标（打标后刷新可见）
    const tagAfterSet = await page.evaluate((rid) => {
      const row = [...document.querySelectorAll('.req-table .el-table__row')]
        .find((r) => r.textContent.includes(rid));
      return row ? row.textContent.includes('超期风险') : false;
    }, first ? first.req_id : '');
    check('打标后行内出现「超期风险」红标', tagAfterSet, first ? first.req_id : '');

    // ── 勾选首行 → 批量按钮出现 ──
    await page.evaluate(() => {
      const box = document.querySelector('.req-table .el-table__row .el-checkbox');
      if (box) box.click();
    });
    await sleep(600);
    const batchBtn = await page.evaluate(() => {
      const btns = [...document.querySelectorAll('.table-toolbar button')];
      const b = btns.find((x) => x.textContent.includes('标记超期风险'));
      return b ? b.textContent.trim() : '';
    });
    check('勾选后出现「标记超期风险」批量按钮', batchBtn.includes('标记超期风险'), batchBtn);

    // ── 清标（clear，自清理）──
    if (first) {
      await page.evaluate(async (API, rid) => {
        await fetch(`${API}/requirements/risk-flag/batch`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ req_ids: [rid], action: 'clear' }),
        });
      }, API, first.req_id);
      await page.reload({ waitUntil: 'networkidle2', timeout: TIMEOUT });
      await sleep(RENDER_WAIT);
      const tagAfterClear = await page.evaluate((rid) => {
        const row = [...document.querySelectorAll('.req-table .el-table__row')]
          .find((r) => r.textContent.includes(rid));
        return row ? row.textContent.includes('超期风险') : false;
      }, first.req_id);
      check('清标后红标消失（自清理）', !tagAfterClear);
    }

    // ── 敏感需求跟踪面板：移出按钮存在（不点击）──
    await page.evaluate(() => {
      const tabs = [...document.querySelectorAll('.el-tabs__item')];
      const target = tabs.find((t) => t.textContent.includes('敏感需求跟踪'));
      if (target) target.click();
    });
    await sleep(RENDER_WAIT + 500);
    const dismissBtn = await page.evaluate(() => {
      const btns = [...document.querySelectorAll('.el-table__row button')];
      return btns.filter((b) => b.textContent.trim() === '移出').length;
    });
    check('敏感面板操作列有「移出」按钮', dismissBtn > 0, `${dismissBtn} 个`);
    check('无页面 JS 错误', pageErrors.length === 0, pageErrors.slice(0, 2).join(' | '));

    console.log(`\n结果：${pass} passed, ${fail} failed`);
  } finally {
    await browser.close();
  }
  process.exit(fail > 0 ? 1 : 0);
}

run();
