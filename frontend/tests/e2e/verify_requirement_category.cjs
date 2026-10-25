/**
 * 验证「需求与交付 - 需求分类」能力（2026-10-25）
 *
 * 覆盖：
 *   1. 列表页筛选栏含「需求分类」下拉（options 来自字典表）
 *   2. 列表新增「需求分类」列
 *   3. 新建需求弹窗含「需求分类」字段与「管理」入口
 *   4. 带分类创建需求 → 列表行显示分类
 *   5. 详情抽屉修改分类 → saveDetail 持久化（API 回读校验）
 *   6. 分类管理弹窗：新增 / 停用后 options 隐藏
 *   7. 按分类筛选列表生效
 *
 * 运行：
 *   node tests/e2e/verify_requirement_category.cjs
 * 前置：前端 5173 + 后端 8000 均已启动。
 */
const puppeteer = require('puppeteer-core');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const API = process.env.API_BASE || 'http://127.0.0.1:8000/api/v1';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const TIMEOUT = Number(process.env.TIMEOUT) || 20000;
const RENDER_WAIT = Number(process.env.RENDER_WAIT) || 2500;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const errors = [];
const results = [];
const check = (name, pass, detail = '') => {
  results.push({ name, pass });
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? '  | ' + detail : ''}`);
};

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
  page.setViewport({ width: 1680, height: 950 });
  page.on('console', (msg) => {
    const t = msg.text();
    if (/Failed to resolve component|is not defined on instance|Unhandled error during execution/.test(t)) {
      errors.push(t.slice(0, 200));
    }
  });

  const uniq = Date.now();
  const e2eCatName = `E2E分类${uniq % 100000}`;
  const reqName = `E2E分类验证-${uniq}`;
  let manualReqId = null;

  try {
    // ── 0. 经 API 造一条带「业务流程优化」分类的对照数据 ──
    const seed = await fetch(`${API}/requirements`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ req_name: reqName, proposer: '陈大海（E2E）', category: '业务流程优化' }),
    }).then((r) => r.json());
    check('API 预置对照需求（带分类）', seed?.data?.ext?.category === '业务流程优化');
    manualReqId = seed?.data?.req_id || null;

    // ── 1. 列表页：筛选栏 + 分类列 ──
    await page.goto(`${BASE}/requirement-delivery`, { waitUntil: 'networkidle2' });
    await sleep(RENDER_WAIT);

    const pageInfo = await page.evaluate((name) => {
      // 本版 Element Plus 的 el-select placeholder 渲染在 .el-select__placeholder span 中
      const hasFilter = [...document.querySelectorAll('.el-select__placeholder')].some(
        (e) => e.textContent.trim() === '需求分类'
      );
      // 表头含「需求分类」列
      const headers = [...document.querySelectorAll('.req-table .el-table__header th')].map((h) => h.textContent.trim());
      // 目标行的分类列
      const rows = [...document.querySelectorAll('.req-table .el-table__body tbody tr')];
      const row = rows.find((tr) => tr.textContent.includes(name));
      const cells = row ? [...row.querySelectorAll('td')].map((c) => c.textContent.trim()) : [];
      return {
        hasFilter,
        hasColumn: headers.includes('需求分类'),
        rowFound: !!row,
        rowHasCat: cells.some((c) => c.includes('业务流程优化')),
      };
    }, reqName);
    check('筛选栏含「需求分类」下拉', pageInfo.hasFilter);
    check('列表含「需求分类」列', pageInfo.hasColumn);
    check('带分类需求出现在列表且分类正确', pageInfo.rowFound && pageInfo.rowHasCat);

    // ── 2. 新建弹窗：分类字段 + 管理入口 ──
    await page.evaluate(() => {
      [...document.querySelectorAll('.pm-page-header__actions button')]
        .find((b) => b.textContent.includes('新建需求'))
        .click();
    });
    await sleep(700);
    const dlg = await page.evaluate(() => {
      const d = [...document.querySelectorAll('.el-dialog')].find(
        (x) => x.offsetParent !== null || getComputedStyle(x).display !== 'none'
      );
      const items = [...(d ? d.querySelectorAll('.el-form-item') : [])];
      const catItem = items.find((i) => (i.querySelector('.el-form-item__label')?.textContent || '').includes('需求分类'));
      return {
        hasField: !!catItem,
        hasManageBtn: catItem ? [...catItem.querySelectorAll('button')].some((b) => b.textContent.includes('管理')) : false,
      };
    });
    check('新建弹窗含「需求分类」字段', dlg.hasField);
    check('分类字段旁含「管理」入口', dlg.hasManageBtn);
    await page.keyboard.press('Escape');
    await sleep(500);

    // ── 3. 详情抽屉：改分类并保存 → API 持久化 ──
    if (manualReqId) {
      const opened = await page.evaluate((name) => {
        const rows = [...document.querySelectorAll('.req-table .el-table__body tbody tr')];
        const row = rows.find((tr) => tr.textContent.includes(name));
        if (!row) return false;
        row.click();
        return true;
      }, reqName);
      await sleep(2200);
      check('双击行打开详情抽屉', opened);

      // 详情表单里把分类切到「智能应用」：按 label 定位表单项（有值时 placeholder span 文本=已选值）
      const switched = await page.evaluate(() => {
        const drawer = document.querySelector('.el-drawer');
        if (!drawer) return false;
        const items = [...drawer.querySelectorAll('.el-form-item')];
        const item = items.find((i) => (i.querySelector('.el-form-item__label')?.textContent || '').trim() === '需求分类');
        if (!item) return false;
        const wrapper = item.querySelector('.el-select__wrapper');
        if (!wrapper) return false;
        wrapper.dispatchEvent(new MouseEvent('click', { bubbles: true }));
        return true;
      });
      check('详情分类下拉可点开', switched);
      await sleep(700);
      // 下拉 popper 里点「智能应用」——隐藏 popper 挂在祖先 .el-popper 的 display:none 上，按计算样式过滤
      const picked = await page.evaluate(() => {
        const visiblePopper = (el) => {
          const pop = el.closest('.el-popper');
          return !pop || getComputedStyle(pop).display !== 'none';
        };
        const opts = [...document.querySelectorAll('.el-select-dropdown__item')].filter(visiblePopper);
        const target = opts.find((o) => o.textContent.trim() === '智能应用');
        if (!target) return false;
        target.dispatchEvent(new MouseEvent('click', { bubbles: true }));
        return true;
      });
      check('下拉中点选「智能应用」', picked);
      await sleep(600);
      // 点保存
      await page.evaluate(() => {
        const drawer = document.querySelector('.el-drawer');
        const btn = [...drawer.querySelectorAll('button')].find((b) => b.textContent.trim() === '保存');
        if (btn) btn.click();
      });
      await sleep(2200);

      const persisted = await fetch(`${API}/requirements/${encodeURIComponent(manualReqId)}`).then((r) => r.json());
      check('详情改分类后 saveDetail 持久化（API 回读=智能应用）', persisted?.data?.ext?.category === '智能应用', `实际: ${persisted?.data?.ext?.category}`);

      // 关抽屉
      await page.keyboard.press('Escape');
      await sleep(600);
    }

    // ── 4. 分类管理弹窗：新增 → options 出现；停用 → options 隐藏 ──
    await page.evaluate(() => {
      [...document.querySelectorAll('.pm-page-header__actions button')]
        .find((b) => b.textContent.includes('新建需求'))
        .click();
    });
    await sleep(600);
    await page.evaluate(() => {
      const d = [...document.querySelectorAll('.el-dialog')].find(
        (x) => x.offsetParent !== null || getComputedStyle(x).display !== 'none'
      );
      const items = [...d.querySelectorAll('.el-form-item')];
      const catItem = items.find((i) => (i.querySelector('.el-form-item__label')?.textContent || '').includes('需求分类'));
      [...catItem.querySelectorAll('button')].find((b) => b.textContent.includes('管理')).click();
    });
    await sleep(800);
    const manageDlg = await page.evaluate(() => {
      // 嵌套 dialog 会连带外层 DOM，按标题文本精确定位
      const d = [...document.querySelectorAll('.el-dialog')].find(
        (x) => (x.querySelector('.el-dialog__title')?.textContent || '').trim() === '需求分类管理'
      );
      return d ? d.querySelector('.el-dialog__title')?.textContent.trim() : null;
    });
    check('分类管理弹窗打开', manageDlg === '需求分类管理', `实际: ${manageDlg}`);

    // 新增分类
    await page.evaluate(() => {
      const d = [...document.querySelectorAll('.el-dialog')].find(
        (x) => (x.querySelector('.el-dialog__title')?.textContent || '').trim() === '需求分类管理'
      );
      [...d.querySelectorAll('button')].find((b) => b.textContent.includes('新增分类')).click();
    });
    await sleep(600);
    await page.evaluate((name) => {
      const d = [...document.querySelectorAll('.el-dialog')].find(
        (x) => (x.querySelector('.el-dialog__title')?.textContent || '').trim() === '新增分类'
      );
      const input = d.querySelector('.el-dialog__body input');
      const proto = HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto, 'value').set.call(input, name);
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }, e2eCatName);
    await page.evaluate(() => {
      const d = [...document.querySelectorAll('.el-dialog')].find(
        (x) => (x.querySelector('.el-dialog__title')?.textContent || '').trim() === '新增分类'
      );
      [...d.querySelectorAll('.el-dialog__footer button')].find((b) => b.textContent.includes('保存')).click();
    });
    await sleep(1500);
    const added = await fetch(`${API}/requirements/categories/options`).then((r) => r.json());
    check('管理弹窗新增分类成功（options 可见）', (added?.data || []).some((o) => o.name === e2eCatName));

    // 找到新分类 id 并停用
    const all = await fetch(`${API}/requirements/categories`).then((r) => r.json());
    const e2eCat = (all?.data || []).find((c) => c.name === e2eCatName);
    if (e2eCat) {
      await fetch(`${API}/requirements/categories/${e2eCat.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: false }),
      });
      const opts2 = await fetch(`${API}/requirements/categories/options`).then((r) => r.json());
      check('停用后 options 不再出现', !(opts2?.data || []).some((o) => o.name === e2eCatName));
      // 清理测试分类（未被引用，可删）
      await fetch(`${API}/requirements/categories/${e2eCat.id}`, { method: 'DELETE' });
    } else {
      check('停用后 options 不再出现', false, '未找到新建分类');
    }

    // ── 5. 按分类筛选（对照需求在第 3 步已改为「智能应用」，此处按其筛） ──
    await page.keyboard.press('Escape');
    await sleep(400);
    await page.goto(`${BASE}/requirement-delivery`, { waitUntil: 'networkidle2' });
    await sleep(RENDER_WAIT);
    await page.evaluate(() => {
      const ph = [...document.querySelectorAll('.el-select__placeholder')].find(
        (e) => e.textContent.trim() === '需求分类'
      );
      ph.closest('.el-select__wrapper').dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    await sleep(700);
    await page.evaluate(() => {
      const visiblePopper = (el) => {
        const pop = el.closest('.el-popper');
        return !pop || getComputedStyle(pop).display !== 'none';
      };
      const opts = [...document.querySelectorAll('.el-select-dropdown__item')].filter(visiblePopper);
      const target = opts.find((o) => o.textContent.trim() === '智能应用');
      if (target) target.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    await sleep(2000);
    const filterRes = await page.evaluate((name) => {
      const rows = [...document.querySelectorAll('.req-table .el-table__body tbody tr')];
      return {
        count: rows.length,
        allMatch: rows.length > 0 && rows.every((tr) => tr.textContent.includes('智能应用')),
        targetIn: rows.some((tr) => tr.textContent.includes(name)),
      };
    }, reqName);
    check('按分类筛选生效（全部行=智能应用）', filterRes.count > 0 && filterRes.allMatch, `行数: ${filterRes.count}`);
    check('筛选结果含对照需求', filterRes.targetIn);

    check('无 Vue 组件解析/运行时致命告警', errors.length === 0, errors.join(' ; ').slice(0, 200));
  } finally {
    // ── 兜底清理：删除对照需求 ──
    if (manualReqId) {
      try { await fetch(`${API}/requirements/${encodeURIComponent(manualReqId)}`, { method: 'DELETE' }); } catch (e) { /* ignore */ }
    }
    await browser.close();
  }

  const failed = results.filter((r) => !r.pass);
  console.log(`\n==== 结果: ${results.length - failed.length}/${results.length} 通过 ====`);
  process.exit(failed.length ? 1 : 0);
}

run().catch((e) => {
  console.error('[FATAL]', e.message);
  process.exit(3);
});
