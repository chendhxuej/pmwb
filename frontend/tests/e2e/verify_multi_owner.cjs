/**
 * 多负责人（任务/工单关联多个责任人）验证
 *
 * 覆盖：
 *  1) 成员待办列表「负责人」列多值以标签展示
 *  2) 编辑成员待办时多人负责人正确回显（多标签）
 *  3) 新增成员待办 —— 人员选择弹窗可勾选多人，确认后触发器显示多个标签
 *  4) 会议行动项页面：负责人列多值展示 + 编辑弹窗使用人员选择组件（支持多选）
 *  5) 无 console error / pageerror
 *
 * 说明：会临时造一条多负责人成员待办用于断言，结束后自动删除。
 * 运行：cd frontend && node tests/e2e/verify_multi_owner.cjs
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

  // 造数据：一条多负责人成员待办（不从界面选人，直接接口造，避免污染）
  const seed = await page.evaluate(async () => {
    const j = await (await fetch('/api/v1/key-works?page=1&page_size=1')).json();
    const kwId = j.data.items[0].id;
    const t = await (await fetch(`/api/v1/key-works/${kwId}/member-tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: '[自动化测试] 多负责人验证',
        assignee: '陈大海,周静',
        status: 'in_progress',
        link_type: 'none',
      }),
    })).json();
    return { kwId, taskId: t.data && t.data.id, assignee: t.data && t.data.assignee };
  });
  log(`  造数据: kw=${seed.kwId} task=${seed.taskId} assignee=${seed.assignee}`);

  await page.reload({ waitUntil: 'networkidle2' }).catch(() => {});
  await sleep(3000);

  // 打开第一条重点工作抽屉
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

  // ---------- 1) 成员待办列表多标签 ----------
  log('==> 成员待办 tab：负责人多值展示');
  assert(await clickTab('成员待办'), '切到「成员待办」tab');

  const taskTable = await page.evaluate(() => {
    const tables = [...document.querySelectorAll('.el-drawer .el-table')];
    const tb = tables.find((t) => {
      const txt = t.innerText || '';
      return txt.includes('负责人') && txt.includes('截止') && txt.includes('关联');
    });
    if (!tb) return null;
    const rows = [...tb.querySelectorAll('.el-table__body-wrapper tbody tr')];
    const target = rows.find((r) => r.innerText.includes('[自动化测试] 多负责人验证'));
    if (!target) return { headers: [...tb.querySelectorAll('thead th')].map((th) => th.innerText.trim()).filter(Boolean), rows: rows.length, found: false };
    const tds = [...target.querySelectorAll('td')];
    const ownerTd = tds.find((td) => td.querySelectorAll('.owner-tag').length > 0) || tds[1];
    return {
      headers: [...tb.querySelectorAll('thead th')].map((th) => th.innerText.trim()).filter(Boolean),
      rows: rows.length,
      found: true,
      ownerTags: [...ownerTd.querySelectorAll('.owner-tag')].map((t) => t.innerText.trim()),
      ownerText: ownerTd.innerText.trim(),
    };
  });
  assert(!!taskTable, '定位到成员待办表格');
  if (taskTable) {
    log('  表头: ' + (taskTable.headers || []).join(' | '));
    assert(taskTable.found, '找到测试待办行');
    if (taskTable.found) {
      log('  负责人列: ' + JSON.stringify(taskTable.ownerTags) + ' / 文本=' + taskTable.ownerText);
      assert((taskTable.ownerTags || []).length === 2, '负责人列以 2 个标签展示多个责任人');
      assert((taskTable.ownerTags || []).includes('陈大海') && (taskTable.ownerTags || []).includes('周静'), '两个责任人姓名都展示');
    }
  }

  // ---------- 2) 编辑弹窗回显多人 ----------
  log('==> 编辑成员待办：多负责人回显');
  await page.evaluate(() => {
    const tables = [...document.querySelectorAll('.el-drawer .el-table')];
    const tb = tables.find((t) => (t.innerText || '').includes('关联') && (t.innerText || '').includes('截止'));
    if (!tb) return;
    const rows = [...tb.querySelectorAll('.el-table__body-wrapper tbody tr')];
    const target = rows.find((r) => r.innerText.includes('[自动化测试] 多负责人验证'));
    const btn = target && [...target.querySelectorAll('button')].find((b) => b.textContent.trim() === '编辑');
    if (btn) btn.click();
  });
  await sleep(1400);

  const editDlg = await page.evaluate(() => {
    const dlgs = [...document.querySelectorAll('.el-dialog')].filter((d) => d.offsetParent !== null);
    const d = dlgs.find((x) => (x.querySelector('.el-dialog__title') || {}).innerText === '成员待办')
      || dlgs[dlgs.length - 1];
    if (!d) return null;
    const sel = d.querySelector('.staff-select');
    return {
      title: (d.querySelector('.el-dialog__title') || {}).innerText || '',
      hasStaffSelect: !!sel,
      tags: sel ? [...sel.querySelectorAll('.el-tag')].map((t) => t.innerText.trim()) : [],
      labels: [...d.querySelectorAll('.el-form-item__label')].map((l) => l.innerText.trim()),
    };
  });
  assert(!!editDlg, '编辑弹窗已打开');
  if (editDlg) {
    log(`  弹窗「${editDlg.title}」字段: ${editDlg.labels.join(' | ')}`);
    assert(editDlg.hasStaffSelect, '负责人使用统一人员选择组件');
    log('  回显标签: ' + JSON.stringify(editDlg.tags));
    assert(editDlg.tags.length === 2, '编辑时两名责任人正确回显');
  }
  await page.keyboard.press('Escape');
  await sleep(900);

  // ---------- 3) 人员选择弹窗真多选交互 ----------
  log('==> 新增成员待办：人员弹窗勾选多人');
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('.el-drawer button')].find((x) => x.textContent.includes('新增待办'));
    if (b) b.click();
  });
  await sleep(1400);

  // 打开人员选择弹窗
  const opened = await page.evaluate(() => {
    const dlgs = [...document.querySelectorAll('.el-dialog')].filter((d) => d.offsetParent !== null);
    const d = dlgs[dlgs.length - 1];
    const sel = d && d.querySelector('.staff-select');
    if (!sel) return false;
    sel.click();
    return true;
  });
  assert(opened, '新增待办弹窗内点击负责人，触发人员选择弹窗');
  await sleep(1800);

  const picker = await page.evaluate(() => {
    const dlgs = [...document.querySelectorAll('.el-dialog')].filter((d) => d.offsetParent !== null);
    const d = dlgs.find((x) => (x.innerText || '').includes('选择人员'));
    if (!d) return null;
    const opts = [...d.querySelectorAll('.staff-picker-option')];
    return {
      optionCount: opts.length,
      firstName: opts[0] ? opts[0].innerText.trim() : '',
      secondName: opts[1] ? opts[1].innerText.trim() : '',
      hasCheckBox: opts.length ? !!opts[0].querySelector('.staff-picker-check') : false,
    };
  });
  assert(!!picker, '人员选择弹窗已打开');
  if (picker) {
    log(`  候选人数=${picker.optionCount} 前两位=${picker.firstName} / ${picker.secondName}`);
    assert(picker.hasCheckBox, '多选模式显示勾选标记（支持多选）');

    // 注意：两次点击必须分帧执行 —— 同 tick 连点会因 v-model props 异步回流互相覆盖
    const pickNames = [];
    for (const idx of [0, 1]) {
      const nm = await page.evaluate((i) => {
        const dlgs = [...document.querySelectorAll('.el-dialog')].filter((d) => d.offsetParent !== null);
        const d = dlgs.find((x) => (x.innerText || '').includes('选择人员'));
        const opts = [...d.querySelectorAll('.staff-picker-option')];
        if (!opts[i]) return null;
        const name = opts[i].innerText.trim().split('\n')[0];
        opts[i].click();
        return name;
      }, idx);
      pickNames.push(nm);
      await sleep(700); // 等父组件 props 回流 + 渲染
    }
    const selInfo = await page.evaluate(() => {
      const dlgs = [...document.querySelectorAll('.el-dialog')].filter((d) => d.offsetParent !== null);
      const d = dlgs.find((x) => (x.innerText || '').includes('选择人员'));
      if (!d) return null;
      return {
        selLabel: (d.innerText.match(/已选\s*(\d+)\s*人/) || [])[1],
        tagCount: d.querySelectorAll('.staff-picker-tags .el-tag').length,
      };
    });
    log('  勾选: ' + JSON.stringify(pickNames) + ' → 已选=' + (selInfo && selInfo.selLabel) + ' 标签数=' + (selInfo && selInfo.tagCount));
    assert(selInfo && selInfo.selLabel === '2' && selInfo.tagCount === 2, '弹窗内可同时勾选两人（已选 2 人 + 2 个标签）');

    // 确认
    const confirmed = await page.evaluate(() => {
      const dlgs = [...document.querySelectorAll('.el-dialog')].filter((d) => d.offsetParent !== null);
      const d = dlgs.find((x) => (x.innerText || '').includes('选择人员'));
      const btns = [...d.querySelectorAll('button')];
      const ok = btns.find((b) => b.textContent.includes('确认'));
      if (ok) { ok.click(); return true; }
      return false;
    });
    assert(confirmed, '人员弹窗「确认」按钮可点击');
    await sleep(1200);

    const afterConfirm = await page.evaluate(() => {
      const dlgs = [...document.querySelectorAll('.el-dialog')].filter((d) => d.offsetParent !== null);
      // 编辑成员待办弹窗：含「负责人」label
      const target = dlgs.find((d) => [...d.querySelectorAll('.el-form-item__label')].some((l) => l.innerText.trim() === '负责人'));
      const sel = target && target.querySelector('.staff-select');
      return {
        hasDialog: !!target,
        tags: sel ? [...sel.querySelectorAll('.el-tag')].map((t) => t.innerText.trim()) : null,
      };
    });
    log('  确认后触发器标签: ' + JSON.stringify(afterConfirm));
    assert((afterConfirm.tags || []).length === 2, '确认后表单内显示两名责任人标签');
  }

  // ---------- 4) 会议行动项 ----------
  log('==> 会议行动项页面');
  await page.keyboard.press('Escape');
  await sleep(600);
  await page.goto(`${BASE}/meeting/actions`, { waitUntil: 'networkidle2', timeout: 40000 }).catch(() => {});
  await sleep(4000);

  const actions = await page.evaluate(() => {
    const tb = document.querySelector('.el-table');
    if (!tb) return null;
    const headers = [...tb.querySelectorAll('thead th')].map((th) => th.innerText.trim()).filter(Boolean);
    const rows = [...tb.querySelectorAll('.el-table__body-wrapper tbody tr')];
    return {
      headers,
      rows: rows.length,
      firstRowText: rows[0] ? rows[0].innerText.replace(/\n/g, ' / ') : '',
      firstRowTags: rows[0] ? [...rows[0].querySelectorAll('.owner-tag')].map((t) => t.innerText.trim()) : [],
    };
  });
  assert(!!actions, '行动项表格已渲染');
  if (actions) {
    log('  表头: ' + actions.headers.join(' | ') + ` (行数=${actions.rows})`);
    assert(actions.headers.includes('负责人'), '行动项列表含「负责人」列');
    if (actions.firstRowTags.length) log('  首行负责人标签: ' + JSON.stringify(actions.firstRowTags));
  }

  // 编辑弹窗内是否使用人员选择组件（多选）
  const editOpened = await page.evaluate(() => {
    const btns = [...document.querySelectorAll('.el-table__body-wrapper tbody tr button')];
    const b = btns.find((x) => x.textContent.trim() === '编辑');
    if (b) { b.click(); return true; }
    return false;
  });
  if (editOpened) {
    await sleep(1400);
    const dlg = await page.evaluate(() => {
      const dlgs = [...document.querySelectorAll('.el-dialog')].filter((d) => d.offsetParent !== null);
      const d = dlgs[dlgs.length - 1];
      if (!d) return null;
      return {
        title: (d.querySelector('.el-dialog__title') || {}).innerText || '',
        hasStaffSelect: !!d.querySelector('.staff-select'),
        labels: [...d.querySelectorAll('.el-form-item__label')].map((l) => l.innerText.trim()),
      };
    });
    assert(!!dlg && dlg.hasStaffSelect, `行动项编辑弹窗使用人员选择组件（弹窗：${dlg && dlg.title}）`);
    if (dlg) log('  字段: ' + dlg.labels.join(' | '));
    await page.keyboard.press('Escape');
    await sleep(600);
  } else {
    log('  [INFO] 当前无可编辑行动项行');
  }

  // ---------- 5) 清理 + 控制台 ----------
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
