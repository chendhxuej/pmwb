/**
 * kc4-6 知识中心三视图冒烟：验证 HUB / 检索 / 沉淀向导 三个视图无白屏、无控制台报错。
 */
import puppeteer from 'puppeteer-core'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const outDir = path.join(__dirname, '..', 'tmp_smoke', 'kc4_6')
fs.mkdirSync(outDir, { recursive: true })

const BASE_URL = 'http://127.0.0.1:5173'
const consoleErrors = []

const run = async () => {
  const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  })
  const page = await browser.newPage()
  await page.setViewport({ width: 1600, height: 1000 })
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })
  page.on('pageerror', (err) => consoleErrors.push('PAGEERROR: ' + err.message))

  // 1. 打开知识中心（新三视图）
  await page.goto(`${BASE_URL}/knowledge-center`, { waitUntil: 'networkidle2' })
  await new Promise((r) => setTimeout(r, 3000))

  // 调试：打印路由路径和渲染状态
  const dbg = await page.evaluate(() => ({
    url: window.location.pathname,
    bodyHTML: document.querySelector('.knowledge-center')?.innerHTML?.slice(0, 300) || 'NO .knowledge-center',
    kcBody: document.querySelector('.kc-body') ? 'has .kc-body' : 'no .kc-body',
    routerView: document.querySelector('.knowledge-center router-view') ? 'has router-view' : 'no router-view',
  }))
  console.log('DEBUG:', JSON.stringify(dbg))

  await page.screenshot({ path: path.join(outDir, '1-hub.png') })

  // 断言：三视图 Tab 存在
  const tabs = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('.kc-tab')).map((t) => t.textContent.trim())
  })
  console.log('Tabs:', tabs)
  if (!tabs.includes('业务全景')) throw new Error('缺少「业务全景」Tab')
  if (!tabs.includes('知识检索')) throw new Error('缺少「知识检索」Tab')
  if (!tabs.includes('沉淀向导')) throw new Error('缺少「沉淀向导」Tab')

  // 2. 切到「知识检索」
  const searchTab = await page.evaluate(() => {
    const t = Array.from(document.querySelectorAll('.kc-tab')).find((x) => x.textContent.includes('检索'))
    if (t) { t.click(); return true }
    return false
  })
  if (!searchTab) throw new Error('未找到检索 Tab')
  await new Promise((r) => setTimeout(r, 1500))
  await page.screenshot({ path: path.join(outDir, '2-search.png') })

  const hasSearchInput = await page.evaluate(() => !!document.querySelector('.sp-bar input'))
  if (!hasSearchInput) throw new Error('检索视图缺少搜索框')

  // 3. 切到「沉淀向导」
  const sedTab = await page.evaluate(() => {
    const t = Array.from(document.querySelectorAll('.kc-tab')).find((x) => x.textContent.includes('沉淀'))
    if (t) { t.click(); return true }
    return false
  })
  if (!sedTab) throw new Error('未找到沉淀向导 Tab')
  await new Promise((r) => setTimeout(r, 1500))
  await page.screenshot({ path: path.join(outDir, '3-sediment.png') })

  const hasSedCards = await page.evaluate(() => document.querySelectorAll('.sp-card').length >= 3)
  if (!hasSedCards) throw new Error('沉淀向导卡片不足 3 个')

  // 4. 回到 HUB，检查领域卡片
  await page.evaluate(() => {
    const t = Array.from(document.querySelectorAll('.kc-tab')).find((x) => x.textContent.includes('全景'))
    if (t) t.click()
  })
  await new Promise((r) => setTimeout(r, 1500))
  await page.screenshot({ path: path.join(outDir, '4-hub-cards.png') })

  const cardCount = await page.evaluate(() => document.querySelectorAll('.dk-card').length)
  console.log('Domain cards:', cardCount)

  // 5. 选中一个领域，打开产品圣经
  await page.evaluate(() => {
    const c = document.querySelector('.dk-card')
    if (c) c.click()
  })
  await new Promise((r) => setTimeout(r, 1500))
  await page.screenshot({ path: path.join(outDir, '5-hub-detail.png') })

  // 滚动到底部确保产品圣经按钮可见
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
  await new Promise((r) => setTimeout(r, 500))

  const openedBible = await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'))
    const btn = btns.find((b) => b.textContent.includes('产商品体系'))
    if (btn) { btn.click(); return { ok: true, text: btn.textContent.trim() } }
    return { ok: false, texts: btns.map(b => b.textContent.trim().slice(0, 50)) }
  })
  console.log('Product bible button:', JSON.stringify(openedBible))
  if (!openedBible.ok) throw new Error(`HUB 未找到产品圣经入口按钮 (buttons: ${JSON.stringify(openedBible.texts?.slice(0,5))})`)
  await new Promise((r) => setTimeout(r, 4000))
  await page.waitForSelector('.pb-content', { timeout: 8000 }).catch(() => {})
  await page.screenshot({ path: path.join(outDir, '6-product-bible.png') })

  const urlAfter = page.url()
  console.log('URL after bible click:', urlAfter)

  // 产品圣经页面应展示 §2 产商品章节
  const bibleOk = await page.evaluate(() => {
    try {
      const md = document.querySelector('.pb-content')
      if (!md) return { ok: false, reason: 'no .pb-content' }
      return { ok: md.textContent.includes('产商品与资费'), text: md.textContent.slice(0, 200) }
    } catch(e) { return { ok: false, reason: e.message } }
  })
  console.log('Product bible §2:', JSON.stringify(bibleOk))
  if (!bibleOk.ok) throw new Error(`产品圣经未渲染 §2 (${bibleOk.reason}, url=${urlAfter})`)

  await browser.close()

  console.log('=== kc4-6 三视图冒烟结果 ===')
  console.log(`Tabs: ${tabs.join(' / ')}`)
  console.log(`Domain cards: ${cardCount}`)
  console.log('--- 控制台错误 ---')
  console.log(consoleErrors.length ? consoleErrors.join('\n') : '(无)')
  const ok = tabs.length === 3 && hasSearchInput && hasSedCards && consoleErrors.length === 0
  console.log(ok ? '\nSMOKE PASS' : '\nSMOKE FAIL')
  process.exit(ok ? 0 : 1)
}

run().catch((e) => {
  console.error('SMOKE ERROR:', e.message)
  process.exit(1)
})
