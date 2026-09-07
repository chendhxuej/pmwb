const puppeteer = require('puppeteer-core')
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const BASE = 'http://127.0.0.1:5173'
function sleep(ms){return new Promise(r=>setTimeout(r,ms))}
async function clickByText(page, selector, text){
  const h = await page.evaluateHandle((sel,t)=>{const els=[...document.querySelectorAll(sel)];return els.find(e=>e.textContent.trim().includes(t))||null},selector,text)
  const el=h.asElement(); if(!el) throw new Error(`未找到「${text}」的 ${selector}`); await el.click(); return el
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
  // 点「新增一级」，打开新增分类表单
  await clickByText(page,'button','新增一级'); await sleep(900)
  // 打开 父分类 el-tree-select 下拉
  const tsHandle = await page.$('.el-tree-select')
  if(tsHandle) await tsHandle.click()
  await sleep(800)
  // 在下拉里点选「汇报材料」节点
  const picked = await clickByTextEval(page,'.el-tree-select__popper .el-tree-node__content, .el-select-dropdown__item', '汇报材料')
  console.log('picked 汇报材料=', picked)
  await sleep(500)
  // 读取 el-tree-select 当前显示文本（验证选中）
  const selText = await page.evaluate(()=>{const t=document.querySelector('.el-tree-select');return t?t.innerText.trim():'(none)'})
  console.log('tree-select 显示=', selText)
  // 填 名称 / 编码
  const fillByPh = async (ph, val) => page.evaluate((p,v)=>{const inp=[...document.querySelectorAll('input')].find(i=>(i.placeholder||'').includes(p));if(inp){inp.focus();inp.value='';inp.dispatchEvent(new Event('input',{bubbles:true}));inp.value=v;inp.dispatchEvent(new Event('input',{bubbles:true}));return true}return false},ph,val)
  await fillByPh('汇报材料','下拉复现子分类')
  await fillByPh('report','repro_drop_'+Date.now())
  await sleep(300)
  const clicked = await clickByTextEval(page,'button','保存')
  console.log('clicked 保存=', clicked)
  await sleep(2000)
  console.log('=== CAPTURED ===')
  console.log(JSON.stringify(captured,null,2))
  await browser.close()
})().catch(e=>{console.error('SCRIPT ERROR',e);process.exit(1)})
