// 报告导出 PDF —— 关键：必须在打印媒体下按 A4 内容宽度重绘 ECharts 再打印，
// 否则 canvas 仍是屏幕尺寸，右侧图例/底部会被裁切（2026-10-27 已踩坑）。
// 用法: node pdf_export.js <html绝对路径> <pdf绝对路径>

const puppeteer = require('D:/项目/个人工作台系统/frontend/node_modules/puppeteer-core');

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PAGE_CONTENT_W = 733; // A4 210mm - 左右各 8mm ≈ 733px @96dpi

const [, , htmlPath, pdfPath] = process.argv;
if (!htmlPath || !pdfPath) {
  console.error('用法: node pdf_export.js <html> <pdf>');
  process.exit(2);
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--disable-gpu', '--font-render-hinting=none', '--force-color-profile=srgb'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: PAGE_CONTENT_W, height: 1120, deviceScaleFactor: 2 });
  await page.goto('file:///' + htmlPath.replace(/\\/g, '/'), { waitUntil: 'networkidle0' });

  // 等图表实例就绪（无图表时直接跳过）
  const hasChart = await page.evaluate(() => document.querySelectorAll('.chart').length > 0);
  if (hasChart) {
    await page.waitForFunction(
      () => document.querySelectorAll('.chart canvas').length >= document.querySelectorAll('.chart').length,
      { timeout: 20000 },
    );
    await new Promise(r => setTimeout(r, 500));
  }

  // 切打印媒体 → 按 A4 内容宽度重绘，消除裁切
  await page.emulateMediaType('print');
  await new Promise(r => setTimeout(r, 300));
  const overflow = await page.evaluate(async () => {
    const bad = [];
    for (const el of document.querySelectorAll('.chart,.chart-sm')) {
      const inst = window.echarts && echarts.getInstanceByDom(el);
      if (inst) inst.resize();
      await new Promise(r => requestAnimationFrame(() => r()));
      const cv = el.querySelector('canvas');
      if (cv) {
        const dx = Math.round(cv.getBoundingClientRect().width - el.clientWidth);
        const dy = Math.round(cv.getBoundingClientRect().height - el.clientHeight);
        if (dx || dy) bad.push({ id: el.id, dx, dy });
      }
    }
    return bad;
  });
  if (overflow.length) console.log('WARN 图表溢出:', JSON.stringify(overflow));

  await new Promise(r => setTimeout(r, 400));
  await page.pdf({
    path: pdfPath,
    printBackground: true,
    preferCSSPageSize: true,
    margin: { top: 0, right: 0, bottom: 0, left: 0 },
  });
  await browser.close();

  const fs = require('fs');
  console.log('PDF OK', pdfPath, fs.statSync(pdfPath).size, 'bytes');
})().catch(e => { console.error('ERR', e); process.exit(1); });
