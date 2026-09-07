const puppeteer=require('puppeteer-core')
const CHROME='C:/Program Files/Google/Chrome/Application/chrome.exe'
const BASE='http://127.0.0.1:5173'
function sleep(ms){return new Promise(r=>setTimeout(r,ms))}
async function clickByText(page,selector,text){const h=await page.evaluateHandle((sel,t)=>{const els=[...document.querySelectorAll(sel)];return els.find(e=>e.textContent.trim().includes(t))||null},selector,text);const el=h.asElement();if(!el)throw new Error(`未找到「${text}」`);await el.click();return el}
;(async()=>{
  const b=await puppeteer.launch({executablePath:CHROME,headless:'new',args:['--no-sandbox','--disable-setuid-sandbox']})
  const p=await b.newPage()
  await p.goto(BASE,{waitUntil:'networkidle2',timeout:60000});await sleep(2000)
  await clickByText(p,'button.nav-parent','业务资料库');await sleep(2000)
  const r=await p.evaluate(()=>{
    const all=[...document.querySelectorAll('button')].map(e=>e.textContent.trim()).filter(Boolean)
    return all.filter(t=>t.includes('分类')||t.includes('管理'))
  })
  console.log('匹配按钮:',JSON.stringify(r,null,2))
  await b.close()
})().catch(e=>{console.error(e);process.exit(1)})
