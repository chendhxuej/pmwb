/**
 * 客诉专题 · 页面联动回归（#71/#72/#73/#75，零依赖，走 CDP）
 *
 * 验证「主要投诉点(闭集)」为唯一主干的跨页联动：
 *   1. 投诉现状看板：顶部「主要投诉点速览」卡片（KPI + TOP 缺陷类 + 下钻）
 *   2. 热点投诉：同款速览卡片（同源，消除双口径观感）
 *   3. 主要投诉点：主表带「下钻」列（工单 / 问题台账）
 *   4. 工单明细：?module_problem_id= 进入即过滤（total 正确）+「L2 模块问题」列
 *   5. 问题台账：?module_problem_id= 定位对应候选（candidate tab + 定位标签）
 *
 * 用法（项目根执行；需后端已加载 #75 之后的 list_tickets 投影）：
 *   PMWB_BASE=http://127.0.0.1:8000 PMWB_AUTH_USER=chendh PMWB_AUTH_PW=*** \
 *     node scripts/verify_complaint_linkage.mjs
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

const BASE = process.env.PMWB_BASE || 'http://127.0.0.1:8000'
const PORT = Number(process.env.CDP_PORT || 9356)
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
    await sleep(700)
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
  const profile = await mkdtemp(join(tmpdir(), 'pmwb-link-'))
  const chrome = spawn(CHROME, [
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${profile}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--window-size=1680,1100',
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

    // ── 1. 投诉现状看板：主要投诉点速览 ──
    console.log('\n▶ 投诉现状 /complaint-center/dashboard')
    await cdp.goto(`${BASE}/complaint-center/dashboard`)
    const dashOk = await cdp.waitFor('.complaint-dashboard .mp-overview', 25000)
    dashOk ? ok('看板挂载「主要投诉点速览」卡片') : bad('看板未挂载速览卡片')
    await sleep(3500)
    const dashKpi = await cdp.eval(`(() => {
      const stats = [...document.querySelectorAll('.complaint-dashboard .mp-overview .pm-stat')]
        .map(s => s.querySelector('.pm-stat__label')?.textContent.trim() + '='
          + (s.querySelector('.pm-stat__val')?.textContent || '').trim())
      const tops = document.querySelectorAll('.complaint-dashboard .mp-overview .mp-top__item').length
      return { stats, tops }
    })()`).catch(() => ({ stats: [], tops: 0 }))
    const dTotal = dashKpi.stats.find((s) => s.startsWith('总工单='))
    const dDef = dashKpi.stats.find((s) => s.startsWith('缺陷已归集='))
    const dCls = dashKpi.stats.find((s) => s.startsWith('缺陷类数='))
    dTotal && dTotal.includes('1486') ? ok('看板速览 KPI 总工单=1486', dTotal) : bad('看板速览 KPI 总工单异常', String(dTotal))
    dDef && dDef.includes('886') ? ok('看板速览 KPI 缺陷已归集=886', dDef) : bad('看板速览 KPI 缺陷已归集异常', String(dDef))
    dCls && dCls.includes('19') ? ok('看板速览 KPI 缺陷类数=19', dCls) : bad('看板速览 KPI 缺陷类数异常', String(dCls))
    dashKpi.tops >= 6 ? ok(`看板速览 TOP 缺陷类 ${dashKpi.tops} 项`) : bad('看板速览 TOP 缺陷类不足 6 项', `got=${dashKpi.tops}`)
    // 看板速览 TOP 点击 → 弹出下钻抽屉
    await cdp.clickAt('.complaint-dashboard .mp-overview .mp-top__item')
    const drawerOk = await cdp.waitFor('.el-drawer', 8000)
    drawerOk ? ok('看板速览 TOP 点击弹出工单下钻抽屉') : bad('看板速览 TOP 点击未弹出抽屉')

    // ── 2. 热点投诉：同款速览卡片 ──
    console.log('\n▶ 热点投诉 /complaint-center/hotspots')
    await cdp.goto(`${BASE}/complaint-center/hotspots`)
    const hotOk = await cdp.waitFor('.complaint-hotspots .mp-overview', 25000)
    hotOk ? ok('热点页挂载「主要投诉点速览」卡片') : bad('热点页未挂载速览卡片')
    await sleep(3000)
    const hotTops = await cdp.eval(
      `document.querySelectorAll('.complaint-hotspots .mp-overview .mp-top__item').length`
    ).catch(() => 0)
    hotTops >= 6 ? ok(`热点页速览 TOP 缺陷类 ${hotTops} 项`) : bad('热点页速览 TOP 不足', `got=${hotTops}`)

    // ── 3. 主要投诉点：下钻列 ──
    console.log('\n▶ 主要投诉点 /complaint-center/module-problem')
    await cdp.goto(`${BASE}/complaint-center/module-problem`)
    const mpOk = await cdp.waitFor('.module-problem', 25000)
    mpOk ? ok('主要投诉点页挂载') : bad('主要投诉点页未挂载')
    await sleep(3500)
    const drillBtns = await cdp.eval(`(() => {
      const rows = [...document.querySelectorAll('.module-problem .el-table__row')]
      const hasTicketBtn = rows.some(r => [...r.querySelectorAll('button')].some(b => b.textContent.includes('工单')))
      const hasLedgerBtn = rows.some(r => [...r.querySelectorAll('button')].some(b => b.textContent.includes('问题台账')))
      return { rows: rows.length, hasTicketBtn, hasLedgerBtn }
    })()`).catch(() => ({ rows: 0, hasTicketBtn: false, hasLedgerBtn: false }))
    drillBtns.hasTicketBtn ? ok('主要投诉点主表带「工单」下钻按钮') : bad('主表缺「工单」下钻按钮')
    drillBtns.hasLedgerBtn ? ok('主要投诉点主表带「问题台账」下钻按钮') : bad('主表缺「问题台账」下钻按钮')
    // 点击首行「工单」按钮 → 跳工单明细带过滤
    await cdp.eval(`(() => {
      const row = document.querySelector('.module-problem .el-table__row')
      const btn = [...row.querySelectorAll('button')].find(b => b.textContent.includes('工单'))
      if (btn) btn.click()
      return !!btn
    })()`)
    await sleep(1800)
    const drillUrl = await cdp.eval('location.href')
    drillUrl.includes('module_problem_id=') && drillUrl.includes('/tickets')
      ? ok('点击「工单」跳转工单明细并携带 module_problem_id', drillUrl.replace(BASE, ''))
      : bad('点击「工单」跳转异常', drillUrl)

    // ── 4. 工单明细：过滤 + L2 列 ──
    console.log('\n▶ 工单明细（module_problem_id 下钻）')
    // 显式导航到固定模块（首行点击已验证跳转链路，此处验证过滤数值口径）
    await cdp.goto(`${BASE}/complaint-center/tickets?module_problem_id=MP-BROADBAND-ACT`)
    await sleep(2500)
    const tkOk = await cdp.waitFor('.el-table', 20000)
    tkOk ? ok('工单明细页挂载') : bad('工单明细页未挂载')
    await sleep(2500)
    const tkInfo = await cdp.eval(`(() => {
      const pager = document.querySelector('.complaint-ticket-ledger .el-pagination__total, .el-pagination__total')
      const totalTxt = pager ? pager.textContent : ''
      const mpCells = [...document.querySelectorAll('.complaint-ticket-ledger .el-table__row')]
        .filter(r => r.textContent.includes('MP-') || r.querySelector('.mp-link'))
        .length
      return { totalTxt, mpCells }
    })()`).catch(() => ({ totalTxt: '', mpCells: 0 }))
    tkInfo.totalTxt.includes('86')
      ? ok('下钻过滤 total=86（MP-BROADBAND-ACT 全量）', tkInfo.totalTxt.trim())
      : bad('下钻过滤 total 异常（期望 86）', tkInfo.totalTxt.trim())
    tkInfo.mpCells > 0
      ? ok(`「L2 模块问题」列 ${tkInfo.mpCells}/${20} 行有标签`)
      : bad('「L2 模块问题」列无标签（若后端未重启属预期）')

    // ── 5. 问题台账：定位候选 ──
    console.log('\n▶ 问题台账（module_problem_id 定位候选）')
    await cdp.goto(`${BASE}/complaint-center/problems?module_problem_id=MP-BROADBAND-ACT`)
    const pbOk = await cdp.waitFor('.problem-ledger, .el-tabs', 20000)
    pbOk ? ok('问题台账页挂载') : bad('问题台账页未挂载')
    await sleep(3500)
    const pbInfo = await cdp.eval(`(() => {
      const candTab = [...document.querySelectorAll('.el-tabs__item')]
        .find(t => (t.textContent || '').includes('待确认候选'))
      const candActive = candTab && candTab.classList.contains('is-active')
      const located = [...document.querySelectorAll('.el-tag')]
        .some(t => (t.textContent || '').includes('已定位模块·MP-BROADBAND-ACT'))
      const rows = document.querySelectorAll('.el-table__row').length
      return { candActive, located, rows }
    })()`).catch(() => ({ candActive: false, located: false, rows: 0 }))
    pbInfo.candActive ? ok('自动切到「待确认候选」tab') : bad('未自动切候选 tab')
    pbInfo.located ? ok('显示「已定位模块·MP-BROADBAND-ACT」标签') : bad('未显示定位标签')

    console.log(`\n════════ 结果：${pass} 通过 / ${fail} 失败 ════════`)
    if (failures.length) {
      console.log('失败项：' + failures.join('；'))
      process.exitCode = 1
    }
  } finally {
    try { chrome.kill() } catch {}
  }
}

main().catch((e) => {
  console.error('FATAL:', e.message)
  process.exit(1)
})
