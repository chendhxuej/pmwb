/**
 * 客诉根因深化（CP-R1~R6）—— 真实浏览器回归（零依赖，走 Chrome DevTools Protocol）
 *
 * 覆盖：
 *   1. 根因库页 /complaint-center/rootcause：KPI 卡、根因簇表格、簇详情抽屉（关联工单）
 *   2. 投诉现状看板「分析四问」：① 根因簇表 ② 环节/责任条形非空 ③ 批量问题表与压降空间
 *   3. 工单台账：根因列渲染（真实根因文本 + 系统/环节标签 + 簇编号）
 *
 * 用法（backend 目录外，项目根执行）：
 *   PMWB_BASE=http://127.0.0.1:8010 PMWB_AUTH_USER=chendh PMWB_AUTH_PW=xxx \
 *     node scripts/verify_complaint_rootcause.mjs
 * 前置：后端已加载新代码（含 /complaint/rootcause/* 端点）且托管最新 dist。
 */
import { existsSync } from 'node:fs'
import { spawn } from 'node:child_process'
import { mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const CHROME =
  process.env.CHROME_PATH ||
  [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  ].find((p) => existsSync(p))

const BASE = process.env.PMWB_BASE || 'http://127.0.0.1:8010'
const PORT = Number(process.env.CDP_PORT || 9346)
const USER = process.env.PMWB_AUTH_USER || 'chendh'
const PW = process.env.PMWB_AUTH_PW || ''

let pass = 0
let fail = 0
const failures = []
function ok(name, extra = '') {
  pass++
  console.log(`  PASS  ${name}${extra ? '  ' + extra : ''}`)
}
function bad(name, extra = '') {
  fail++
  failures.push(name)
  console.log(`  FAIL  ${name}${extra ? '  ' + extra : ''}`)
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

class CDP {
  constructor(ws) {
    this.ws = ws
    this.id = 0
    this.pending = new Map()
    ws.addEventListener('message', (ev) => {
      const msg = JSON.parse(ev.data)
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id)
        this.pending.delete(msg.id)
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result)
      }
    })
  }
  send(method, params = {}) {
    const id = ++this.id
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject })
      this.ws.send(JSON.stringify({ id, method, params }))
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id)
          reject(new Error(`CDP timeout: ${method}`))
        }
      }, 30000)
    })
  }
  async eval(expression) {
    const r = await this.send('Runtime.evaluate', {
      expression, returnByValue: true, awaitPromise: true,
    })
    if (r.exceptionDetails) {
      throw new Error(r.exceptionDetails.exception?.description || 'eval error')
    }
    return r.result.value
  }
  async goto(url) {
    await this.send('Page.navigate', { url })
  }
  async waitFor(sel, timeout = 25000) {
    const t0 = Date.now()
    while (Date.now() - t0 < timeout) {
      const found = await this.eval(`!!document.querySelector(${JSON.stringify(sel)})`).catch(() => false)
      if (found) return true
      await sleep(400)
    }
    return false
  }
  async clickAt(sel, idx = 0) {
    const r = await this.eval(`(() => {
      const els = document.querySelectorAll(${JSON.stringify(sel)})
      const el = els[${idx}]
      if (!el) return false
      el.click()
      return true
    })()`)
    if (!r) throw new Error(`click target not found: ${sel}[${idx}]`)
    await sleep(500)
  }
}

async function fetchWsUrl() {
  for (let i = 0; i < 40; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/list`)
      const tabs = await res.json()
      const page = tabs.find((t) => t.type === 'page')
      if (page) return page.webSocketDebuggerUrl
    } catch {}
    await sleep(500)
  }
  throw new Error('CDP endpoint not ready')
}

async function login(cdp) {
  await cdp.goto(`${BASE}/login`)
  const hasCard = await cdp.waitFor('.login-card', 20000)
  if (!hasCard) return false
  await sleep(800)
  await cdp.eval(`(() => {
    const inputs = [...document.querySelectorAll('.login-card input')]
    const set = (el, v) => {
      const proto = Object.getPrototypeOf(el)
      const desc = Object.getOwnPropertyDescriptor(proto, 'value')
      desc.set.call(el, v)
      el.dispatchEvent(new Event('input', { bubbles: true }))
    }
    set(inputs[0], ${JSON.stringify(USER)})
    set(inputs[1], ${JSON.stringify(PW)})
    return true
  })()`)
  await cdp.clickAt('.login-card .el-button')
  return cdp.waitFor('.main-layout', 25000)
}

async function main() {
  const profile = await mkdtemp(join(tmpdir(), 'pmwb-rc-'))
  const chrome = spawn(CHROME, [
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${profile}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--window-size=1440,940',
    'about:blank',
  ], { stdio: 'ignore' })

  try {
    const wsUrl = await fetchWsUrl()
    const ws = new WebSocket(wsUrl)
    await new Promise((res, rej) => {
      ws.addEventListener('open', res, { once: true })
      ws.addEventListener('error', rej, { once: true })
    })
    const cdp = new CDP(ws)
    await cdp.send('Page.enable')

    console.log('\n▶ 登录')
    const logged = await login(cdp)
    logged ? ok('登录并进入主布局') : bad('登录失败（检查 PMWB_AUTH_USER/PW）')

    /* ── 1. 根因库页 ── */
    console.log('\n▶ 根因库页 /complaint-center/rootcause')
    await cdp.goto(`${BASE}/complaint-center/rootcause`)
    const hasLib = await cdp.waitFor('.rootcause-lib', 25000)
    hasLib ? ok('页面挂载 .rootcause-lib') : bad('根因库页未挂载')
    await sleep(2500) // 等接口回包与表格渲染

    const libDom = await cdp.eval(`(() => {
      const kpis = [...document.querySelectorAll('.rootcause-lib .kpi-card')]
        .map(c => ({
          num: (c.querySelector('.kpi-num')?.innerText || '').trim(),
          label: (c.querySelector('.kpi-label')?.innerText || '').trim(),
        }))
      const tables = [...document.querySelectorAll('.rootcause-lib .el-table')]
      const mainRows = tables[0] ? tables[0].querySelectorAll('.el-table__body tbody tr').length : 0
      const firstRow = tables[0]?.querySelector('.el-table__body tbody tr')
      const firstTitle = firstRow ? (firstRow.querySelector('.rc-title')?.innerText || '').trim() : ''
      const firstNo = firstRow ? (firstRow.querySelector('b')?.innerText || '').trim() : ''
      const firstCnt = firstRow
        ? [...firstRow.querySelectorAll('td')].map(td => td.innerText.trim()).join('|')
        : ''
      const reviewRows = tables[1] ? tables[1].querySelectorAll('.el-table__body tbody tr').length : 0
      return { kpis, mainRows, firstTitle, firstNo, firstCnt, reviewRows, tableCount: tables.length }
    })()`)

    libDom.kpis.length === 5 ? ok('KPI 卡 5 张', libDom.kpis.map(k => k.num).join('/')) : bad('KPI 卡数量异常', String(libDom.kpis.length))
    String(libDom.kpis[0]?.num || '').includes('%') ? ok('根因覆盖率显示百分比', libDom.kpis[0].num) : bad('覆盖率不是百分比', JSON.stringify(libDom.kpis[0]))
    libDom.mainRows > 0 ? ok('根因簇表格有数据', `${libDom.mainRows} 行`) : bad('根因簇表格为空')
    String(libDom.firstNo).startsWith('RC-') ? ok('簇编号格式正确', libDom.firstNo) : bad('簇编号异常', libDom.firstNo)
    libDom.firstTitle.length >= 6 ? ok('根因标题有实质内容', libDom.firstTitle.slice(0, 24)) : bad('根因标题过短', libDom.firstTitle)
    libDom.tableCount >= 2 ? ok('含待人工确认队列表') : bad('待人工表缺失', String(libDom.tableCount))

    /* ── 1.1 簇详情抽屉：关联工单 ── */
    console.log('\n▶ 簇详情抽屉')
    await cdp.clickAt('.rootcause-lib .el-table__body tbody tr .el-button', 0)
    const drawerOpen = await cdp.waitFor('.el-drawer', 12000)
    drawerOpen ? ok('抽屉打开') : bad('抽屉未打开')
    await sleep(1200)
    const drawer = await cdp.eval(`(() => {
      const d = document.querySelector('.el-drawer')
      if (!d) return { rows: 0 }
      const rows = d.querySelectorAll('.el-table__body tbody tr').length
      const cause = (d.querySelector('.el-table__body tbody tr td:nth-child(4)')?.innerText || '').trim()
      return { rows, cause, metaTags: d.querySelectorAll('.detail-meta .el-tag').length }
    })()`)
    drawer.rows > 0 ? ok('抽屉内关联工单有数据', `${drawer.rows} 行`) : bad('抽屉内工单为空')
    drawer.cause.length >= 10 ? ok('工单根因文本非空', drawer.cause.slice(0, 30)) : bad('工单根因文本缺失', drawer.cause)
    drawer.metaTags >= 5 ? ok('簇标签齐全', `${drawer.metaTags} 个`) : bad('簇标签缺失', String(drawer.metaTags))
    await cdp.eval(`(() => { const b = document.querySelector('.el-drawer__close-btn'); b && b.click(); return true })()`)
    await sleep(600)

    /* ── 2. 看板「分析四问」 ── */
    console.log('\n▶ 投诉现状看板 /complaint-center/dashboard')
    await cdp.goto(`${BASE}/complaint-center/dashboard`)
    const hasCard2 = await cdp.waitFor('.rc-analysis', 30000)
    hasCard2 ? ok('分析区块 .rc-analysis 存在') : bad('分析区块缺失')
    await sleep(2500)

    const dash = await cdp.eval(`(() => {
      const box = document.querySelector('.rc-analysis')
      if (!box) return null
      const asks = [...box.querySelectorAll('.rc-ask-title')].map(e => e.innerText.trim())
      const tables = [...box.querySelectorAll('.el-table')]
      const clusterRows = tables[0] ? tables[0].querySelectorAll('.el-table__body tbody tr').length : 0
      const batchRows = tables[1] ? tables[1].querySelectorAll('.el-table__body tbody tr').length : 0
      const bars = [...box.querySelectorAll('.rc-bar-row')]
      const barW = bars.map(b => b.querySelector('.rc-bar-fill')?.style.width || '')
      const winNums = [...box.querySelectorAll('.rc-win .kpi-num')].map(e => e.innerText.trim())
      const covTag = (box.querySelector('.card-header .el-tag')?.innerText || '').trim()
      return {
        asks, clusterRows, batchRows, bars: bars.length,
        filledBars: barW.filter(w => w && w !== '0%').length,
        winNums, covTag, hasTip: !!box.querySelector('.rc-tip'),
      }
    })()`)

    dash ? ok('分析区块 DOM 可取') : bad('分析区块取不到')
    if (dash) {
      dash.asks.length === 3 ? ok('三个分析分节标题', dash.asks.join(' / ')) : bad('分析分节数量异常', JSON.stringify(dash.asks))
      dash.asks[0]?.includes('投诉的是什么问题') ? ok('分节①文案正确') : bad('分节①文案异常', dash.asks[0] || '')
      dash.asks[2]?.includes('一次消灭') ? ok('分节③文案正确') : bad('分节③文案异常', dash.asks[2] || '')
      dash.clusterRows > 0 ? ok('根因簇表有数据', `${dash.clusterRows} 行`) : bad('根因簇表为空')
      dash.bars > 0 ? ok('环节/责任条形渲染', `${dash.bars} 条`) : bad('条形图未渲染')
      dash.filledBars > 0 ? ok('条形宽度非零（真实数据驱动）', `${dash.filledBars}/${dash.bars}`) : bad('条形宽度全为 0')
      dash.batchRows > 0 ? ok('批量问题表有数据', `${dash.batchRows} 行`) : bad('批量问题表为空')
      dash.winNums.length === 3 ? ok('压降空间 KPI 3 张', dash.winNums.join('/')) : bad('压降空间 KPI 数量异常', JSON.stringify(dash.winNums))
      Number(dash.winNums[0]) > 0 ? ok('批量问题覆盖单量 > 0', dash.winNums[0]) : bad('批量覆盖单量为 0')
      String(dash.covTag).includes('根因分析') ? ok('覆盖率标签可见', dash.covTag) : bad('覆盖率标签缺失', dash.covTag)
    }

    /* ── 3. 工单台账根因列 ── */
    console.log('\n▶ 工单台账 /complaint-center/tickets')
    await cdp.goto(`${BASE}/complaint-center/tickets`)
    await cdp.waitFor('.complaint-tickets', 25000)
    await sleep(2500)
    const ledger = await cdp.eval(`(() => {
      const root = document.querySelector('.complaint-tickets')
      if (!root) return null
      const heads = [...root.querySelectorAll('.el-table th')].map(th => th.innerText.trim())
      const cells = [...root.querySelectorAll('.el-table__body tbody tr .rc-text')]
      const tags = root.querySelectorAll('.el-table__body tbody tr .rc-tags .el-tag').length
      const nos = [...root.querySelectorAll('.el-table__body tbody tr .rc-no')].map(e => e.innerText.trim())
      return {
        hasRootcauseCol: heads.some(h => h.includes('根因')),
        cells: cells.length,
        firstCause: cells[0]?.innerText.trim() || '',
        tags,
        firstNo: nos[0] || '',
      }
    })()`)
    ledger ? ok('台账页挂载') : bad('台账页未挂载')
    if (ledger) {
      ledger.hasRootcauseCol ? ok('存在「根因分析」列') : bad('根因列缺失')
      ledger.cells > 0 ? ok('根因单元格有内容', `${ledger.cells} 个`) : bad('根因单元格为空')
      ledger.firstCause.length >= 15 ? ok('首行根因文本具体', ledger.firstCause.slice(0, 30)) : bad('首行根因过短', ledger.firstCause)
      ledger.tags >= 3 ? ok('系统/环节/性质标签渲染', `${ledger.tags} 个`) : bad('标签缺失', String(ledger.tags))
      String(ledger.firstNo).startsWith('RC-') ? ok('簇编号可下钻链接', ledger.firstNo) : bad('簇编号链接缺失', ledger.firstNo)
    }
  } finally {
    chrome.kill()
  }

  console.log(`\n结果：PASS ${pass} / FAIL ${fail}`)
  if (fail) {
    console.log('失败项：' + failures.join('；'))
    process.exit(1)
  }
}

main().catch((e) => {
  console.error('回归异常：', e.message)
  process.exit(2)
})
