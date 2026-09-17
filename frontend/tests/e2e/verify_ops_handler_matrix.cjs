// 运营监控总览页「责任人分布」矩阵端到端验证
// 断言：旧区域已删除 / 矩阵结构与接口口径一致 / 点单元格跳转子页面并按人+状态检索
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const API = process.env.API_URL || 'http://127.0.0.1:8000';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const OUT = path.resolve(__dirname, '../../tmp_uishots');

const STATUS_KEYS = ['pending', 'processing', 'verify', 'resolved', 'closed', 'suspended'];
const STATUS_LABELS = ['待处理', '处理中', '验证中', '已解决', '已关闭', '已挂起'];
const CAT_KEYS = ['bug', 'data', 'prod', 'task', 'complaint'];

const log = [];
const check = (name, cond, extra) => log.push(`${cond ? 'PASS' : 'FAIL'} ${name}${extra ? ' | ' + extra : ''}`);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });

  let data = null;
  try {
    const r = await fetch(API + '/api/v1/operation/stats/by-handler');
    data = (await r.json()).data;
    check('聚合接口可用', !!data && Array.isArray(data.handlers), `handlers=${data.handlers.length}`);
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

  await page.goto(BASE + '/operation/overview', { waitUntil: 'networkidle2', timeout: 45000 });
  await sleep(2000);
  await page.screenshot({ path: path.join(OUT, 'ops_handler_matrix.png'), fullPage: false });

  const dom = await page.evaluate(() => {
    const root = document.querySelector('.operation-overview');
    return {
      rootFound: !!root,
      rootText: root ? root.innerText : '',
      hmBlocks: document.querySelectorAll('.hm-block').length,
      catTiles: document.querySelectorAll('.cat-tile').length,
      legacyCount: document.querySelectorAll('.ops-list-col, .research-quick-card, .ops-side-col, .ops-table').length,
      tileNums: Array.from(document.querySelectorAll('.cat-tile')).map((t) => ({
        name: t.querySelector('.cat-name')?.innerText || '',
        count: t.querySelector('.cat-count')?.innerText.trim() || '',
      })),
      grid: Array.from(document.querySelectorAll('.hm-block')).map((b) => ({
        name: (b.querySelector('.hm-name')?.innerText || '').trim(),
        rows: Array.from(b.querySelectorAll('tbody tr')).map((tr) =>
          Array.from(tr.querySelectorAll('td')).map((td) => ({
            t: td.innerText.trim(),
            clickable: !!td.querySelector('.hm-cell:not(.hm-cell-empty)'),
          }))
        ),
      })),
    };
  });

  check('总览页容器渲染', dom.rootFound);
  check('旧区域已删除(一线调研卡/工单列表/侧栏)', dom.legacyCount === 0, `legacyEls=${dom.legacyCount}`);
  check('页面内不再出现一线调研', !dom.rootText.includes('一线调研'));
  check('6 个分类磁贴保留', dom.catTiles === 6, `tiles=${dom.catTiles}`);

  if (data) {
    const expectHandlers = data.handlers.filter((h) => !h.unassigned);
    check('责任人区块数 = 接口责任人数', dom.hmBlocks === expectHandlers.length, `dom=${dom.hmBlocks} api=${expectHandlers.length}`);

    // 逐块逐格比对：DOM 数字 vs 接口数字（0 显示为 –）
    let cellTotal = 0;
    let cellMismatch = 0;
    let clickableMismatch = 0;
    dom.grid.forEach((blk, bi) => {
      const api = expectHandlers[bi];
      if (!api) { cellMismatch++; return; }
      if (blk.name !== api.name) { cellMismatch++; log.push(`  name-diff idx${bi} dom=${blk.name} api=${api.name}`); }
      CAT_KEYS.forEach((cat, ci) => {
        STATUS_KEYS.forEach((st, si) => {
          const domTxt = blk.rows[ci] ? blk.rows[ci][si + 1].t : '?';
          const val = (api.matrix[cat] && api.matrix[cat][st]) || 0;
          const expect = val ? String(val) : '–';
          cellTotal++;
          if (domTxt !== expect) {
            cellMismatch++;
            if (cellMismatch <= 5) log.push(`  cell-diff ${api.name}/${cat}/${st} dom=${domTxt} api=${expect}`);
          }
          const domClickable = blk.rows[ci] ? blk.rows[ci][si + 1].clickable : false;
          if (domClickable !== (val > 0)) clickableMismatch++;
        });
      });
    });
    check(`全部 ${cellTotal} 个单元格数字与接口一致`, cellMismatch === 0, `mismatch=${cellMismatch}`);
    check('有数据单元格可点、空单元格不可点', clickableMismatch === 0, `mismatch=${clickableMismatch}`);

    // 选一个最大的非空格子做跳转验证
    let target = null;
    expectHandlers.forEach((h, hi) => {
      CAT_KEYS.forEach((cat, ci) => {
        STATUS_KEYS.forEach((st, si) => {
          const v = (h.matrix[cat] && h.matrix[cat][st]) || 0;
          if (v > 0 && (!target || v > target.v)) target = { h, hi, cat, ci, st, si, v };
        });
      });
    });

    if (target) {
      const el = await page.evaluateHandle((name, ci, si) => {
        const blocks = Array.from(document.querySelectorAll('.hm-block'));
        const b = blocks.find((x) => (x.querySelector('.hm-name')?.innerText || '').trim() === name);
        if (!b) return null;
        const tr = b.querySelectorAll('tbody tr')[ci];
        if (!tr) return null;
        return tr.querySelectorAll('td.hm-td-num')[si].querySelector('.hm-cell:not(.hm-cell-empty)');
      }, target.h.name, target.ci, target.si);

      const node = el.asElement();
      check('目标单元格可定位', !!node, `${target.h.name}/${target.cat}/${target.st}=${target.v}`);
      if (node) {
        const box = await node.boundingBox();
        await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
        const expectPath = `/operation/${target.cat}`;
        try {
          await page.waitForFunction((p) => location.pathname === p, { timeout: 15000 }, expectPath);
          await sleep(1500);
          const after = await page.evaluate(() => ({
            url: location.pathname + location.search,
            hint: document.querySelector('.filter-hint') ? document.querySelector('.filter-hint').innerText : '',
            statItems: document.querySelectorAll('.stat-item').length,
            activeSt: document.querySelector('.st-tag.active')?.innerText || '',
            bodyRows: document.querySelectorAll('.el-table__body-wrapper tbody tr').length,
          }));
          check('跳转到对应工单子页面', after.url.startsWith(expectPath), after.url);
          const m = after.hint.match(/命中\s*(\d+)\s*条/);
          const hintNum = m ? Number(m[1]) : -1;
          check('子页面命中条数 = 单元格数字', hintNum === target.v, `hint=${hintNum} cell=${target.v}`);
          check('提示条带责任人', after.hint.includes(target.h.name), after.hint.replace(/\n/g, ' / '));
          check('提示条带状态', after.hint.includes(STATUS_LABELS[target.si]));
          check('子页面正常渲染(统计卡 8 项)', after.statItems === 8, `statItems=${after.statItems}`);
          check('状态标签为深链状态', after.activeSt.includes(STATUS_LABELS[target.si]), after.activeSt);
          log.push(`  detail: rows=${after.bodyRows} url=${after.url}`);

          // 清除责任人筛选 → 应回到「该类别 + 该状态」的全量口径
          const closeEl = await page.$('.filter-hint .el-tag .el-tag__close');
          if (closeEl) {
            await closeEl.click();
            await sleep(1500);
            const cleared = await page.evaluate(() => ({
              url: location.pathname + location.search,
              hint: document.querySelector('.filter-hint') ? document.querySelector('.filter-hint').innerText : '',
            }));
            const cm = cleared.hint.match(/命中\s*(\d+)\s*条/);
            const globalVal = (data.category_matrix[target.cat] && data.category_matrix[target.cat][target.st]) || 0;
            check('清除责任人后 URL 去掉 handler', !/[?&]handler=/.test(cleared.url), cleared.url);
            check('清除后命中数 = 该类该状态全量', cm && Number(cm[1]) === globalVal, `hint=${cm ? cm[1] : 'n/a'} api=${globalVal}`);
          }
        } catch (e) {
          check('跳转到对应工单子页面', false, e.message);
        }
      }
    }
  }

  // ---- 深链落地后：子页签切换应保留责任人、复位状态，且地址栏同步 ----
  if (data && data.handlers.length) {
    const hName = data.handlers.find((h) => !h.unassigned).name;
    await page.goto(
      `${BASE}/operation/data?handler=${encodeURIComponent(hName)}&status=processing`,
      { waitUntil: 'networkidle2', timeout: 45000 }
    );
    await sleep(1500);
    const beforeTab = await page.evaluate(() => ({
      hint: document.querySelector('.filter-hint') ? document.querySelector('.filter-hint').innerText : '',
      url: location.pathname + location.search,
    }));
    const bm = beforeTab.hint.match(/命中\s*(\d+)\s*条/);
    const expectDataProcessing =
      (data.handlers.find((h) => h.name === hName).matrix.data || {}).processing || 0;
    check('深链直达(责任人在 URL 生效)', bm && Number(bm[1]) === expectDataProcessing,
      `hint=${bm ? bm[1] : 'n/a'} api=${expectDataProcessing}`);

    await page.evaluate(() => {
      const t = Array.from(document.querySelectorAll('.sub-tabs .sub-tab')).find((x) =>
        x.innerText.includes('临时交办')
      );
      if (t) t.click();
    });
    await sleep(1800);
    const afterTab = await page.evaluate(() => ({
      hint: document.querySelector('.filter-hint') ? document.querySelector('.filter-hint').innerText : '',
      url: location.pathname + location.search,
      activeSt: document.querySelector('.st-tag.active') ? document.querySelector('.st-tag.active').innerText : '',
    }));
    const am = afterTab.hint.match(/命中\s*(\d+)\s*条/);
    const expectTaskAll = data.handlers.find((h) => h.name === hName).cat_totals.task || 0;
    check('子页签切换保留责任人筛选', afterTab.hint.includes(hName), afterTab.hint.replace(/\n/g, ' / '));
    check('子页签切换复位状态为全部', afterTab.activeSt.includes('全部'), afterTab.activeSt);
    check('切换后命中数 = 该责任人临时交办全量', am && Number(am[1]) === expectTaskAll,
      `hint=${am ? am[1] : 'n/a'} api=${expectTaskAll}`);
    check('地址栏与页面状态同步(去掉 status)', !/[?&]status=/.test(afterTab.url) && /[?&]handler=/.test(afterTab.url), afterTab.url);
  }

  // ---- 5 个工单子页面无白屏冒烟 ----
  const subRouteResults = [];
  for (const cat of CAT_KEYS) {
    await page.goto(`${BASE}/operation/${cat}`, { waitUntil: 'networkidle2', timeout: 45000 });
    await sleep(1200);
    const r = await page.evaluate(() => ({
      statItems: document.querySelectorAll('.stat-item').length,
      rows: document.querySelectorAll('.el-table__body-wrapper tbody tr').length,
      appText: (document.querySelector('#app') ? document.querySelector('#app').innerText : '').length,
    }));
    subRouteResults.push(`${cat}:${r.statItems}/${r.rows}/${r.appText}`);
    if (r.appText < 300 || r.statItems !== 8) {
      check(`子页面 /operation/${cat} 渲染正常`, false, JSON.stringify(r));
    }
  }
  check('5 个工单子页面渲染正常', subRouteResults.every((s) => Number(s.split(':')[1].split('/')[0]) === 8), subRouteResults.join(' '));

  check('无页面运行时错误', errs.length === 0, errs.slice(0, 4).join(' | ') || 'none');
  fs.writeFileSync(path.join(OUT, '_handler_matrix_log.txt'), log.join('\n') + '\n', 'utf8');
  await browser.close();
})();
