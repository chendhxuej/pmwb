/**
 * 全路由渲染冒烟 —— 防「编译通过但页面白屏」
 *
 * 背景（2026-09-11 事故）：
 *   HomeView.vue 模板引用了未定义的 researchStats，vite build 编译通过，
 *   但运行时 Vue 渲染抛错导致整个组件树卸载 → 首页白屏。
 *   这类问题 build / lint 都抓不到，只有真实 DOM 断言能抓到。
 *
 * 断言：
 *   1. #app 内渲染内容非空（白屏直接判定失败）
 *   2. 无 Vue「未定义引用 / 渲染未处理错误」类告警
 *
 * 运行：
 *   cd frontend && node tests/e2e/route-smoke.e2e.cjs
 *
 * 环境变量：
 *   BASE_URL     默认 http://localhost:5173
 *   CHROME_PATH  默认 C:/Program Files/Google/Chrome/Application/chrome.exe
 *   TIMEOUT      默认 20000 (ms)
 *   RENDER_WAIT  默认 2500 (ms)，每个路由渲染后的等待时间
 */
const puppeteer = require('puppeteer-core');

const BASE = process.env.BASE_URL || 'http://localhost:5173';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const TIMEOUT = Number(process.env.TIMEOUT) || 20000;
const RENDER_WAIT = Number(process.env.RENDER_WAIT) || 2500;

/** 一级可直达路由（跳过 :code 等带参路由） */
const ROUTES = [
  '/dashboard',
  '/task-center',
  '/requirement-delivery',
  '/operation/overview',
  '/research',
  '/meeting/list',
  '/todo',
  '/key-works',
  '/ai-center/qa',
  '/basic-data',
  '/business-domains',
  '/knowledge-center/hub',
  '/material-library',
  '/reminder-center',
  '/mail-center/logs',
  '/work-report',
  '/llm-provider',
];

/** Vue 运行时崩溃特征：编译能过，运行才炸 */
const FATAL_PATTERNS = [
  /is not defined on instance/,
  /Unhandled error during execution of/,
  /Cannot read properties of (null|undefined)/,
  /is not a function/,
];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function run() {
  const results = [];
  let browser;

  try {
    browser = await puppeteer.launch({
      executablePath: CHROME,
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    });
  } catch (err) {
    console.error(`[FATAL] 浏览器启动失败: ${err.message}`);
    console.error(`[HINT] 检查 CHROME_PATH，当前值: ${CHROME}`);
    process.exit(2);
  }

  const page = await browser.newPage();
  page.setDefaultTimeout(TIMEOUT);
  page.setViewport({ width: 1440, height: 900 });

  /** 当前路由收集到的致命日志 */
  let fatal = [];

  const collect = (text) => {
    if (FATAL_PATTERNS.some((re) => re.test(text))) fatal.push(text);
  };

  page.on('console', (msg) => {
    const text = msg.text();
    if (msg.type() === 'error' || msg.type() === 'warning') collect(text);
  });
  page.on('pageerror', (err) => collect(err.message));

  for (const route of ROUTES) {
    fatal = [];
    let appLen = -1;
    let bodyLen = -1;
    let navError = '';

    try {
      await page.goto(`${BASE}${route}`, { waitUntil: 'domcontentloaded', timeout: TIMEOUT });
      await sleep(RENDER_WAIT);
      const m = await page.evaluate(() => {
        const app = document.getElementById('app');
        return {
          appLen: app ? (app.innerHTML || '').length : -1,
          bodyLen: (document.body.innerText || '').length,
        };
      });
      appLen = m.appLen;
      bodyLen = m.bodyLen;
    } catch (err) {
      navError = err.message;
    }

    const problems = [];
    if (navError) problems.push(`导航失败: ${navError}`);
    if (appLen <= 0) problems.push(`白屏（#app 渲染长度 ${appLen}）`);
    else if (bodyLen <= 0) problems.push(`无可见文本（body innerText 长度 ${bodyLen}）`);
    if (fatal.length) problems.push(...fatal.slice(0, 3).map((f) => `运行时错误: ${f.slice(0, 200)}`));

    const ok = problems.length === 0;
    results.push({ route, ok, appLen, problems });
    console.log(`${ok ? 'PASS' : 'FAIL'}  ${route}  (app=${appLen}, text=${bodyLen})`);
    if (!ok) problems.forEach((p) => console.log(`        ↳ ${p}`));
  }

  await browser.close();

  const passed = results.filter((r) => r.ok).length;
  const failed = results.length - passed;

  console.log('');
  console.log(`===== 全路由渲染冒烟: ${passed} passed / ${failed} failed （共 ${results.length}） =====`);
  if (failed > 0) {
    console.log('失败路由:');
    results.filter((r) => !r.ok).forEach((r) => console.log(`  - ${r.route}`));
    process.exit(1);
  }
  console.log('全部路由渲染正常，无白屏。');
  process.exit(0);
}

run().catch((err) => {
  console.error(`[FATAL] ${err && err.stack ? err.stack : err}`);
  process.exit(2);
});
