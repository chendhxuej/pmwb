/**
 * 验证「主动优化」工单详情抽屉：点击标题 → 抽屉弹出 + 内容完整
 *
 * 断言点：
 *   1. 主动优化 tab 存在且可切换
 *   2. 表格加载出工单行
 *   3. 点击标题 → el-drawer 弹出（可见）
 *   4. 抽屉头部：#id + 标题 + StatusBadge + 优先级
 *   5. 抽屉主体：现状描述/优化建议/业务管理员/关联需求/备注说明/创建时间 六块
 *   6. 抽屉底部：关闭/编辑/催办/同步 四按钮
 */
const puppeteer = require('puppeteer-core');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const SHOT = process.env.SHOT || 'D:/项目/个人工作台系统/frontend/tests/e2e/_active_opt_drawer.png';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const errors = [];

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

  const page = await browser.newPage();
  page.setViewport({ width: 1440, height: 900 });
  page.on('console', (msg) => {
    const t = msg.text();
    if (/Failed to resolve component|is not defined on instance|Unhandled error during execution/.test(t)) {
      errors.push(t.slice(0, 200));
    }
  });

  const results = [];
  const check = (name, pass, detail = '') => {
    results.push({ name, pass, detail });
    console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? '  | ' + detail : ''}`);
  };

  await page.goto(`${BASE}/requirement-delivery`, { waitUntil: 'networkidle2' });
  await sleep(2500);

  // 1. 切到主动优化 tab
  const switched = await page.evaluate(() => {
    const tabs = [...document.querySelectorAll('.el-tabs__item')];
    const tab = tabs.find((t) => t.textContent.includes('主动优化'));
    if (!tab) return false;
    tab.click();
    return true;
  });
  check('「主动优化」tab 可切换', switched);
  await sleep(2000);

  // 2. 表格有数据行
  const rows = await page.evaluate(() => {
    const pane = [...document.querySelectorAll('.el-tab-pane')].find((p) =>
      p.querySelector('.el-table')
    );
    const tables = [...document.querySelectorAll('.el-table')];
    const t = tables[tables.length - 1];
    return t ? t.querySelectorAll('.el-table__body tbody tr').length : 0;
  });
  check('主动优化表格有数据行', rows > 0, `rows=${rows}`);

  // 3. 点击标题触发抽屉
  const clicked = await page.evaluate(() => {
    const tables = [...document.querySelectorAll('.el-table')];
    const t = tables[tables.length - 1];
    if (!t) return false;
    const firstRow = t.querySelector('.el-table__body tbody tr');
    if (!firstRow) return false;
    const link = firstRow.querySelector('.link-text');
    if (!link) return false;
    link.click();
    return true;
  });
  check('工单标题可点击(link-text 存在)', clicked);
  await sleep(1200);

  // 4. 抽屉弹出 + 内容断言
  const drawer = await page.evaluate(() => {
    const drawers = [...document.querySelectorAll('.el-drawer')];
    const d = drawers.find((x) => {
      const s = getComputedStyle(x.closest('.el-overlay') || x);
      return s.display !== 'none' && (x.closest('.el-overlay')?.offsetParent !== null || getComputedStyle(x.closest('.el-overlay')).visibility !== 'hidden');
    });
    if (!d) return { open: false };
    const text = d.textContent || '';
    return {
      open: true,
      width: getComputedStyle(d).width,
      hasId: /#\d+/.test(text),
      hasStatusBadge: !!d.querySelector('.status-badge, [class*="status"]'),
      hasPriority: /P[0-3]/.test(text),
      blocks: ['现状描述', '优化建议', '业务管理员', '关联需求', '备注说明', '创建时间'].filter(
        (k) => text.includes(k)
      ),
      footerBtns: ['关闭', '编辑', '催办', '同步'].filter((b) =>
        [...d.querySelectorAll('button')].some((x) => x.textContent.includes(b))
      ),
    };
  });
  check('点击标题后抽屉弹出', drawer.open, `width=${drawer.width || '-'}`);
  if (drawer.open) {
    check('抽屉头部含 #工单ID', drawer.hasId);
    check('抽屉头部含状态徽章', drawer.hasStatusBadge);
    check('抽屉含优先级标签', drawer.hasPriority);
    check('六信息块齐全', drawer.blocks.length === 6, `实际: ${drawer.blocks.join('/')}`);
    check('底部四操作按钮齐全', drawer.footerBtns.length === 4, `实际: ${drawer.footerBtns.join('/')}`);
    await page.screenshot({ path: SHOT });
    console.log(`截图: ${SHOT}`);
  }

  // ── 5. 入口增强回归：详情按钮 + 整行点击 ──
  // 关闭当前抽屉
  await page.evaluate(() => {
    const btn = document.querySelector('.el-drawer__close-btn');
    if (btn) btn.click();
  });
  await sleep(900);

  // 5a. 操作列「详情」按钮存在且可开抽屉
  const hasDetailBtn = await page.evaluate(() => {
    const tables = [...document.querySelectorAll('.el-table')];
    const t = tables[tables.length - 1];
    const firstRow = t && t.querySelector('.el-table__body tbody tr');
    return !!(firstRow && [...firstRow.querySelectorAll('button')].some((b) => b.textContent.includes('详情')));
  });
  check('操作列含「详情」按钮', hasDetailBtn);

  if (hasDetailBtn) {
    await page.evaluate(() => {
      const tables = [...document.querySelectorAll('.el-table')];
      const t = tables[tables.length - 1];
      const firstRow = t.querySelector('.el-table__body tbody tr');
      [...firstRow.querySelectorAll('button')].find((b) => b.textContent.includes('详情')).click();
    });
    await sleep(1000);
    const open2 = await page.evaluate(() => {
      const d = [...document.querySelectorAll('.el-drawer')].find(
        (x) => getComputedStyle(x.closest('.el-overlay')).display !== 'none'
      );
      return !!d && /#\d+/.test(d.textContent);
    });
    check('点击「详情」按钮可开抽屉', open2);
    await page.evaluate(() => document.querySelector('.el-drawer__close-btn')?.click());
    await sleep(900);
  }

  // 5b. 整行点击（非标题单元格）可开抽屉
  await page.evaluate(() => {
    const tables = [...document.querySelectorAll('.el-table')];
    const t = tables[tables.length - 1];
    const firstRow = t.querySelector('.el-table__body tbody tr');
    const cells = firstRow.querySelectorAll('td');
    // 点「创建时间」单元格（倒数第 2 列，避开 fixed 操作列与标题列）
    const cell = cells[Math.max(0, cells.length - 2)];
    cell.querySelector('*')?.click();
  });
  await sleep(1000);
  const open3 = await page.evaluate(() => {
    const d = [...document.querySelectorAll('.el-drawer')].find(
      (x) => getComputedStyle(x.closest('.el-overlay')).display !== 'none'
    );
    return !!d && /#\d+/.test(d.textContent);
  });
  check('点击行内非标题区域可开抽屉(row-click)', open3);

  check('无 Vue 致命告警', errors.length === 0, errors.join(' ; ').slice(0, 150));

  await browser.close();
  const failed = results.filter((r) => !r.pass);
  console.log(`\n==== 结果: ${results.length - failed.length}/${results.length} 通过 ====`);
  process.exit(failed.length ? 1 : 0);
}

run().catch((e) => {
  console.error('[FATAL]', e.message);
  process.exit(3);
});
