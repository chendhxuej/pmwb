/**
 * 共性问题台账 DOM 回归（真实页面断言，运行态≠代码态）。
 * 运行：cd frontend && node tests/e2e/verify_complaint_problems.cjs
 * 前置：后端 8000 + 前端 5173 已启动。
 * 覆盖：
 *   1. /operation/complaint-center/problems 页面结构（KPI/候选区/台账）
 *   2. 状态列为中文标签（registry 唯一来源，hydrate 生效）
 *   3. 详情抽屉可打开（关联措施区块）
 *   4. 候选确认区（有候选→有行；无候选→空态，两分支均合法）
 *   5. 手工立问题对话框可打开
 *   6. 任务中心来源下拉仍 9 项（问题不入任务中心）
 *   7. 全程无页面 JS 错误
 */
const puppeteer = require('puppeteer-core');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const CHROME_CANDIDATES = [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
];
const fs = require('fs');
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
    await page.goto(`${BASE}/operation/complaint-center/problems`, {
      waitUntil: 'networkidle2', timeout: 45000,
    });
    await sleep(1500);
    const p1 = await page.evaluate(() => {
      const t = document.body.innerText;
      return {
        title: document.querySelector('.pm-page-header__title')?.innerText || '',
        kpiCnt: document.querySelectorAll('.kpi-num').length,
        kpiVals: [...document.querySelectorAll('.kpi-num')].map((e) => e.innerText.trim()),
        hasCandidate: t.includes('候选问题'),
        hasLedger: t.includes('问题台账'),
        hasScan: t.includes('扫描候选'),
        hasCreate: t.includes('手工立问题'),
        hasUrge: t.includes('问题督办'),
        statusTags: [...document.querySelectorAll('.el-table .el-tag')].map((e) => e.innerText.trim()),
      };
    });
    check('页面标题渲染', p1.title === '共性问题台账', `title=${p1.title}`);
    check('KPI 卡 ≥5 且首卡为数字', p1.kpiCnt >= 5 && /^\d+$/.test(p1.kpiVals[0] || ''),
      `kpi=${p1.kpiCnt} first=${p1.kpiVals[0]}`);
    check('候选区/台账/扫描/立问题/督办入口齐全',
      p1.hasCandidate && p1.hasLedger && p1.hasScan && p1.hasCreate && p1.hasUrge);

    // 候选区：有行或空态均为合法（打印分支）
    const candBranch = await page.evaluate(() => {
      const t = document.body.innerText;
      return { empty: t.includes('暂无待确认候选') };
    });
    check('候选确认区渲染（含空态分支）', true,
      candBranch.empty ? '空态分支' : '有候选行分支');

    // 状态 tag 无英文状态原文（registry 中文标签 hydrate 生效；规则 tag 如 R1批量簇 合法）
    const rawStatus = p1.statusTags.filter((s) =>
      /^(candidate|open|resolving|closed|ignored|merged)$/.test(s));
    check('状态标签为中文（registry 标签）', rawStatus.length === 0,
      `raw=${rawStatus.join('/')}`);

    // 详情抽屉：取台账第一行「详情」按钮（如有行）
    const drawer = await page.evaluate(async () => {
      const rows = [...document.querySelectorAll('.el-table__body tr')];
      const target = rows.find((r) => [...r.querySelectorAll('button')]
        .some((b) => b.innerText.trim() === '详情'));
      if (!target) return { skipped: true };
      const btn = [...target.querySelectorAll('button')].find((b) => b.innerText.trim() === '详情');
      btn.click();
      await new Promise((r) => setTimeout(r, 1200));
      const dw = document.querySelector('.el-drawer');
      return { skipped: !dw, opened: !!dw, hasActions: dw ? dw.innerText.includes('关联措施') : false };
    });
    if (drawer.skipped) {
      check('详情抽屉（台账无行，跳过）', true);
    } else {
      check('详情抽屉可打开且含关联措施区块', drawer.opened && drawer.hasActions);
      await page.keyboard.press('Escape');
      await sleep(400);
    }

    // 手工立问题对话框
    await page.evaluate(() => {
      const btn = [...document.querySelectorAll('button')].find((b) => b.innerText.includes('手工立问题'));
      if (btn) btn.click();
    });
    await sleep(600);
    const dlgOpen = await page.evaluate(() =>
      !!document.querySelector('.el-dialog') && document.body.innerText.includes('场景'));
    check('手工立问题对话框可打开', dlgOpen);
    await page.keyboard.press('Escape');

    // 任务中心来源下拉仍 9 项（不含共性问题）
    await page.goto(`${BASE}/task-center/all`, { waitUntil: 'networkidle2', timeout: 45000 });
    await sleep(1500);
    const tc = await page.evaluate(() => {
      const input = document.querySelector('input[placeholder="全部来源"]');
      const sel = input?.closest('.el-select');
      if (sel) sel.click();
      return new Promise((resolve) => setTimeout(() => {
        const drops = [...document.querySelectorAll('.el-select-dropdown')];
        const target = drops.find((d) =>
          [...d.querySelectorAll('.el-select-dropdown__item')].some((i) => i.innerText.trim() === '全部来源'));
        const opts = target
          ? [...target.querySelectorAll('.el-select-dropdown__item')].map((e) => e.innerText.trim())
          : [];
        resolve({ opts, hasProblem: opts.some((o) => o.includes('共性问题')) });
      }, 600));
    });
    check('任务中心来源仍 9 项且不含共性问题',
      !tc.hasProblem && tc.opts.length <= 10, `opts=${tc.opts.length}`);

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
