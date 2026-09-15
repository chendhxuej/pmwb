/**
 * 首页看板 2.0（统一规范版）DOM + 布局断言
 *
 * 对齐原型 prototype/home-dashboard-v2-r3-unified.html，验证点：
 *   A. 行序：问候(greeting-tile) → KPI(×4) → 模块概览 label → 快捷操作 → 核心工作区 label → 今日聚焦
 *   B. 问候语含「老大」，全文无「陈工」
 *   C. KPI 4 卡 label 固定，且数值与 /api/v1/dashboard 接口一致（value_text 优先）
 *   D. 模块概览 6 卡 · NEW 徽标 ×2 · 运营卡 caliber「含一线调研」· 会议卡「去补录」
 *   E. 首行两卡高度对齐（grid 拉伸应完全一致，容差 2px）
 *   F. console 无 Vue 运行时致命错误（防「编译过但白屏」）
 *
 * 运行：
 *   cd frontend && node tests/e2e/verify_home_v2.cjs
 * 环境变量：BASE_URL(默认 http://127.0.0.1:5173) CHROME_PATH TIMEOUT RENDER_WAIT
 */
const puppeteer = require('puppeteer-core');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const TIMEOUT = Number(process.env.TIMEOUT) || 20000;
const RENDER_WAIT = Number(process.env.RENDER_WAIT) || 3500;

const FATAL_PATTERNS = [
  /is not defined on instance/,
  /Unhandled error during execution of/,
  /Cannot read properties of (null|undefined)/,
  /is not a function/,
  /Property .* was accessed during render/,
];

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
  page.setViewport({ width: 1600, height: 1000 });

  const errors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', (err) => errors.push(err.message));

  console.log(`打开 ${BASE} 首页...`);
  await page.goto(`${BASE}/dashboard`, { waitUntil: 'domcontentloaded', timeout: TIMEOUT });
  await sleep(RENDER_WAIT);

  // ── DOM 断言 ──
  const dom = await page.evaluate(() => {
    const q = (s) => document.querySelector(s);
    const qa = (s) => Array.from(document.querySelectorAll(s));
    const txt = (el) => (el ? (el.textContent || '').trim() : null);
    const following = (a, b) => !!(a && b && (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING));

    const greetTile = q('.greeting-tile');
    const liveCard = greetTile ? greetTile.nextElementSibling : null;
    const labels = qa('.row-label');
    const actionRow = q('.action-row');
    const kpiFirst = q('.kpi-card');
    const fzFirst = q('.fz-item');

    const greetH = greetTile ? greetTile.getBoundingClientRect().height : -1;
    const liveH = liveCard ? liveCard.getBoundingClientRect().height : -1;

    return {
      bodyText: (document.body.innerText || ''),
      hello: txt(q('.g-hello')) || '',
      gSub: txt(q('.g-sub')) || '',
      gStats: qa('.g-stat').map((el) => txt(el)),
      efficiency: txt(q('.g-eff-val')) || '',
      kpis: qa('.kpi-card').map((c) => ({
        num: txt(c.querySelector('.kpi-num')),
        label: txt(c.querySelector('.kpi-label')),
        trend: txt(c.querySelector('.kpi-trend')),
      })),
      rowLabels: qa('.row-label .rl-t').map(txt),
      modCards: qa('.mod-grid').length,
      newBadges: qa('.new-badge').map(txt),
      calibers: qa('.caliber').map(txt),
      pmTags: qa('.pm-tag.amber').map(txt),
      fzItems: qa('.fz-item').length,
      kpItems: qa('.kp-item').length,
      lsItems: qa('.ls-item').length,
      lsSrcs: qa('.ls-src').map(txt),
      chartPoly: qa('.chart-svg polyline').length,
      stat4Reqs: qa('.stat4').length,
      order: {
        greet_kpi: following(greetTile, kpiFirst),
        kpi_modlabel: following(kpiFirst, labels[0]),
        modlabel_action: following(labels[0], actionRow),
        action_worklabel: following(actionRow, labels[1]),
        worklabel_focus: following(labels[1], fzFirst),
      },
      heights: { greet: Math.round(greetH), live: Math.round(liveH) },
      modCenters: qa('.mod-grid').map((g) => {
        const card = g.closest('.card');
        const num = g.querySelector('.mod-num');
        const sub = g.querySelector('.mod-sub');
        const cr = card ? card.getBoundingClientRect() : g.getBoundingClientRect();
        const nr = num.getBoundingClientRect();
        const hDev = Math.abs((nr.left + nr.right) / 2 - (cr.left + cr.right) / 2);
        const gr = g.getBoundingClientRect();
        const sr = sub ? sub.getBoundingClientRect() : nr;
        const vDev = Math.abs((nr.top - gr.top) - (gr.bottom - sr.bottom));
        return { h: Math.round(hDev * 10) / 10, v: Math.round(vDev) };
      }),
    };
  });

  // ── 接口一致性 ──
  const api = await page.evaluate(async () => {
    try {
      const r = await fetch('/api/v1/dashboard', { credentials: 'include' });
      const j = await r.json();
      return j && j.data ? j.data : null;
    } catch (e) {
      return { __err: String(e) };
    }
  });

  await browser.close();

  // ══ 判定 ══
  const results = [];
  const check = (name, ok, detail) => results.push({ name, ok: !!ok, detail: detail || '' });

  check('F. console 无致命错误', errors.filter((e) => FATAL_PATTERNS.some((re) => re.test(e))).length === 0,
    errors.length ? `errors(${errors.length}): ${errors.slice(0, 3).map((e) => e.slice(0, 120)).join(' | ')}` : 'clean');
  check('A1. 问候卡在 KPI 之前', dom.order.greet_kpi);
  check('A2. KPI 在模块概览 label 之前', dom.order.kpi_modlabel);
  check('A3. 模块概览 label 在快捷操作之前', dom.order.modlabel_action);
  check('A4. 快捷操作在核心工作区 label 之前', dom.order.action_worklabel);
  check('A5. 核心工作区 label 在今日聚焦之前', dom.order.worklabel_focus);
  check('A6. 行标签 = [模块概览, 核心工作区]', JSON.stringify(dom.rowLabels) === JSON.stringify(['模块概览', '核心工作区']),
    dom.rowLabels.join(','));
  check('B1. 问候语含「老大」', dom.hello.includes('老大'), dom.hello);
  check('B2. 全文无「陈工」', !dom.bodyText.includes('陈工'));
  check('C1. KPI 恰好 4 卡', dom.kpis.length === 4, `got ${dom.kpis.length}`);
  const kpiLabels = dom.kpis.map((k) => k.label).join('|');
  check('C2. KPI label 含核心4项', ['我的待办', '本周会议', '跟踪中需求', '邮件'].every((k) => kpiLabels.includes(k)), kpiLabels);
  if (api && !api.__err && Array.isArray(api.kpis)) {
    const mism = [];
    dom.kpis.forEach((k, i) => {
      const a = api.kpis[i];
      if (!a) { mism.push(`#${i} 接口缺`); return; }
      const expect = String(a.value_text || (a.value ?? ''));
      if (String(k.num) !== expect) mism.push(`#${i} ${a.label}: DOM=${k.num} API=${expect}`);
    });
    check('C3. KPI 数值与接口一致', mism.length === 0, mism.join('; ') || '4/4 一致');
    check('C4. 接口 user_name=老大', api.user_name === '老大', String(api.user_name));
    check('C5. 接口 focus_items 非空', Array.isArray(api.focus_items) && api.focus_items.length > 0,
      `got ${Array.isArray(api.focus_items) ? api.focus_items.length : 'null'}`);
  } else {
    check('C3. KPI 数值与接口一致', false, `接口不可用: ${api && api.__err ? api.__err : 'unknown'}`);
  }
  check('D1. 模块概览 6 卡', dom.modCards === 6, `got ${dom.modCards}`);
  check('D2. NEW 徽标 ×2', dom.newBadges.length === 2, dom.newBadges.join(','));
  check('D3. 运营卡含「含一线调研」caliber', dom.calibers.some((c) => c.includes('含一线调研')), dom.calibers.join(' / '));
  check('D4. 会议卡含「去补录」', dom.pmTags.some((t) => t.includes('去补录')), dom.pmTags.join(',') || 'none');
  check('D5. 今日聚焦条目 > 0', dom.fzItems > 0, `got ${dom.fzItems}`);
  check('D6. 重点工作条目 > 0', dom.kpItems > 0, `got ${dom.kpItems}`);
  check('D7. 实时动态 ≥ 4 条且带来源徽标', dom.lsItems >= 4 && dom.lsSrcs.length === dom.lsItems,
    `items=${dom.lsItems} srcs=${dom.lsSrcs.join(',')}`);
  check('D8. 需求概览趋势 SVG polyline 存在', dom.chartPoly >= 1, `got ${dom.chartPoly}`);
  check('E. 首行两卡高度对齐(容差2px)', Math.abs(dom.heights.greet - dom.heights.live) <= 2,
    `greet=${dom.heights.greet} live=${dom.heights.live}`);
  check('D9. 模块概览数字水平居中(≤4px)', dom.modCenters.length === 6 && dom.modCenters.every((c) => c.h <= 4),
    dom.modCenters.map((c) => c.h).join(','));
  check('D10. 模块概览内容垂直居中(≤8px)', dom.modCenters.length === 6 && dom.modCenters.every((c) => c.v <= 8),
    dom.modCenters.map((c) => c.v).join(','));

  // info 输出
  console.log('\n── 关键内容快照 ──');
  console.log('hello   :', dom.hello, '|', dom.gSub);
  console.log('g-stats :', dom.gStats.join(' · '), '| 闭环率', dom.efficiency);
  console.log('kpis    :', dom.kpis.map((k) => `${k.label}=${k.num}(${k.trend})`).join(' | '));
  console.log('calibers:', dom.calibers.join(' / '));
  console.log('ls-srcs :', dom.lsSrcs.join(','));
  console.log('heights :', JSON.stringify(dom.heights));

  console.log('\n══════ 首页看板 2.0 断言结果 ══════');
  let fail = 0;
  results.forEach((r) => {
    if (!r.ok) fail += 1;
    console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.name}${r.detail ? '  → ' + r.detail : ''}`);
  });
  console.log(`══════ ${results.length - fail} passed / ${fail} failed ══════`);
  process.exit(fail > 0 ? 1 : 0);
}

run().catch((err) => {
  console.error(`[FATAL] ${err && err.stack ? err.stack : err}`);
  process.exit(2);
});
