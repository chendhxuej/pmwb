const puppeteer = require('puppeteer-core');
const fs = require('fs');
(async () => {
  const b = await puppeteer.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: 'new', args: ['--no-sandbox'] });
  const p = await b.newPage();
  const errors = [];
  p.on('console', msg => console.log('[CONSOLE]', msg.type().toUpperCase(), msg.text()));
  p.on('pageerror', err => { errors.push(err.message); console.log('[PAGEERROR]', err.message); });
  p.on('response', async r => {
    if (r.url().includes('/api/v1/')) {
      const ok = r.status() < 400;
      const body = ok ? '' : await r.text();
      console.log('[API]', r.status(), ok ? 'OK' : 'FAIL', r.url());
      if (!ok) console.log('  body:', body);
    }
  });
  await p.goto('http://localhost:5173/knowledge-center/timeline', { waitUntil: 'networkidle2' });
  await p.waitForSelector('.timeline-title', { timeout: 20000 });
  await new Promise(r => setTimeout(r, 2000));
  const html = await p.content();
  fs.writeFileSync('D:/fixbk/timeline_page.html', html);
  await p.screenshot({ path: 'D:/fixbk/timeline_screenshot.png', fullPage: true });
  const txt = await p.evaluate(() => document.body.innerText);
  console.log('\n=== BODY TEXT (first 1200 chars) ===');
  console.log(txt.slice(0, 1200));
  console.log('\n=== ERRORS ===');
  console.log(errors.length ? errors.join('\n') : 'none');
  await b.close();
})();
