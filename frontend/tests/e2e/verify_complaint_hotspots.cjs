/**
 * 热点投诉模块 + 全链路下钻 DOM 回归（真实页面断言，运行态≠代码态）。
 * 运行：cd frontend && node tests/e2e/verify_complaint_hotspots.cjs
 * 前置：后端 8000 + 前端 5173 已启动。
 * 覆盖：
 *   1. /operation/complaint-center/hotspots 页面结构（标题/摘要/榜单行）
 *   2. 榜单行：场景名 + 一级性质中文标签 + 环比 badge + 单量数字
 *   3. 「工单明细」下钻抽屉可打开且含工单行（数量下钻明细）
 *   4. 抽屉内再点工单行 → 详情抽屉含 AI 分析块（置信度/依据）
 *   5. 旧入口 /operation/complaint 重定向到热点模块（热点口径唯一）
 *   6. 立问题/关联已有问题按钮二选一存在
 *   7. 全程无页面 JS 错误
 */
const puppeteer = require('puppeteer-core');
const fs = require('fs');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const CHROME_CANDIDATES = [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
];
const exe = CHROME_CANDIDATES.find((p) => fs.existsSync(p));

const log = [];
const check = (name, cond, extra) =>
  log.push(`${cond ? 'PASS' : 'FAIL'} ${name}${extra ? ' | ' + extra : ''}`);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const browser = await puppeteer.launch({
    executablePath: exe,
    headless: 'new',
    args: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1000 });
  const jsErrors = [];
  page.on('pageerror', (e) => jsErrors.push(String(e)));

  try {
    // ── 1. 页面结构 ──
    await page.goto(`${BASE}/operation/complaint-center/hotspots`, {
      waitUntil: 'networkidle2', timeout: 45000,
    });
    await sleep(1600);

    const head = await page.evaluate(() => ({
      title: document.querySelector('.page-header__title, .page-title, h1, h2')?.innerText || '',
      body: document.body.innerText.slice(0, 400),
      rows: document.querySelectorAll('.hot-row').length,
      empty: !!document.querySelector('.hot-list .el-empty'),
    }));
    check('热点页标题含「热点投诉」', /热点投诉/.test(head.title), head.title);
    check('摘要区含「本周新增投诉」', /本周新增投诉/.test(head.body));
    check('榜单行或空态二者其一', head.rows > 0 || head.empty, `rows=${head.rows}, empty=${head.empty}`);

    // ── 2. 榜单行内容 ──
    const rowInfo = await page.evaluate(() => {
      const rows = [...document.querySelectorAll('.hot-row')];
      if (!rows.length) return null;
      const first = rows[0];
      return {
        name: first.querySelector('.hot-name')?.innerText.trim() || '',
        tags: [...first.querySelectorAll('.hot-name .el-tag')].map((t) => t.innerText.trim()),
        badge: first.querySelector('.hot-cnt .badge')?.innerText.trim() || '',
        cnt: first.querySelector('.hot-cnt .n')?.innerText.trim() || '',
        hasDrill: [...first.querySelectorAll('button')].some((b) => b.innerText.includes('工单明细')),
        hasProblemBtn: [...first.querySelectorAll('button')].some(
          (b) => b.innerText.includes('立问题') || b.innerText.includes('关联已有问题')),
      };
    });
    if (rowInfo) {
      const L1 = ['系统问题', '流程优化', '投诉咨询', '数据问题', '待分析'];
      check('榜首行有场景名', rowInfo.name.length > 0, rowInfo.name.slice(0, 30));
      check('一级性质为 4 类中文标签',
        rowInfo.tags.some((t) => L1.some((l) => t.includes(l))), rowInfo.tags.join('/'));
      check('环比 badge 有文案', rowInfo.badge.length > 0, rowInfo.badge);
      check('单量为数字', /^\d+$/.test(rowInfo.cnt), rowInfo.cnt);
      check('行内有「工单明细」按钮', rowInfo.hasDrill);
      check('行内有立问题或关联已有问题按钮', rowInfo.hasProblemBtn);
    } else {
      check('榜单行内容检查（无数据跳过）', true, 'empty state');
    }

    // ── 3. 下钻抽屉 ──
    if (rowInfo && rowInfo.hasDrill) {
      await page.evaluate(() => {
        const btn = [...document.querySelectorAll('.hot-row button')]
          .find((b) => b.innerText.includes('工单明细'));
        btn && btn.click();
      });
      await sleep(1800);
      const drill = await page.evaluate(() => {
        const drawers = [...document.querySelectorAll('.el-drawer')]
          .filter((d) => d.offsetParent !== null);
        const d = drawers[drawers.length - 1];
        if (!d) return { open: false };
        return {
          open: true,
          title: d.querySelector('.el-drawer__title, .el-drawer__header')?.innerText.trim() || '',
          rows: d.querySelectorAll('.el-table__body-wrapper tbody tr').length,
          headers: [...d.querySelectorAll('.el-table__header th')].map((t) => t.innerText.trim()).filter(Boolean),
          body: d.innerText.slice(0, 200),
        };
      });
      check('下钻抽屉打开', drill.open, drill.title || '');
      check('抽屉表格有工单行', (drill.rows || 0) > 0, `rows=${drill.rows}`);
      check('抽屉列含工单号与 AI 置信',
        (drill.headers || []).some((h) => h.includes('工单号'))
        && (drill.headers || []).some((h) => h.includes('AI')), (drill.headers || []).join(','));

      // ── 4. 行点击 → 详情抽屉含 AI 分析块 ──
      if ((drill.rows || 0) > 0) {
        await page.evaluate(() => {
          const drawers = [...document.querySelectorAll('.el-drawer')]
            .filter((d) => d.offsetParent !== null);
          const d = drawers[drawers.length - 1];
          const tr = d?.querySelector('.el-table__body-wrapper tbody tr');
          tr && tr.click();
        });
        await sleep(1500);
        const detail = await page.evaluate(() => {
          const drawers = [...document.querySelectorAll('.el-drawer')]
            .filter((d) => d.offsetParent !== null);
          const d = drawers[drawers.length - 1];
          return { hasAi: !!d?.querySelector('.ai-block'), text: (d?.innerText || '').slice(0, 300) };
        });
        check('工单详情含 AI 分析块', detail.hasAi, detail.text.slice(0, 80));
      }
    }

    // ── 5. 旧入口重定向 ──
    await page.goto(`${BASE}/operation/complaint`, { waitUntil: 'networkidle2', timeout: 45000 });
    await sleep(1200);
    check('旧热点入口重定向到专题热点模块',
      page.url().includes('/complaint-center/hotspots'), page.url());

    // ── 6. 无 JS 错误 ──
    check('全程无页面 JS 错误', jsErrors.length === 0, jsErrors.slice(0, 2).join(' / '));
  } catch (e) {
    check('流程异常', false, String(e).slice(0, 160));
  } finally {
    await browser.close();
  }

  console.log(log.join('\n'));
  const fail = log.filter((l) => l.startsWith('FAIL')).length;
  const total = log.length;
  console.log(`\n=== TOTAL ${total} / PASS ${total - fail} / FAIL ${fail} ===`);
  process.exit(fail ? 1 : 0);
})();
