// 任务中心「批量督办」弹窗接线验证（2026-09-19 新增）
// 仅验证交互接线：责任人卡片「督办」按钮 → 弹窗打开 → 拉取该人未完结任务 → 默认全选。
// 不发送真实邮件（遵守邮件红线）。
const puppeteer = require('puppeteer-core');
const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const API = process.env.API_URL || 'http://127.0.0.1:8000';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';

const log = [];
const check = (n, c, e) => log.push(`${c ? 'PASS' : 'FAIL'} ${n}${e ? ' | ' + e : ''}`);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
    defaultViewport: { width: 1600, height: 1100 },
  });
  const page = await browser.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push('pageerror: ' + e.message));
  page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text()); });

  await page.goto(BASE + '/task-center/overview', { waitUntil: 'networkidle2', timeout: 45000 });
  await sleep(1500);

  // 找到第一个带督办按钮的责任人（非未指派）
  const target = await page.evaluate(() => {
    const blocks = Array.from(document.querySelectorAll('.hm-block'));
    for (const b of blocks) {
      const btn = b.querySelector('.hm-supervise');
      if (btn && b.querySelector('.hm-name')) {
        return { name: b.querySelector('.hm-name').innerText.trim() };
      }
    }
    return null;
  });
  check('存在带「督办」按钮的责任人卡片', !!target, target ? target.name : '未找到');

  if (target) {
    // 接口侧该人未完结任务数
    let apiCount = -1;
    try {
      const r = await fetch(`${API}/api/v1/task-center/tasks?owners=${encodeURIComponent(target.name)}&include_done=false&page=1&page_size=500`);
      apiCount = (await r.json()).data.total;
    } catch (e) { check('接口拉取该人未完结任务', false, e.message); }

    // 点击督办按钮
    await page.evaluate(() => {
      const blocks = Array.from(document.querySelectorAll('.hm-block'));
      for (const b of blocks) {
        const btn = b.querySelector('.hm-supervise');
        if (btn) { btn.click(); return; }
      }
    });
    await sleep(1500);

    const dlg = await page.evaluate(() => {
      const el = document.querySelector('.task-batch-supervise');
      if (!el) return null;
      const rows = el.querySelectorAll('.el-table__body-wrapper tbody tr').length;
      const checked = el.querySelectorAll('.el-table__body-wrapper .el-checkbox.is-checked').length;
      const headerChecked = !!el.querySelector('.el-table__header .el-checkbox.is-checked');
      const title = (el.querySelector('.el-dialog__title')?.innerText || '').trim();
      const tip = (el.querySelector('.tbs-tip')?.innerText || '').trim();
      const countText = (el.querySelector('.tbs-count')?.innerText || '').trim();
      return { title, rows, checked, headerChecked, tip, countText };
    });
    check('督办弹窗打开', !!dlg, dlg ? dlg.title : '');
    if (dlg) {
      check('弹窗文案含责任人名', dlg.tip.includes(target.name), dlg.tip.slice(0, 40));
      check('弹窗列出该人未完结任务数=接口', dlg.rows === apiCount, `dom=${dlg.rows} api=${apiCount}`);
      const selectedOk = dlg.headerChecked && dlg.checked === dlg.rows && dlg.rows > 0;
      check('默认全选(表头勾选且行勾选数=任务数)', selectedOk, `header=${dlg.headerChecked} checked=${dlg.checked} rows=${dlg.rows} count="${dlg.countText}"`);
      // 截图备查
      await page.screenshot({ path: require('path').resolve(__dirname, '../../tmp_uishots/supervise_dialog.png') });
    }
  }

  check('全程无页面 JS 错误', errs.filter((e) => !e.includes('favicon')).length === 0, errs.slice(0, 3).join(' ; '));

  console.log(log.join('\n'));
  const fails = log.filter((l) => l.startsWith('FAIL'));
  console.log(`\n=== TOTAL ${log.length} / PASS ${log.length - fails.length} / FAIL ${fails.length} ===`);
  await browser.close();
  process.exit(fails.length ? 1 : 0);
})();
