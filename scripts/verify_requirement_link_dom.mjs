/**
 * 需求与交付：关联工单卡片 + 提出人编辑入口 真实 DOM 回归
 *
 * 用法： node scripts/verify_requirement_link_dom.mjs
 * 覆盖： PMWB_BASE=http://127.0.0.1:8010  CDP_PORT=9373  CHROME_PATH=...
 * 说明：需一个 AUTH_REQUIRED=false 的实例（8010），不打断 8000。
 * 铁律：ok(name, cond, extra)；断言必须能真失败。
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
const BASE = process.env.PMWB_BASE || 'http://127.0.0.1:8010'
const PORT = Number(process.env.CDP_PORT || 9373)

let pass = 0, fail = 0
const ok = (n, cond, e = '') => {
  if (cond) { pass++; console.log(`  PASS  ${n}${e ? '  ' + e : ''}`) }
  else { fail++; console.log(`  FAIL  ${n}${e ? '  ' + e : ''}`) }
}
const sleep = ms => new Promise(r => setTimeout(r, ms))

class CDP {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map()
    ws.addEventListener('message', ev => {
      const m = JSON.parse(ev.data)
      if (m.id && this.pending.has(m.id)) {
        const { resolve: res, reject: rej } = this.pending.get(m.id)
        this.pending.delete(m.id)
        m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result)
      }
    })
  }
  send(method, params = {}) {
    const id = ++this.id
    return new Promise((res, rej) => {
      this.pending.set(id, { resolve: res, reject: rej })
      this.ws.send(JSON.stringify({ id, method, params }))
      setTimeout(() => { if (this.pending.has(id)) { this.pending.delete(id); rej(new Error('CDP timeout ' + method)) } }, 30000)
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
}
async function poll(cdp, expr, timeout = 20000) {
  const t0 = Date.now()
  while (Date.now() - t0 < timeout) {
    if (await cdp.eval(expr).catch(() => false)) return true
    await sleep(300)
  }
  return false
}
async function fetchWsUrl() {
  for (let i = 0; i < 40; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/list`)
      const p = (await res.json()).find(x => x.type === 'page')
      if (p?.webSocketDebuggerUrl) return p.webSocketDebuggerUrl
    } catch (_) { /* chrome 尚未就绪 */ }
    await sleep(300)
  }
  throw new Error('CDP endpoint not ready')
}

async function main() {
  if (!CHROME) throw new Error('未找到 Chrome / Edge')
  const profile = await mkdtemp(join(tmpdir(), 'pmwb-reqlink-'))
  const chrome = spawn(CHROME, [
    `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
    '--no-first-run', '--no-default-browser-check', '--headless=new',
    '--window-size=1680,1100', 'about:blank',
  ], { stdio: 'ignore' })
  let cdp
  try {
    const ws = new WebSocket(await fetchWsUrl())
    cdp = new CDP(ws)
    await new Promise((res, rej) => { ws.addEventListener('open', res, { once: true }); ws.addEventListener('error', rej, { once: true }) })
    await cdp.send('Page.enable')
    await cdp.send('Runtime.enable')

    // 先证明断言能真失败（不存在文案不应被判为存在）
    ok('R0 断言框架可真失败', !(await poll(cdp, `document.body.innerText.includes('__PMWB_NOT_EXIST__')`, 300)))

    let ready = false
    for (let i = 0; i < 2 && !ready; i++) {
      await cdp.goto(`${BASE}/requirement-delivery?v=linkcheck`)
      ready = await cdp.waitFor('.el-table__row', 25000)
      if (!ready) await sleep(800)
    }
    ok('R1 需求列表真实渲染', ready)
    const rows = await cdp.eval('document.querySelectorAll(".el-table__row").length').catch(() => 0)
    ok('R2 有真实数据行', rows > 0, `rows=${rows}`)

    await cdp.eval('document.querySelector(".el-table__row")?.click(); true')
    const drawer = `[...document.querySelectorAll('.el-drawer')].find(d => d.offsetParent !== null && d.innerText.includes('需求采集'))`
    const opened = await poll(cdp, `!!${drawer}`, 20000)
    ok('R3 点击行打开工作流抽屉', opened)

    if (opened) {
      ok('R4 关联工单卡片真实渲染', await cdp.eval(`!!${drawer} && ${drawer}.innerText.includes('关联需求工单（1:1 单向，状态全量镜像到从工单）')`))
      ok('R5 关联搜索框存在', await cdp.eval(`!!${drawer} && ${drawer}.querySelectorAll('.el-select').length > 0`))
      const hasProposer = await cdp.eval(`!!${drawer} && [...${drawer}.querySelectorAll('.el-form-item__label')].some(l => l.innerText.includes('提出人'))`)
      ok('R6 提出人可编辑入口存在', hasProposer)
      ok('R7 关联状态区已渲染（未关联/当前关联二选一）', await cdp.eval(`!!${drawer} && (${drawer}.innerText.includes('未关联') || ${drawer}.innerText.includes('当前关联：'))`))
    }
    console.log(`\n=== requirement-link DOM: ${pass} PASS / ${fail} FAIL ===`)
    if (fail) process.exitCode = 1
  } finally {
    try { cdp?.ws.close() } catch (_) { /* ignore */ }
    chrome.kill()
  }
}

main().catch(e => { console.error(e); process.exitCode = 1 })
