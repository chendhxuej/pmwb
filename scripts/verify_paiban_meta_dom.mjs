/**
 * 排版管理 · 版本计划登记弹窗「字典转译」真态回归（2026-11-19）
 *
 * 背景：老大反馈登记弹窗显示 regular / draft / open 英文原值，且看不到「适用范围」的
 * 统一默认 / 指定系统选项。根因指向 /paiban/meta 字典在浏览器侧未加载成功。
 * 本脚本用真实登录 token + 真实 API（不 mock），验证弹窗在拿到字典后是否正确转译：
 *   - 适用范围 radio 出现「统一默认 / 指定系统」（即支持个性化系统版本计划）
 *   - 版本类型 / 计划状态 / 准入模式显示中文 label，而非英文 value
 *
 * 铁律：ok(name, cond, extra)，断言必须能真失败；不写真实业务数据。
 * 用法： node scripts/verify_paiban_meta_dom.mjs
 * 可覆盖： PMWB_BASE=http://127.0.0.1:8000  CDP_PORT=9399  CHROME_PATH=...
 */
import { existsSync } from 'node:fs'
import { spawn } from 'node:child_process'
import { mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const CHROME = process.env.CHROME_PATH || [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].find(existsSync)
const BASE = process.env.PMWB_BASE || 'http://127.0.0.1:8000'
const PORT = Number(process.env.CDP_PORT || 9399)
const USER = process.env.PMWB_USER || 'chendh'
const PASS = process.env.PMWB_PASS || 'Chenxue520'

let pass = 0, fail = 0
const failures = []
const ok = (n, cond, e = '') => {
  if (cond) { pass++; console.log(`  PASS  ${n}${e ? '  ' + e : ''}`) }
  else { fail++; failures.push(n); console.log(`  FAIL  ${n}${e ? '  ' + e : ''}`) }
}
const sleep = ms => new Promise(r => setTimeout(r, ms))

class CDP {
  constructor(ws, onEvent) {
    this.ws = ws; this.id = 0; this.pending = new Map()
    ws.addEventListener('message', ev => {
      const m = JSON.parse(ev.data)
      if (m.method && onEvent) { onEvent(m); return }
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
  console.log('\n=== 0 真实 API 前置：登录 + 字典返回中文 ===')
  const lr = await fetch(`${BASE}/api/v1/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: USER, password: PASS }),
  })
  const lj = await lr.json()
  const token = lj?.data?.token || ''
  ok('0.1 登录成功拿到 token', !!token, `len=${token.length}`)
  const metaR = await fetch(`${BASE}/api/v1/paiban/meta`, { headers: { Authorization: `Bearer ${token}` } })
  const metaJ = await metaR.json()
  const md = metaJ?.data || {}
  ok('0.2 meta.version_types 为中文', (md.version_types || []).some(x => x.label === '常规版'))
  ok('0.3 meta 含统一默认/指定系统两种范围',
    (md.scope_types || []).some(x => x.value === 'default') && (md.scope_types || []).some(x => x.value === 'system'))

  if (!CHROME) throw new Error('未找到 Chrome / Edge')
  const profile = await mkdtemp(join(tmpdir(), 'pmwb-pbmeta-'))
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

    // 注入真实 token（先落到首页域，再跳版本计划页）
    await cdp.goto(`${BASE}/`)
    await sleep(900)
    await cdp.eval(`localStorage.setItem('pmwb_token', ${JSON.stringify(token)}); 'ok'`)

    let ready = false
    for (let i = 0; i < 2 && !ready; i++) {
      await cdp.goto(`${BASE}/paiban/versions?v=metacheck-${Date.now()}`)
      ready = await cdp.waitFor('.pb-version', 20000)
      if (!ready) await sleep(800)
    }
    ok('1.1 版本计划页真实渲染', ready)

    // 字典就绪：登记按钮未禁用（metaReady）；弹窗 radio 只能在弹窗打开后判断
    const btnReady = await cdp.eval(`(() => {
      const b = [...document.querySelectorAll('button')].find(x => x.textContent.includes('登记版本计划'));
      return b ? !b.disabled : false;
    })()`)
    ok('1.2 字典就绪后登记按钮可用（metaReady）', btnReady === true)

    // 打开登记弹窗
    const clicked = await cdp.eval(`(() => {
      const b = [...document.querySelectorAll('button')].find(x => x.textContent.includes('登记版本计划'));
      if (!b) return false; b.click(); return true;
    })()`)
    ok('1.3 点击「登记版本计划」', clicked === true)
    await cdp.waitFor('.el-dialog', 15000)
    await sleep(500)

    const dlg = await cdp.eval(`(() => {
      const d = [...document.querySelectorAll('.el-dialog')].find(x => x.offsetParent !== null || getComputedStyle(x).display !== 'none');
      return d ? d.innerText : '';
    })()`)
    const scope = await cdp.eval(`[...document.querySelectorAll('.el-dialog .el-radio')].map(x=>x.innerText.trim()).filter(Boolean).join('|')`)
    const selects = await cdp.eval(`[...document.querySelectorAll('.el-dialog .el-select')].map(x=>x.innerText.trim()).filter(Boolean).join(' | ')`)

    ok('2.1 适用范围含「统一默认」', scope.includes('统一默认'), `scope=${scope}`)
    ok('2.2 适用范围含「指定系统」（个性化系统版本计划）', scope.includes('指定系统'), `scope=${scope}`)
    ok('2.3 弹窗无裸英文版本类型 regular', !/\bregular\b/.test(dlg), '')
    ok('2.4 弹窗无裸英文计划状态 draft', !/\bdraft\b/.test(dlg), '')
    ok('2.5 弹窗无裸英文准入模式 open', !/\bopen\b/.test(dlg), '')
    ok('2.6 弹窗出现中文「拟定」', dlg.includes('拟定'))
    ok('2.7 弹窗出现中文「常规版」', dlg.includes('常规版'))
    ok('2.8 弹窗出现中文「开放」', dlg.includes('开放'))
    ok('2.9 适用范围有个性化说明（指定系统 = 个性化版本计划）', dlg.includes('个性化版本计划'))
    const defaultChecked = await cdp.eval(`(() => {
      const r = [...document.querySelectorAll('.el-dialog .el-radio')].find(x => x.innerText.includes('统一默认'));
      return r ? (r.classList.contains('is-checked') || !!r.querySelector('[aria-checked="true"],.el-radio__input.is-checked')) : false;
    })()`)
    ok('2.10 新登记默认选中「统一默认」', defaultChecked === true, `checked=${defaultChecked}`)
    console.log(`\n  [debug] selects = ${selects}`)

    // === 3 降级态：字典加载失败时入口锁定，不出现英文原值弹窗 ===
    console.log('\n=== 3 降级态：/paiban/meta 失败时登记入口锁定 ===')
    await cdp.send('Fetch.enable', { patterns: [{ urlPattern: '*api/v1/paiban/meta*', requestStage: 'Request' }] })
    const dlgState = { served: false }
    // 注册一次性的失败响应处理（用 send 的并行 listener）
    const ws2Handler = async (m) => {
      if (m.method !== 'Fetch.requestPaused') return
      const body = Buffer.from(JSON.stringify({ code: 500, message: 'mock meta down', data: null })).toString('base64')
      await cdp.send('Fetch.fulfillRequest', {
        requestId: m.params.requestId, responseCode: 200,
        responseHeaders: [{ name: 'Content-Type', value: 'application/json; charset=utf-8' }],
        body,
      }).catch(() => {})
      dlgState.served = true
    }
    cdp.ws.addEventListener('message', ev => { const m = JSON.parse(ev.data); ws2Handler(m).catch(() => {}) })
    await cdp.goto(`${BASE}/paiban/versions?v=metadown-${Date.now()}`)
    await sleep(2500)
    const degraded = await cdp.eval(`(() => {
      const b = [...document.querySelectorAll('button')].find(x => x.textContent.includes('登记版本计划'));
      const alert = [...document.querySelectorAll('.el-alert')].some(x => x.innerText.includes('字典加载失败'));
      return { disabled: b ? b.disabled : null, alert };
    })()`)
    ok('3.1 字典失败时提示「字典加载失败」', degraded.alert === true, `alert=${degraded.alert}`)
    ok('3.2 字典失败时登记按钮锁定', degraded.disabled === true, `disabled=${degraded.disabled}`)
    await cdp.send('Fetch.disable').catch(() => {})
  } finally {
    try { chrome.kill() } catch (_) {}
  }

  console.log(`\n=== 汇总：PASS ${pass} / FAIL ${fail} ===`)
  if (fail) { console.log('FAIL 项：' + failures.join('、')); process.exitCode = 1 }
}
main().catch(e => { console.error('ERR', e); process.exitCode = 1 })
