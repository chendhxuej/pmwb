/**
 * 选人弹窗卡顿 · 浏览器侧双地址对照验证（V1）
 *
 * 假设：浏览器用 http://localhost:5173 打开时，因 localhost→::1 的 IPv6 解析错配
 *      （vite 仅监听 127.0.0.1:5173），每个请求先撞 ::1 超时 ~2s 再回退 IPv4，
 *      导致页面加载、HMR、/api 请求全部被拖慢；用 http://127.0.0.1:5173 直连则流畅。
 *
 * 本脚本用 puppeteer-core 启动真实 Chrome（无头），分别用两种 base 跑同一套交互：
 *   1. 页面 goto 加载耗时
 *   2. 选人弹窗初始化时 org-options / role-options / staff-options 的 /api 请求耗时（CDP 抓取）
 *   3. 打开组织下拉的交互墙钟耗时
 * 输出对比表，判定 IPv6 错配是否坐实。
 *
 * 运行：
 *   cd frontend && node tests/e2e/verify_ipv6_lag.cjs
 */
const puppeteer = require('puppeteer-core');

const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function measure(base) {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  const apiCalls = [];
  const reqStart = new Map();
  const client = await page.target().createCDPSession();
  await client.send('Network.enable');
  client.on('Network.requestWillBeSent', (p) => {
    reqStart.set(p.requestId, p.timestamp); // 秒（单调）
  });
  client.on('Network.responseReceived', (p) => {
    const start = reqStart.get(p.requestId);
    const dur = start != null ? Math.round((p.timestamp - start) * 1000) : null;
    const u = p.response.url;
    if (u.includes('/api')) {
      apiCalls.push({
        path: u.replace(/^https?:\/\/[^\/]+/, ''),
        status: p.response.status,
        ms: dur,
      });
    }
    reqStart.delete(p.requestId);
  });

  console.log(`\n===== [${base}] 开始测量 =====`);
  const tGoto = Date.now();
  await page.goto(`${base}/meeting/list`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  const gotoMs = Date.now() - tGoto;

  // 等首屏 + 让首屏 /api 请求发完
  await sleep(4000);
  const gotoApiCalls = apiCalls.slice();
  const beforeDialog = apiCalls.length;

  // 打开会议表单 → 选人弹窗
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find((x) => x.textContent.includes('新增会议'));
    if (b) b.click();
  });
  await sleep(1200);
  const hasTrigger = await page.$$eval('.staff-select', (els) => els.length);
  if (!hasTrigger) {
    console.error(`  [${base}] 未找到 .staff-select 触发器，导航可能失败`);
    await browser.close();
    return { base, gotoMs, apiCalls, dialogOpen: false };
  }
  await page.click('.staff-select');
  await sleep(1500);

  const afterDialogApiCalls = apiCalls.slice(beforeDialog);

  // 交互：点组织下拉，测量墙钟
  const tInteract = Date.now();
  await page.click('.staff-picker-filters .el-select:nth-child(1) .el-select__wrapper, .staff-picker-filters .el-select:nth-child(1) input');
  await sleep(800);
  const interactMs = Date.now() - tInteract;

  await browser.close();

  return {
    base,
    gotoMs,
    gotoApiCalls,
    dialogApiCalls: afterDialogApiCalls,
    interactMs,
    dialogOpen: true,
  };
}

function fmtCalls(calls) {
  if (!calls.length) return '    (无 /api 请求)';
  return calls
    .map((c) => `    ${c.ms != null ? String(c.ms).padStart(5) : '  ? '} ms  [${c.status}] ${c.path}`)
    .join('\n');
}

(async () => {
  const r1 = await measure('http://127.0.0.1:5173');
  const r2 = await measure('http://localhost:5173');

  console.log('\n\n########## 对比结果 ##########');
  console.log(`\n[127.0.0.1] 页面加载 ${r1.gotoMs}ms | 组织下拉交互 ${r1.interactMs}ms | 弹窗API请求数 ${r1.dialogApiCalls.length}`);
  console.log(fmtCalls(r1.dialogApiCalls));
  console.log(`\n[localhost ] 页面加载 ${r2.gotoMs}ms | 组织下拉交互 ${r2.interactMs}ms | 弹窗API请求数 ${r2.dialogApiCalls.length}`);
  console.log(fmtCalls(r2.dialogApiCalls));

  const ipv4Slow = r1.gotoMs > 2000 || r1.dialogApiCalls.some((c) => c.ms > 2000);
  const localSlow = r2.gotoMs > 2000 || r2.dialogApiCalls.some((c) => c.ms > 2000);
  console.log('\n########## 判定 ##########');
  if (localSlow && !ipv4Slow) {
    console.log('✅ 坐实 IPv6 错配：localhost 明显慢（>2s），127.0.0.1 流畅 → 转 F1 改 vite 双栈监听');
  } else if (localSlow && ipv4Slow) {
    console.log('⚠️ 两者都慢 → 转 V2：aTrust/DLP 驱动层劫持，与地址无关');
  } else if (!localSlow && !ipv4Slow) {
    console.log('ℹ️ 无头 Chrome 下两者都快 → 错配未在测试中被复现，需老大真实 Chrome 侧 NetLog 或 aTrust 排查');
  } else {
    console.log('ℹ️ 127.0.0.1 慢而 localhost 快（异常）→ 需进一步看机器 DNS/路由');
  }
})().catch((e) => {
  console.error('[FATAL]', e);
  process.exit(1);
});
