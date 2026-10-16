/**
 * 插件「厂家工单扫描」真实浏览器回归
 *
 * 验证点：
 *   1. 扫描器是「表头驱动」而非写死列下标（两个 fixture 都刻意打乱了列序）
 *   2. 原生 table 与 Element UI 组件库（表头/表体分离）两种 DOM 都能识别
 *   3. 只命中「系统名称=IT开发子流程 且 当前环节=已上线待需求录入人确认」
 *   4. 标题三段解析：编号 + [厂家团队] + 需求标题
 *   5. 详情链接 detailUrl 正确提取（供后续进详情页抓操作手册）
 *
 * 运行：node frontend/tests/e2e/verify_workorder_scan.cjs
 */
const path = require('path');
const fs = require('fs');
const puppeteer = require('puppeteer-core');

const ROOT = path.resolve(__dirname, '..', '..', '..');
const POPUP = path.join(ROOT, 'extension', 'popup', 'popup.js');
const FIX_DIR = path.join(ROOT, 'extension', 'tests');
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';

let pass = 0;
let fail = 0;
function ok(name, cond, extra) {
  if (cond) { pass++; console.log(`  PASS  ${name}`); }
  else { fail++; console.log(`  FAIL  ${name}${extra ? '  ->  ' + extra : ''}`); }
}

/** 从 popup.js 抽出「详情页抓操作手册」源码 */
function extractManualSource() {
  const src = fs.readFileSync(POPUP, 'utf8').replace(/\r\n/g, '\n');
  const s = src.indexOf('async function grabManualInPage() {');
  const e = src.indexOf('/** 打开工单详情页并抓取操作手册');
  if (s < 0 || e < 0) throw new Error('未定位到 grabManualInPage 源码段');
  return src.slice(s, e);
}

/** 从 popup.js 抽出扫描器 + 标题解析器源码（不整份 eval，避免 chrome.* API 报错） */
function extractSource() {
  const src = fs.readFileSync(POPUP, 'utf8').replace(/\r\n/g, '\n');
  const s = src.indexOf('const WO_FILTER = {');
  const e = src.indexOf('/** 扫描当前页的待办工单 */');
  if (s < 0 || e < 0 || e <= s) throw new Error('未定位到扫描器源码段');
  return src.slice(s, e);
}

const PAGE_PROBE = `
  const s = scanWorkorderListInPage(WO_FILTER);
  const rows = s.rows.map((r) => {
    const p = parseWorkorderTitle(r.title);
    return { title: r.title, system: r.system, stage: r.stage, detailUrl: r.detailUrl,
             submitter: r.submitter, receiveDate: r.receiveDate,
             code: p.code, vendor: p.vendor, reqTitle: p.reqTitle, warn: p.warn };
  });
  return { ok: s.ok, heads: s.heads, total: s.total, matched: s.matched, rows };
`;

async function probe(page, file) {
  await page.goto('file:///' + path.join(FIX_DIR, file).replace(/\\/g, '/'), { waitUntil: 'load' });
  return page.evaluate(
    (source, probe) => new Function(source + '\n' + probe)(),
    extractSource(),
    PAGE_PROBE
  );
}

/** 在详情页执行 grabManualInPage（异步，puppeteer 会自动 await promise） */
async function probeManual(page, file) {
  await page.goto('file:///' + path.join(FIX_DIR, file).replace(/\\/g, '/'), { waitUntil: 'load' });
  return page.evaluate(
    (source) => new Function(source + '\nreturn grabManualInPage();')(),
    extractManualSource()
  );
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--allow-file-access-from-files'],
  });
  try {
    const page = await browser.newPage();

    // ---------- 场景 A：原生 table，列序打乱（接收日期在最前） ----------
    console.log('\n[场景A] 原生 table（fixture_todo_list.html）');
    const a = await probe(page, 'fixture_todo_list.html');
    console.log('  表头:', JSON.stringify(a.heads));
    console.log('  总行:', a.total, '命中:', a.matched);
    ok('A1 表识别成功', a.ok === true);
    ok('A2 总行数=4', a.total === 4, String(a.total));
    ok('A3 命中=2（列序打乱仍正确）', a.matched === 2, JSON.stringify(a.rows.map((r) => r.title)));
    const codes = a.rows.map((r) => `${r.code}|${r.vendor}`).sort();
    ok('A4 同编号两厂家', JSON.stringify(codes) ===
      JSON.stringify(['REQ_2026第0930620号|CRM', 'REQ_2026第0930620号|订单中心'].sort()),
      JSON.stringify(codes));
    ok('A5 需求标题去「关于」前缀', a.rows.every((r) => r.reqTitle === '购物车协议复制步骤简化的需求'),
      JSON.stringify(a.rows.map((r) => r.reqTitle)));
    ok('A6 detailUrl 提取', a.rows.some((r) => r.detailUrl.includes('/detail/2')) &&
      a.rows.some((r) => r.detailUrl.includes('/detail/3')),
      JSON.stringify(a.rows.map((r) => r.detailUrl)));
    ok('A7 无解析告警', a.rows.every((r) => r.warn === false));
    ok('A8 排除：环节不符 + 系统不符', a.rows.every((r) => !r.title.includes('0991412') && !r.title.includes('0986193')));

    // ---------- 场景 B：Element UI（表头/表体分离 + 幽灵表） ----------
    console.log('\n[场景B] Element UI 组件库（fixture_todo_list_eltable.html）');
    const b = await probe(page, 'fixture_todo_list_eltable.html');
    console.log('  表头:', JSON.stringify(b.heads));
    console.log('  总行:', b.total, '命中:', b.matched);
    ok('B1 表识别成功（表头表体分离）', b.ok === true);
    ok('B2 总行数=4（未被 .hidden-columns 幽灵表污染）', b.total === 4, String(b.total));
    ok('B3 命中=2', b.matched === 2, JSON.stringify(b.rows.map((r) => r.title)));
    const bcodes = b.rows.map((r) => `${r.code}|${r.vendor}`).sort();
    ok('B4 同编号两厂家', JSON.stringify(bcodes) ===
      JSON.stringify(['REQ_2026第0930620号|CRM', 'REQ_2026第0930620号|订单中心'].sort()),
      JSON.stringify(bcodes));
    ok('B5 detailUrl 提取', b.rows.some((r) => r.detailUrl.includes('/detail/11')) &&
      b.rows.some((r) => r.detailUrl.includes('/detail/12')),
      JSON.stringify(b.rows.map((r) => r.detailUrl)));
    ok('B6 submitter/接收日期按表头取对', b.rows.every((r) => r.submitter === 'admin' && r.receiveDate === '2026-10-12'),
      JSON.stringify(b.rows.map((r) => [r.submitter, r.receiveDate])));

    // ---------- 场景 C：无工单页面应友好失败 ----------
    console.log('\n[场景C] 空白页');
    await page.goto('data:text/html,<h1>no table</h1>', { waitUntil: 'load' });
    const c = await page.evaluate(
      (source, probe) => new Function(source + '\n' + probe)(),
      extractSource(),
      PAGE_PROBE
    );
    ok('C1 未识别时 ok=false 不抛异常', c.ok === false && Array.isArray(c.rows), JSON.stringify(c));

    // ---------- 场景 D：真实标题解析 ----------
    console.log('\n[场景D] 真实标题解析');
    const titles = [
      'REQ_2026第0930620号[CRM]关于购物车协议复制步骤简化的需求',
      'REQ_2026第0930620号[订单中心]关于购物车协议复制步骤简化的需求',
      'REQ_2026第091412号[商机审批中心]企助手-商客版产品需求',
    ];
    const parsed = await page.evaluate(
      (source, list) => {
        const f = new Function('list', source + '\nreturn list.map((t) => parseWorkorderTitle(t));');
        return f(list);
      },
      extractSource(),
      titles
    );
    parsed.forEach((p, i) => console.log('  ', JSON.stringify(p)));
    ok('D1 全部解析出编号+厂家+标题', parsed.every((p) => p.code && p.vendor && p.reqTitle));

    // ---------- 场景 E：详情页抓手册 —— 直链下载 ----------
    console.log('\n[场景E] 详情页 · 附件摘要页签 + a[href] 直链下载');
    const e1 = await probeManual(page, 'fixture_detail_href.html');
    console.log('  ', JSON.stringify({ ok: e1.ok, filename: e1.filename, via: e1.via, reason: e1.reason }));
    ok('E1 抓取成功', e1.ok === true, e1.reason);
    ok('E2 命中「操作手册」文件（非需求说明书/测试报告）',
      e1.filename === '操作手册-购物车协议复制V1.2.docx', e1.filename);
    ok('E3 走 href 直链路', e1.via === 'href', e1.via);
    ok('E4 内容正确', Buffer.from(e1.base64 || '', 'base64').toString('utf8') === 'Hello-Manual',
      Buffer.from(e1.base64 || '', 'base64').toString('utf8'));

    // ---------- 场景 F：详情页抓手册 —— blob 下载（无直链） ----------
    console.log('\n[场景F] 详情页 · blob 下载（hook createObjectURL）');
    const f1 = await probeManual(page, 'fixture_detail_blob.html');
    console.log('  ', JSON.stringify({ ok: f1.ok, filename: f1.filename, via: f1.via, reason: f1.reason }));
    ok('F1 抓取成功', f1.ok === true, f1.reason);
    ok('F2 命中「操作手册」文件', f1.filename === '操作手册-订单中心V2.0.docx', f1.filename);
    ok('F3 走 blob-hook 降级路', f1.via === 'blob-hook', f1.via);
    ok('F4 内容正确', Buffer.from(f1.base64 || '', 'base64').toString('utf8') === 'BLOBMANUAL',
      Buffer.from(f1.base64 || '', 'base64').toString('utf8'));

    // ---------- 场景 G：无手册附件应友好失败 ----------
    console.log('\n[场景G] 详情页 · 无「操作手册」附件');
    await page.goto('data:text/html,<div class="tabs"><span>附件摘要</span></div><table><tr><td>需求说明书.docx</td><td><a>下载</a></td></tr></table>', { waitUntil: 'load' });
    const g1 = await page.evaluate(
      (source) => new Function(source + '\nreturn grabManualInPage();')(),
      extractManualSource()
    );
    ok('G1 ok=false 且给出原因', g1.ok === false && !!g1.reason, JSON.stringify(g1));
  } catch (e) {
    fail++;
    console.log('\n  EXCEPTION: ' + e.message);
    console.log(e.stack);
  } finally {
    await browser.close();
  }

  console.log(`\n===== verify_workorder_scan: ${pass} passed, ${fail} failed =====`);
  process.exit(fail ? 1 : 0);
})();
