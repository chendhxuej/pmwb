const puppeteer = require('puppeteer-core')
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const BASE = 'http://127.0.0.1:5173'
function sleep(ms){return new Promise(r=>setTimeout(r,ms))}
;(async()=>{
  const b = await puppeteer.launch({executablePath:CHROME,headless:'new',args:['--no-sandbox','--disable-setuid-sandbox']})
  const p = await b.newPage()
  await p.goto(BASE,{waitUntil:'networkidle2',timeout:60000})
  await sleep(2000)
  const info = await p.evaluate(()=>{
    const menus=[...document.querySelectorAll('.el-menu-item,.el-sub-menu__title')].map(e=>e.textContent.trim())
    return {url:location.href, menus, bodyLen:document.body.innerText.length, hasLogin: !!document.querySelector('input[type=password],.login')}
  })
  console.log(JSON.stringify(info,null,2))
  await b.close()
})().catch(e=>{console.error(e);process.exit(1)})
