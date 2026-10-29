/**
 * 回归：业务资料库「材料分类」左侧栏 → 顶部横向卡片导航（2026-10-29 新增）
 *
 * 覆盖点：
 *  1. 左侧分类栏已移除（无 .material-aside），顶部导航 .material-cat-nav 存在且位于 .table-toolbar 之前
 *  2. 一级卡片数 = 接口一级分类数 + 2（全部/未分类）
 *  3. 各一级卡计数 = 接口 material_count；「全部」= Σ一级 + 未分类；「未分类」= uncategorized_count
 *  4. 点一级卡 → 联动：面包屑「X ›」+「不限」高亮 + 子胶囊数正确 + 列表 total = 接口 category_id 查询
 *  5. 点二级胶囊 → 胶囊高亮 + 父卡 is-open + 列表 total 一致
 *  6. 点「全部」→ 列表 total = 接口全量 total
 *  7. 临时分类 CRUD 同步：新增后卡片出现（计数 0）；改名/停用后同步；选中态下经管理弹窗删除 →
 *     卡片消失 + 自动回退「全部」+ 提示（只用 e2e_tmp_nav 临时分类，禁碰真实业务分类）
 *  8. 响应式：1680 宽卡片 min-width 132px；960 宽 96px
 *  9. 无 Vue 运行时报错
 *
 * 红线：build 过 ≠ 能渲染。本脚本必须真实 DOM 断言。
 * 注意：本文件为 LF 行尾；.gitignore 忽略 verify_*.cjs，提交需 `git add -f`。
 */
const puppeteer = require('puppeteer-core')

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173'
const API = process.env.API_URL || 'http://127.0.0.1:8000'
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const ROUTE = '/material-library'
const TMP_CODE = 'e2e_tmp_nav'
const TMP_NAME = 'E2E临时分类'

const log = []
const check = (name, cond, extra) => {
  log.push(`${cond ? 'PASS' : 'FAIL'} ${name}${extra ? ' | ' + extra : ''}`)
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function apiGet(path) {
  const r = await fetch(API + path)
  const j = await r.json()
  if (j.code !== 0) throw new Error(`GET ${path} -> code=${j.code} ${j.message}`)
  return j.data
}
async function apiSend(method, path, body) {
  const r = await fetch(API + path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  const j = await r.json().catch(() => ({}))
  return { ok: r.ok && j.code === 0, data: j.data, message: j.message }
}

;(async () => {
  let tmpId = null
  // 预清理：上次运行残留的临时分类
  try {
    const cats0 = await apiGet('/api/v1/material-categories')
    const stale = cats0.find((c) => c.code === TMP_CODE)
    if (stale) await apiSend('DELETE', `/api/v1/material-categories/${stale.id}`)
  } catch (e) { /* 忽略 */ }

  // ── 接口基准 ──
  const cats = await apiGet('/api/v1/material-categories')
  const probe = await apiGet('/api/v1/materials?page=1&page_size=1')
  const l1 = cats.filter((c) => !c.parent_id)
  const sumL1 = l1.reduce((s, c) => s + (c.material_count || 0), 0)
  const uncat = probe.uncategorized_count ?? 0

  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
    defaultViewport: { width: 1680, height: 1100 },
  })
  const page = await browser.newPage()
  const errs = []
  page.on('pageerror', (e) => errs.push('pageerror: ' + e.message))
  page.on('console', (c) => {
    if (c.type() === 'error') {
      const t = c.text()
      if (!/favicon|404 \(Not Found\)/i.test(t)) errs.push('console: ' + t)
    }
  })

  const open = async () => {
    await page.goto(BASE + ROUTE, { waitUntil: 'networkidle2', timeout: 60000 })
    await sleep(1500)
  }
  const clickCard = async (name) => {
    const hit = await page.evaluate((n) => {
      const el = [...document.querySelectorAll('.cat-l1-card')].find(
        (e) => e.querySelector('.cat-l1-name-text')?.innerText.trim() === n
      )
      if (!el) return false
      el.click()
      return true
    }, name)
    if (!hit) throw new Error(`找不到一级卡片「${name}」`)
    await sleep(1200)
  }
  // 注意：pageFunction 序列化进页面上下文，只能用页面内可用的全局（parseInt），不能引用 Node 侧函数
  const pagerTotal = () => page.$eval('.el-pagination__total',
    (e) => parseInt((e.innerText || '').replace(/[^\d]/g, ''), 10) || 0
  ).catch(() => -1)
  const activeCardName = () => page.$eval('.cat-l1-card.is-active .cat-l1-name-text', (e) => e.innerText.trim()).catch(() => '')

  try {
    await open()

    // 1. 布局结构
    check('左侧分类栏已移除', (await page.$('.material-aside')) === null)
    const navPos = await page.evaluate(() => {
      const nav = document.querySelector('.material-cat-nav')
      const tb = document.querySelector('.table-toolbar')
      if (!nav || !tb) return 'missing'
      return nav.compareDocumentPosition(tb) & Node.DOCUMENT_POSITION_FOLLOWING ? 'before' : 'after'
    })
    check('顶部导航存在且位于筛选条之前', navPos === 'before', `position=${navPos}`)

    // 2/3. 卡片数量与计数口径
    const cardCount = await page.$$eval('.cat-l1-card', (els) => els.length)
    check('一级卡片数 = 接口一级数 + 2', cardCount === l1.length + 2, `DOM=${cardCount} API=${l1.length}+2`)
  // 只取 .cat-l1-num 第一个文本节点（纯数字），避免把「N 子类」的数字并进计数
  const domCards = await page.$$eval('.cat-l1-card', (els) =>
    els.map((e) => ({
      name: e.querySelector('.cat-l1-name-text')?.innerText.trim(),
      count: parseInt((e.querySelector('.cat-l1-num')?.childNodes[0]?.textContent || '0').replace(/[^\d]/g, ''), 10) || 0,
    }))
  )
    const allCard = domCards.find((c) => c.name === '全部')
    const uncCard = domCards.find((c) => c.name === '未分类')
    check('「全部」卡计数 = Σ一级 + 未分类', allCard && allCard.count === sumL1 + uncat,
      `DOM=${allCard?.count} 期望=${sumL1 + uncat}`)
    check('「未分类」卡计数 = 接口 uncategorized_count', uncCard && uncCard.count === uncat,
      `DOM=${uncCard?.count} 期望=${uncat}`)
    const mismatch = []
    l1.forEach((c) => {
      const d = domCards.find((x) => x.name === c.name)
      if (!d) mismatch.push(`${c.name}:缺卡片`)
      else if (d.count !== (c.material_count || 0)) mismatch.push(`${c.name}:DOM=${d.count} API=${c.material_count}`)
    })
    check('全部一级卡计数与接口一致', mismatch.length === 0, mismatch.join('; ').slice(0, 200))

    // 4. 点一级卡（分析报告，4 个子分类）
    await clickCard('分析报告')
    const crumb = await page.$eval('.mcn-crumb', (e) => e.innerText.trim()).catch(() => '')
    check('二级行出现面包屑「分析报告 ›」', crumb === '分析报告 ›', `实际=${crumb}`)
    const chipCount = await page.$$eval('.mcn-l2 .cat-l2-chip', (els) => els.length)
    const fx = cats.find((c) => c.name === '分析报告')
    check('子胶囊数 = 1(不限) + 子分类数', chipCount === 1 + (fx?.children_count || 0),
      `DOM=${chipCount} 期望=${1 + (fx?.children_count || 0)}`)
    const unlimitActive = await page.$eval('.mcn-l2 .cat-l2-chip', (e) => e.classList.contains('is-active'))
    check('「不限」胶囊高亮', unlimitActive)
    check('一级卡高亮（分析报告）', (await activeCardName()) === '分析报告')
    const apiFx = await apiGet('/api/v1/materials?category_id=' + fx.id + '&page=1&page_size=1')
    check('点一级卡后列表 total = 接口同口径', (await pagerTotal()) === apiFx.total,
      `DOM=${await pagerTotal()} API=${apiFx.total}`)

    // 5. 点二级胶囊
    const kid = await apiGet('/api/v1/material-categories').then((d) => d.find((c) => c.parent_id === fx.id && c.name === '主动运营分析'))
    await page.evaluate(() => {
      const el = [...document.querySelectorAll('.mcn-l2 .cat-l2-chip')].find(
        (e) => e.innerText.replace(/\d+$/, '').trim() === '主动运营分析'
      )
      if (el) el.click()
    })
    await sleep(1200)
    const kidChipActive = await page.evaluate(() => {
      const el = [...document.querySelectorAll('.mcn-l2 .cat-l2-chip')].find(
        (e) => e.innerText.replace(/\d+$/, '').trim() === '主动运营分析'
      )
      return el ? el.classList.contains('is-active') : false
    })
    check('二级胶囊高亮', kidChipActive)
    const parentOpen = await page.evaluate(() => {
      const el = [...document.querySelectorAll('.cat-l1-card')].find(
        (e) => e.querySelector('.cat-l1-name-text')?.innerText.trim() === '分析报告'
      )
      return el ? el.classList.contains('is-open') : false
    })
    check('父一级卡进入 is-open 半选态', parentOpen)
    const apiKid = await apiGet('/api/v1/materials?category_id=' + kid.id + '&page=1&page_size=1')
    check('点二级胶囊后列表 total = 接口同口径', (await pagerTotal()) === apiKid.total,
      `DOM=${await pagerTotal()} API=${apiKid.total}`)

    // 6. 回「全部」
    await clickCard('全部')
    check('点「全部」后列表 total = 接口全量', (await pagerTotal()) === probe.total,
      `DOM=${await pagerTotal()} API=${probe.total}`)

    // 7. 临时分类 CRUD 同步
    const cr = await apiSend('POST', '/api/v1/material-categories',
      { code: TMP_CODE, name: TMP_NAME, parent_id: null, sort_order: 0, enabled: true })
    check('临时分类创建成功', cr.ok, cr.message || '')
    tmpId = cr.data?.id
    await open()
    check('新增分类后卡片自动出现', await page.evaluate((n) =>
      [...document.querySelectorAll('.cat-l1-card .cat-l1-name-text')].some((e) => e.innerText.trim() === n), TMP_NAME))

    await clickCard(TMP_NAME)
    check('临时分类可选中且高亮', (await activeCardName()) === TMP_NAME)
    check('空分类列表为空态（无分页）', (await page.$('.el-pagination')) === null && (await page.$('.material-grid .el-empty')) !== null)

    await apiSend('PUT', `/api/v1/material-categories/${tmpId}`, { name: TMP_NAME + 'B' })
    await open()
    check('改名后卡片名称同步', await page.evaluate((n) =>
      [...document.querySelectorAll('.cat-l1-card .cat-l1-name-text')].some((e) => e.innerText.trim() === n), TMP_NAME + 'B'))

    await apiSend('PUT', `/api/v1/material-categories/${tmpId}`, { enabled: false })
    await open()
    const disabledShown = await page.evaluate((n) => {
      const el = [...document.querySelectorAll('.cat-l1-card')].find(
        (e) => e.querySelector('.cat-l1-name-text')?.innerText.trim() === n
      )
      return el ? el.classList.contains('is-disabled') : false
    }, TMP_NAME + 'B')
    check('停用分类置灰展示（is-disabled）', disabledShown)

    // 选中停用分类 → 经管理弹窗删除 → 回退「全部」
    await clickCard(TMP_NAME + 'B')
    await page.evaluate(() => {
      const btn = [...document.querySelectorAll('.material-cat-nav button')].find((e) => e.innerText.includes('管理分类'))
      if (btn) btn.click()
    })
    await page.waitForSelector('.cat-tree', { timeout: 8000 })
    await sleep(600)
    const delClicked = await page.evaluate((n) => {
      const node = [...document.querySelectorAll('.cat-tree .cat-node')].find((e) => e.innerText.includes(n))
      if (!node) return false
      const btn = [...node.querySelectorAll('.cat-ops button')].find((b) => b.innerText.trim() === '删')
      if (!btn) return false
      btn.click()
      return true
    }, TMP_NAME + 'B')
    check('管理弹窗内找到临时分类并点删', delClicked)
    await page.waitForSelector('.el-message-box', { timeout: 8000 })
    await sleep(400)
    await page.evaluate(() => {
      const btn = document.querySelector('.el-message-box__btns .el-button--primary')
      if (btn) btn.click()
    })
    await sleep(1500)
    check('删除后卡片消失', !(await page.evaluate((n) =>
      [...document.querySelectorAll('.cat-l1-card .cat-l1-name-text')].some((e) => e.innerText.trim() === n), TMP_NAME + 'B')))
    check('选中分类被删后自动回退「全部」', (await activeCardName()) === '全部',
      `实际=${await activeCardName()}`)
    const fallbackMsg = await page.evaluate(() =>
      [...document.querySelectorAll('.el-message')].some((e) => e.innerText.includes('已切换到「全部」'))
    ).catch(() => false)
    check('出现回退提示', fallbackMsg)
    tmpId = null // 已删除

    // 8. 响应式
    await page.setViewport({ width: 960, height: 800 })
    await open()
    const mw960 = await page.$eval('.cat-l1-card', (e) => getComputedStyle(e).minWidth)
    check('960 宽：卡片 min-width 96px', mw960 === '96px', `实际=${mw960}`)
    await page.setViewport({ width: 1680, height: 1100 })
    await open()
    const mw1680 = await page.$eval('.cat-l1-card', (e) => getComputedStyle(e).minWidth)
    check('1680 宽：卡片 min-width 132px', mw1680 === '132px', `实际=${mw1680}`)

    // 9. 运行时错误
    check('无 Vue 运行时报错', errs.length === 0, errs.slice(0, 3).join(' | '))
  } catch (e) {
    check('脚本执行无异常', false, e.message)
  } finally {
    if (tmpId != null) {
      try { await apiSend('DELETE', `/api/v1/material-categories/${tmpId}`) } catch (e) { /* 忽略 */ }
    }
    await browser.close()
  }

  console.log(log.join('\n'))
  const fails = log.filter((l) => l.startsWith('FAIL')).length
  console.log(`\n${log.length - fails}/${log.length} passed`)
  process.exit(fails ? 1 : 0)
})()
