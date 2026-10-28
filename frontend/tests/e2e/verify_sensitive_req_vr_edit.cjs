/**
 * 验证「敏感面板内便捷设置版本要求上线时间」（2026-10-28）
 *
 * 覆盖（真实 DOM 断言，只读真实库、不保存任何修改）：
 *   1. 敏感需求跟踪面板：打开一条跟踪工单详情抽屉
 *   2. 上线要求未填时：meta 区出现「去设置」按钮 + 警告条含「立即设置」入口，
 *      且「生成倒排建议」按钮保持禁用（原有守门不回退）
 *   3. 上线要求已填时：出现「修改」按钮（无警告条）
 *   4. 点击设置入口 → 弹出「设置版本要求上线时间」弹窗（日期控件 + 取消/保存按钮）
 *   5. 点「取消」关闭弹窗，不落库（版本要求上线时间是倒排终点权威源，
 *      真实保存会连带重排里程碑/督办口径，e2e 不动真实数据）
 *
 * 运行：node tests/e2e/verify_sensitive_req_vr_edit.cjs
 * 前置：前端 5173 + 后端 8000 已启动，敏感池内至少有 1 条跟踪工单。
 */
const puppeteer = require('puppeteer-core');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const TIMEOUT = Number(process.env.TIMEOUT) || 20000;
const RENDER_WAIT = Number(process.env.RENDER_WAIT) || 2500;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let pass = 0;
let fail = 0;

function check(name, ok, extra = '') {
  if (ok) { pass++; console.log(`  [OK]   ${name}${extra ? ' -> ' + extra : ''}`); }
  else { fail++; console.log(`  [FAIL] ${name}${extra ? ' -> ' + extra : ''}`); }
}

async function run() {
  let browser;
  try {
    browser = await puppeteer.launch({
      executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    });
  } catch (err) {
    console.error(`[FATAL] 浏览器启动失败: ${err.message}`);
    process.exit(2);
  }

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1600, height: 1000 });
    const pageErrors = [];
    page.on('pageerror', (e) => pageErrors.push(e.message));

    await page.goto(`${BASE}/requirement-delivery`, { waitUntil: 'networkidle2', timeout: TIMEOUT });
    await sleep(RENDER_WAIT);

    // ── 切到敏感需求跟踪 tab ──
    await page.evaluate(() => {
      const tabs = [...document.querySelectorAll('.el-tabs__item')];
      const target = tabs.find((t) => t.textContent.includes('敏感需求跟踪'));
      if (target) target.click();
    });
    await sleep(RENDER_WAIT + 500);

    // ── 打开首行详情抽屉 ──
    await page.evaluate(() => {
      const btn = [...document.querySelectorAll('.el-table__row button')]
        .find((b) => b.textContent.trim() === '详情');
      if (btn) btn.click();
    });
    await sleep(RENDER_WAIT + 300);

    const drawer = await page.evaluate(() => {
      const meta = document.querySelector('.srp-meta');
      if (!meta) return null;
      const text = meta.textContent;
      const vrBtn = [...meta.querySelectorAll('button')]
        .find((b) => b.textContent.includes('去设置') || b.textContent.includes('修改'));
      const genBtn = [...meta.querySelectorAll('button')]
        .find((b) => b.textContent.includes('生成倒排建议') || b.textContent.includes('调整倒排'));
      const notice = document.querySelector('.srp-notice-warn');
      return {
        hasVrBtn: !!vrBtn,
        vrBtnText: vrBtn ? vrBtn.textContent.trim() : '',
        genBtnDisabled: genBtn ? genBtn.disabled : null,
        hasNotice: !!notice,
        noticeHasEntry: notice ? notice.textContent.includes('立即设置') : false,
      };
    });
    check('详情抽屉打开且 meta 区可见', !!drawer);
    if (!drawer) throw new Error('详情抽屉未打开');
    check('上线要求旁有设置入口（去设置/修改）', drawer.hasVrBtn, drawer.vrBtnText);

    if (drawer.vrBtnText.includes('去设置')) {
      check('未填时警告条出现', drawer.hasNotice);
      check('警告条含「立即设置」便捷入口', drawer.noticeHasEntry);
      check('未填时「生成倒排建议」保持禁用', drawer.genBtnDisabled === true, `disabled=${drawer.genBtnDisabled}`);
    } else {
      check('已填时无警告条', !drawer.hasNotice);
      check('已填时「生成倒排建议」可用', drawer.genBtnDisabled === false, `disabled=${drawer.genBtnDisabled}`);
    }

    // ── 点设置入口 → 弹窗出现（不保存）──
    await page.evaluate(() => {
      const btn = [...document.querySelectorAll('.srp-meta button')]
        .find((b) => b.textContent.includes('去设置') || b.textContent.includes('修改'));
      if (btn) btn.click();
    });
    await sleep(800);

    const dlg = await page.evaluate(() => {
      const dialogs = [...document.querySelectorAll('.el-dialog')];
      const d = dialogs.find((x) => x.textContent.includes('设置版本要求上线时间'));
      if (!d) return null;
      const visible = getComputedStyle(d).display !== 'none';
      return {
        visible,
        hasDatePicker: !!d.querySelector('.el-date-editor'),
        hasCancel: [...d.querySelectorAll('button')].some((b) => b.textContent.trim() === '取消'),
        hasSave: [...d.querySelectorAll('button')].some((b) => b.textContent.trim() === '保存'),
      };
    });
    check('设置弹窗弹出', !!dlg && dlg.visible);
    check('弹窗含日期控件', !!dlg && dlg.hasDatePicker);
    check('弹窗含取消/保存按钮', !!dlg && dlg.hasCancel && dlg.hasSave);

    // ── 取消关闭（不落库）──
    if (dlg && dlg.visible) {
      await page.evaluate(() => {
        const dialogs = [...document.querySelectorAll('.el-dialog')];
        const d = dialogs.find((x) => x.textContent.includes('设置版本要求上线时间'));
        const cancel = [...d.querySelectorAll('button')].find((b) => b.textContent.trim() === '取消');
        if (cancel) cancel.click();
      });
      await sleep(600);
      const closed = await page.evaluate(() => {
        const dialogs = [...document.querySelectorAll('.el-dialog')];
        const d = dialogs.find((x) => x.textContent.includes('设置版本要求上线时间'));
        // el-dialog 关闭时隐藏的是祖先 .el-overlay，dialog 自身 computed display 不变
        const overlay = d ? d.closest('.el-overlay') : null;
        return !d || !overlay || getComputedStyle(overlay).display === 'none';
      });
      check('取消后弹窗关闭（未落库）', closed);
    }

    check('无页面 JS 错误', pageErrors.length === 0, pageErrors.slice(0, 2).join(' | '));

    console.log(`\n结果：${pass} passed, ${fail} failed`);
  } finally {
    await browser.close();
  }
  process.exit(fail > 0 ? 1 : 0);
}

run();
