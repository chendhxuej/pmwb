/**
 * StaffSelect 性能重构验证：功能正确性 + 结构变化（轻量化 / v-show 不重建整表）
 *
 * 运行：cd frontend && node tests/e2e/verify_staff_fix.cjs
 */
const puppeteer = require('puppeteer-core');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const TIMEOUT = Number(process.env.TIMEOUT) || 25000;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const log = (...a) => console.log(...a);
let failures = 0;
function assert(cond, msg) {
  if (cond) log(`  ✅ ${msg}`);
  else { log(`  ❌ ${msg}`); failures++; }
}

async function run() {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  page.setDefaultTimeout(TIMEOUT);
  await page.setViewport({ width: 1440, height: 900 });

  const errors = [];
  page.on('pageerror', (e) => errors.push(`[pageerror] ${e.message}`));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(`[console.error] ${m.text()}`); });

  // 长任务观察器（衡量主线程阻塞）
  await page.evaluateOnNewDocument(() => {
    window.__lt = [];
    try {
      new PerformanceObserver((l) => l.getEntries().forEach((e) => window.__lt.push(Math.round(e.duration))))
        .observe({ entryTypes: ['longtask'] });
    } catch (e) {}
  });

  log(`==> 打开 ${BASE}/meeting/list`);
  await page.goto(`${BASE}/meeting/list`, { waitUntil: 'networkidle2', timeout: 40000 }).catch(() => {});
  await sleep(2500);

  const url = page.url();
  log(`    当前 URL: ${url}`);
  const isLogin = await page.evaluate(() => /login|登录|signin/i.test(document.body.innerText) && !document.querySelector('.staff-select'));
  if (isLogin) { log('  ⚠️ 被登录页拦截，需已登录会话才能验证（puppeteer 匿名无 cookie）。请在已登录浏览器手动验证，或注入 token。'); await browser.close(); process.exit(3); }

  // 打开会议表单（含 StaffSelect）
  const opened = await page.evaluate(() => {
    const cand = ['新增会议', '新建会议', '新增', '新建'];
    const btns = [...document.querySelectorAll('button')];
    for (const c of cand) {
      const b = btns.find((x) => x.textContent.trim().includes(c));
      if (b) { b.click(); return c; }
    }
    return null;
  });
  log(`    点击新增入口: ${opened || '(未找到，尝试直接定位)'}`);
  await sleep(1500);

  // 打开【多选】选人弹窗（参会人 multiple 模式，便于验证多选/全选/显隐）
  const multiOpened = await page.evaluate(() => {
    const triggers = [...document.querySelectorAll('.staff-select')];
    const t = triggers.find((e) => e.innerText.includes('参会人')) || triggers[0];
    if (t) { t.click(); return t.innerText.includes('参会人'); }
    return false;
  });
  if (!multiOpened) { log('  ❌ 未找到多选选人触发器'); await browser.close(); process.exit(1); }
  log(`    打开的选人组件: ${multiOpened ? '参会人(多选)' : '第一个(可能单选)'}`);
  await page.waitForSelector('.staff-picker', { timeout: TIMEOUT });
  await sleep(800);
  log('==> 选人弹窗已打开');

  // —— 结构断言 ——
  const struct = await page.evaluate(() => {
    const opts = [...document.querySelectorAll('.staff-picker-option')];
    const visible = opts.filter((o) => o.offsetParent !== null).length;
    return {
      elCheckbox: document.querySelectorAll('.staff-picker .el-checkbox').length,
      checkMarks: document.querySelectorAll('.staff-picker-check').length,
      totalOpts: opts.length,
      visibleOpts: visible,
      groups: document.querySelectorAll('.staff-picker-group').length,
      hasEmpty: !!document.querySelector('.staff-picker .el-empty'),
    };
  });
  log('--- 结构 ---');
  log(`    el-checkbox 实例数 = ${struct.elCheckbox}（改造前=总人数，应=0）`);
  log(`    .staff-picker-check 轻量勾选框 = ${struct.checkMarks}（应>0）`);
  log(`    全量渲染的 .staff-picker-option = ${struct.totalOpts}（v-show 全量渲染）`);
  log(`    默认可见 option = ${struct.visibleOpts}（应=全量）`);
  log(`    分组数 = ${struct.groups}`);
  assert(struct.elCheckbox === 0, '已移除 el-checkbox 重组件（实例数=0）');
  assert(struct.checkMarks > 0 && struct.totalOpts === struct.checkMarks, '轻量勾选框覆盖全部选项');
  assert(struct.totalOpts > 0 && struct.visibleOpts === struct.totalOpts, '默认全量可见');

  // —— 性能：筛选不重建整表（v-show 节点数不变，仅 display 切换）——
  // 用搜索框验证 optionVisible + v-show（el-input 交互可靠；组织/身份下拉共用同一函数）
  log('==> 模拟「搜索筛选」交互（验证 v-show 显隐 + optionVisible 逻辑）');
  const firstLabel = await page.evaluate(() => {
    const o = document.querySelector('.staff-picker-option .staff-picker-name');
    return o ? o.innerText.trim() : '';
  });
  const kw = firstLabel ? firstLabel.slice(0, Math.max(1, Math.ceil(firstLabel.length / 2))) : '';
  const t0 = Date.now();
  await page.type('.staff-picker-search input', kw);
  await sleep(500);
  const filterMs = Date.now() - t0;
  const afterFilter = await page.evaluate(() => {
    const opts = [...document.querySelectorAll('.staff-picker-option')];
    return {
      total: opts.length,
      visible: opts.filter((o) => o.offsetParent !== null).length,
      hidden: opts.filter((o) => o.style.display === 'none').length,
    };
  });
  log(`    搜索词: "${kw}"（取自真实姓名片段 "${firstLabel}"）`);
  log(`    筛选墙钟耗时(输入+列表更新) = ${filterMs}ms`);
  log(`    筛选后 全量节点=${afterFilter.total}（不变，证明非重建） / 可见=${afterFilter.visible} / display:none=${afterFilter.hidden}`);
  assert(afterFilter.total === struct.totalOpts, '筛选后节点总数不变（v-show 显隐，不重建整表）');
  assert(afterFilter.visible < struct.totalOpts && afterFilter.hidden > 0, '搜索后部分项被 v-show 隐藏（显隐生效）');
  // 清除搜索
  await page.evaluate(() => {
    const clr = document.querySelector('.staff-picker-search .el-input__clear');
    if (clr) clr.click();
  });
  await sleep(400);

  // —— 功能：多选（两次点击间留 tick，模拟真实用户间隔，避免同步竞态）——
  log('==> 多选两个人员');
  const clickNth = (n) => page.evaluate((idx) => {
    const vis = [...document.querySelectorAll('.staff-picker-option')].filter((o) => o.offsetParent !== null);
    if (vis[idx]) vis[idx].click();
  }, n);
  await clickNth(0);
  await sleep(250);
  await clickNth(1);
  await sleep(300);
  const selAfterMulti = await page.evaluate(() => {
    const tags = document.querySelectorAll('.staff-picker-tags .el-tag').length;
    const active = document.querySelectorAll('.staff-picker-option.active').length;
    return { tags, active };
  });
  log(`    已选标签数 = ${selAfterMulti.tags} / 高亮行数 = ${selAfterMulti.active}`);
  assert(selAfterMulti.active >= 2, '多选后至少 2 行高亮（active 态正确）');

  // —— 功能：全选某组 ——
  log('==> 点第一组「全选」');
  const beforeAll = await page.evaluate(() => document.querySelectorAll('.staff-picker-tags .el-tag').length);
  await page.evaluate(() => {
    const btn = document.querySelector('.staff-picker-group-select-all');
    if (btn) btn.click();
  });
  await sleep(400);
  const afterAll = await page.evaluate(() => document.querySelectorAll('.staff-picker-tags .el-tag').length);
  log(`    全选前标签 = ${beforeAll} / 全选后 = ${afterAll}`);
  assert(afterAll > beforeAll, '全选按钮使已选人数增加（group 全选生效）');

  // —— 功能：确认关闭 ——
  log('==> 点「确认」');
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll('.staff-picker-footer-actions .el-button')].find((b) => /确认/.test(b.innerText));
    if (btn) btn.click();
  });
  await sleep(600);
  const closed = await page.evaluate(() => !document.querySelector('.staff-picker'));
  assert(closed, '确认后弹窗关闭');

  // —— 性能汇总 ——
  const lt = await page.evaluate(() => window.__lt || []);
  log('--- 性能 ---');
  log(`    交互期间长任务(>50ms)次数 = ${lt.length}，最长 = ${lt.length ? Math.max(...lt) : 0}ms`);

  log('--- 报错 ---');
  if (errors.length) { errors.slice(0, 10).forEach((e) => log(`    ${e}`)); } else { log('    无 pageerror / console.error'); }

  await browser.close();
  log(`\n===== 验证结果：${failures === 0 ? '全部通过 ✅' : failures + ' 项失败 ❌'} =====`);
  process.exit(failures === 0 ? 0 : 1);
}

run().catch((e) => { console.error('[FATAL]', e); process.exit(2); });
