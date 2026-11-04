/**
 * 客诉根因深化（CP-R1~R6）—— 真实浏览器回归（零依赖，走 Chrome DevTools Protocol）
 *
 * 覆盖：
 *   1. 根因库页 /complaint-center/rootcause：KPI 卡、根因簇表格、簇详情抽屉（关联工单）
 *   2. 投诉现状看板（冒烟：五板块 + 已知问题率；完整断言见 verify_complaint_analysis.mjs）
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
      const kpis = [...document.querySelectorAll('.rootcause-lib .pm-stat')]
        .map(c => ({
          num: (c.querySelector('.pm-stat__val')?.innerText || '').trim(),
          label: (c.querySelector('.pm-stat__label')?.innerText || '').trim(),
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
      const btnTexts = [...document.querySelectorAll('.rootcause-lib .el-button')]
        .map(b => (b.innerText || '').trim())
      return { kpis, mainRows, firstTitle, firstNo, firstCnt, reviewRows, btnTexts, tableCount: tables.length }
    })()`)

    libDom.kpis.length === 5 ? ok('KPI 卡 5 张', libDom.kpis.map(k => k.num).join('/')) : bad('KPI 卡数量异常', String(libDom.kpis.length))
    String(libDom.kpis[0]?.num || '').includes('%') ? ok('根因覆盖率显示百分比', libDom.kpis[0].num) : bad('覆盖率不是百分比', JSON.stringify(libDom.kpis[0]))
    libDom.mainRows > 0 ? ok('根因簇表格有数据', `${libDom.mainRows} 行`) : bad('根因簇表格为空')
    String(libDom.firstNo).startsWith('RC-') ? ok('簇编号格式正确', libDom.firstNo) : bad('簇编号异常', libDom.firstNo)
    libDom.firstTitle.length >= 6 ? ok('根因标题有实质内容', libDom.firstTitle.slice(0, 24)) : bad('根因标题过短', libDom.firstTitle)
    libDom.tableCount >= 2 ? ok('含待人工确认队列表') : bad('待人工表缺失', String(libDom.tableCount))
    libDom.btnTexts.some(t => t.includes('新建根因簇'))
      ? ok('有「新建根因簇」入口（按需维护）') : bad('缺少新建根因簇入口', JSON.stringify(libDom.btnTexts.slice(0, 6)))
    libDom.btnTexts.some(t => t.includes('编辑'))
      ? ok('行内「编辑」入口在位（改键自查重）') : bad('缺少行内编辑入口')

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
      const cause = (d.querySelector('.el-table__body tbody tr td:nth-child(5)')?.innerText || '').trim()
      const moveBtn = d.querySelector('.js-move-btn')
      return {
        rows, cause, metaTags: d.querySelectorAll('.detail-meta .el-tag').length,
        hasMove: !!moveBtn, moveDisabled: moveBtn ? moveBtn.disabled : null,
        hasSelection: !!d.querySelector('.el-table__header .el-checkbox'),
      }
    })()`)
    drawer.rows > 0 ? ok('抽屉内关联工单有数据', `${drawer.rows} 行`) : bad('抽屉内工单为空')
    drawer.cause.length >= 10 ? ok('工单根因文本非空', drawer.cause.slice(0, 30)) : bad('工单根因文本缺失', drawer.cause)
    drawer.metaTags >= 5 ? ok('簇标签齐全', `${drawer.metaTags} 个`) : bad('簇标签缺失', String(drawer.metaTags))
    drawer.hasSelection ? ok('工单可多选（拆簇移出用）') : bad('缺少多选列')
    drawer.hasMove ? ok('「移出选中」按钮在位') : bad('缺少移出按钮')
    drawer.moveDisabled === true ? ok('未选工单时移出按钮禁用') : bad('移出按钮未禁用', String(drawer.moveDisabled))
    await cdp.eval(`(() => { const b = document.querySelector('.el-drawer__close-btn'); b && b.click(); return true })()`)
    await sleep(600)

    /* ── 1.2 新建根因簇弹窗：只验证可打开与字段齐全，不提交（不写库）── */
    console.log('\n▶ 新建根因簇弹窗')
    const clicked = await cdp.eval(`(() => {
      const b = [...document.querySelectorAll('.rootcause-lib .el-button')]
        .find(x => (x.innerText || '').includes('新建根因簇'))
      if (b) b.click()
      return !!b
    })()`)
    if (clicked) {
      const dlgOpen = await cdp.waitFor('.el-dialog', 8000)
      dlgOpen ? ok('新建弹窗打开') : bad('新建弹窗未打开')
      await sleep(500)
      const dlg = await cdp.eval(`(() => {
        const d = [...document.querySelectorAll('.el-dialog')].filter(x => x.offsetParent !== null).pop()
        if (!d) return null
        return {
          selects: d.querySelectorAll('.el-select').length,
          textareas: d.querySelectorAll('textarea').length,
          hasTip: (d.innerText || '').includes('簇键'),
        }
      })()`)
      dlg && dlg.selects >= 3 ? ok('三要素下拉齐全', `${dlg.selects} 个 select`) : bad('下拉不足', JSON.stringify(dlg))
      dlg && dlg.textareas >= 2 ? ok('标题/判定边界输入在位', `${dlg.textareas} 个`) : bad('文本框缺失', JSON.stringify(dlg))
      dlg && dlg.hasTip ? ok('显示簇键口径说明') : bad('缺少簇键说明')
      await cdp.eval(`(() => {
        const d = [...document.querySelectorAll('.el-dialog')].filter(x => x.offsetParent !== null).pop()
        const b = d && [...d.querySelectorAll('.el-button')].find(x => (x.innerText || '').trim() === '取消')
        if (b) b.click()
        return true
      })()`)
      await sleep(400)
    } else {
      bad('未找到「新建根因簇」按钮')
    }

    /* ── 2. 看板「分析四问」 ── */
    /* ── 2. 投诉现状：看板已重构为「五板块分析报告」（2026-11-04）
       完整断言见 scripts/verify_complaint_analysis.mjs（34 项）。此处只做冒烟，
       避免两个脚本各维护一套看板断言、改版时双处返工。 ── */
    console.log('\n▶ 投诉现状看板 /complaint-center/dashboard（冒烟）')
    await cdp.goto(`${BASE}/complaint-center/dashboard`)
    const hasDash = await cdp.waitFor('.complaint-dashboard', 30000)
    hasDash ? ok('看板页挂载') : bad('看板页未挂载')
    await sleep(2500)
    const dashBrief = await cdp.eval(`(() => {
      const root = document.querySelector('.complaint-dashboard')
      if (!root) return null
      const kpis = [...root.querySelectorAll('.pm-stat')].map(c => ({
        num: (c.querySelector('.pm-stat__val')?.innerText || '').trim(),
        label: (c.querySelector('.pm-stat__label')?.innerText || '').trim(),
      }))
      return {
        titles: [...root.querySelectorAll('.card-header h3')].map(h => h.innerText.trim()),
        kpis,
      }
    })()`)
    dashBrief ? ok('看板 DOM 可取') : bad('看板 DOM 取不到')
    if (dashBrief) {
      dashBrief.titles.length >= 5 ? ok('五板块标题在位', `${dashBrief.titles.length} 个`) : bad('板块标题不足', JSON.stringify(dashBrief.titles))
      const rh = dashBrief.kpis.find(k => k.label.includes('已知问题率'))
      rh && String(rh.num).includes('%') ? ok('已知问题率出数', rh.num) : bad('已知问题率缺失')
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
