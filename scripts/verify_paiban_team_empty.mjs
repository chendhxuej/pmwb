/**
 * 排版管理 · 团队跟踪空态引导真态验证（2026-11-19）
 * 场景：版本计划已配但主行 0 条时，团队页应显式引导去「排版跟踪→候选池纳入」。
 * 真实登录 + 真 API + 真 Chrome DOM，不 mock、不写业务数据。
 * 铁律：ok(name, cond, extra)，断言必须能真失败。
 * 用法： node scripts/verify_paiban_team_empty.mjs
 */
import { existsSync } from 'node:fs'
import { spawn } from 'node:child_process'
import { mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const CHROME = ['C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(existsSync)
const BASE = process.env.PMWB_BASE || 'http://127.0.0.1:8000'
const PORT = Number(process.env.CDP_PORT || 9408)
const sleep = ms => new Promise(r => setTimeout(r, ms))
let pass = 0, fail = 0
const ok = (n, c, e = '') => { if (c) { pass++; console.log(`  PASS  ${n}${e ? '  ' + e : ''}`) } else { fail++; console.log(`  FAIL  ${n}${e ? '  ' + e : ''}`) } }

class CDP {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.p = new Map()
    ws.addEventListener('message', ev => {
      const m = JSON.parse(ev.data)
      if (m.id && this.p.has(m.id)) {
        const { resolve: r, reject: j } = this.p.get(m.id); this.p.delete(m.id)
        m.error ? j(new Error(JSON.stringify(m.error))) : r(m.result)
      }
    })
  }
  send(method, params = {}) {
    const id = ++this.id
    return new Promise((r, j) => {
      this.p.set(id, { resolve: r, reject: j }); this.ws.send(JSON.stringify({ id, method, params }))
      setTimeout(() => { if (this.p.has(id)) { this.p.delete(id); j(new Error('timeout ' + method)) } }, 30000)
    })
  }
  async eval(expression) {
    const r = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description)
    return r.result.value
  }
  goto(url) { return this.send('Page.navigate', { url }) }
  async waitFor(sel, t = 20000) {
    const t0 = Date.now()
    while (Date.now() - t0 < t) {
      if (await this.eval(`!!document.querySelector(${JSON.stringify(sel)})`).catch(() => false)) return true
      await sleep(400)
    }
    return false
  }
}
async function wsurl() {
  for (let i = 0; i < 40; i++) {
    try { const r = await fetch(`http://127.0.0.1:${PORT}/json/list`); const p = (await r.json()).find(x => x.type === 'page'); if (p?.webSocketDebuggerUrl) return p.webSocketDebuggerUrl } catch (_) {}
    await sleep(300)
  }
  throw new Error('cdp not ready')
}

const lr = await fetch(`${BASE}/api/v1/auth/login`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: 'chendh', password: 'Chenxue520' }),
})
const token = (await lr.json()).data.token
const prof = await mkdtemp(join(tmpdir(), 'pbteam-'))
const ch = spawn(CHROME, [`--remote-debugging-port=${PORT}`, `--user-data-dir=${prof}`,
  '--no-first-run', '--headless=new', '--window-size=1600,1000', 'about:blank'], { stdio: 'ignore' })
try {
  const ws = new WebSocket(await wsurl()); const c = new CDP(ws)
  await new Promise((r, j) => { ws.addEventListener('open', r, { once: true }); ws.addEventListener('error', j, { once: true }) })
  await c.send('Page.enable'); await c.send('Runtime.enable')
  await c.goto(`${BASE}/`); await sleep(900)
  await c.eval(`localStorage.setItem('pmwb_token',${JSON.stringify(token)});'ok'`)

  // SPA 首导航偶发旧上下文：用带 ?v= 的新 URL + 多轮重试，缓存清除
  let ready = false
  for (let i = 0; i < 4 && !ready; i++) {
    await c.goto(`${BASE}/paiban/teams?v=empty-${Date.now()}-${i}`)
    ready = await c.waitFor('.pb-page', 20000)
    if (!ready) { await sleep(1000); await c.eval(`location.reload();'ok'`).catch(() => {}); await sleep(800) }
  }
  ok('1 团队跟踪页渲染', ready, `url=${await c.eval('location.href').catch(()=>'')}`)
  await sleep(1800) // 等接口数据回来（waitFor 容器只证明挂载）
  const txt = (await c.eval(`document.body.innerText`)) || ''
  if (!ready) console.log('  DEBUG body:', txt.slice(0, 600))
  ok('2 空态提示「尚未纳入任何工单」出现', txt.includes('尚未纳入任何工单'))
  ok('3 提示指向「排版跟踪」', txt.includes('排版跟踪'))
  ok('4 提示指向「候选池」', txt.includes('候选池'))
  ok('5 说明「不会自动抓取需求和 BUG」', txt.includes('不会自动抓取'))
  ok('6 版本下拉有已配计划', txt.includes('11月26号统一版本'))
  console.log(`\n=== PASS ${pass} / FAIL ${fail} ===`)
  if (fail) process.exitCode = 1
} finally { try { ch.kill() } catch (_) {} }
