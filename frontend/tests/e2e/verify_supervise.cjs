// 任务中心「批量督办」弹窗接线验证（2026-09-19 新增）
// 验证：责任人卡片「督办」按钮 → 弹窗打开 → 拉取该人未完结任务 → 默认全选 →
//       点击「撰写催办邮件」→ MailComposeDialog 打开且左侧 Markdown 草稿已填充、右侧预览已渲染。
// 不点击「发送」，避免真实发信（邮件红线）；正文非空即保证不会再报“请输入邮件正文”。
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

      // 点击「撰写催办邮件」→ 进入 MailComposeDialog（会拉取草稿 + 预览，不发送）
      await page.evaluate(() => {
        const btns = Array.from(document.querySelectorAll('.task-batch-supervise .el-dialog__footer .el-button'));
        const b = btns.find((x) => x.innerText.includes('撰写催办邮件'));
        if (b) b.click();
      });
      await sleep(2500); // 等草稿拉取 + 预览渲染

      const compose = await page.evaluate(() => {
        const cd = document.querySelector('.mail-compose-dialog');
        if (!cd) return null;
        // 左侧正文编辑区（Markdown textarea）
        const ta = cd.querySelector('.compose-body textarea, .compose-edit .el-textarea__inner');
        const bodyVal = ta ? ta.value || '' : '';
        // 左侧主题输入框（.compose-row 中 label=主题 的那个 el-input）
        const subjRow = Array.from(cd.querySelectorAll('.compose-row')).find(
          (r) => (r.querySelector('.compose-label')?.innerText || '').trim() === '主题'
        );
        const subjInput = subjRow ? subjRow.querySelector('input.el-input__inner') : null;
        const subjectVal = subjInput ? subjInput.value || '' : '';
        // 右侧预览 iframe
        const frame = cd.querySelector('.compose-preview-frame');
        const previewHasContent = !!(frame && frame.getAttribute('srcdoc') && frame.getAttribute('srcdoc').length > 50);
        const previewSubject = (cd.querySelector('.compose-preview-subject')?.innerText || '').trim();
        const title = (cd.querySelector('.el-dialog__title')?.innerText || '').trim();
        return {
          title, bodyLen: bodyVal.length, bodyHead: bodyVal.slice(0, 40),
          previewHasContent, subjectVal, previewSubject,
        };
      });
      check('撰写弹窗(MailComposeDialog)打开', !!compose, compose ? compose.title : '');
      if (compose) {
        check('左侧 Markdown 编辑框已填充草稿(非空)', compose.bodyLen > 0, `len=${compose.bodyLen} head="${compose.bodyHead}"`);
        check('右侧预览 iframe 已渲染', compose.previewHasContent, `preview=${compose.previewHasContent}`);
        // 2026-09-20：主题预填 + 左右一致性（修复主题输入框空白/与预览不一致）
        check('左侧主题输入框已预填(非空)', compose.subjectVal.length > 0, `subject="${compose.subjectVal.slice(0, 40)}"`);
        check('左侧主题与右侧预览主题一致', compose.subjectVal.length > 0 && compose.subjectVal === compose.previewSubject, `left="${compose.subjectVal.slice(0, 40)}" right="${compose.previewSubject.slice(0, 40)}"`);
        await page.screenshot({ path: require('path').resolve(__dirname, '../../tmp_uishots/supervise_compose.png') });
      }
      // 注意：不点击「发送」，避免真实发信（邮件红线）；正文非空即意味着不会再报“请输入邮件正文”
    }
  }

  check('全程无页面 JS 错误', errs.filter((e) => !e.includes('favicon')).length === 0, errs.slice(0, 3).join(' ; '));

  console.log(log.join('\n'));
  const fails = log.filter((l) => l.startsWith('FAIL'));
  console.log(`\n=== TOTAL ${log.length} / PASS ${log.length - fails.length} / FAIL ${fails.length} ===`);
  await browser.close();
  process.exit(fails.length ? 1 : 0);
})();
