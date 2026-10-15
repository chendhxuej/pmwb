// 任务中心「高级别工单」子模块接线验证（2026-10-15 新增）
//
// 覆盖：
//  1. 路由 /task-center/highlevel 可达，页面根节点 .task-high-level 渲染
//  2. 四张统计卡数值 == GET /high-level/stats（在跟池单一数据源）
//  3. 责任人 chips（.hl-owner-chips .el-check-tag）数量 == stats.by_handler 长度
//     → 依赖后端 by_handler，禁止前端拿当前分页自己算
//  4. 主表行数 == min(total, pageSize)，级别/判定依据列非空
//  5. 「按责任人督办」链路：点 chip → 出现 .hl-supervise-owner → 打开 .hl-supervise 弹窗，
//     弹窗内行数 == 该责任人在跟数
//  6. 「按勾选督办」链路：勾 1 行 → 批量督办 → 弹窗行数 == 1
//  7. 详情抽屉：双击行 → .hl-detail 渲染 + .hl-track-actions + 督办记录 .email-supervise-log
//
// 红线：全程不点击「发送」，不触发真实发信。
const puppeteer = require('puppeteer-core');
const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const API = process.env.API_URL || 'http://127.0.0.1:8000';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';

const log = [];
const check = (n, c, e) => log.push(`${c ? 'PASS' : 'FAIL'} ${n}${e ? ' | ' + e : ''}`);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const num = (s) => parseInt(String(s || '0').replace(/[^\d]/g, ''), 10) || 0;

(async () => {
  // 接口侧基准数据
  const stats = (await (await fetch(`${API}/api/v1/high-level/stats`)).json()).data;
  const byHandler = stats.by_handler || [];

  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
    defaultViewport: { width: 1680, height: 1100 },
  });
  const page = await browser.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push('pageerror: ' + e.message));
  page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text()); });

  await page.goto(BASE + '/task-center/highlevel', { waitUntil: 'networkidle2', timeout: 45000 });
  await sleep(1800);

  check('页面根节点渲染 (.task-high-level)', await page.$('.task-high-level') !== null);

  // ── 统计卡 ────────────────────────────────────────────────
  const cards = await page.evaluate(() => Array.from(document.querySelectorAll('.hl-stat')).map((c) => ({
    label: (c.querySelector('.hl-stat-label')?.innerText || '').trim(),
    value: (c.querySelector('.hl-stat-value')?.innerText || '').trim(),
  })));
  check('统计卡 = 4 张', cards.length === 4, `dom=${cards.length}`);
  const cardMap = Object.fromEntries(cards.map((c) => [c.label, num(c.value)]));
  check('统计卡「在跟高级别」= 接口 total', cardMap['在跟高级别'] === stats.total, `dom=${cardMap['在跟高级别']} api=${stats.total}`);
  check('统计卡「已超期」= 接口 overdue', cardMap['已超期'] === stats.overdue, `dom=${cardMap['已超期']} api=${stats.overdue}`);
  check('统计卡「已升级」= 接口 escalated', cardMap['已升级'] === stats.escalated, `dom=${cardMap['已升级']} api=${stats.escalated}`);
  check('统计卡「未分配责任人」= 接口 unassigned', cardMap['未分配责任人'] === stats.unassigned, `dom=${cardMap['未分配责任人']} api=${stats.unassigned}`);

  // ── 责任人 chips（by_handler 单一数据源）────────────────────
  const chips = await page.evaluate(() => Array.from(document.querySelectorAll('.hl-owner-chips .el-check-tag')).map((c) => c.innerText.trim()));
  check('责任人 chips 数量 = stats.by_handler 长度', chips.length === byHandler.length, `dom=${chips.length} api=${byHandler.length}`);
  if (chips.length && byHandler.length) {
    const first = byHandler[0];
    check('首个 chip 文案 = 姓名 · 数量（且降序）', chips[0].startsWith(first.name) && num(chips[0]) === first.count,
      `dom="${chips[0]}" api=${first.name}·${first.count}`);
  }

  // ── 主表 ─────────────────────────────────────────────────
  const tbl = await page.evaluate(() => {
    const rows = document.querySelectorAll('.hl-table .el-table__body-wrapper tbody tr');
    const first = rows[0];
    return {
      rows: rows.length,
      lvl: (first?.querySelector('.hl-level')?.innerText || '').trim(),
      reason: (first?.querySelector('.hl-reason')?.innerText || '').trim(),
      urge: (first?.querySelector('.hl-urge-count')?.innerText || '').trim(),
    };
  });
  const expectRows = Math.min(stats.total, 20);
  check('主表行数 = min(total, 20)', tbl.rows === expectRows, `dom=${tbl.rows} api=${expectRows}`);
  check('首行「级别」列非空', /^P[0-2]$/.test(tbl.lvl), `lvl="${tbl.lvl}"`);
  check('首行「判定依据」非空', tbl.reason.length > 0, `reason="${tbl.reason.slice(0, 30)}"`);

  // 跟踪态必须渲染中文标签（防静默降级英文 key；域经 /meta/status-domains 注入）
  const TRACK_LABELS = ['待跟进', '跟踪中', '已升级', '已闭环', '已移除'];
  const trackCells = await page.evaluate(() => Array.from(
    document.querySelectorAll('.hl-table .el-table__body-wrapper tbody tr')
  ).map((tr) => {
    const badges = tr.querySelectorAll('.pm-status-badge .pm-status-text');
    return badges.length ? badges[badges.length - 1].innerText.trim() : '';
  }));
  const badTrack = trackCells.filter((t) => !TRACK_LABELS.includes(t));
  check('跟踪态列全部为中文标签（未降级英文 key）', trackCells.length > 0 && badTrack.length === 0,
    `n=${trackCells.length} bad=${JSON.stringify(badTrack.slice(0, 3))}`);
  await page.screenshot({ path: require('path').resolve(__dirname, '../../tmp_uishots/highlevel_main.png') });

  // ── 按责任人督办链路 ──────────────────────────────────────
  if (chips.length) {
    const ownerName = byHandler[0].name;
    await page.evaluate((name) => {
      const c = Array.from(document.querySelectorAll('.hl-owner-chips .el-check-tag'))
        .find((x) => x.innerText.trim().startsWith(name));
      if (c) c.click();
    }, ownerName);
    await sleep(1600);

    const filtered = await page.evaluate(() => ({
      ownerBtn: !!document.querySelector('.hl-supervise-owner'),
      rows: document.querySelectorAll('.hl-table .el-table__body-wrapper tbody tr').length,
    }));
    check('选中 chip 后出现「督办 XX 全部…」按钮', filtered.ownerBtn === true);
    check('筛选后主表行数 = 该责任人在跟数', filtered.rows === byHandler[0].count, `dom=${filtered.rows} api=${byHandler[0].count}`);

    await page.evaluate(() => document.querySelector('.hl-supervise-owner')?.click());
    await sleep(1800);
    const dlg = await page.evaluate(() => {
      const d = document.querySelector('.hl-supervise');
      if (!d) return null;
      return {
        title: (d.querySelector('.el-dialog__title')?.innerText || '').trim(),
        tip: (d.querySelector('.hls-tip')?.innerText || '').trim(),
        rows: d.querySelectorAll('.el-table__body-wrapper tbody tr').length,
        count: (d.querySelector('.hls-count')?.innerText || '').trim(),
      };
    });
    check('按责任人督办弹窗打开 (.hl-supervise)', !!dlg, dlg ? dlg.title : '未打开');
    if (dlg) {
      check('弹窗文案含责任人名', dlg.tip.includes(ownerName), dlg.tip.slice(0, 40));
      check('弹窗行数 = 该责任人在跟数', dlg.rows === byHandler[0].count, `dom=${dlg.rows} api=${byHandler[0].count} count="${dlg.count}"`);
      await page.screenshot({ path: require('path').resolve(__dirname, '../../tmp_uishots/highlevel_owner_dialog.png') });

      // 弹窗首行标题（后面校验草稿正文里要出现真实标题，不能是「（无标题）」）
      const firstTitle = await page.evaluate(() => (document.querySelector('.hl-supervise .hls-title')?.innerText || '').trim());

      // 撰写督办邮件 → MailComposeDialog（走 /high-level/draft 拿 body_md；不发送）
      await page.evaluate(() => {
        const d = document.querySelector('.hl-supervise');
        const b = d && Array.from(d.querySelectorAll('.el-dialog__footer .el-button')).find((x) => x.innerText.includes('撰写督办邮件'));
        if (b) b.click();
      });
      for (let i = 0; i < 24; i++) {
        const ok = await page.evaluate(() => {
          const cd = document.querySelector('.mail-compose-dialog');
          if (!cd) return false;
          const ta = cd.querySelector('.compose-body textarea, .compose-edit .el-textarea__inner');
          const f = cd.querySelector('.compose-preview-frame');
          return !!(ta && (ta.value || '').trim().length > 0) && !!(f && (f.getAttribute('srcdoc') || '').length > 50);
        });
        if (ok) break;
        await sleep(500);
      }
      const compose = await page.evaluate(() => {
        const cd = document.querySelector('.mail-compose-dialog');
        if (!cd) return null;
        const ta = cd.querySelector('.compose-body textarea, .compose-edit .el-textarea__inner');
        const subjRow = Array.from(cd.querySelectorAll('.compose-row')).find(
          (r) => (r.querySelector('.compose-label')?.innerText || '').trim() === '主题'
        );
        const f = cd.querySelector('.compose-preview-frame');
        return {
          body: ta ? ta.value || '' : '',
          subject: subjRow ? (subjRow.querySelector('input.el-input__inner')?.value || '') : '',
          previewLen: f ? (f.getAttribute('srcdoc') || '').length : 0,
        };
      });
      check('撰写弹窗(MailComposeDialog)打开', !!compose);
      if (compose) {
        check('草稿正文非空', compose.body.length > 0, `len=${compose.body.length}`);
        check('草稿正文含真实工单标题（非「无标题」占位）',
          !!firstTitle && firstTitle !== '（无标题）' && compose.body.includes(firstTitle),
          `title="${firstTitle.slice(0, 20)}"`);
        check('草稿正文不含「（无标题）」占位', !compose.body.includes('（无标题）'), compose.body.slice(0, 60).replace(/\n/g, ' '));
        check('主题 = 【高级别工单督办】前缀', compose.subject.includes('高级别工单督办'), compose.subject);
        check('右侧预览已渲染', compose.previewLen > 200, `srcdoc=${compose.previewLen}`);
        await page.screenshot({ path: require('path').resolve(__dirname, '../../tmp_uishots/highlevel_compose.png') });
      }
      // 关闭撰写弹窗（不点发送，避免真发信）
      await page.evaluate(() => {
        const btns = Array.from(document.querySelectorAll('.mail-compose-dialog .el-dialog__footer .el-button'));
        const b = btns.find((x) => x.innerText.trim() === '取消') || btns[0];
        if (b) b.click();
      });
      await sleep(800);
    }
    // 关闭弹窗
    await page.evaluate(() => {
      const d = document.querySelector('.hl-supervise');
      const b = d && Array.from(d.querySelectorAll('.el-dialog__footer .el-button')).find((x) => x.innerText.trim() === '取消');
      if (b) b.click();
    });
    await sleep(700);
    // 取消 chip 筛选，恢复全量
    await page.evaluate((name) => {
      const c = Array.from(document.querySelectorAll('.hl-owner-chips .el-check-tag')).find((x) => x.innerText.trim().startsWith(name));
      if (c) c.click();
    }, ownerName);
    await sleep(1200);
  }

  // ── 按勾选督办链路 ───────────────────────────────────────
  const picked = await page.evaluate(() => {
    const cb = document.querySelector('.hl-table .el-table__body-wrapper tbody tr .el-checkbox');
    if (!cb) return false;
    cb.click();
    return true;
  });
  await sleep(900);
  check('勾选首行生效', picked);
  const batchBtnText = await page.evaluate(() => {
    const b = Array.from(document.querySelectorAll('.hl-filter-bar .el-button')).find((x) => x.innerText.includes('批量督办'));
    return b ? b.innerText.trim() : '';
  });
  check('「批量督办」按钮计数 = 1', batchBtnText.includes('1'), batchBtnText);
  await page.evaluate(() => {
    const b = Array.from(document.querySelectorAll('.hl-filter-bar .el-button')).find((x) => x.innerText.includes('批量督办'));
    if (b) b.click();
  });
  await sleep(1800);
  const dlg2 = await page.evaluate(() => {
    const d = document.querySelector('.hl-supervise');
    if (!d) return null;
    return { tip: (d.querySelector('.hls-tip')?.innerText || '').trim(), rows: d.querySelectorAll('.el-table__body-wrapper tbody tr').length };
  });
  check('按勾选督办弹窗打开', !!dlg2);
  if (dlg2) check('按勾选弹窗行数 = 1', dlg2.rows === 1, `rows=${dlg2.rows} tip="${dlg2.tip.slice(0, 30)}"`);
  await page.evaluate(() => {
    const d = document.querySelector('.hl-supervise');
    const b = d && Array.from(d.querySelectorAll('.el-dialog__footer .el-button')).find((x) => x.innerText.trim() === '取消');
    if (b) b.click();
  });
  await sleep(700);

  // ── 详情抽屉 ─────────────────────────────────────────────
  await page.evaluate(() => {
    const tr = document.querySelector('.hl-table .el-table__body-wrapper tbody tr');
    if (tr) {
      tr.dispatchEvent(new MouseEvent('dblclick', { bubbles: true }));
    }
  });
  await sleep(1800);
  const drawer = await page.evaluate(() => {
    const d = document.querySelector('.hl-detail');
    if (!d) return null;
    return {
      title: (document.querySelector('.hl-detail-title')?.innerText || '').trim(),
      secs: Array.from(document.querySelectorAll('.hl-detail-sec-title')).map((x) => x.innerText.trim()),
      trackActions: document.querySelectorAll('.hl-track-actions .el-button').length,
      log: !!document.querySelector('.email-supervise-log'),
      kv: document.querySelectorAll('.hl-kv').length,
    };
  });
  check('详情抽屉打开 (.hl-detail)', !!drawer, drawer ? drawer.title.slice(0, 26) : '未打开');
  if (drawer) {
    check('抽屉含「工单信息/汇聚跟踪/督办记录」三节',
      drawer.secs.includes('工单信息') && drawer.secs.includes('汇聚跟踪') && drawer.secs.includes('督办记录'),
      drawer.secs.join(','));
    check('抽屉 KV 字段 >= 8 项', drawer.kv >= 8, `kv=${drawer.kv}`);
    check('跟踪态操作区按钮存在（流转/锁定/提级/移出）', drawer.trackActions >= 4, `buttons=${drawer.trackActions}`);
    check('督办记录组件已挂载 (.email-supervise-log)', drawer.log === true);
    await page.screenshot({ path: require('path').resolve(__dirname, '../../tmp_uishots/highlevel_detail.png') });
  }

  const realErrs = errs.filter((e) => !e.includes('favicon'));
  check('全程无页面 JS 错误', realErrs.length === 0, realErrs.slice(0, 3).join(' ; '));

  console.log(log.join('\n'));
  const fails = log.filter((l) => l.startsWith('FAIL'));
  console.log(`\n=== TOTAL ${log.length} / PASS ${log.length - fails.length} / FAIL ${fails.length} ===`);
  await browser.close();
  process.exit(fails.length ? 1 : 0);
})();
