// 验证周报 HTML 单文件自包含：下载→本地打开→canvas≥2 且 echarts 就绪
// 用法: node verify_report_inline.js <html路径>
const puppeteer = require('D:/项目/个人工作台系统/frontend/node_modules/puppeteer-core');
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const [, , htmlPath] = process.argv;
if (!htmlPath) { console.error('用法: node verify_report_inline.js <html>'); process.exit(2); }
(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    args: ['--no-sandbox', '--disable-gpu'],
  });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('requestfailed', r => errors.push('REQ_FAIL:' + r.url()));
  await page.setViewport({ width: 1100, height: 900 });
  await page.goto('file:///' + htmlPath.replace(/\\/g, '/'), { waitUntil: 'networkidle0' });
  await new Promise(r => setTimeout(r, 800));
  const res = await page.evaluate(() => ({
    echartsLoaded: typeof window.echarts === 'object',
    chartDivs: document.querySelectorAll('.chart').length,
    canvas: document.querySelectorAll('.chart canvas').length,
  }));
  console.log(JSON.stringify(res), 'pageerrors:', JSON.stringify(errors));
  const ok = res.echartsLoaded && res.canvas >= 2 && errors.length === 0;
  console.log(ok ? 'PASS' : 'FAIL');
  await browser.close();
  process.exit(ok ? 0 : 1);
})();
