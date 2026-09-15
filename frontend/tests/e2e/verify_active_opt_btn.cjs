/**
 * 验证「需求与交付 - 主动优化」创建工单入口恢复
 *
 * 背景（2026-09-15）：
 *   RequirementDeliveryView.vue 漏 import PageHeader → Vue 运行时降级为
 *   原生空元素 → 页头「新增主动优化」按钮整个消失。
 *   修复后必须真实 DOM 断言：按钮存在、可见、可点击弹出表单。
 *
 * 运行：
 *   node tests/e2e/verify_active_opt_btn.cjs
 */
const puppeteer = require('puppeteer-core');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const TIMEOUT = Number(process.env.TIMEOUT) || 20000;
const RENDER_WAIT = Number(process.env.RENDER_WAIT) || 2500;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const errors = [];

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

  // ── 1. 需求与交付页：PageHeader + 新增主动优化按钮 ──
  await page.goto(`${BASE}/requirement-delivery`, { waitUntil: 'networkidle2' });
  await sleep(RENDER_WAIT);

  const headerInfo = await page.evaluate(() => {
    const h = document.querySelector('.pm-page-header');
    const title = document.querySelector('.pm-page-header__title');
    const btns = [...document.querySelectorAll('.pm-page-header__actions button')];
    const target = btns.find((b) => b.textContent.includes('新增主动优化'));
    let visible = false;
    if (target) {
      const box = target.getBoundingClientRect();
      const style = getComputedStyle(target);
      visible = box.width > 0 && box.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
    }
    return {
      hasHeader: !!h,
      title: title ? title.textContent.trim() : null,
      hasBtn: !!target,
      btnVisible: visible,
      btnText: target ? target.textContent.trim() : null,
    };
  });
  check('页头区域渲染(pm-page-header)', headerInfo.hasHeader);
  check('页头标题=需求与交付', headerInfo.title === '需求与交付', `实际: ${headerInfo.title}`);
  check('「新增主动优化」按钮存在', headerInfo.hasBtn);
  check('「新增主动优化」按钮可见', headerInfo.btnVisible);

  // ── 2. 点击按钮 → 弹窗出现（可用性）──
  let dialogOk = false;
  if (headerInfo.hasBtn) {
    await page.evaluate(() => {
      const btns = [...document.querySelectorAll('.pm-page-header__actions button')];
      btns.find((b) => b.textContent.includes('新增主动优化')).click();
    });
    await sleep(800);
    dialogOk = await page.evaluate(() => {
      const dialogs = [...document.querySelectorAll('.el-dialog')];
      const d = dialogs.find((x) => x.offsetParent !== null || getComputedStyle(x).display !== 'none');
      return !!d && d.textContent.includes('工单标题');
    });
  }
  check('点击后弹窗出现(含工单标题表单)', dialogOk);
  await page.keyboard.press('Escape');
  await sleep(400);

  // ── 3. 主动优化 tab 基本渲染（顺带回归）──
  const tabOk = await page.evaluate(() => {
    const tabs = [...document.querySelectorAll('.el-tabs__item')];
    return tabs.some((t) => t.textContent.includes('主动优化'));
  });
  check('「主动优化」标签存在', tabOk);

  // ── 4. 邮件记录页回归（同病同修）──
  await page.goto(`${BASE}/mail-center/logs`, { waitUntil: 'networkidle2' });
  await sleep(RENDER_WAIT);
  const mailHeader = await page.evaluate(() => {
    const title = document.querySelector('.pm-page-header__title');
    return title ? title.textContent.trim() : null;
  });
  check('邮件记录页头标题渲染', mailHeader === '邮件记录', `实际: ${mailHeader}`);

  check('无 Vue 组件解析/运行时致命告警', errors.length === 0, errors.join(' ; ').slice(0, 200));

  await browser.close();

  const failed = results.filter((r) => !r.pass);
  console.log(`\n==== 结果: ${results.length - failed.length}/${results.length} 通过 ====`);
  process.exit(failed.length ? 1 : 0);
}

run().catch((e) => {
  console.error('[FATAL]', e.message);
  process.exit(3);
});
