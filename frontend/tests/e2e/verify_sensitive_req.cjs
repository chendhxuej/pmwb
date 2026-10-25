/**
 * 验证「需求与交付 - 敏感需求跟踪」tab（2026-10-25 新增）
 *
 * 背景：
 *   P0/P1 敏感需求端到端倒排跟踪子模块。本回归确保在**真实 DOM** 里可用：
 *     1. 第 5 个 tab「敏感需求跟踪」存在且可点击，面板真实渲染
 *     2. 统计条 5 张卡（在跟/超期/临期/督办升级/逾期未上线）
 *     3. 列表真实渲染：需求编号+名称、级别、上线要求、里程碑进度、跟踪态
 *     4. 跟踪态徽章为**中文标签**（来自状态注册表 sensitive_req_track 域），
 *        不能退化成 active/delayed 等英文 key（2026-09-20 同类事故）
 *     5. 详情抽屉打开：关键信息条（上线要求/倒计时）+ 泳道/空态 + 督办记录
 *     6. 深链 ?sensitive=<req_id> 直开详情抽屉
 *
 * 运行：
 *   node tests/e2e/verify_sensitive_req.cjs
 * 前置：前端 5173 + 后端 8000 均已启动，且已执行过 POST /sensitive-reqs/sync。
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

    // 前置：确保池里有数据
    const syncRes = await page.evaluate(async (API) => {
      const r = await fetch(`${API}/sensitive-reqs/sync`, { method: 'POST' }).then((x) => x.json());
      return r?.data || null;
    }, API);
    console.log(`sync: ${JSON.stringify(syncRes || {})}`);
    check('sync 接口可用', !!syncRes && typeof syncRes.sensitive === 'number');

    await page.goto(`${BASE}/requirement-delivery`, { waitUntil: 'networkidle2', timeout: TIMEOUT });
    await sleep(RENDER_WAIT);

    // 1. 第 5 个 tab 存在
    const tabInfo = await page.evaluate(() => {
      const tabs = [...document.querySelectorAll('.el-tabs__item')];
      const target = tabs.find((t) => t.textContent.includes('敏感需求跟踪'));
      return { count: tabs.length, found: !!target, text: target ? target.textContent.trim() : '' };
    });
    check('tab「敏感需求跟踪」存在', tabInfo.found, `共 ${tabInfo.count} 个 tab`);

    // 2. 点击进入面板
    await page.evaluate(() => {
      const tabs = [...document.querySelectorAll('.el-tabs__item')];
      const target = tabs.find((t) => t.textContent.includes('敏感需求跟踪'));
      if (target) target.click();
    });
    await sleep(RENDER_WAIT + 500);

    // 3. 统计条
    const statsInfo = await page.evaluate(() => {
      const panel = document.querySelector('.srp');
      if (!panel) return { mounted: false };
      const labels = [...panel.querySelectorAll('.pm-stat__label')].map((e) => e.textContent.trim());
      return {
        mounted: true,
        labels,
        hasInPool: labels.includes('在跟需求'),
        hasOverdue: labels.includes('里程碑超期'),
        hasDeadline: labels.includes('逾期未上线'),
      };
    });
    check('面板挂载', statsInfo.mounted === true);
    check('统计条含 在跟/超期/逾期未上线 卡', statsInfo.hasInPool && statsInfo.hasOverdue && statsInfo.hasDeadline,
      (statsInfo.labels || []).join('/'));

    // 4. 列表与中文跟踪态徽章
    const listInfo = await page.evaluate(() => {
      const panel = document.querySelector('.srp');
      if (!panel) return { rows: 0 };
      const rows = panel.querySelectorAll('.el-table__body tr');
      const badges = [...panel.querySelectorAll('.el-table__body .el-tag, .el-table__body [class*="badge"]')]
        .map((e) => e.textContent.trim());
      const badEnglish = rows.length > 0 && [...panel.querySelectorAll('.el-table__body')].some(
        (tb) => /(^|\s)(active|delayed|escalated)(\s|$)/.test(tb.textContent)
      );
      const hasProgress = /\/\s*\d+/.test(panel.querySelector('.el-table__body')?.textContent || '');
      return { rows: rows.length, badges: badges.slice(0, 6), badEnglish, hasProgress };
    });
    check('列表有在跟数据行', listInfo.rows > 0, `${listInfo.rows} 行`);
    check('里程碑进度列渲染（done/total）', listInfo.hasProgress === true);
    check('跟踪态未退化成英文 key', listInfo.badEnglish === false);

    // 5. 详情抽屉（点第一行「详情」）
    const firstReqId = await page.evaluate(() => {
      const panel = document.querySelector('.srp');
      if (!panel) return null;
      const idEl = panel.querySelector('.el-table__body .srp-req-id');
      return idEl ? idEl.textContent.trim() : null;
    });
    check('拿到首行需求编号', !!firstReqId, firstReqId || '');

    await page.evaluate(() => {
      const panel = document.querySelector('.srp');
      const btns = [...panel.querySelectorAll('.el-table__body .el-button')];
      const detail = btns.find((b) => b.textContent.includes('详情'));
      if (detail) detail.click();
    });
    await sleep(RENDER_WAIT + 800);

    const drawerInfo = await page.evaluate(() => {
      const drawers = [...document.querySelectorAll('.el-drawer')];
      const open = drawers.find((d) => d.closest('.el-overlay')?.style?.display !== 'none' && d.offsetParent !== null)
        || drawers.find((d) => d.textContent.includes('上线要求'));
      if (!open) return { open: false };
      const text = open.textContent;
      return {
        open: true,
        hasDeadline: text.includes('上线要求'),
        hasCountdown: text.includes('倒计时'),
        hasLog: text.includes('督办记录'),
        hasEditorBtn: /调整倒排|生成倒排建议/.test(text),
      };
    });
    check('详情抽屉打开', drawerInfo.open === true);
    check('关键信息条含 上线要求/倒计时', drawerInfo.hasDeadline && drawerInfo.hasCountdown);
    check('倒排编辑按钮存在', drawerInfo.hasEditorBtn === true);
    check('督办记录区存在', drawerInfo.hasLog === true);

    // 关闭抽屉
    await page.keyboard.press('Escape');
    await sleep(800);

    // 6. 深链 ?sensitive=<req_id> 直开抽屉
    if (firstReqId) {
      await page.goto(`${BASE}/requirement-delivery?sensitive=${encodeURIComponent(firstReqId)}`,
        { waitUntil: 'networkidle2', timeout: TIMEOUT });
      await sleep(RENDER_WAIT + 1000);
      const deepInfo = await page.evaluate(() => {
        const drawers = [...document.querySelectorAll('.el-drawer')];
        const open = drawers.find((d) => d.textContent.includes('上线要求') && d.textContent.includes('督办记录'));
        return { open: !!open };
      });
      check('深链 ?sensitive= 直开详情', deepInfo.open === true);
    }

    // 页面 JS 错误检查（computed('字符串') 白屏类事故的兜底）
    check('无页面 JS 错误', pageErrors.length === 0, pageErrors.slice(0, 2).join(' | '));

  } catch (err) {
    console.error(`[FATAL] ${err.message}`);
    fail++;
  } finally {
    await browser.close();
  }

  console.log(`\n结果：${pass} 通过 / ${fail} 失败`);
  process.exit(fail > 0 ? 1 : 0);
}

run();
