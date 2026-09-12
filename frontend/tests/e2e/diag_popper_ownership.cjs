/** 探查：选人弹窗组织/身份下拉的 popper 归属 + 各阶段耗时细分 */
const puppeteer = require('puppeteer-core');
const BASE = process.env.BASE_URL || 'http://localhost:5173';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function run() {
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  await page.goto(`${BASE}/meeting/list`, { waitUntil: 'networkidle2' });
  await sleep(2000);
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find((x) => x.textContent.includes('新增会议'));
    b && b.click();
  });
  await sleep(1000);

  // 打开选人弹窗
  await page.click('.staff-select');
  await sleep(800);

  const popperInfo = await page.evaluate(() => {
    const pops = [...document.querySelectorAll('.el-select-dropdown')];
    return pops.map((p) => {
      const r = p.getBoundingClientRect();
      // 找归属：向上找 aria-controls 对应的 select 或所在 dialog
      let anc = [];
      let n = p;
      for (let i = 0; i < 6 && n; i++) { n = n.parentElement; if (n) anc.push(n.className && String(n.className).split(' ')[0]); }
      return { items: p.querySelectorAll('.el-select-dropdown__item').length, visible: r.height > 0, w: Math.round(r.width), anc: anc.filter(Boolean).slice(0, 4) };
    });
  });
  console.log('el-select-dropdown 明细:');
  popperInfo.forEach((p, i) => console.log(`  #${i} items=${p.items} visible=${p.visible} w=${p.w} 祖先=${p.anc.join(' < ')}`));

  // 打开组织下拉，细粒度计时（Performance.now 包 click 前后帧）
  const timing = await page.evaluate(async () => {
    const sel = document.querySelector('.staff-picker-filters .el-select:nth-child(1) .el-select__wrapper')
      || document.querySelector('.staff-picker-filters .el-select:nth-child(1) input');
    const t0 = performance.now();
    sel.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    const tAfter2Frames = performance.now();
    return { clickTo2Frames: Math.round(tAfter2Frames - t0) };
  });
  console.log('组织下拉打开(click→2帧):', timing);

  // input 聚焦后逐字符输入，测每键耗时（若 dropdown 有 filterable）
  const opts = await page.evaluate(() => {
    const pops = [...document.querySelectorAll('.el-select-dropdown')].filter((p) => p.getBoundingClientRect().height > 0);
    return pops.map((p) => ({ cls: p.className, hasInput: !!p.querySelector('input') }));
  });
  console.log('可见 popper:', JSON.stringify(opts));

  await browser.close();
}
run().catch((e) => { console.error('[FATAL]', e); process.exit(1); });
