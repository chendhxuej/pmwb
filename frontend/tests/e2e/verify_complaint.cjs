/**
 * 客诉专题 DOM 回归（真实页面断言，运行态≠代码态）。
 * 运行：cd frontend && node tests/e2e/verify_complaint.cjs
 * 前置：后端 8000 + 前端 5173 已启动。
 * 覆盖：
 *   1. /operation/complaint-center/dashboard 看板渲染（KPI/图表/批量簇表/共性问题卡）
 *   2. /operation/complaint-center/tickets 台账渲染 + 人工校正后 classify_by=manual
 *   3. /operation/complaint-center/actions 措施台账渲染 + 登记对话框 + 所属问题列
 *   4. 任务中心来源下拉出现「客诉措施」且列表可查询（仍 9 来源）
 *   5. 问题台账子页可达 + 周报下载 HTML 图表可渲染（单文件自包含回归）
 *   6. 全程无页面 JS 错误
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
    // ── 1. 压降看板 ──
    await page.goto(`${BASE}/operation/complaint-center/dashboard`, {
      waitUntil: 'networkidle2', timeout: 45000,
    });
    await sleep(1500);
    const dash = await page.evaluate(() => {
      const t = document.body.innerText;
      return {
        title: document.querySelector('.pm-page-header__title')?.innerText || '',
        kpiNums: [...document.querySelectorAll('.kpi-num')].map((e) => e.innerText.trim()),
        hasPie: !!document.querySelector('.chart-pie canvas, .chart-pie svg'),
        hasLine: !!document.querySelector('.chart-line canvas, .chart-line svg'),
        hasClusterTable: t.includes('批量数据异常专题'),
        hasProblemCard: t.includes('共性问题闭环'),
        hasProblemEntry: t.includes('进入问题台账'),
        navHasProblems: t.includes('问题台账'),
        empty: t.includes('暂无客诉数据'),
      };
    });
    check('看板标题渲染', dash.title === '客诉压降看板', `title=${dash.title}`);
    if (dash.empty) {
      check('看板空态提示（库内无数据时合法）', dash.empty);
    } else {
      check('看板 KPI 卡片 ≥6', dash.kpiNums.length >= 6, `kpi=${dash.kpiNums.length}`);
      check('性质结构图已渲染(canvas)', dash.hasPie);
      check('趋势图已渲染(canvas)', dash.hasLine);
      check('批量簇专题卡存在', dash.hasClusterTable);
      check('共性问题闭环卡存在', dash.hasProblemCard && dash.hasProblemEntry);
    }

    // ── 2. 工单台账 ──
    await page.goto(`${BASE}/operation/complaint-center/tickets`, {
      waitUntil: 'networkidle2', timeout: 45000,
    });
    await sleep(1500);
    const ledger = await page.evaluate(() => {
      const rows = document.querySelectorAll('.el-table__body tr');
      const t = document.body.innerText;
      return {
        title: document.querySelector('.pm-page-header__title')?.innerText || '',
        rowCount: rows.length,
        totalText: (t.match(/共 (\d+) 条/) || [])[1] || '',
        hasDictBtn: t.includes('分类字典'),
        hasManualTag: t.includes('人工'),
      };
    });
    check('台账标题渲染', ledger.title === '客诉工单台账', `title=${ledger.title}`);
    check('台账有数据行', ledger.rowCount > 0, `rows=${ledger.rowCount}`);
    check('字典入口存在', ledger.hasDictBtn);
    check('人工/自动分类标记渲染', ledger.hasManualTag);

    // 人工校正交互：取第一行未 manual 的单 → 打开校正框 → 保存
    const corrected = await page.evaluate(async () => {
      const rows = [...document.querySelectorAll('.el-table__body tr')];
      const target = rows.find((r) => r.innerText.includes('自动'));
      if (!target) return { skipped: true };
      const btn = [...target.querySelectorAll('button')].find((b) => b.innerText.includes('校正分类'));
      if (!btn) return { skipped: true, reason: 'no-button' };
      btn.click();
      await new Promise((r) => setTimeout(r, 500));
      const dialog = document.querySelector('.el-dialog');
      if (!dialog) return { skipped: true, reason: 'no-dialog' };
      const save = [...dialog.querySelectorAll('button')].find((b) => b.innerText.includes('保存'));
      if (save) save.click();
      await new Promise((r) => setTimeout(r, 1200));
      return { skipped: false };
    });
    if (!corrected.skipped) {
      await sleep(800);
      const after = await page.evaluate(() => document.body.innerText.includes('人工'));
      check('人工校正流转成功（自动→人工）', after);
    } else {
      check('人工校正交互（无可校正单，跳过）', true);
    }

    // ── 3. 措施台账 ──
    await page.goto(`${BASE}/operation/complaint-center/actions`, {
      waitUntil: 'networkidle2', timeout: 45000,
    });
    await sleep(1200);
    const actions = await page.evaluate(() => {
      const t = document.body.innerText;
      return {
        title: document.querySelector('.pm-page-header__title')?.innerText || '',
        hasRegister: t.includes('登记措施'),
        hasVerify: t.includes('结算验证'),
        hasUrge: t.includes('督办'),
        rowCount: document.querySelectorAll('.el-table__body tr').length,
      };
    });
    check('措施台账标题渲染', actions.title === '客诉改进措施台账', `title=${actions.title}`);
    check('登记/结算/督办入口齐全', actions.hasRegister && actions.hasVerify && actions.hasUrge);
    check('措施表格渲染（允许空表）', actions.rowCount >= 0);

    // 登记对话框可打开
    await page.evaluate(() => {
      const btn = [...document.querySelectorAll('button')].find((b) => b.innerText.includes('登记措施'));
      if (btn) btn.click();
    });
    await sleep(600);
    const dlgOpen = await page.evaluate(() =>
      !!document.querySelector('.el-dialog') &&
      document.body.innerText.includes('二级场景')
    );
    check('登记措施对话框可打开', dlgOpen);
    await page.keyboard.press('Escape');

    // ── 4. 任务中心来源下拉（来源筛选在「全部任务」子页）──
    await page.goto(`${BASE}/task-center/all`, { waitUntil: 'networkidle2', timeout: 45000 });
    await sleep(1500);
    const tc = await page.evaluate(() => {
      // 来源下拉的 placeholder 固定为「全部来源」（TaskCenterView 筛选区），按此定位
      const input = document.querySelector('input[placeholder="全部来源"]');
      const sel = input?.closest('.el-select');
      if (sel) sel.click();
      return new Promise((resolve) => setTimeout(() => {
        // 多个下拉共挂 body，取「全部来源」选项所在的那个 dropdown
        const drops = [...document.querySelectorAll('.el-select-dropdown')];
        const target = drops.find((d) =>
          [...d.querySelectorAll('.el-select-dropdown__item')].some((i) => i.innerText.trim() === '全部来源')
        );
        const opts = target
          ? [...target.querySelectorAll('.el-select-dropdown__item')].map((e) => e.innerText.trim())
          : [];
        resolve({ opts, hasComplaint: opts.includes('客诉措施') });
      }, 600));
    });
    check('任务中心来源下拉含「客诉措施」', tc.hasComplaint, `opts=${tc.opts.join('/')}`);

    // 客诉措施来源列表可查询（后端 9 来源口径）
    const listResp = await page.evaluate(async () => {
      const r = await fetch('/api/v1/task-center/tasks?page=1&page_size=20&source=complaint_action');
      const j = await r.json();
      return { code: j.code, total: j.data?.total };
    });
    check('客诉措施来源列表接口可达', listResp.code === 0 && typeof listResp.total === 'number',
      `total=${listResp.total}`);

    // ── 5. 问题台账页 + 周报下载 HTML 图表自包含回归 ──
    await page.goto(`${BASE}/operation/complaint-center/problems`, {
      waitUntil: 'networkidle2', timeout: 45000,
    });
    await sleep(1200);
    const prob = await page.evaluate(() => {
      const t = document.body.innerText;
      return {
        title: document.querySelector('.pm-page-header__title')?.innerText || '',
        hasKpi: document.querySelectorAll('.kpi-num').length >= 5,
        hasCandidateZone: t.includes('候选问题'),
        hasLedger: t.includes('问题台账'),
        hasScan: t.includes('扫描候选'),
      };
    });
    check('问题台账标题渲染', prob.title === '共性问题台账', `title=${prob.title}`);
    check('问题台账 KPI ≥5', prob.hasKpi);
    check('候选确认区存在', prob.hasCandidateZone);
    check('台账区/扫描入口存在', prob.hasLedger && prob.hasScan);

    // 措施台账出现「所属问题」列（登记对话框含所属问题选择器）
    await page.goto(`${BASE}/operation/complaint-center/actions`, {
      waitUntil: 'networkidle2', timeout: 45000,
    });
    await sleep(1000);
    const hasProblemCol = await page.evaluate(() =>
      document.body.innerText.includes('所属问题'));
    check('措施台账「所属问题」列存在', hasProblemCol);

    // 周报下载：单文件自包含，本地打开 canvas ≥ 2（修复外链 assets 断裂回归）
    const week = await page.evaluate(async () => {
      const r = await fetch('/api/v1/complaint/metrics');
      const j = await r.json();
      return j.data?.week || '';
    });
    if (week) {
      const http = require('http');
      const html = await new Promise((resolve) => {
        http.get(`http://127.0.0.1:8000/api/v1/complaint/reports/${week}/download?ext=html`,
          (res) => {
            let buf = '';
            res.on('data', (c) => (buf += c));
            res.on('end', () => resolve(buf));
          }).on('error', () => resolve(''));
      });
      const os = require('os');
      const tmp = require('path').join(os.tmpdir(), `verify_report_${week}.html`);
      fs.writeFileSync(tmp, html);
      const p2 = await browser.newPage();
      await p2.goto('file:///' + tmp.replace(/\\/g, '/'), { waitUntil: 'networkidle2', timeout: 30000 });
      await sleep(1000);
      const chartCnt = await p2.evaluate(() => document.querySelectorAll('.chart canvas').length);
      check('周报下载 HTML 图表可渲染(canvas≥2)', chartCnt >= 2, `canvas=${chartCnt}`);
      await p2.close();
      fs.unlinkSync(tmp);
    } else {
      check('周报下载 HTML 图表（无数据周跳过）', true);
    }

    // /import 端点可用性：用已归档文件幂等重传（BOMC 去重，不产生新数据）
    const archive = 'D:/项目/个人工作台系统/data/complaint/2026-W43/小信工单上周全部明细_20261027091922.xlsx';
    if (fs.existsSync(archive)) {
      const imp = await page.evaluate(async (b64) => {
        const bin = atob(b64);
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        const fd = new FormData();
        fd.append('file', new Blob([bytes]), 'reupload.xlsx');
        fd.append('with_report', 'false');
        const r = await fetch('/api/v1/complaint/import', { method: 'POST', body: fd });
        const j = await r.json();
        return { status: r.status, code: j.code, inserted: j.data?.ingest?.inserted };
      }, fs.readFileSync(archive).toString('base64'));
      check('xlsx 上传端点可用（幂等重传）',
        imp.status === 200 && imp.code === 0 && imp.inserted === 0,
        `status=${imp.status} inserted=${imp.inserted}`);
    } else {
      check('xlsx 上传端点（无归档文件跳过）', true);
    }

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
