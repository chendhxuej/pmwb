/**
 * 截取「敏感需求跟踪」关键页面截图（可演示、可还原）
 * 用法：node tests/e2e/shot_sensitive_req.cjs
 *
 * 演示流程：生成模板倒排建议 → 截图 → 保存(为泳道出效果) → 截图 → **还原为空**（不留演示数据）
 */
const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173';
const API = process.env.API_BASE || 'http://127.0.0.1:8000/api/v1';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const OUT_DIR = path.resolve(__dirname, '../../shots-sensitive');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const shot = async (page, name) => {
  await page.screenshot({ path: path.join(OUT_DIR, name) });
  console.log('shot ->', name);
};

async function run() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1680, height: 1050, deviceScaleFactor: 1.5 });
  page.on('pageerror', (e) => console.log('[JS ERROR]', e.message));

  await page.evaluate(async (API) => {
    await fetch(`${API}/sensitive-reqs/sync`, { method: 'POST' });
  }, API);

  // ① 列表页（统计条 + 跟踪列表）
  await page.goto(`${BASE}/requirement-delivery`, { waitUntil: 'networkidle2', timeout: 25000 });
  await sleep(2500);
  await page.evaluate(() => {
    const t = [...document.querySelectorAll('.el-tabs__item')].find((x) => x.textContent.includes('敏感需求跟踪'));
    if (t) t.click();
  });
  await sleep(3000);
  await shot(page, '1-敏感需求跟踪-列表页.png');

  // ② 打开首行详情
  const firstReqId = await page.evaluate(() => {
    const p = document.querySelector('.srp');
    const el = p && p.querySelector('.el-table__body .srp-req-id');
    return el ? el.textContent.trim() : null;
  });
  console.log('firstReqId =', firstReqId);
  await page.evaluate(() => {
    const p = document.querySelector('.srp');
    const b = [...p.querySelectorAll('.el-table__body .el-button')].find((x) => x.textContent.includes('详情'));
    if (b) b.click();
  });
  await sleep(3000);
  await shot(page, '2-详情抽屉-关键信息条.png');

  // ③ 生成倒排建议 → 编辑弹窗（模板 5 阶段 × 团队，未保存）
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('.el-drawer .el-button')]
      .find((x) => /生成倒排建议|调整倒排/.test(x.textContent));
    if (b) b.click();
  });
  await sleep(3000);
  await shot(page, '3-倒排编辑-模板建议.png');

  // ④ 保存 → 泳道出效果
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('.el-dialog__footer .el-button')]
      .find((x) => x.textContent.includes('保存倒排'));
    if (b) b.click();
  });
  await sleep(4000);
  await shot(page, '4-详情抽屉-团队泳道倒排.png');

  // ⑤ 还原：全量覆盖为空（不留演示数据）
  const restored = await page.evaluate(async (API, reqId) => {
    const r = await fetch(`${API}/sensitive-reqs/${encodeURIComponent(reqId)}/milestones`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: [] }),
    }).then((x) => x.json());
    return r && r.code;
  }, API, firstReqId);
  console.log('restore milestones -> code', restored);

  await page.keyboard.press('Escape');
  await sleep(1200);

  // ⑥ 督办邮件草稿弹窗（dry_run 预览，不发信）
  await page.evaluate(() => {
    const p = document.querySelector('.srp');
    const b = [...p.querySelectorAll('.el-table__body .el-button')].find((x) => x.textContent.includes('督办'));
    if (b) b.click();
  });
  await sleep(4000);
  await shot(page, '5-督办邮件草稿预览.png');
  await page.keyboard.press('Escape');
  await sleep(600);
  // 兜底关掉可能残留的确认框
  await page.evaluate(() => {
    const btns = [...document.querySelectorAll('.el-dialog__footer .el-button, .el-message-box__btns .el-button')];
    const cancel = btns.find((b) => /取消|关闭/.test(b.textContent));
    if (cancel) cancel.click();
  });
  await sleep(800);

  // ⑦ 任务总览（第 8 来源磁贴）—— 路由是 /task-center（/task-overview 不存在）
  await page.goto(`${BASE}/task-center`, { waitUntil: 'networkidle2', timeout: 30000 });
  await sleep(3500);
  await shot(page, '6-任务总览-第8来源磁贴.png');

  await browser.close();
  console.log('DONE ->', OUT_DIR);
}

run().catch((e) => { console.error('[FATAL]', e.message); process.exit(1); });
