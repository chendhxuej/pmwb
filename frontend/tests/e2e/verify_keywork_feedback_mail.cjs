/**
 * 重点工作「周反馈」邮件 —— 在途过滤 + 状态中文转译 验证
 *
 * 覆盖（2026-10-15 修复）：
 *  1) 周反馈页签 B.月计划 / C.周计划 / D.成员待办 三块清单只显示「在途」子项，
 *     status=completed（已完成）/ cancelled（已作废）的项不出现；
 *  2) 清单行数与接口返回的在途数一致（真实数据回归，非空断言）；
 *  3) 「预览并发送反馈请求」弹窗正文（Markdown 值 + 渲染预览 srcdoc）状态全为中文，
 *     无 not_started / in_progress / delayed 等英文裸值；正文行数 = 在途数；
 *  4) 无 console error / pageerror。
 *
 * 说明：脚本会向目标工单临时追加 3 条成员待办（已完成 / 已作废 / 进行中）用于确定性断言，
 *       结束时全部删除；不修改任何既有数据的 status。
 * 运行：cd frontend && node tests/e2e/verify_keywork_feedback_mail.cjs
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
const info = (...a) => log('  ▸', ...a);

const TERMINAL = ['completed', 'cancelled'];
const isTerm = (x) => TERMINAL.includes(String((x && x.status) || ''));
const stat = (arr) => {
  const list = arr || [];
  return {
    n: list.length,
    inflight: list.filter((x) => !isTerm(x)).length,
    termItems: list.filter(isTerm),
    inflightItems: list.filter((x) => !isTerm(x)),
  };
};

const SEED_TASKS = [
  { status: 'completed', title: '[自动化测试] 在途过滤-已完成' },
  { status: 'cancelled', title: '[自动化测试] 在途过滤-已作废' },
  { status: 'in_progress', title: '[自动化测试] 在途过滤-进行中' },
];
const SEED_DONE_TITLE = SEED_TASKS[0].title;
const SEED_CANCELLED_TITLE = SEED_TASKS[1].title;
const SEED_ACTIVE_TITLE = SEED_TASKS[2].title;

/** 与前端 currentIsoWeek() 同算法：ISO 周次 YYYY-Www */
function currentIsoWeek() {
  const now = new Date();
  const day = (now.getDay() + 6) % 7;
  const thursday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - day + 3);
  const jan4 = new Date(thursday.getFullYear(), 0, 4);
  const jan4Iso = ((jan4.getDay() + 6) % 7) + 1;
  const diffDays = Math.round((thursday - jan4) / 86400000);
  const week = Math.ceil((diffDays + jan4Iso) / 7);
  return `${thursday.getFullYear()}-W${String(week).padStart(2, '0')}`;
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

  const week = currentIsoWeek();
  log(`==> 打开 ${BASE}/key-works（周次 ${week}）`);
  await page.goto(`${BASE}/key-works`, { waitUntil: 'networkidle2', timeout: 40000 }).catch(() => {});
  await sleep(3000);

  const isLogin = await page.evaluate(
    () => /登录|signin/i.test(document.body.innerText) && !document.querySelector('.el-table')
  );
  if (isLogin) { log('  [SKIP] 被登录页拦截'); await browser.close(); process.exit(3); }

  // ---------- 1) 选目标工单：优先选「终态子项最多」且已设置负责人的工单 ----------
  const pick = await page.evaluate(async (wk) => {
    const lst = await (await fetch('/api/v1/key-works?page=1&page_size=20')).json();
    const items = (lst.data && lst.data.items) || [];
    const cands = [];
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      if (!(it.owner || '').trim()) continue;
      const r = await (await fetch(`/api/v1/key-works/${it.id}/weekly-feedback-form?week=${wk}`)).json();
      const g = (r.data && r.data.groups && r.data.groups[0]) || null;
      if (!g) continue;
      const st = (arr) => {
        const list = arr || [];
        const term = list.filter((x) => ['completed', 'cancelled'].includes(String((x && x.status) || ''))).length;
        return { n: list.length, term };
      };
      const m = st(g.monthly_items); const w = st(g.weekly_items); const t = st(g.task_items);
      cands.push({ id: it.id, title: it.title, owner: it.owner, rowIndex: i, m, w, t, totalTerm: m.term + w.term + t.term, isMonthEnd: !!r.data.is_month_end });
    }
    cands.sort((a, b) => b.totalTerm - a.totalTerm);
    return { top: cands.slice(0, 3), count: cands.length };
  }, week);

  if (!pick.top.length) {
    log('  [SKIP] 无「已设置负责人」的重点工作，无法生成周反馈工作单');
    await browser.close();
    process.exit(3);
  }
  const target = pick.top[0];
  log(`  候选 ${pick.count} 条；选中 id=${target.id} 行序=${target.rowIndex}`);
  log(`  「${target.title}」负责人=${target.owner}`);
  info(`改前 B/C/D 终态项数：月计划 ${target.m.term}/${target.m.n}、周计划 ${target.w.term}/${target.w.n}、成员待办 ${target.t.term}/${target.t.n}`);
  assert(
    target.m.term + target.w.term + target.t.term > 0,
    '目标工单存在终态子项（B/C/D 过滤断言非退化）'
  );

  // ---------- 2) 造数：3 条成员待办（已完成 / 已作废 / 进行中） ----------
  const seededIds = await page.evaluate(async ({ kwId, owner, tasks }) => {
    const ids = [];
    for (const t of tasks) {
      const r = await (await fetch(`/api/v1/key-works/${kwId}/member-tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: t.title, assignee: owner, status: t.status, link_type: 'none', link_id: null }),
      })).json();
      if (r && r.data && r.data.id) ids.push(r.data.id);
    }
    return ids;
  }, { kwId: target.id, owner: target.owner, tasks: SEED_TASKS });
  assert(seededIds.length === SEED_TASKS.length, `造数成功（${seededIds.length}/${SEED_TASKS.length} 条成员待办）`);

  const cleanup = async () => {
    const res = await page.evaluate(async ({ kwId, ids }) => {
      const out = [];
      for (const id of ids) {
        const r = await fetch(`/api/v1/key-works/${kwId}/member-tasks/${id}`, { method: 'DELETE' });
        out.push(r.status);
      }
      return out;
    }, { kwId: target.id, ids: seededIds }).catch(() => []);
    return res;
  };

  // ---------- 3) 取期望值（造数后的工作单接口数据） ----------
  const form = await page.evaluate(async ({ kwId, wk }) => {
    const r = await (await fetch(`/api/v1/key-works/${kwId}/weekly-feedback-form?week=${wk}`)).json();
    return r.data || null;
  }, { kwId: target.id, wk: week });
  if (!form || !form.groups || !form.groups[0]) {
    log('  [FAIL] 工作单接口未返回 groups');
    await cleanup();
    await browser.close();
    process.exit(1);
  }
  const g = form.groups[0];
  const M = stat(g.monthly_items);
  const W = stat(g.weekly_items);
  const T = stat(g.task_items);
  const isMonthEnd = !!form.is_month_end;
  info(`期望在途数：月计划 ${M.inflight}（共${M.n}）、周计划 ${W.inflight}（共${W.n}）、成员待办 ${T.inflight}（共${T.n}）；月底=${isMonthEnd}`);

  // ---------- 4) 刷新页面 → 打开该工单抽屉 → 切「周反馈」 ----------
  await page.reload({ waitUntil: 'networkidle2' }).catch(() => {});
  await sleep(3000);
  await page.evaluate((idx) => {
    const rows = document.querySelectorAll('.el-table__body-wrapper tbody tr');
    if (rows[idx]) rows[idx].click();
  }, target.rowIndex);
  await sleep(2500);
  const drawerOpen = await page.evaluate(() => !!document.querySelector('.el-drawer'));
  assert(drawerOpen, '工单抽屉已打开');
  if (!drawerOpen) { await cleanup(); await browser.close(); process.exit(1); }

  const tabOk = await page.evaluate(() => {
    const tabs = [...document.querySelectorAll('.el-drawer .el-tabs__item')];
    const t = tabs.find((x) => x.textContent.trim() === '周反馈');
    if (t) { t.click(); return true; }
    return false;
  });
  await sleep(2000);
  assert(tabOk, '切到「周反馈」页签');

  // 负责人卡片默认收起（body 为 v-if="isExpanded(g)"），需先展开才会渲染 B/C/D 清单
  const expanded = await page.evaluate(() => {
    if (document.querySelector('.el-drawer .feedback-card-body')) return true;
    const head = document.querySelector('.el-drawer .feedback-card-head');
    if (head) { head.click(); return true; }
    return false;
  });
  await sleep(1800);
  assert(expanded, '展开负责人反馈卡片（B/C/D 清单渲染）');

  // ---------- 5) B/C/D 三块清单断言 ----------
  const dom = await page.evaluate(() => {
    const items = [...document.querySelectorAll('.el-drawer .el-collapse-item')];
    const byPrefix = (p) => items.find((el) => (((el.querySelector('.el-collapse-item__header') || {}).innerText) || '').trim().startsWith(p));
    const rowsOf = (el, sel) => (el ? [...el.querySelectorAll(sel)] : []);
    const texts = (el, sel) => rowsOf(el, sel).map((x) => (x.innerText || '').replace(/\s+/g, ' ').trim());
    const b = byPrefix('B.');
    const c = byPrefix('C.');
    const d = byPrefix('D.');
    return {
      monthly: rowsOf(b, '.feedback-items .el-checkbox').length,
      weekly: rowsOf(c, '.feedback-items .el-checkbox').length,
      task: rowsOf(d, '.el-table__body-wrapper tbody tr').length,
      monthlyText: texts(b, '.feedback-items .el-checkbox').join(' || '),
      weeklyText: texts(c, '.feedback-items .el-checkbox').join(' || '),
      taskText: texts(d, '.el-table__body-wrapper tbody tr').join(' || '),
      paneText: (document.querySelector('.el-drawer .el-tab-pane') || {}).innerText || '',
      hasBC: !!b && !!c && !!d,
    };
  });
  assert(dom.hasBC, '定位到 B.月计划 / C.周计划 / D.成员待办 三块');
  log(`  DOM 行数：月计划 ${dom.monthly}、周计划 ${dom.weekly}、成员待办 ${dom.task}`);
  assert(dom.monthly === M.inflight, `B.月计划 仅显示在途项（DOM ${dom.monthly} == 在途 ${M.inflight}，共 ${M.n}）`);
  assert(dom.weekly === W.inflight, `C.周计划 仅显示在途项（DOM ${dom.weekly} == 在途 ${W.inflight}，共 ${W.n}）`);
  assert(dom.task === T.inflight, `D.成员待办 仅显示在途项（DOM ${dom.task} == 在途 ${T.inflight}，共 ${T.n}）`);

  const dText = [dom.monthlyText, dom.weeklyText, dom.taskText, dom.paneText].join(' || ');
  assert(!dText.includes(SEED_DONE_TITLE), `页面清单不含「已完成」造数项（${SEED_DONE_TITLE}）`);
  assert(!dText.includes(SEED_CANCELLED_TITLE), `页面清单不含「已作废」造数项（${SEED_CANCELLED_TITLE}）`);
  assert(dText.includes(SEED_ACTIVE_TITLE), `页面清单含「进行中」造数项（${SEED_ACTIVE_TITLE}）`);

  // ---------- 6) 邮件预览弹窗断言 ----------
  const clicked = await page.evaluate(() => {
    const b = [...document.querySelectorAll('.el-drawer button, button')].find((x) => (x.innerText || '').includes('预览并发送反馈请求'));
    if (b) { b.click(); return true; }
    return false;
  });
  assert(clicked, '点击「预览并发送反馈请求」');
  await sleep(4000);

  const mail = await page.evaluate(() => {
    const dlgs = [...document.querySelectorAll('.el-dialog')].filter((d) => d.offsetParent !== null);
    const d = dlgs.find((x) => (x.innerText || '').includes('邮件预览')) || dlgs[dlgs.length - 1];
    if (!d) return null;
    const ta = d.querySelector('.compose-body textarea');
    const frame = d.querySelector('.compose-preview-frame');
    return {
      subject: (((d.querySelector('.compose-preview-subject') || {}).innerText) || '').trim(),
      body: ta ? ta.value : '',
      srcdoc: frame ? frame.getAttribute('srcdoc') || '' : '',
    };
  });
  assert(!!mail && mail.body.length > 0, '邮件预览弹窗正文已生成');
  if (mail && mail.body) {
    const body = mail.body;
    const lines = body.split('\n');
    const cnt = (re) => lines.filter((l) => re.test(l)).length;
    const nMonthly = cnt(/^- [✅⬜] 【月计划】/);
    const nWeekly = cnt(/^- [✅⬜] 【周计划】/);
    const nTask = cnt(/^- \*\*/);
    log(`  [邮件] 主题=${mail.subject}`);
    log(`  [邮件] 月计划行 ${nMonthly}、周计划行 ${nWeekly}、成员待办行 ${nTask}`);
    log('  [邮件] 正文首 8 行: ' + lines.slice(0, 8).join(' / '));

    assert(nWeekly === W.inflight, `邮件周计划行数 == 在途数（${nWeekly}/${W.inflight}，共 ${W.n}）`);
    assert(nTask === T.inflight, `邮件成员待办行数 == 在途数（${nTask}/${T.inflight}，共 ${T.n}）`);
    assert(nMonthly === (isMonthEnd ? M.inflight : 0), `邮件月计划行数 == ${isMonthEnd ? '在途数' : '0（非月底不渲染）'}（${nMonthly}）`);

    const engParen = /（(not_started|in_progress|delayed|completed|cancelled)）/;
    const engPipe = /\| (not_started|in_progress|delayed|completed|cancelled) \|/;
    assert(!engParen.test(body), '邮件正文无「（英文状态）」裸值');
    assert(!engPipe.test(body), '邮件正文成员待办无「| 英文状态 |」裸值');
    const zh = ['（进行中）', '（未开始）', '（已延期）'];
    assert(zh.some((x) => body.includes(x)), `邮件正文出现中文状态（${zh.filter((x) => body.includes(x)).join('/')}）`);

    assert(!body.includes(SEED_DONE_TITLE), `邮件不含「已完成」造数项（${SEED_DONE_TITLE}）`);
    assert(!body.includes(SEED_CANCELLED_TITLE), `邮件不含「已作废」造数项（${SEED_CANCELLED_TITLE}）`);
    assert(body.includes(SEED_ACTIVE_TITLE), `邮件含「进行中」造数项（${SEED_ACTIVE_TITLE}）`);

    if (mail.srcdoc) {
      assert(!engParen.test(mail.srcdoc), '渲染预览 HTML 亦无英文状态裸值');
      assert(!mail.srcdoc.includes(SEED_DONE_TITLE), '渲染预览 HTML 不含已完成项');
    } else {
      info('渲染预览 iframe 未就绪，跳过 srcdoc 断言');
    }
  }

  // ---------- 7) 清理造数 ----------
  const delStatus = await cleanup();
  assert(delStatus.length === seededIds.length && delStatus.every((s) => s === 200), `造数清理完成（${delStatus.join(',')}）`);

  // ---------- 8) 报错 ----------
  const realErrors = errors.filter((e) => !/favicon|ResizeObserver|Vue Devtools|DevTools/i.test(e));
  assert(realErrors.length === 0, `无 console/page 错误（实际 ${realErrors.length} 条）`);
  if (realErrors.length) realErrors.slice(0, 8).forEach((e) => log('    ', e));

  await browser.close();
  log(`\n===== 结果: ${failures === 0 ? '全部通过' : failures + ' 项失败'} =====`);
  process.exit(failures === 0 ? 0 : 1);
}

run().catch((e) => { console.error('脚本异常:', e); process.exit(3); });
