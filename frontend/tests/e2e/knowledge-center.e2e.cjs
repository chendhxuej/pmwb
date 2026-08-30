/**
 * T10 全场景验证：知识中心真实浏览器端到端测试
 * 运行：cd frontend && node tests/e2e/knowledge-center.e2e.cjs
 *
 * 验证点：
 * 1. /knowledge-center/hub 业务全景渲染（领域树、卡片、详情区）
 * 2. 点击领域卡片后加载主笔记标准化结构 + 时间线
 * 3. /knowledge-center/domain 按领域浏览渲染 + 弹窗详情
 * 4. 控制台无 error / 无未捕获异常
 */
const puppeteer = require('puppeteer-core');

const BASE = process.env.BASE_URL || 'http://localhost:5173';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const TIMEOUT = Number(process.env.TIMEOUT) || 20000;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function run() {
  const logs = [];
  const errors = [];
  let browser;
  let passed = 0;
  let failed = 0;

  function log(kind, msg) {
    console.log(`[${kind}] ${msg}`);
    logs.push(`[${kind}] ${msg}`);
  }

  try {
    browser = await puppeteer.launch({
      executablePath: CHROME,
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    });

    const page = await browser.newPage();
    page.setDefaultTimeout(TIMEOUT);
    page.setViewport({ width: 1440, height: 900 });

    page.on('console', (msg) => {
      const text = `[console.${msg.type()}] ${msg.text()}`;
      logs.push(text);
      if (msg.type() === 'error') {
        errors.push(text);
        log('FAIL', `控制台 error: ${msg.text()}`);
      }
    });
    page.on('pageerror', (err) => {
      const text = `[pageerror] ${err.message}`;
      errors.push(text);
      log('FAIL', `未捕获异常: ${err.message}`);
    });
    page.on('requestfailed', (req) => {
      const text = `[requestfailed] ${req.method()} ${req.url()} => ${req.failure()?.errorText}`;
      logs.push(text);
      if (req.url().includes('/api/')) {
        errors.push(text);
        log('FAIL', `API 请求失败: ${req.url()} ${req.failure()?.errorText}`);
      }
    });

    // ---- 场景 1：业务全景 /knowledge-center/hub ----
    log('INFO', '打开 业务全景 /knowledge-center/hub');
    await page.goto(`${BASE}/knowledge-center/hub`, { waitUntil: 'networkidle2' });

    // 页面标题/主导航
    await page.waitForSelector('.hub-title', { timeout: TIMEOUT });
    const hubTitle = await page.$eval('.hub-title', (el) => el.textContent.trim());
    if (hubTitle.includes('总览驾驶舱')) {
      log('PASS', `业务全景标题: ${hubTitle}`);
      passed += 1;
    } else {
      log('FAIL', `业务全景标题异常: ${hubTitle}`);
      failed += 1;
    }

    // KPI 条存在
    await page.waitForSelector('.kpi-strip', { timeout: TIMEOUT });
    log('PASS', 'KPI 条已渲染');
    passed += 1;

    // 分组 tab 存在
    await page.waitForSelector('.grp-tabs', { timeout: TIMEOUT });
    log('PASS', '分组 tab 已渲染');
    passed += 1;

    // 领域卡片至少 1 个
    await page.waitForSelector('.domain-grid .domain-card', { timeout: TIMEOUT });
    const cardCount = await page.$$eval('.domain-grid .domain-card', (els) => els.length);
    if (cardCount > 0) {
      log('PASS', `领域卡片数量: ${cardCount}`);
      passed += 1;
    } else {
      log('FAIL', '领域卡片数量为 0');
      failed += 1;
    }

    // 点击第一个卡片
    await page.click('.domain-grid .domain-card');
    await page.waitForSelector('.domain-detail', { timeout: TIMEOUT });
    log('PASS', '点击领域卡片后详情区已渲染');
    passed += 1;

    // 主笔记标准化区
    await page.waitForSelector('.bible-list', { timeout: TIMEOUT });
    log('PASS', '主笔记标准化结构区已渲染');
    passed += 1;

    // 时间线区
    await page.waitForSelector('.detail-timeline', { timeout: TIMEOUT });
    log('PASS', '业务全过程时间线区已渲染');
    passed += 1;

    // ---- 场景 2：按领域浏览 /knowledge-center/domain ----
    log('INFO', '打开 按领域浏览 /knowledge-center/domain');
    await page.goto(`${BASE}/knowledge-center/domain`, { waitUntil: 'networkidle2' });

    await page.waitForSelector('.domain-knowledge h2', { timeout: TIMEOUT });
    const dkTitle = await page.$eval('.domain-knowledge h2', (el) => el.textContent.trim());
    if (dkTitle === '按业务领域浏览') {
      log('PASS', `按领域浏览标题: ${dkTitle}`);
      passed += 1;
    } else {
      log('FAIL', `按领域浏览标题异常: ${dkTitle}`);
      failed += 1;
    }

    await page.waitForSelector('.domain-knowledge .dk-card', { timeout: TIMEOUT });
    const dkCardCount = await page.$$eval('.domain-knowledge .dk-card', (els) => els.length);
    if (dkCardCount > 0) {
      log('PASS', `按领域浏览卡片数量: ${dkCardCount}`);
      passed += 1;
    } else {
      log('FAIL', '按领域浏览卡片数量为 0');
      failed += 1;
    }

    await page.click('.domain-knowledge .dk-card');
    await page.waitForSelector('.domain-knowledge .el-dialog', { timeout: TIMEOUT });
    log('PASS', '按领域浏览点击卡片后弹窗已渲染');
    passed += 1;

    // 给时间线/异步请求一点收尾时间
    await sleep(800);

    if (errors.length === 0) {
      log('PASS', '全场景验证完成，控制台与 API 均无错误');
      passed += 1;
    } else {
      log('FAIL', `全场景验证完成，但发现 ${errors.length} 个错误（见上）`);
      failed += 1;
    }
  } catch (err) {
    log('FAIL', `测试执行异常: ${err.message}\n${err.stack || ''}`);
    failed += 1;
  } finally {
    if (browser) await browser.close();
  }

  console.log('\n=== T10 全场景验证结果 ===');
  console.log(`通过: ${passed}  失败: ${failed}  错误数: ${errors.length}`);
  if (errors.length > 0) {
    console.log('\n--- 错误摘要 ---');
    errors.forEach((e) => console.log(e));
  }
  process.exit(failed > 0 ? 1 : 0);
}

run();
