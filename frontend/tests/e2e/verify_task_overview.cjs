// 任务中心「任务总览」端到端验证（2026-09-18 新增，2026-09-19 改未完结口径）
//
// 覆盖：二级导航结构 / 总览卡(超期率主指标)与来源磁贴(超期率)取数与接口一致 /
//       责任人分布矩阵逐格比对(仅未完结2态) / 格子深链下钻 / 8 来源子页 + 全部任务页冒烟 /
//       运营监控矩阵未被泛化改造改坏（回归）
//
// 口径（2026-09-19 老大拍板）：未完结 = pending + in_progress，排除 done 与 blocked；
// 总览主指标改为「整体超期率」，blocked_total 单独暴露。
//
// 运行：cd frontend && node tests/e2e/verify_task_overview.cjs
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const API = process.env.API_URL || 'http://127.0.0.1:8000';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const OUT = path.resolve(__dirname, '../../tmp_uishots');

const STATUS_KEYS = ['pending', 'in_progress', 'done', 'blocked'];
const STATUS_LABELS = { pending: '待处理', in_progress: '进行中', done: '已完成', blocked: '阻塞/挂起' };
// 任务总览矩阵仅展示未完结两态（与前端 TaskOverviewView.MATRIX_STATUSES 一致）
const MATRIX_STATUSES = ['pending', 'in_progress'];
const SOURCES = [
  { key: 'todo', label: '个人待办', slug: 'todo' },
  { key: 'operation_issue', label: '运营问题', slug: 'operation-issue' },
  { key: 'research_issue', label: '一线调研', slug: 'research-issue' },
  { key: 'dev_ticket', label: '开发工单', slug: 'dev-ticket' },
  { key: 'meeting_action', label: '会议行动项', slug: 'meeting-action' },
  { key: 'key_work', label: '重点工作', slug: 'key-work' },
  { key: 'requirement_urge', label: '需求催办', slug: 'requirement-urge' },
  { key: 'active_optimization', label: '主动优化', slug: 'active-optimization' },
];

const log = [];
const check = (name, cond, extra) => log.push(`${cond ? 'PASS' : 'FAIL'} ${name}${extra ? ' | ' + extra : ''}`);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const labelOf = (k) => (SOURCES.find((s) => s.key === k) || {}).label || k;
const slugOf = (k) => (SOURCES.find((s) => s.key === k) || {}).slug || k;

(async () => {
  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });

  // ---- 后端契约 ----
  let data = null;
  try {
    const r = await fetch(API + '/api/v1/task-center/stats/by-owner');
    data = (await r.json()).data;
    check('聚合接口可用', !!data && Array.isArray(data.owners), `owners=${data ? data.owners.length : 0}`);
    check('summary 含未完结口径字段(超期率，无完成率)',
      !!(data && data.summary && data.summary.total > 0 && 'overdue_rate' in data.summary && !('completion_rate' in data.summary)),
      data ? `total=${data.summary.total} rate=${data.summary.overdue_rate}` : '');
    check('四态状态枚举', !!data && JSON.stringify(data.statuses) === JSON.stringify(STATUS_KEYS), data ? String(data.statuses) : '');
    check('责任人已归一(无「我」桶)', !!data && !data.owners.some((o) => o.name === '我'), '');
    // 未完结口径：total = pending + in_progress（排除 done/blocked），blocked_total 单独计数
    check('未完结口径 total = pending + in_progress',
      !!data && data.summary.total === data.summary.pending + data.summary.in_progress,
      data ? `${data.summary.total} vs ${data.summary.pending}+${data.summary.in_progress}` : '');
    check('blocked_total 单独暴露(>=0)', !!data && typeof data.summary.blocked_total === 'number' && data.summary.blocked_total >= 0,
      data ? `blocked_total=${data.summary.blocked_total}` : '');
    check('超期率=超期/未完结(四舍五入1位)',
      !!data && data.summary.overdue_rate === Math.round((data.summary.overdue / data.summary.total) * 1000) / 10,
      data ? `rate=${data.summary.overdue_rate} calc=${Math.round((data.summary.overdue / data.summary.total) * 1000) / 10}` : '');
    check('来源矩阵求和 = 未完结 total', !!data && (() => {
      const sum = Object.values(data.source_matrix).reduce((s, m) => s + m.total, 0);
      return sum === data.summary.total;
    })(), data ? `matrix=${Object.values(data.source_matrix).reduce((s, m) => s + m.total, 0)} total=${data.summary.total}` : '');
  } catch (e) {
    check('聚合接口可用', false, e.message);
  }

  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1600,1100'],
    defaultViewport: { width: 1600, height: 1100, deviceScaleFactor: 1 },
  });
  const page = await browser.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push('pageerror: ' + e.message));
  page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
  const apiCalls = [];
  page.on('request', (req) => {
    const u = req.url();
    if (u.includes('/api/v1/task-center/tasks')) apiCalls.push(decodeURIComponent(u));
  });

  // ---- 1. 旧入口重定向 ----
  await page.goto(BASE + '/task-center', { waitUntil: 'networkidle2', timeout: 45000 });
  await sleep(1500);
  check('/task-center 重定向到总览', page.url().includes('/task-center/overview'), page.url());

  await page.screenshot({ path: path.join(OUT, 'task_overview.png'), fullPage: false });

  // ---- 2. 总览页结构 ----
  const ov = await page.evaluate(() => {
    const root = document.querySelector('.task-overview');
    const tiles = Array.from(document.querySelectorAll('.src-tile'));
    const blocks = Array.from(document.querySelectorAll('.hm-block'));
    const navChildren = Array.from(document.querySelectorAll('.nav-children .nav-child')).map((b) => b.innerText.trim());
    const activeChild = Array.from(document.querySelectorAll('.nav-child.active')).map((b) => b.innerText.trim());
    return {
      rootFound: !!root,
      rootText: root ? root.innerText : '',
      donutVal: (document.querySelector('.to-donut-val')?.innerText || '').trim(),
      donutLabel: (document.querySelector('.to-donut-label')?.innerText || '').trim(),
      metas: Array.from(document.querySelectorAll('.to-meta-item')).map((m) => ({
        num: (m.querySelector('.to-meta-num')?.innerText || '').trim(),
        lab: (m.querySelector('.to-meta-lab')?.innerText || '').trim(),
        warn: !!m.querySelector('.to-meta-num.warn'),
      })),
      tiles: tiles.map((t) => ({
        name: (t.querySelector('.src-name')?.innerText || '').trim(),
        count: (t.querySelector('.src-count')?.innerText || '').trim(),
        sub: (t.querySelector('.src-count-sub')?.innerText || '').trim(),
        rate: (t.querySelector('.src-rate-val')?.innerText || '').trim(),
      })),
      blocks: blocks.map((b) => ({
        name: (b.querySelector('.hm-name')?.innerText || '').trim(),
        hasRateBar: !!b.querySelector('.hm-rate-bar b'),
        isOpen: b.classList.contains('is-open'),
        chips: Array.from(b.querySelectorAll('.hm-chip')).map((c) => c.innerText.trim()),
        rateText: (b.querySelector('.hm-rate em')?.innerText || '').trim(),
        statText: Array.from(b.querySelectorAll('.hm-stat')).map((s) => s.innerText.trim()),
        overdueTag: (b.querySelector('.el-tag')?.innerText || '').trim(),
      })),
      matrixHeader: (document.querySelector('.hm-block:first-child .hm-th-cat')?.innerText || '').trim(),
      navChildren,
      activeChild,
      tabsGone: document.querySelectorAll('.task-tabs').length === 0,
    };
  });

  check('总览页容器渲染', ov.rootFound);
  check('甜甜圈标签=整体超期率', ov.donutLabel === '整体超期率', ov.donutLabel);
  check('矩阵行表头=任务来源', ov.matrixHeader === '任务来源', ov.matrixHeader);
  check('口径提示存在(未完结口径)', ov.rootText.includes('未完结口径'), '');

  if (data) {
    const s = data.summary;
    check('甜甜圈值=接口超期率', ov.donutVal === `${s.overdue_rate}%`, `dom=${ov.donutVal} api=${s.overdue_rate}%`);
    const metaMap = Object.fromEntries(ov.metas.map((m) => [m.lab, m]));
    check('指标-未完结总量', metaMap['未完结总量'] && metaMap['未完结总量'].num === String(s.total), `dom=${metaMap['未完结总量'] && metaMap['未完结总量'].num} api=${s.total}`);
    check('指标-已超期(有超期时红色)', metaMap['已超期'] && metaMap['已超期'].num === String(s.overdue) && (s.overdue === 0 || metaMap['已超期'].warn),
      `dom=${metaMap['已超期'] && metaMap['已超期'].num} warn=${metaMap['已超期'] && metaMap['已超期'].warn}`);
    check('指标-阻塞挂起', metaMap['阻塞挂起'] && metaMap['阻塞挂起'].num === String(s.blocked_total), `dom=${metaMap['阻塞挂起'] && metaMap['阻塞挂起'].num} api=${s.blocked_total}`);
    check('指标-临期(3天内)', metaMap['临期(3天内)'] && metaMap['临期(3天内)'].num === String(s.due_soon), `dom=${metaMap['临期(3天内)'] && metaMap['临期(3天内)'].num} api=${s.due_soon}`);

    // 磁贴：全部 + 有数据的来源
    const expectTiles = 1 + data.sources.length;
    check('来源磁贴数量=1+有效来源数', ov.tiles.length === expectTiles, `dom=${ov.tiles.length} api=${expectTiles}`);
    check('磁贴含「全部」', ov.tiles[0] && ov.tiles[0].name === '全部', ov.tiles[0] && ov.tiles[0].name);
    const tileOk = data.sources.every((src) => {
      const t = ov.tiles.find((x) => x.name === labelOf(src));
      const m = data.source_matrix[src];
      return t && t.count === String(m.total) && t.rate === `${m.overdue_rate}%`;
    });
    check('各来源磁贴数量/完成率=接口', tileOk, ov.tiles.map((t) => `${t.name}:${t.count}/${t.rate}`).join(' '));
    check('开发工单(0 条)磁贴不占位', !ov.tiles.some((t) => t.name === '开发工单'), '');

    // 矩阵摘要卡
    check('矩阵摘要卡数=接口责任人数', ov.blocks.length === data.owners.length, `dom=${ov.blocks.length} api=${data.owners.length}`);
    check('默认收起(无展开态)', ov.blocks.every((b) => !b.isOpen), '');
    check('每卡都有完成率条', ov.blocks.every((b) => b.hasRateBar), '');
    const rateMatch = ov.blocks.every((b) => {
      const api = data.owners.find((o) => o.name === b.name);
      return api && b.rateText === `${api.overdue_rate}%`;
    });
    check('卡内完成率=接口值', rateMatch, '');
    const chipsMatch = ov.blocks.every((b) => {
      const api = data.owners.find((o) => o.name === b.name);
      if (!api) return false;
      const nonzero = Object.values(api.matrix).reduce((n, row) => n + STATUS_KEYS.filter((k) => row[k] > 0).length, 0);
      return b.chips.length === Math.min(nonzero, 8);
    });
    check('chips 数量=min(非零格子,8)', chipsMatch, '');
    const overdueTagOk = data.owners.filter((o) => o.overdue > 0).length > 0
      && ov.blocks.some((b) => /^逾期 \d+$/.test(b.overdueTag));
    check('超期责任人显示逾期 tag', overdueTagOk, '');

    // ---- 3. 二级导航（2026-09-20 精简：仅总览 + 全部任务，来源不再独立子页）----
    const expectNav = ['任务总览', '全部任务'];
    const navOk = expectNav.every((n) => ov.navChildren.includes(n));
    check('二级导航含总览/全部', navOk, `nav=${ov.navChildren.join(',')}`);
    check('二级导航不含来源子页(已精简)', !SOURCES.some((s2) => ov.navChildren.includes(s2.label)), `nav=${ov.navChildren.join(',')}`);
    check('当前高亮=任务总览', ov.activeChild.includes('任务总览'), ov.activeChild.join(','));
  }

  // ---- 4. 展开矩阵逐格比对 ----
  await page.evaluate(() => {
    document.querySelector('.hm-block .hm-head').click();
  });
  await sleep(500);
  const detail = await page.evaluate(() => {
    const b = document.querySelector('.hm-block');
    const name = (b.querySelector('.hm-name')?.innerText || '').trim();
    const headers = Array.from(b.querySelectorAll('thead th')).map((t) => t.innerText.trim());
    const rows = Array.from(b.querySelectorAll('tbody tr')).filter((tr) => !tr.classList.contains('hm-row-sum'));
    const grid = rows.map((tr) => {
      const tds = Array.from(tr.querySelectorAll('td'));
      return {
        cat: tds[0].innerText.trim(),
        cells: tds.slice(1, tds.length - 1).map((td) => {
          const c = td.querySelector('.hm-cell');
          return {
            text: (c?.innerText || '').trim(),
            empty: !!c && c.classList.contains('hm-cell-empty'),
            cls: c ? c.className : '',
          };
        }),
        sum: tds[tds.length - 1].innerText.trim(),
      };
    });
    const sumRow = Array.from(b.querySelectorAll('tbody tr.hm-row-sum td')).map((td) => td.innerText.trim());
    return { name, headers, grid, sumRow, tableVisible: b.querySelector('.hm-table')?.offsetParent !== null, isOpen: b.classList.contains('is-open') };
  });

  check('点击后展开热力矩阵', detail.isOpen && detail.tableVisible, `isOpen=${detail.isOpen}`);
  check('矩阵列头=未完结2态+类别+合计', detail.headers.length === MATRIX_STATUSES.length + 2 && MATRIX_STATUSES.every((k) => detail.headers.includes(STATUS_LABELS[k])),
    detail.headers.join('|'));

  if (data) {
    const api = data.owners.find((o) => o.name === detail.name);
    // 矩阵行固定为「全局有数据的来源」（与运营监控固定 5 类别同构）：某人在某来源为 0 时保留空行，
    // 保证各责任人横向可比（能看出"漏在哪"），而不是各自只显示自己的来源。
    check('矩阵行数=全局有效来源数(固定行)', detail.grid.length === data.sources.length,
      `dom=${detail.grid.length} api=${data.sources.length}`);
    const bad = [];
    detail.grid.forEach((row) => {
      const catKey = (SOURCES.find((s2) => s2.label === row.cat) || {}).key;
      if (!catKey) { bad.push(`未知行:${row.cat}`); return; }
      MATRIX_STATUSES.forEach((st, i) => {
        const v = (api.matrix[catKey] || {})[st] || 0;
        const cell = row.cells[i];
        if (v > 0 && (cell.empty || cell.text !== String(v))) bad.push(`${catKey}.${st} dom=${cell.text}${cell.empty ? '(empty)' : ''} api=${v}`);
        if (v === 0 && !cell.empty) bad.push(`${catKey}.${st} dom=${cell.text} api=0`);
      });
      const rowSum = MATRIX_STATUSES.reduce((a, st) => a + ((api.matrix[catKey] || {})[st] || 0), 0);
      if (row.sum !== String(rowSum)) bad.push(`${catKey}.合计 dom=${row.sum} api=${rowSum}`);
    });
    check('矩阵逐格数值=接口', bad.length === 0, `mismatch=${bad.length} ${bad.slice(0, 5).join(' ; ')}`);
    const colSum = MATRIX_STATUSES.map((st) => String(api.status_totals[st]));
    const domColSum = detail.sumRow.slice(1, 1 + MATRIX_STATUSES.length);
    check('矩阵列合计=接口 status_totals', MATRIX_STATUSES.every((st, i) => domColSum[i] === colSum[i]),
      `dom=${domColSum.join(',')} api=${colSum.join(',')}`);
  }

  // ---- 5. 格子深链下钻（2026-09-20 精简后：下钻到全部任务页并自动设置 ?source=&owner=&status=）----
  apiCalls.length = 0;
  const jump = await page.evaluate(() => {
    const b = document.querySelector('.hm-block');
    const name = (b.querySelector('.hm-name')?.innerText || '').trim();
    const rows = Array.from(b.querySelectorAll('tbody tr')).filter((tr) => !tr.classList.contains('hm-row-sum'));
    const headers = Array.from(b.querySelectorAll('thead th')).map((t) => t.innerText.trim());
    for (const tr of rows) {
      const tds = Array.from(tr.querySelectorAll('td'));
      const cat = tds[0].innerText.trim();
      if (cat === '需求催办') continue; // SA 分组视图无 filter-bar，下钻验证跳过该来源
      for (let i = 1; i < tds.length - 1; i++) {
        const cell = tds[i].querySelector('.hm-cell:not(.hm-cell-empty)');
        if (cell) {
          const info = { name, cat, stLabel: headers[i], val: cell.innerText.trim() };
          cell.click();
          return info;
        }
      }
    }
    return null;
  });

  await sleep(2500);
  if (jump) {
    const stKey = Object.entries(STATUS_LABELS).find(([, v]) => v === jump.stLabel)?.[0];
    const srcKey = (SOURCES.find((s2) => s2.label === jump.cat) || {}).key;
    const u = new URL(page.url());
    check('格子下钻到全部任务页(all)', u.pathname === '/task-center/all', `${page.url()} expect=/task-center/all`);
    check('下钻 query 带 source', u.searchParams.get('source') === srcKey, `source=${u.searchParams.get('source')} expect=${srcKey}`);
    check('下钻 query 带 owner', u.searchParams.get('owner') === jump.name, `owner=${u.searchParams.get('owner')}`);
    check('下钻 query 带 status', u.searchParams.get('status') === stKey, `status=${u.searchParams.get('status')} expect=${stKey}`);
    const called = apiCalls.some((c) => c.includes(`owners=${jump.name}`) && c.includes(`status=${stKey}`)
      && c.includes(`source=${srcKey}`));
    check('列表页按深链参数拉取(owner+status+source)', called, apiCalls[0] || 'no call');

    // 列表页可见筛选控件回填
    const back = await page.evaluate(() => {
      const sel = document.querySelector('.filter-bar .el-select');
      const srcSel = document.querySelector('.source-bar .el-select');
      const tags = Array.from(document.querySelectorAll('.filter-bar .el-tag, .filter-bar .el-select__tags-text')).map((t) => t.innerText.trim());
      const statusText = sel ? sel.innerText.trim() : '';
      const srcText = srcSel ? srcSel.innerText.trim() : '';
      const title = (document.querySelector('.pm-page-header__title')?.innerText || '').trim();
      return { statusText, srcText, tags, title, tabs: document.querySelectorAll('.task-tabs').length };
    });
    check('列表页标题=任务中心·来源名', back.title === `任务中心 · ${jump.cat}`, back.title);
    check('来源下拉回填为下钻来源', back.srcText.includes(jump.cat), `sourceSelect=${back.srcText}`);
    check('状态筛选回填', back.statusText.includes(jump.stLabel), `statusSelect=${back.statusText}`);
    check('责任人筛选回填', back.tags.some((t) => t.includes(jump.name)), `tags=${back.tags.join(',')}`);
    check('顶部 el-tabs 已退役', back.tabs === 0, '');
  } else {
    check('格子深链下钻', false, '未找到可点击的非空格子(或仅剩需求催办)');
  }

  // ---- 6. 全部任务页冒烟（精简后仅 /task-center/all 一个列表页）----
  apiCalls.length = 0;
  await page.goto(`${BASE}/task-center/all`, { waitUntil: 'networkidle2', timeout: 45000 });
  await sleep(1200);
  const allSt = await page.evaluate(() => ({
    hasRoot: !!document.querySelector('.task-center'),
    title: (document.querySelector('.pm-page-header__title')?.innerText || '').trim(),
    navActive: Array.from(document.querySelectorAll('.nav-child.active')).map((b) => b.innerText.trim()),
    sourceBar: !!document.querySelector('.source-bar .el-select'),
  }));
  const allNoErr = errs.filter((e) => !e.includes('favicon')).length === 0;
  check('子页 /task-center/all 渲染', allSt.hasRoot && allNoErr, `title=${allSt.title} active=${allSt.navActive.join(',')} errs=${errs.length}`);
  check('子页 /task-center/all 标题=任务中心', allSt.title === '任务中心', `dom=${allSt.title}`);
  check('子页 /task-center/all 含来源下拉', allSt.sourceBar, '');

  // ---- 7. 无 JS 错误 ----
  const realErrs = errs.filter((e) => !e.includes('favicon'));
  check('全程无页面 JS 错误', realErrs.length === 0, realErrs.slice(0, 3).join(' ; '));

  fs.writeFileSync(path.join(OUT, '_log.txt'), log.join('\n'), 'utf8');
  const fails = log.filter((l) => l.startsWith('FAIL'));
  console.log(log.join('\n'));
  console.log(`\n=== TOTAL ${log.length} / PASS ${log.length - fails.length} / FAIL ${fails.length} ===`);

  await browser.close();
  process.exit(fails.length ? 1 : 0);
})();
