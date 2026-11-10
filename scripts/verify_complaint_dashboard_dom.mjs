/**
 * 投诉现状看板 · 真实 DOM 口径回归（2026-11-10）
 *
 * 老大反馈的两处「数字对不上」，在真实页面上逐项核对：
 *   1. TOP 缺陷类：卡片显示的单量严格降序、与接口 week_cnt 一致、点击下钻数量一致；
 *   2. 已知问题（按本周命中单量）：表格命中数 == 下钻抽屉明细数，且筛选标签用对字段。
 *
 * 用法：
 *   PMWB_BASE=http://127.0.0.1:8000 PMWB_AUTH_USER=chendh PMWB_AUTH_PW=*** \
 *     node scripts/verify_complaint_dashboard_dom.mjs
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
const PORT = Number(process.env.CDP_PORT || 9368)
const USER = process.env.PMWB_AUTH_USER || 'chendh'
const PW = process.env.PMWB_AUTH_PW || ''

let pass = 0, fail = 0
const failures = []
// 注意：ok 必须收 (name, cond, extra)。早期写成 (n, e='') 时 cond 被当成说明文字，
// 所有断言恒 PASS（假绿）——2026-11-10 自查踩过，勿再简化签名。
const ok = (n, cond, e = '') => {
  if (cond) { pass++; console.log(`  PASS  ${n}${e ? '  ' + e : ''}`) }
  else { fail++; failures.push(n); console.log(`  FAIL  ${n}${e ? '  ' + e : ''}`) }
}
const bad = (n, e = '') => { fail++; failures.push(n); console.log(`  FAIL  ${n}${e ? '  ' + e : ''}`) }
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

// 抽屉里的「导出明细（N 单）」是 total 的响应式回显，比标题更可靠
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

// SPA 首次导航偶发落在旧执行上下文，waitFor 会空转；重试导航而不是放宽断言
async function openDashboard(cdp) {
  for (let i = 0; i < 3; i++) {
    await cdp.goto(`${BASE}/complaint-center/dashboard`)
    await sleep(1500)
    if (await cdp.waitFor('.mp-top__item', 20000)) return true
  }
  return false
}

async function main() {
  const profile = await mkdtemp(join(tmpdir(), 'pmwb-dashdom-'))
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

    // ── 1. TOP 缺陷类 ──
    console.log('\n▶ TOP 缺陷类（显示 / 排序 / 下钻）')
    ok('看板 TOP 卡片挂载', await openDashboard(cdp))
    await sleep(2500)
    const top = await cdp.eval(`(() => {
      const title = document.querySelector('.mp-top__title')?.textContent.trim() || ''
      const items = [...document.querySelectorAll('.mp-top__item')].map(e => ({
        rank: Number(e.querySelector('.mp-rank')?.textContent.trim()),
        name: e.querySelector('.mp-name')?.textContent.trim() || '',
        cnt: Number((e.querySelector('.mp-cnt')?.textContent || '').replace(/[^0-9]/g, '')),
      }))
      return { title, items }
    })()`).catch(() => ({ title: '', items: [] }))
    const wk = (top.title.match(/20\d\d-W\d\d/) || [])[0] || ''
    ok('标题标注所选周', !!wk, wk)
    ok('TOP 渲染 6 项', top.items.length === 6, `count=${top.items.length}`)
    const cnts = top.items.map(x => x.cnt)
    ok('单量严格降序（老大反馈点 1）', cnts.length > 0 && cnts.every((v, i) => i === 0 || cnts[i - 1] >= v), cnts.join(' > '))

    const cls = await apiJson(`/api/v1/complaint/module-problem/classes?include_consult=false&week=${encodeURIComponent(wk)}`, token)
    const expect = (cls.items || []).filter(x => (x.week_cnt || 0) > 0).slice(0, 6).map(x => x.week_cnt)
    ok('DOM 单量 = 接口 week_cnt', JSON.stringify(cnts) === JSON.stringify(expect),
      `DOM=${cnts.join(',')} API=${expect.join(',')}`)
    ok('stat_week 与页面周一致', (cls.items || []).every(x => x.stat_week === wk), wk)

    await cdp.clickAt('.mp-top__item')
    const d1 = await cdp.eval(DRAWER_STATE).catch(() => ({ open: false, total: -1, tags: [] }))
    ok('点击 TOP 项弹出下钻抽屉', d1.open)
    ok('下钻明细数 = 卡片显示单量', d1.total === cnts[0], `显示 ${cnts[0]} / 下钻 ${d1.total}`)
    ok('下钻条件带周（不再拉全周期）', d1.tags.some(t => t.startsWith('周：') && t.includes(wk)),
      d1.tags.join(' | ').slice(0, 120))

    // ── 2. 已知问题表 ──
    console.log('\n▶ 已知问题（本周命中 = 下钻明细）')
    await openDashboard(cdp)
    await sleep(2800)
    const rowInfo = await cdp.eval(`(() => {
      const h = [...document.querySelectorAll('.sub-h')].find(e => e.textContent.includes('已知问题（按本周命中单量）'))
      const table = h && h.nextElementSibling
      const tr = table && table.querySelector('.el-table__body-wrapper tbody tr')
      if (!tr) return null
      const td = [...tr.querySelectorAll('td')]
      return {
        no: td[0]?.textContent.trim() || '',
        cnt: Number((td[3]?.textContent || '').replace(/[^0-9]/g, '')),
        hasBtn: !!td[5]?.querySelector('button'),
      }
    })()`).catch(() => null)
    ok('已知问题表定位到首行', !!rowInfo, rowInfo ? `${rowInfo.no} 命中 ${rowInfo.cnt}` : 'null')

    const clicked = await cdp.eval(`(() => {
      const h = [...document.querySelectorAll('.sub-h')].find(e => e.textContent.includes('已知问题（按本周命中单量）'))
      const table = h && h.nextElementSibling
      const tr = table && table.querySelector('.el-table__body-wrapper tbody tr')
      const btn = tr && [...tr.querySelectorAll('td')][5]?.querySelector('button')
      if (!btn) return false
      btn.click(); return true
    })()`).catch(() => false)
    ok('点击该行「下钻」', clicked)
    await sleep(1400)
    const d2 = await cdp.eval(DRAWER_STATE).catch(() => ({ open: false, total: -1, tags: [] }))
    ok('已知问题下钻抽屉弹出', d2.open)
    ok('下钻明细数 = 本周命中数（老大反馈点 2）', rowInfo && d2.total === rowInfo.cnt,
      `命中 ${rowInfo?.cnt ?? '?'} / 下钻 ${d2.total}`)
    ok('下钻用 known_problem_no 而非 problem_no',
      d2.tags.some(t => t.startsWith('已知问题：') && rowInfo && t.includes(rowInfo.no)),
      d2.tags.join(' | ').slice(0, 160))
    ok('下钻带 known_flag=1', d2.tags.some(t => t.startsWith('已知/新增：1')),
      d2.tags.join(' | ').slice(0, 160))

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
