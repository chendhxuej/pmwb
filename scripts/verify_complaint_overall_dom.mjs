/**
 * 客诉「整体投诉全貌」· 真实 DOM 回归（2026-11-11）
 *
 * 验证老大进入页面后第一眼实际看到的内容，而不只是接口数字：
 *   · 整体区常驻在周维度之前、KPI/结论/趋势/三栏全部渲染；
 *   · 异常波动 chips 与实际异常周一致（且不含低基数假信号 W38）；
 *   · 点击任一数字 → 下钻明细数与展示值一致、筛选标签用对字段；
 *   · 周维度 6 个区块仍在，未被新增整体区破坏。
 *
 * 用法：
 *   PMWB_BASE=http://127.0.0.1:8000 PMWB_AUTH_USER=chendh PMWB_AUTH_PW=*** \
 *     node scripts/verify_complaint_overall_dom.mjs
 */
import { existsSync } from 'node:fs'
import { spawn } from 'node:child_process'
import { mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const CHROME = process.env.CHROME_PATH || [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].find(existsSync)
const BASE = process.env.PMWB_BASE || 'http://127.0.0.1:8000'
const PORT = Number(process.env.CDP_PORT || 9371)
const USER = process.env.PMWB_AUTH_USER || 'chendh'
const PW = process.env.PMWB_AUTH_PW || ''

let pass = 0, fail = 0
const failures = []
// 断言签名必须是 (name, cond, extra)；早期写成 (n, e='') 会全部恒 PASS（假绿）。
const ok = (n, cond, e = '') => {
  if (cond) { pass++; console.log(`  PASS  ${n}${e ? '  ' + e : ''}`) }
  else { fail++; failures.push(n); console.log(`  FAIL  ${n}${e ? '  ' + e : ''}`) }
}
const sleep = ms => new Promise(r => setTimeout(r, ms))

class CDP {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map()
    ws.addEventListener('message', ev => {
      const m = JSON.parse(ev.data)
      if (m.id && this.pending.has(m.id)) {
        const { resolve, reject } = this.pending.get(m.id)
        this.pending.delete(m.id)
        m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result)
      }
    })
  }
  send(method, params = {}) {
    const id = ++this.id
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject })
      this.ws.send(JSON.stringify({ id, method, params }))
      setTimeout(() => { if (this.pending.has(id)) { this.pending.delete(id); reject(new Error('CDP timeout ' + method)) } }, 30000)
    })
  }
  async eval(expression) {
    const r = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || 'eval error')
    return r.result.value
  }
  goto(url) { return this.send('Page.navigate', { url }) }
  async waitFor(sel, timeout = 25000) {
    const t0 = Date.now()
    while (Date.now() - t0 < timeout) {
      if (await this.eval(`!!document.querySelector(${JSON.stringify(sel)})`).catch(() => false)) return true
      await sleep(400)
    }
    return false
  }
  async clickAt(sel, idx = 0) {
    const r = await this.eval(`(() => { const e=document.querySelectorAll(${JSON.stringify(sel)})[${idx}]; if(!e)return false; e.click(); return true })()`)
    if (!r) throw new Error('click target not found: ' + sel)
    await sleep(900)
  }
}

async function fetchWsUrl() {
  for (let i = 0; i < 40; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/list`)
      const page = (await res.json()).find(t => t.type === 'page')
      if (page) return page.webSocketDebuggerUrl
    } catch {}
    await sleep(500)
  }
  throw new Error('CDP endpoint not ready')
}

async function login(cdp) {
  await cdp.goto(`${BASE}/login`)
  if (!await cdp.waitFor('.login-card', 20000)) return false
  await sleep(700)
  await cdp.eval(`(() => {
    const inputs = [...document.querySelectorAll('.login-card input')]
    const set = (el, v) => {
      const d = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value')
      d.set.call(el, v); el.dispatchEvent(new Event('input', { bubbles: true }))
    }
    set(inputs[0], ${JSON.stringify(USER)}); set(inputs[1], ${JSON.stringify(PW)})
    return true
  })()`)
  await cdp.clickAt('.login-card .el-button')
  return cdp.waitFor('.main-layout', 25000)
}

const DRAWER_STATE = `(() => {
  const d = [...document.querySelectorAll('.el-drawer')].find(e => e.offsetParent !== null)
  if (!d) return { open: false, total: -1, tags: [] }
  const bar = d.querySelector('.drill-bar')
  const btn = [...(bar ? bar.querySelectorAll('button') : [])].find(b => b.textContent.includes('导出明细'))
  const m = btn ? btn.textContent.match(/(\\d+)\\s*单/) : null
  const tags = [...(bar ? bar.querySelectorAll('.el-tag') : [])].map(t => t.textContent.trim())
  return { open: true, total: m ? Number(m[1]) : -1, tags }
})()`

async function apiJson(path, token) {
  const r = await fetch(BASE + path, { headers: { Authorization: 'Bearer ' + token } })
  return (await r.json()).data
}

// SPA 首次导航偶发落在旧执行上下文，重试导航而不是放宽断言
async function openDashboard(cdp) {
  for (let i = 0; i < 3; i++) {
    await cdp.goto(`${BASE}/complaint-center/dashboard`)
    await sleep(1500)
    if (await cdp.waitFor('.ov-card .pm-stat', 20000)) return true
  }
  return false
}

async function main() {
  const profile = await mkdtemp(join(tmpdir(), 'pmwb-ovdom-'))
  const chrome = spawn(CHROME, [
    `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
    '--no-first-run', '--no-default-browser-check', '--window-size=1680,1100', 'about:blank',
  ], { stdio: 'ignore' })
  try {
    const cdp = new CDP(new WebSocket(await fetchWsUrl()))
    await new Promise((res, rej) => { cdp.ws.addEventListener('open', res, { once: true }); cdp.ws.addEventListener('error', rej, { once: true }) })
    await cdp.send('Page.enable')

    console.log('\n▶ 登录')
    ok('登录并进入主布局', await login(cdp))
    const loginResp = await fetch(`${BASE}/api/v1/auth/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: USER, password: PW }),
    })
    const token = (await loginResp.json()).data.token
    const d = await apiJson('/api/v1/complaint/overall', token)
    const s = d.scope, ts = d.trend_summary, cl = d.closure

    // ── 1. 整体区挂载与位置 ──
    console.log('\n▶ 整体区挂载 / 位置 / KPI')
    ok('看板整体区挂载', await openDashboard(cdp))
    await sleep(2500)
    const pos = await cdp.eval(`(() => {
      const ov = document.querySelector('.ov-card')
      const mp = document.querySelector('.mp-overview')
      const wk = [...document.querySelectorAll('.dashboard-body h3')].map(e => e.textContent.trim())
      if (!ov || !mp) return { order: -1, wk }
      return { order: ov.compareDocumentPosition(mp) & Node.DOCUMENT_POSITION_FOLLOWING ? 1 : -1, wk }
    })()`).catch(() => ({ order: -1, wk: [] }))
    ok('整体区位于周维度内容之前（进入第一眼可见）', pos.order === 1)
    ok('周维度 6 个区块仍在', pos.wk.length >= 5 && pos.wk.some(x => x.includes('本周概览')),
      pos.wk.join(' | ').slice(0, 120))

    const kpi = await cdp.eval(`(() => {
      const cards = [...document.querySelectorAll('.ov-card .pm-stat')]
      const vals = cards.map(c => (c.querySelector('.pm-stat__val')?.textContent || '').replace(/[^0-9.]/g, ''))
      return { n: cards.length, vals, labels: cards.map(c => c.querySelector('.pm-stat__label')?.textContent.trim()) }
    })()`).catch(() => ({ n: 0, vals: [], labels: [] }))
    ok('整体区 KPI 渲染 6 张', kpi.n === 6, `count=${kpi.n}`)
    ok('累计工单 KPI = 接口总量', Number(kpi.vals[0]) === s.total,
      `DOM=${kpi.vals[0]} API=${s.total}`)
    ok('闭环率 KPI = 接口闭环率', Number(kpi.vals[4]) === cl.closed_pct,
      `DOM=${kpi.vals[4]} API=${cl.closed_pct}`)
    ok('未闭环 KPI = 接口未闭环存量', Number(kpi.vals[5]) === cl.open,
      `DOM=${kpi.vals[5]} API=${cl.open}`)
    ok('KPI 文案区分全量口径', kpi.labels.includes('完整周周均') && kpi.labels.includes('覆盖周期'))

    // ── 2. 结论 / 趋势 / 异常波动 ──
    console.log('\n▶ 关键结论 / 趋势 / 异常波动')
    const concl = await cdp.eval(`(() => {
      const rows = [...document.querySelectorAll('.ov-conclusion')]
      return { n: rows.length, text: rows.map(r => r.textContent).join(' '),
               clickable: rows.every(r => r.querySelector('.ov-conclusion__go')) }
    })()`).catch(() => ({ n: 0, text: '', clickable: false }))
    ok('结论摘要渲染 ≥ 10 条', concl.n >= 10, `count=${concl.n}`)
    ok('结论含异常波动 / 闭环 / 进行中周 / 未归类',
      ['异常波动', '闭环率', '进行中', '待自动补跑'].every(k => concl.text.includes(k)))
    ok('每条结论都有下钻入口', concl.clickable)
    ok('结论明确「已回复 ≠ 结单」', concl.text.includes('已回复 ≠ 结单'))

    const chart = await cdp.eval(`(() => ({
      canvas: document.querySelectorAll('.ov-card canvas').length,
      chips: [...document.querySelectorAll('.ov-chip')].map(e => e.textContent.trim()),
    }))()`).catch(() => ({ canvas: 0, chips: [] }))
    ok('周趋势图渲染（echarts canvas）', chart.canvas >= 1, `canvas=${chart.canvas}`)
    const anomalyChips = chart.chips.filter(x => x.includes('突增') || x.includes('骤降'))
    ok('异常波动 chips 数 = 接口 anomaly_cnt', anomalyChips.length === ts.anomaly_cnt,
      `${anomalyChips.length} vs ${ts.anomaly_cnt}`)
    ok('异常 chips 不含低基数假信号 W38', !anomalyChips.some(x => x.includes('2026-W38')),
      anomalyChips.join(' | '))
    ok('异常 chips 含 W43 突增与 W37 骤降',
      anomalyChips.some(x => x.includes('W43') && x.includes('突增')) &&
      anomalyChips.some(x => x.includes('W37') && x.includes('骤降')))
    ok('不完整周 chips 全部标出',
      s.incomplete_weeks.every(w => chart.chips.some(x => x.includes(w) && x.includes('不完整周'))),
      chart.chips.join(' | ').slice(0, 150))

    // ── 3. 三栏内容 ──
    console.log('\n▶ 分类占比 / 高频问题 / 闭环状态')
    const panels = await cdp.eval(`(() => {
      const drift = [...document.querySelectorAll('.ov-drift__row')].map(e => ({
        name: e.querySelector('.ov-drift__name')?.textContent.trim(),
        // 「442 单 / 27.9%」只取第一个数字；模板字符串里正则须写 \\d，否则 JS 吞成 /d+/
        cnt: Number((e.querySelector('.ov-drift__val')?.textContent || '').match(/\\d+/)?.[0] || 0),
      }))
      const top = [...document.querySelectorAll('.ov-top__item')].map(e => ({
        name: e.querySelector('.ov-top__name')?.textContent.trim(),
        cnt: Number((e.querySelector('.ov-top__cnt')?.textContent || '').replace(/[^0-9]/g, '')),
      }))
      const status = [...document.querySelectorAll('.ov-status__row')].map(e =>
        e.querySelector('.ov-status__name')?.textContent.trim())
      const exportBtn = [...document.querySelectorAll('.ov-card button')]
        .some(b => b.textContent.includes('导出全量明细'))
      return { drift, top, status, exportBtn }
    })()`).catch(() => ({ drift: [], top: [], status: [], exportBtn: false }))
    ok('分类占比渲染 5 类', panels.drift.length === d.categories.length,
      `DOM=${panels.drift.length} API=${d.categories.length}`)
    ok('分类 DOM 数字 = 接口 cnt',
      panels.drift.every((x, i) => x.cnt === d.categories[i].cnt),
      panels.drift.map(x => x.cnt).join(','))
    ok('高频问题渲染 8 条', panels.top.length === d.top_problems.length,
      `DOM=${panels.top.length} API=${d.top_problems.length}`)
    ok('高频问题首行 = 接口累计单量（非本周）',
      panels.top[0]?.cnt === d.top_problems[0].cnt,
      `DOM=${panels.top[0]?.cnt} API=${d.top_problems[0].cnt}`)
    ok('高频问题首行展示跨周期信息',
      (await cdp.eval(`document.querySelector('.ov-top__meta')?.textContent || ''`)
        .catch(() => '')).includes('持续'))
    ok('处理状态渲染 4 种', panels.status.length === cl.status_breakdown.length)
    ok('整体区有「导出全量明细」按钮', panels.exportBtn)

    // ── 4. 点击下钻：展示 = 下钻明细 ──
    console.log('\n▶ 点击下钻（展示 = 明细数）')
    const a0 = ts.anomaly_weeks[0]
    await cdp.clickAt('.ov-chip', 0)
    await sleep(1400)
    const dA = await cdp.eval(DRAWER_STATE).catch(() => ({ open: false, total: -1, tags: [] }))
    ok('点击异常周 chip 弹出下钻抽屉', dA.open)
    ok('异常周下钻明细数 = 该周单量', dA.total === a0.total,
      `显示 ${a0.total} / 下钻 ${dA.total}`)
    ok('异常周下钻条件带周', dA.tags.some(t => t.startsWith('周：') && t.includes(a0.week)),
      dA.tags.join(' | ').slice(0, 140))

    await openDashboard(cdp)
    await sleep(2000)
    await cdp.clickAt('.ov-top__item', 0)
    await sleep(1400)
    const dT = await cdp.eval(DRAWER_STATE).catch(() => ({ open: false, total: -1, tags: [] }))
    ok('点击高频问题弹出下钻抽屉', dT.open)
    ok('高频问题下钻明细数 = 累计单量', dT.total === d.top_problems[0].cnt,
      `显示 ${d.top_problems[0].cnt} / 下钻 ${dT.total}`)
    ok('高频问题下钻用模块问题锚',
      dT.tags.some(t => t.startsWith('模块问题：') && t.includes(d.top_problems[0].module_problem_id)),
      dT.tags.join(' | ').slice(0, 140))

    await openDashboard(cdp)
    await sleep(2000)
    const statusIdx = cl.status_breakdown.findIndex(x => x.name === '已回复')
    await cdp.clickAt('.ov-status__row', statusIdx)
    await sleep(1400)
    const dS = await cdp.eval(DRAWER_STATE).catch(() => ({ open: false, total: -1, tags: [] }))
    ok('点击「已回复」弹出下钻抽屉', dS.open)
    ok('已回复下钻明细数 = 展示数', dS.total === cl.status_breakdown[statusIdx].cnt,
      `显示 ${cl.status_breakdown[statusIdx].cnt} / 下钻 ${dS.total}`)
    ok('状态下钻标签用「处理状态」', dS.tags.some(t => t.startsWith('处理状态：')),
      dS.tags.join(' | ').slice(0, 140))

    // ── 5. 收起/展开 ──
    console.log('\n▶ 收起 / 展开')
    await openDashboard(cdp)
    await sleep(1800)
    const collapseBtn = await cdp.eval(`(() => {
      const b = [...document.querySelectorAll('.ov-card button')].find(x => x.textContent.trim() === '收起')
      if (!b) return false
      b.click(); return true
    })()`).catch(() => false)
    await sleep(600)
    const hidden = await cdp.eval(`(() => {
      const b = document.querySelector('.ov-card .card-body')
      return b ? getComputedStyle(b).display === 'none' : false
    })()`).catch(() => false)
    ok('收起按钮可点击', collapseBtn)
    ok('收起后整体区内容隐藏（不干扰周维度浏览）', hidden)

    console.log('\n' + '════════════════════════════════════════════')
    console.log(`════════ 结果：${pass} 通过 / ${fail} 失败 ════════`)
    if (failures.length) { failures.forEach(n => console.log('  ✗ ' + n)); console.log('HAS_FAILURE') }
    else console.log('ALL_PASS')
  } finally {
    chrome.kill()
  }
  if (fail) process.exitCode = 1
}

main().catch(e => { console.error(e); process.exitCode = 1 })
