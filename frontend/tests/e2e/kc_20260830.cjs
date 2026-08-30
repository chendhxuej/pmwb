const puppeteer = require('puppeteer-core');
const fs = require('fs');
(async () => {
  const b = await puppeteer.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: 'new', args: ['--no-sandbox'] });
  const p = await b.newPage();
  p.on('pageerror', err => console.log('[PAGEERROR]', err.message));
  p.on('console', msg => {
    if (msg.type() === 'error') console.log('[CONSOLE]', msg.text());
  });
  for (const [path, name] of [
    ['/knowledge-center/hub', 'hub'],
    ['/knowledge-center/timeline', 'timeline'],
    ['/knowledge-center/relations', 'relations'],
    ['/knowledge-center/manage', 'manage'],
  ]) {
    await p.goto('http://localhost:5173' + path, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1500));
    await p.screenshot({ path: `D:/fixbk/kc_${name}.png`, fullPage: true });
    console.log('captured', name);
  }
  await b.close();
})();
