/**
 * 重点工作「周计划 / 成员待办」字段调整验证
 *
 * 覆盖：
 *  1) 周计划列表不再有「周次」「责任人」列，且新增「关联待办（成员）」列
 *  2) 新增周计划弹窗不再有「周次」「责任人」表单项
 *  3) 成员待办列表「关联」列可见（关联周计划后显示周计划标题）+ 「编辑」入口可用
 *  4) 无 console error / pageerror
 *
 * 说明：脚本会用接口临时造一条关联待办用于断言，结束后自动删除。
 * 运行：cd frontend && node tests/e2e/verify_weekly_fields.cjs
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

  const isLogin = await page.evaluate(
    () => /登录|signin/i.test(document.body.innerText) && !document.querySelector('.el-table')
  );
  if (isLogin) { log('  [SKIP] 被登录页拦截'); await browser.close(); process.exit(3); }

  // 造数据：一条关联到「某条现有周计划」的成员待办
  const seed = await page.evaluate(async () => {
    const j = await (await fetch('/api/v1/key-works?page=1&page_size=1')).json();
    const kwId = j.data.items[0].id;
    const d = await (await fetch(`/api/v1/key-works/${kwId}`)).json();
    const wp = (d.data.weekly_plans || [])[0] || null;
    const t = await (await fetch(`/api/v1/key-works/${kwId}/member-tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: '[自动化测试] 关联可见性验证',
        assignee: '陈大海',
        status: 'in_progress',
        link_type: wp ? 'weekly_plan' : 'none',
        link_id: wp ? wp.id : null,
      }),
    })).json();
    return { kwId, wpId: wp && wp.id, wpTitle: wp && wp.title, taskId: t.data && t.data.id };
  });
  log(`  造数据: kw=${seed.kwId} weekly=${seed.wpId}(${seed.wpTitle}) task=${seed.taskId}`);

  await page.reload({ waitUntil: 'networkidle2' }).catch(() => {});
  await sleep(3000);

  // 打开第一条工单抽屉
  await page.evaluate(() => {
    const rows = document.querySelectorAll('.el-table__body-wrapper tbody tr');
    if (rows.length) rows[0].click();
  });
  await sleep(2500);
  const drawerOpen = await page.evaluate(() => !!document.querySelector('.el-drawer'));
  assert(drawerOpen, '工单抽屉已打开');
  if (!drawerOpen) { await browser.close(); process.exit(1); }

  const clickTab = async (label) => {
    const ok = await page.evaluate((lb) => {
      const tabs = [...document.querySelectorAll('.el-drawer .el-tabs__item')];
      const t = tabs.find((x) => x.textContent.trim() === lb);
      if (t) { t.click(); return true; }
      return false;
    }, label);
    await sleep(1300);
    return ok;
  };

  // ---------- 1) 周计划 tab ----------
  log('==> 周计划 tab');
  assert(await clickTab('周计划'), '切到「周计划」tab');

  const weekly = await page.evaluate(() => {
    const tables = [...document.querySelectorAll('.el-drawer .el-table')];
    // 周计划表：含「任务标题」且不含「月份」（月度计划表才有月份）
    const tb = tables.find((t) => {
      const txt = t.innerText || '';
      return txt.includes('任务标题') && !txt.includes('月份');
    });
    if (!tb) return null;
    return {
      headers: [...tb.querySelectorAll('thead th')].map((th) => th.innerText.trim()).filter(Boolean),
      rows: tb.querySelectorAll('.el-table__body-wrapper tbody tr').length,
      firstRowText: (tb.querySelector('.el-table__body-wrapper tbody tr') || {}).innerText || '',
    };
  });
  assert(!!weekly, '定位到周计划表格');
  if (weekly) {
    log('  表头: ' + weekly.headers.join(' | ') + ` (行数=${weekly.rows})`);
    log('  首行: ' + weekly.firstRowText.replace(/\n/g, ' / ').slice(0, 160));
    assert(!weekly.headers.includes('周次'), '周计划列表已无「周次」列');
    assert(!weekly.headers.includes('责任人'), '周计划列表已无「责任人」列');
    assert(weekly.headers.some((h) => h.includes('关联待办')), '周计划列表新增「关联待办（成员）」列');
    if (weekly.rows > 0) {
      assert(weekly.firstRowText.includes('陈大海') || weekly.firstRowText.includes('未指派'),
        '周计划行内展示关联待办的负责人（联动可见）');
    }
  }

  // 新增周计划弹窗
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('.el-drawer button')].find((x) => x.textContent.includes('新增周计划'));
    if (b) b.click();
  });
  await sleep(1300);
  const weeklyDialog = await page.evaluate(() => {
    const dlgs = [...document.querySelectorAll('.el-dialog')].filter((d) => d.offsetParent !== null);
    const d = dlgs[dlgs.length - 1];
    if (!d) return null;
    return {
      title: (d.querySelector('.el-dialog__title') || {}).innerText || '',
      labels: [...d.querySelectorAll('.el-form-item__label')].map((l) => l.innerText.trim()),
    };
  });
  assert(!!weeklyDialog, '新增周计划弹窗已打开');
  if (weeklyDialog) {
    log(`  弹窗「${weeklyDialog.title}」字段: ${weeklyDialog.labels.join(' | ')}`);
    assert(!weeklyDialog.labels.includes('周次'), '新增周计划弹窗已无「周次」字段');
    assert(!weeklyDialog.labels.includes('责任人'), '新增周计划弹窗已无「责任人」字段');
  }
  await page.keyboard.press('Escape');
  await sleep(900);

  // ---------- 2) 成员待办 tab ----------
  log('==> 成员待办 tab');
  assert(await clickTab('成员待办'), '切到「成员待办」tab');

  const task = await page.evaluate(() => {
    const tables = [...document.querySelectorAll('.el-drawer .el-table')];
    const tb = tables.find((t) => {
      const txt = t.innerText || '';
      return txt.includes('负责人') && txt.includes('截止') && txt.includes('关联');
    });
    if (!tb) return null;
    const rows = [...tb.querySelectorAll('.el-table__body-wrapper tbody tr')];
    const target = rows.find((r) => r.innerText.includes('[自动化测试] 关联可见性验证')) || rows[0];
    return {
      headers: [...tb.querySelectorAll('thead th')].map((th) => th.innerText.trim()).filter(Boolean),
      rows: rows.length,
      targetText: target ? target.innerText.replace(/\n/g, ' / ') : '',
      targetButtons: target ? [...target.querySelectorAll('button')].map((b) => b.textContent.trim()) : [],
    };
  });
  assert(!!task, '定位到成员待办表格');
  if (task) {
    log('  表头: ' + task.headers.join(' | ') + ` (行数=${task.rows})`);
    log('  目标行: ' + task.targetText.slice(0, 160));
    assert(task.headers.includes('关联'), '成员待办列表新增「关联」列');
    assert(/周计划[:：]/.test(task.targetText), '关联列显示所属周计划标题');
    assert(task.targetButtons.includes('编辑'), '行内已有「编辑」按钮');
  }

  // 点编辑验证弹窗
  await page.evaluate(() => {
    const tables = [...document.querySelectorAll('.el-drawer .el-table')];
    const tb = tables.find((t) => (t.innerText || '').includes('关联') && (t.innerText || '').includes('截止'));
    if (!tb) return;
    const rows = [...tb.querySelectorAll('.el-table__body-wrapper tbody tr')];
    const target = rows.find((r) => r.innerText.includes('[自动化测试] 关联可见性验证')) || rows[0];
    const btn = target && [...target.querySelectorAll('button')].find((b) => b.textContent.trim() === '编辑');
    if (btn) btn.click();
  });
  await sleep(1300);
  const editDlg = await page.evaluate(() => {
    const dlgs = [...document.querySelectorAll('.el-dialog')].filter((d) => d.offsetParent !== null);
    const d = dlgs[dlgs.length - 1];
    if (!d) return null;
    const inputs = [...d.querySelectorAll('input')].map((i) => i.value);
    return {
      title: (d.querySelector('.el-dialog__title') || {}).innerText || '',
      labels: [...d.querySelectorAll('.el-form-item__label')].map((l) => l.innerText.trim()),
      inputs,
    };
  });
  assert(!!editDlg && editDlg.title.includes('编辑成员待办'), `点「编辑」打开编辑弹窗（标题：${editDlg && editDlg.title}）`);
  if (editDlg) {
    log('  编辑弹窗字段: ' + editDlg.labels.join(' | '));
    assert(editDlg.inputs.some((v) => v && v.includes('关联可见性验证')), '编辑弹窗已回填原待办标题');
  }
  await page.keyboard.press('Escape');
  await sleep(600);

  // ---------- 3) 清理 + 控制台 ----------
  const cleaned = await page.evaluate(async (s) => {
    if (!s.taskId) return 'no-task';
    const r = await (await fetch(`/api/v1/key-works/${s.kwId}/member-tasks/${s.taskId}`, { method: 'DELETE' })).json();
    return JSON.stringify(r.data);
  }, seed);
  log(`==> 清理测试待办: ${cleaned}`);

  const realErrors = errors.filter((e) => !/favicon|ResizeObserver/i.test(e));
  log(`==> console errors: ${realErrors.length}`);
  realErrors.slice(0, 6).forEach((e) => log('    ' + e));
  assert(realErrors.length === 0, '无 console/page error');

  log(`\n结果: ${failures === 0 ? 'ALL PASS' : failures + ' FAILED'}`);
  await browser.close();
  process.exit(failures === 0 ? 0 : 1);
}

run().catch((e) => { console.error(e); process.exit(2); });
