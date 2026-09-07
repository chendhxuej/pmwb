const puppeteer = require('puppeteer-core')
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const BASE = 'http://127.0.0.1:5173'
function sleep(ms){return new Promise(r=>setTimeout(r,ms))}
async function clickByText(page, selector, text){
  const h = await page.evaluateHandle((sel,t)=>{const els=[...document.querySelectorAll(sel)];return els.find(e=>e.textContent.trim().includes(t))||null},selector,text)
  const el=h.asElement(); if(!el) throw new Error(`未找到「${text}」`); await el.click(); return el
}
async function clickByTextEval(page, selector, text){
  return await page.evaluate((sel,t)=>{const els=[...document.querySelectorAll(sel)];const e=els.find(x=>x.textContent.trim().includes(t));if(e){e.click();return true}return false},selector,text)
}
;(async()=>{
  const browser=await puppeteer.launch({executablePath:CHROME,headless:'new',args:['--no-sandbox','--disable-setuid-sandbox']})
  const page=await browser.newPage()
  const captured=[]
  page.on('request',req=>{if(req.method()==='POST'&&req.url().includes('/material-categories'))captured.push({type:'REQ',url:req.url(),body:req.postData()})})
  page.on('response',async res=>{if(res.request().method()==='POST'&&res.url().includes('/material-categories')){let rb=null;try{rb=await res.json()}catch{};captured.push({type:'RES',status:res.status(),body:rb})}})
  await page.goto(BASE,{waitUntil:'networkidle2',timeout:60000}); await sleep(2000)
  await clickByText(page,'button.nav-parent','业务资料库'); await sleep(1800)
  const manageBtn = await page.$('.material-aside .aside-head button')
  if(manageBtn) await manageBtn.click()
  await sleep(1200)
  await clickByText(page,'button','新增一级'); await sleep(900)
  const tsHandle = await page.$('.el-tree-select'); if(tsHandle) await tsHandle.click(); await sleep(800)
  await clickByTextEval(page,'.el-tree-select__popper .el-tree-node__content','汇报材料'); await sleep(500)
  const fillByPh = async (ph, val) => page.evaluate((p,v)=>{const inp=[...document.querySelectorAll('input')].find(i=>(i.placeholder||'').includes(p));if(inp){inp.focus();inp.value='';inp.dispatchEvent(new Event('input',{bubbles:true}));inp.value=v;inp.dispatchEvent(new Event('input',{bubbles:true}));return true}return false},ph,val)
  await fillByPh('汇报材料','复现重复编码')
  await fillByPh('report','report')  // 故意用已存在的编码
  await sleep(300)
  await clickByTextEval(page,'button','保存'); await sleep(2000)
  // 读取页面上弹出的错误提示文本
  const toast = await page.evaluate(()=>{const t=[...document.querySelectorAll('.el-message')].map(e=>e.innerText.trim());return t})
  console.log('页面错误提示=', JSON.stringify(toast))
  console.log('=== CAPTURED ===')
  console.log(JSON.stringify(captured,null,2))
  await browser.close()
})().catch(e=>{console.error('SCRIPT ERROR',e);process.exit(1)})
