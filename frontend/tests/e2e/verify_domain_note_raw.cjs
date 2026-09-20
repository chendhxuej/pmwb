/**
 * 领域详情·主笔记「原文直出」验证（本次改动专用）
 * 运行：cd frontend && node tests/e2e/verify_domain_note_raw.cjs
 *
 * 验证点：
 *  1. 主笔记区直接渲染 Obsidian 笔记原文（含历史重复章节，不再被吞）
 *  2. 章节重排 UI（人工维护区标题头 / 已填 x/y 统计 / 章节徽标 / 附录折叠）已移除
 *  3. 标题层级与表格等原文结构保留，h2 已朴素化（无渐变底/彩色左边框）
 *  4. 顶部栏「编辑主笔记」按钮可进入编辑态（DomainDetailView panelRef 修复）
 *  5. HubPanel 内嵌领域详情同样原文直出
 *  6. 「自动区状态」tab 未受影响
 */
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-core');

const BASE = process.env.BASE_URL || 'http://localhost:5173';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const CODE = process.env.DOMAIN_CODE || 'ftto';
// 日志产物落在被 .gitignore 忽略的 logs/ 下，避免污染仓库
const OUT = process.env.OUT_FILE
  || path.resolve(__dirname, '../../../logs/e2e/verify_domain_note_raw.txt');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const lines = [];
let passed = 0;
let failed = 0;

function log(kind, msg) {
  const line = `[${kind}] ${msg}`;
  console.log(line);
  lines.push(line);
  if (kind === 'PASS') passed += 1;
  else if (kind === 'FAIL') failed += 1;
}

const norm = (s) => String(s || '').replace(/\s+/g, ' ').trim();

async function run() {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });

  try {
    const page = await browser.newPage();
    page.setDefaultTimeout(25000);
    page.setViewport({ width: 1440, height: 1000 });
    const consoleErrors = [];
    page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });

    // ── 场景 1：领域详情独立子页 ──
    await page.goto(`${BASE}/knowledge-center/domain/${CODE}`, { waitUntil: 'networkidle2' });
    await page.waitForSelector('.bible-full-content', { timeout: 25000 });
    log('PASS', '主笔记原文容器 .bible-full-content 已渲染');

    const noteText = await page.$eval('.bible-full-content', (el) => el.innerText);

    // (1) 原文本体：含旧实现被吞掉的第二次重复章节内容
    const expectRaw = [
      ['业务全过程时间线（系统自动）', '原文第二次重复章节标题'],
      ['MEET-20260807-372', '重复时间线章节内的自动区事件'],
      ['关联系统与接口（人工维护）', '原文第二次重复章节标题'],
      ['CRM/ESOP', '两次章节中的关联系统表格内容'],
      ['相关子笔记 MOC', '子笔记 MOC 章节'],
    ];
    for (const [kw, desc] of expectRaw) {
      if (norm(noteText).includes(norm(kw))) log('PASS', `原文直出包含「${kw}」— ${desc}`);
      else log('FAIL', `原文缺失「${kw}」— ${desc}`);
    }

    // (2) 章节重排 UI 元素清零
    const counters = await page.evaluate(() => ({
      zoneBlock: document.querySelectorAll('.zone-block').length,
      secCard: document.querySelectorAll('.sec-card').length,
      secBadge: document.querySelectorAll('.sec-badge').length,
      appendix: document.querySelectorAll('.appendix, .appendix-note, .appendix-title').length,
    }));
    const totalRemoved = Object.values(counters).reduce((a, b) => a + b, 0);
    if (totalRemoved === 0) log('PASS', '章节重排 UI 元素数为 0（zone-block/sec-card/sec-badge/appendix 全部移除）');
    else log('FAIL', `仍存在章节重排 UI 元素: ${JSON.stringify(counters)}`);

    // (3) 重排 UI 文案清零
    const bodyText = await page.$eval('body', (el) => el.innerText);
    const banned = [
      '系统自动区 · 系统维护区（附录）',
      '点击右上角「编辑主笔记」填写',
      '暂无自动回流内容',
      '该模板无人工维护章节',
      '个章节，由系统自动回流',
    ];
    for (const b of banned) {
      if (bodyText.includes(b)) log('FAIL', `重排 UI 文案仍存在：${b}`);
      else log('PASS', `重排 UI 文案已移除：${b}`);
    }
    if (/已填 \d+\/\d+/.test(bodyText)) log('FAIL', '主笔记区仍存在「已填 x/y」章节填充统计');
    else log('PASS', '「已填 x/y」章节填充统计已移除');

    // (4) 原文结构保留（标题层级）
    const hCount = await page.evaluate(() => {
      const q = (s) => document.querySelectorAll(`.bible-full-content ${s}`).length;
      return { h1: q('h1'), h2: q('h2'), h3: q('h3'), table: q('table'), li: q('li') };
    });
    if (hCount.h2 >= 10 && hCount.h3 >= 5 && hCount.table >= 3) {
      log('PASS', `原文结构保留：h2=${hCount.h2} h3=${hCount.h3} table=${hCount.table} li=${hCount.li}`);
    } else {
      log('FAIL', `原文结构异常：${JSON.stringify(hCount)}`);
    }

    // (5) 排版朴素化：h2 无渐变底、无彩色左边框
    const h2style = await page.$eval('.bible-full-content h2', (el) => {
      const cs = getComputedStyle(el);
      return { bgImage: cs.backgroundImage, bgColor: cs.backgroundColor, borderLeft: cs.borderLeftWidth };
    });
    const plainOk = !h2style.bgImage.includes('gradient')
      && h2style.bgColor === 'rgba(0, 0, 0, 0)'
      && parseFloat(h2style.borderLeft) === 0;
    if (plainOk) log('PASS', `h2 排版已朴素化：bgImage=${h2style.bgImage} bgColor=${h2style.bgColor} borderLeft=${h2style.borderLeft}`);
    else log('FAIL', `h2 仍带重排样式：${JSON.stringify(h2style)}`);

    // (6) 顶部栏「编辑主笔记」按钮（panelRef 修复）可进入编辑态
    const clicked = await page.evaluate(() => {
      const btn = [...document.querySelectorAll('.detail-actions button')]
        .find((x) => x.innerText.includes('编辑主笔记'));
      if (!btn) return false;
      btn.click();
      return true;
    });
    if (!clicked) log('FAIL', '未找到顶部栏「编辑主笔记」按钮');
    else {
      await sleep(700);
      const hasTextarea = await page.$('.bible-textarea');
      if (hasTextarea) log('PASS', '点击「编辑主笔记」后进入编辑态（panelRef 修复生效，Markdown 编辑框出现）');
      else log('FAIL', '点击「编辑主笔记」后未进入编辑态（panelRef 仍失效）');
      // 退出编辑态，绝不触发保存
      await page.evaluate(() => {
        const btn = [...document.querySelectorAll('.edit-actions button')]
          .find((x) => x.innerText.trim() === '取消');
        if (btn) btn.click();
      });
      await sleep(400);
      const backToRead = await page.$('.bible-full-content');
      if (backToRead) log('PASS', '取消编辑后回到原文展示态');
      else log('FAIL', '取消编辑后未回到原文展示态');
    }

    // ── 场景 2：HubPanel 内嵌详情 ──
    await page.goto(`${BASE}/knowledge-center/hub`, { waitUntil: 'networkidle2' });
    await page.waitForSelector('.domain-grid .domain-card', { timeout: 25000 });
    await page.click('.domain-grid .domain-card');
    await page.waitForSelector('#domainDetail .bible-full-content', { timeout: 25000 });
    const hubOk = await page.evaluate(() => ({
      raw: !!document.querySelector('#domainDetail .bible-full-content.bible-md'),
      legacy: document.querySelectorAll('#domainDetail .zone-block, #domainDetail .sec-card').length,
    }));
    if (hubOk.raw && hubOk.legacy === 0) log('PASS', 'HubPanel 内嵌领域详情同样原文直出，无章节重排 UI');
    else log('FAIL', `HubPanel 内嵌详情异常：${JSON.stringify(hubOk)}`);

    // ── 场景 3：「自动区状态」tab 保持可用（本次未改动） ──
    await page.goto(`${BASE}/knowledge-center/domain/${CODE}`, { waitUntil: 'networkidle2' });
    await page.waitForSelector('.bible-full-content', { timeout: 25000 });
    const tabClicked = await page.evaluate(() => {
      const t = [...document.querySelectorAll('.dtabs .dtab')]
        .find((x) => x.innerText.includes('自动区状态'));
      if (!t) return false;
      t.click();
      return true;
    });
    if (!tabClicked) log('FAIL', '未找到「自动区状态」tab');
    else {
      await sleep(600);
      const tabText = await page.$eval('.dbody', (el) => el.innerText);
      if (tabText.includes('人工维护区填充') && tabText.includes('主笔记已建')) {
        log('PASS', '「自动区状态」tab 未受影响（章节填充度等仍正常展示）');
      } else {
        log('FAIL', `「自动区状态」tab 内容异常：${norm(tabText).slice(0, 160)}`);
      }
    }

    // ── 控制台错误 ──
    if (consoleErrors.length === 0) log('PASS', '全流程无 console error');
    else log('FAIL', `发现 ${consoleErrors.length} 条 console error：${consoleErrors.slice(0, 3).join(' | ')}`);
  } catch (e) {
    log('FAIL', `测试执行异常：${e.message}`);
  } finally {
    await browser.close();
    const summary = [
      '',
      '================ 汇总 ================',
      `PASS: ${passed}`,
      `FAIL: ${failed}`,
      failed === 0 ? 'RESULT: ALL PASS' : 'RESULT: HAS FAILURE',
    ].join('\n');
    console.log(summary);
    lines.push(summary);
    fs.mkdirSync(path.dirname(OUT), { recursive: true });
    fs.writeFileSync(OUT, lines.join('\n') + '\n', 'utf-8');
    console.log(`[INFO] 日志已写入 ${OUT}`);
    process.exit(failed === 0 ? 0 : 1);
  }
}

run();
