/**
 * 验证「需求与交付 - 手工新建需求工单」能力（2026-10-12）
 *
 * 背景：
 *   需求列表此前只能由 Chrome 插件抓取邮件写入 sent_emails 产生，插件没抓到的
 *   需求（漏采 / 会议口头交办）无法录入。本回归确保：
 *     1. 需求 tab 页头「新建需求」按钮真实存在、可见、可点开弹窗
 *     2. 弹窗含「需求文号」（留空自动生成）与「提出人」字段
 *     3. 提交后列表出现新需求，并带「手工」来源标签
 *     4. 首页「＋ 新增需求·工单」直连新建弹窗
 *     5. 手工需求删除后列表不再出现（源行一并真删，不会复活）
 *
 * 运行：
 *   node tests/e2e/verify_requirement_manual_create.cjs
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
const createdIds = []; // 兜底清理

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
  page.setViewport({ width: 1440, height: 900 });
  page.on('console', (msg) => {
    const t = msg.text();
    if (/Failed to resolve component|is not defined on instance|Unhandled error during execution/.test(t)) {
      errors.push(t.slice(0, 200));
    }
  });

  const results = [];
  const check = (name, pass, detail = '') => {
    results.push({ name, pass, detail });
    console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? '  | ' + detail : ''}`);
  };
  const visibleDialogTitle = () =>
    page.evaluate(() => {
      const d = [...document.querySelectorAll('.el-dialog')].find(
        (x) => x.offsetParent !== null || getComputedStyle(x).display !== 'none'
      );
      const t = d && d.querySelector('.el-dialog__title');
      return t ? t.textContent.trim() : null;
    });
  const fillFormItem = (labelText, value) =>
    page.evaluate(
      (label, val) => {
        const items = [...document.querySelectorAll('.el-dialog .el-form-item')];
        const item = items.find((i) =>
          (i.querySelector('.el-form-item__label')?.textContent || '').includes(label)
        );
        if (!item) return false;
        const input = item.querySelector('textarea, input');
        if (!input) return false;
        const proto = input.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(proto, 'value').set.call(input, val);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
      },
      labelText,
      value
    );

  const reqName = `E2E手工新建验证-${Date.now()}`;
  let manualReqId = null;

  // ── 1. 需求 tab：新建按钮存在/可见 ──
  await page.goto(`${BASE}/requirement-delivery`, { waitUntil: 'networkidle2' });
  await sleep(RENDER_WAIT);

  const btnInfo = await page.evaluate(() => {
    const btns = [...document.querySelectorAll('.pm-page-header__actions button')];
    const target = btns.find((b) => b.textContent.includes('新建需求'));
    let visible = false;
    if (target) {
      const box = target.getBoundingClientRect();
      const st = getComputedStyle(target);
      visible = box.width > 0 && box.height > 0 && st.display !== 'none' && st.visibility !== 'hidden';
    }
    return { hasBtn: !!target, visible, text: target ? target.textContent.trim() : null };
  });
  check('页头「新建需求」按钮存在', btnInfo.hasBtn, btnInfo.text || '');
  check('「新建需求」按钮可见', btnInfo.visible);

  // ── 2. 弹窗字段 ──
  if (btnInfo.hasBtn) {
    await page.evaluate(() => {
      [...document.querySelectorAll('.pm-page-header__actions button')]
        .find((b) => b.textContent.includes('新建需求'))
        .click();
    });
    await sleep(700);
  }
  const title = await visibleDialogTitle();
  check('弹窗标题=新建需求', title === '新建需求', `实际: ${title}`);

  const fields = await page.evaluate(() => {
    const d = [...document.querySelectorAll('.el-dialog')].find(
      (x) => x.offsetParent !== null || getComputedStyle(x).display !== 'none'
    );
    const labels = [...(d ? d.querySelectorAll('.el-form-item__label') : [])].map((l) =>
      l.textContent.trim()
    );
    return labels;
  });
  check('弹窗含「需求文号」字段（留空自动生成）', fields.includes('需求文号'), fields.join('/'));
  check('弹窗含「提出人」字段', fields.includes('提出人'));
  check('弹窗含「需求名称」字段', fields.includes('需求名称'));

  // ── 3. 提交创建 → 列表出现 + 手工标签 ──
  await fillFormItem('需求名称', reqName);
  await fillFormItem('提出人', '陈大海（E2E）');
  await page.evaluate(() => {
    const d = [...document.querySelectorAll('.el-dialog')].find(
      (x) => x.offsetParent !== null || getComputedStyle(x).display !== 'none'
    );
    const btns = [...d.querySelectorAll('.el-dialog__footer button')];
    btns.find((b) => b.textContent.includes('创建')).click();
  });
  await sleep(2200);

  const listInfo = await page.evaluate((name) => {
    const rows = [...document.querySelectorAll('.req-table .el-table__body tbody tr')];
    const row = rows.find((tr) => tr.textContent.includes(name));
    return {
      found: !!row,
      reqId: row ? (row.querySelector('td')?.textContent || '').replace(/手工$/, '').trim() : null,
      hasOriginTag: row ? !!row.querySelector('.origin-tag') : false,
      successMsg: !!document.querySelector('.el-message--success'),
    };
  }, reqName);
  check('创建成功后列表出现该需求', listInfo.found);
  check('该行带「手工」来源标签', listInfo.hasOriginTag);
  if (listInfo.reqId) {
    manualReqId = listInfo.reqId;
    createdIds.push(manualReqId);
  }
  console.log(`      新建需求编号: ${listInfo.reqId}`);

  // ── 4. 首页按钮直连新建 ──
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle2' });
  await sleep(RENDER_WAIT);
  const homeClicked = await page.evaluate(() => {
    const btn = [...document.querySelectorAll('button')].find((b) =>
      b.textContent.includes('新增需求')
    );
    if (!btn) return false;
    btn.click();
    return true;
  });
  await sleep(2600);
  const homeTitle = await visibleDialogTitle();
  check('首页「＋ 新增需求·工单」直连新建弹窗', homeClicked && homeTitle === '新建需求', `弹窗: ${homeTitle}`);
  const homeUrl = page.url();
  check('跳转到需求与交付页', homeUrl.includes('/requirement-delivery'), homeUrl);
  await page.keyboard.press('Escape');
  await sleep(500);

  // ── 5. 页面删除手工需求 → 不再出现 ──
  await page.goto(`${BASE}/requirement-delivery`, { waitUntil: 'networkidle2' });
  await sleep(RENDER_WAIT);
  const delClicked = await page.evaluate((name) => {
    const rows = [...document.querySelectorAll('.req-table .el-table__body tbody tr')];
    const row = rows.find((tr) => tr.textContent.includes(name));
    if (!row) return false;
    const btn = [...row.querySelectorAll('button')].find((b) => b.textContent.includes('删除'));
    if (!btn) return false;
    btn.click();
    return true;
  }, reqName);
  check('找到待删除行并点击删除', delClicked);
  await sleep(800);
  const confirmText = await page.evaluate(() => {
    const box = document.querySelector('.el-message-box');
    return box ? box.textContent : '';
  });
  check('删除确认文案区分手工需求', /手工新建/.test(confirmText), confirmText.slice(0, 60));
  await page.evaluate(() => {
    const btns = [...document.querySelectorAll('.el-message-box__btns button')];
    btns[btns.length - 1].click();
  });
  await sleep(2000);
  const gone = await page.evaluate((name) => {
    const rows = [...document.querySelectorAll('.req-table .el-table__body tbody tr')];
    return !rows.some((tr) => tr.textContent.includes(name));
  }, reqName);
  check('删除后列表不再出现该需求', gone);

  check('无 Vue 组件解析/运行时致命告警', errors.length === 0, errors.join(' ; ').slice(0, 200));

  // ── 兜底清理：无论如何不留下测试数据 ──
  for (const id of createdIds) {
    try {
      await fetch(`${API}/requirements/${encodeURIComponent(id)}`, { method: 'DELETE' });
    } catch (e) {
      /* ignore */
    }
  }

  await browser.close();
  const failed = results.filter((r) => !r.pass);
  console.log(`\n==== 结果: ${results.length - failed.length}/${results.length} 通过 ====`);
  process.exit(failed.length ? 1 : 0);
}

run().catch((e) => {
  console.error('[FATAL]', e.message);
  process.exit(3);
});
