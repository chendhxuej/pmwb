/**
 * 人员选择弹窗（StaffSelect）组织/身份筛选卡顿诊断
 *
 * 背景：老大反馈公共选人弹窗内「全部组织 / 全部身份」两个筛选下拉操作异常卡顿。
 * 代码与数据量排查（16 组 / 93 人 / 选项接口 <100ms）均正常，故在真实浏览器里做运行态剖析：
 *   1. 拦截 setInterval/setTimeout/rAF —— 抓定时器泄漏 / 死循环
 *   2. PerformanceObserver(longtask) —— 抓主线程长任务
 *   3. 网络请求计数 —— 抓轮询风暴
 *   4. 真实交互：打开弹窗 → 点组织下拉 → 选项 → 清除 → 点身份下拉，统计交互耗时与长任务
 *
 * 运行：
 *   cd frontend && node tests/e2e/diag_staff_select_lag.cjs
 */
const puppeteer = require('puppeteer-core');

const BASE = process.env.BASE_URL || 'http://localhost:5173';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const TIMEOUT = Number(process.env.TIMEOUT) || 20000;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

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
  page.setDefaultTimeout(TIMEOUT);
  await page.setViewport({ width: 1440, height: 900 });

  const consoleLogs = [];
  page.on('console', (msg) => {
    const t = msg.type();
    if (t === 'error' || t === 'warn') consoleLogs.push(`[${t}] ${msg.text()}`);
  });
  page.on('pageerror', (err) => consoleLogs.push(`[pageerror] ${err.message}`));

  // —— 页面脚本加载前注入探针：计时器工厂 + 长任务观察器 + 请求计数 ——
  await page.evaluateOnNewDocument(() => {
    window.__timers = { interval: [], timeout: [], raf: 0 };
    const _si = window.setInterval;
    window.setInterval = function (fn, ms, ...rest) {
      let stack = '';
      try { stack = new Error().stack.split('\n').slice(2, 5).join(' <- '); } catch (e) {}
      const id = _si(fn, ms, ...rest);
      window.__timers.interval.push({ id, ms, stack });
      return id;
    };
    const _st = window.setTimeout;
    window.setTimeout = function (fn, ms, ...rest) {
      const id = _st(fn, ms, ...rest);
      window.__timers.timeout.push({ id, ms });
      return id;
    };
    const _raf = window.requestAnimationFrame;
    window.requestAnimationFrame = function (fn) {
      window.__timers.raf++;
      return _raf(fn);
    };

    window.__longTasks = [];
    try {
      new PerformanceObserver((list) => {
        for (const e of list.getEntries()) {
          window.__longTasks.push({ dur: Math.round(e.duration), t: Date.now() });
        }
      }).observe({ entryTypes: ['longtask'] });
    } catch (e) {}

    window.__reqCount = 0;
    const _fetch = window.fetch;
    window.fetch = function (...a) { window.__reqCount++; return _fetch(...a); };
    const _xo = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (...a) { window.__reqCount++; return _xo.apply(this, a); };
  });

  console.log('==> 打开会议管理页 /meeting/list');
  await page.goto(`${BASE}/meeting/list`, { waitUntil: 'networkidle2', timeout: TIMEOUT });
  await sleep(2500);

  const probe0 = await page.evaluate(() => ({
    intervals: window.__timers.interval,
    timeoutCount: window.__timers.timeout.length,
    rafCount: window.__timers.raf,
    longTasks: window.__longTasks.length,
    reqCount: window.__reqCount,
  }));
  console.log(`[基线] setInterval=${probe0.intervals.length} 个, setTimeout(累计)=${probe0.timeoutCount}, rAF(累计)=${probe0.rafCount}, 长任务=${probe0.longTasks}, 请求=${probe0.reqCount}`);
  for (const it of probe0.intervals) {
    console.log(`  ⏱ setInterval ${it.ms}ms  stack: ${it.stack}`);
  }

  // 空闲 3 秒再采样，看请求/长任务是否在空转时仍在增长（轮询风暴）
  const reqBefore = await page.evaluate(() => window.__reqCount);
  const ltBefore = await page.evaluate(() => window.__longTasks.length);
  await sleep(3000);
  const reqAfter = await page.evaluate(() => window.__reqCount);
  const ltAfter = await page.evaluate(() => window.__longTasks.length);
  console.log(`[空闲3s] 请求 ${reqBefore} -> ${reqAfter} (Δ${reqAfter - reqBefore}), 长任务 ${ltBefore} -> ${ltAfter} (Δ${ltAfter - ltBefore})`);

  // —— 打开选人弹窗：先点「新增会议」打开表单，里面有 StaffSelect ——
  console.log('==> 点击「新增会议」打开会议表单');
  await page.evaluate(() => {
    const btns = [...document.querySelectorAll('button')];
    const add = btns.find((b) => b.textContent.includes('新增会议'));
    if (add) add.click();
  });
  await sleep(1200);
  const triggerCount = await page.$$eval('.staff-select', (els) => els.length);
  console.log(`  页面 StaffSelect 触发器数量: ${triggerCount}`);
  if (!triggerCount) {
    console.error('[FAIL] 页面无 StaffSelect');
    await browser.close();
    process.exit(1);
  }
  await page.click('.staff-select');
  await sleep(1200);

  const dialogInfo = await page.evaluate(() => {
    const dlg = document.querySelector('.el-dialog');
    const filters = [...document.querySelectorAll('.staff-picker-filters .el-select')];
    return {
      dialogOpen: !!dlg,
      filterCount: filters.length,
      groupCount: document.querySelectorAll('.staff-picker-group').length,
      optionCount: document.querySelectorAll('.staff-picker-option').length,
    };
  });
  console.log(`[弹窗] 打开=${dialogInfo.dialogOpen}, 筛选下拉=${dialogInfo.filterCount}, 分组=${dialogInfo.groupCount}, 人员项=${dialogInfo.optionCount}`);

  // —— 交互 1：点「全部组织」下拉并选一个 ——
  const nodeCount = () => page.evaluate(() => document.querySelectorAll('*').length);
  async function interact(label, selectIdx, action) {
    await page.evaluate(() => { window.__longTasks.length = 0; });
    const t0 = Date.now();
    await action();
    const wall = Date.now() - t0;
    const lt = await page.evaluate(() => window.__longTasks.map((e) => e.dur));
    console.log(`[交互:${label}] 耗时=${wall}ms, 长任务=${JSON.stringify(lt)}, DOM节点=${await nodeCount()}`);
    return wall;
  }

  // 可见 popper 内点第一个选项
  async function clickFirstVisibleOption() {
    const ok = await page.evaluate(() => {
      const pops = [...document.querySelectorAll('.el-select-dropdown')];
      const visible = pops.find((p) => p.offsetParent !== null || p.getBoundingClientRect().height > 0);
      if (!visible) return false;
      const item = visible.querySelector('.el-select-dropdown__item');
      if (!item) return false;
      item.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      return true;
    });
    if (!ok) throw new Error('无可见下拉项');
  }

  // 组织下拉
  await interact('打开组织下拉', 0, async () => {
    await page.click('.staff-picker-filters .el-select:nth-child(1) .el-select__wrapper, .staff-picker-filters .el-select:nth-child(1) input');
    await sleep(600);
  });
  let orgItems = await page.$$eval('.el-select-dropdown__item', (els) => els.length).catch(() => 0);
  console.log(`  组织下拉选项数(document内全部popper)=${orgItems}`);
  await page.screenshot({ path: 'tests/e2e/_diag_org_dropdown.png' });

  await interact('点选组织选项', 0, async () => {
    await clickFirstVisibleOption();
    await sleep(600);
  });

  // 清除组织筛选
  await interact('清除组织筛选', 0, async () => {
    const clearBtn = await page.$('.staff-picker-filters .el-select:nth-child(1) .el-select__clear, .staff-picker-filters .el-select:nth-child(1) .el-input__clear');
    if (clearBtn) { await clearBtn.click(); }
    else { console.log('  (无清除按钮，跳过)'); }
    await sleep(400);
  });

  // 身份下拉
  await interact('打开身份下拉', 1, async () => {
    await page.click('.staff-picker-filters .el-select:nth-child(2) .el-select__wrapper, .staff-picker-filters .el-select:nth-child(2) input');
    await sleep(600);
  });
  let roleItems = await page.$$eval('.el-select-dropdown__item', (els) => els.length).catch(() => 0);
  console.log(`  身份下拉选项数(document内全部popper)=${roleItems}`);
  await page.screenshot({ path: 'tests/e2e/_diag_role_dropdown.png' });

  await interact('点选身份选项', 1, async () => {
    await clickFirstVisibleOption();
    await sleep(600);
  });

  // —— 退化测试：反复开/关弹窗，看耗时与 DOM 是否劣化（泄漏签名） ——
  console.log('==> 退化测试：循环开关选人弹窗 8 次');
  await page.evaluate(() => { document.querySelector('.el-dialog__headerbtn, .el-dialog__close')?.closest('button')?.click(); });
  await sleep(500);
  for (let i = 1; i <= 8; i++) {
    await page.click('.staff-select');
    await sleep(400);
    await page.click('.staff-picker-filters .el-select:nth-child(1) .el-select__wrapper, .staff-picker-filters .el-select:nth-child(1) input');
    await sleep(400);
    await clickFirstVisibleOption().catch(() => {});
    await sleep(400);
    const nodes = await nodeCount();
    const items = await page.$$eval('.el-select-dropdown__item', (els) => els.length).catch(() => 0);
    console.log(`  第${i}轮: DOM节点=${nodes}, popper选项累计=${items}`);
    await page.evaluate(() => { document.querySelector('.el-dialog__headerbtn, .el-dialog__close')?.closest('button')?.click(); });
    await sleep(400);
  }

  // —— 汇总 ——
  const probeEnd = await page.evaluate(() => ({
    intervals: window.__timers.interval.length,
    longTasks: window.__longTasks.length,
    reqCount: window.__reqCount,
  }));
  console.log(`[结束] setInterval=${probeEnd.intervals}, 长任务(累计,交互后清零过)=${probeEnd.longTasks}, 请求=${probeEnd.reqCount}`);
  console.log('---- console 错误/警告 ----');
  const uniq = [...new Set(consoleLogs)];
  uniq.slice(0, 20).forEach((l) => console.log('  ' + l));
  if (!uniq.length) console.log('  (无)');

  await browser.close();
}

run().catch((e) => { console.error('[FATAL]', e); process.exit(1); });
