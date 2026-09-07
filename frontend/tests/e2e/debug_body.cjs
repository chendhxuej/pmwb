const puppeteer = require('puppeteer-core')
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const BASE = 'http://127.0.0.1:5173'
function sleep(ms){return new Promise(r=>setTimeout(r,ms))}
;(async()=>{
  const b = await puppeteer.launch({executablePath:CHROME,headless:'new',args:['--no-sandbox','--disable-setuid-sandbox']})
  const p = await b.newPage()
  await p.goto(BASE,{waitUntil:'networkidle2',timeout:60000})
  await sleep(2500)
  const t = await p.evaluate(()=>document.body.innerText)
  console.log('---BODY TEXT---')
  console.log(t.slice(0,1500))
  console.log('---SIDEBAR HTML (first 800)---')
  const sb = await p.evaluate(()=>{const s=document.querySelector('.el-aside,.el-menu,.sidebar')||document.body; return s.innerHTML.slice(0,800)})
  console.log(sb)
  await b.close()
})().catch(e=>{console.error(e);process.exit(1)})
