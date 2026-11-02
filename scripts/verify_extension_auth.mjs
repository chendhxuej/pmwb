/**
 * verify_extension_auth.mjs —— 需求提取插件 × PMWB JWT 鉴权 真实浏览器回归
 *
 * 场景：PMWB 开启 AUTH_REQUIRED 后，插件 popup 直连 127.0.0.1:8000 全部 401。
 * 修复：popup.js 注入 fetch 包装（自动登录 + Bearer 注入 + 401 重试）。
 *
 * 验证方式：真实 Chrome 加载 popup/popup.html（file:// + chrome.* 桩 + 禁 CORS），
 * 断言：① 自动登录成功 ② /plugins/contacts 带 token 拿到真实数据
 *       ③ /plugins/health 200 ④ 未配置凭据时 401 文案可读（引导到设置）
 *
 * 用法：node scripts/verify_extension_auth.mjs [BASE]
 *   BASE 默认 http://127.0.0.1:8000（PMWB_BASE 环境变量可覆盖）
 */
import { existsSync } from 'node:fs'
import { spawn } from 'node:child_process'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const BASE = process.env.PMWB_BASE || 'http://127.0.0.1:8000'
const USER = process.env.PMWB_AUTH_USER || 'chendh'
const PASS = process.env.PMWB_AUTH_PW || 'Chenxue520'
const POPUP_URL = 'file:///D:/' + encodeURIComponent('项目') + '/%E4%B8%AA%E4%BA%BA%E5%B7%A5%E4%BD%9C%E5%8F%B0%E7%B3%BB%E7%BB%9F/extension/popup/popup.html'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

let pass = 0
let fail = 0
const ok = (name) => { pass++; console.log(`  ✅ ${name}`) }
const bad = (name, detail) => { fail++; console.log(`  ❌ ${name} — ${detail}`) }

// ── chrome.* 桩：在页面脚本运行前注入 ──
const CHROME_STUB = `
window.__pmwbStore = {
  pmwb_auth: { username: ${JSON.stringify(USER)}, password: ${JSON.stringify(PASS)} },
};
window.chrome = {
  storage: {
    local: {
      async get(keys) {
        const out = {};
        if (typeof keys === 'string') keys = [keys];
        else if (!Array.isArray(keys)) keys = Object.keys(keys || {});
        for (const k of keys) if (k in window.__pmwbStore) out[k] = window.__pmwbStore[k];
        return out;
      },
      async set(obj) { Object.assign(window.__pmwbStore, obj); },
      async remove(keys) {
        for (const k of [].concat(keys)) delete window.__pmwbStore[k];
      },
    },
  },
  runtime: { getURL: (p) => 'chrome-extension://stub/' + p },
  tabs: { async query() { return [{ url: 'http://dft.js.cmc:32101/ai-dmp/workspace/tasks?userType=1' }] } },
};
true;
`

async function main() {
  const CHROME = [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  ].find(existsSync)
  if (!CHROME) throw new Error('Chrome/Edge not found')

  const profile = await mkdtemp(join(tmpdir(), 'pmwb-ext-'))
  const chrome = spawn(CHROME, [
    '--remote-debugging-port=9345',
    `--user-data-dir=${profile}`,
    '--no-first-run',
    '--disable-web-security',   // file:// → 127.0.0.1 属跨源，仅本地测试用
    '--disable-features=BlockInsecurePrivateNetworkRequests',
    'about:blank',
  ], { stdio: 'ignore' })

  try {
    let wsUrl
    for (let i = 0; i < 40; i++) {
      try {
        const targets = await (await fetch('http://127.0.0.1:9345/json/list')).json()
        const page = targets.find((x) => x.type === 'page')
        if (page) { wsUrl = page.webSocketDebuggerUrl; break }
      } catch {}
      await sleep(400)
    }
    if (!wsUrl) throw new Error('CDP not reachable')

    const ws = new WebSocket(wsUrl)
    await new Promise((res, rej) => {
      ws.addEventListener('open', res, { once: true })
      ws.addEventListener('error', rej, { once: true })
    })
    let id = 0
    const pend = new Map()
    ws.addEventListener('message', (ev) => {
      const m = JSON.parse(ev.data)
      if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id) }
    })
    const send = (method, params = {}) => new Promise((r) => {
      const i = ++id
      pend.set(i, r)
      ws.send(JSON.stringify({ id: i, method, params }))
    })
    const evalp = async (expr) => {
      const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true })
      if (r.result?.exceptionDetails) throw new Error('page eval error: ' + JSON.stringify(r.result.exceptionDetails.exception?.description || '').slice(0, 300))
      return r.result?.result?.value
    }

    await send('Page.enable')
    await send('Page.addScriptToEvaluateOnNewDocument', { source: CHROME_STUB })
    await send('Page.navigate', { url: POPUP_URL })
    // 等 popup 初始化（loadPmwbAuth → loadContacts 全链路）
    await sleep(6000)

    /* ── 1. 页面加载与桩生效 ── */
    const env = await evalp(`(() => ({
      hasChrome: typeof chrome !== 'undefined' && !!chrome.storage,
      hasCrypto: typeof encrypt === 'function' && typeof decrypt === 'function',
      contactsCached: Array.isArray(window._cachedContacts) ? window._cachedContacts.length : -1,
      contactsFromDb: window._contactsFromDb === true,
    }))()`)
    env.hasChrome ? ok('chrome.* 桩注入生效') : bad('chrome.* 桩', JSON.stringify(env))
    env.hasCrypto ? ok('popup.html 脚本加载完整（encrypt/decrypt 就绪）') : bad('popup 脚本', JSON.stringify(env))

    /* ── 2. 自动登录 + token 注入： contacts ── */
    const r2 = await evalp(`(async () => {
      const resp = await fetch('http://127.0.0.1:8000/api/v1/plugins/contacts', { signal: AbortSignal.timeout(10000) })
      const data = await resp.json()
      return { status: resp.status, success: data.success, count: (data.contacts || []).length, err: data.error || '' }
    })()`)
    r2.status === 200 && r2.success === true && r2.count > 0
      ? ok(`自动登录 + token 注入生效（contacts ${r2.count} 人）`)
      : bad('contacts 拉取', JSON.stringify(r2))

    /* ── 3. health 带鉴权 ── */
    const r3 = await evalp(`(async () => {
      const resp = await fetch('http://127.0.0.1:8000/api/v1/plugins/health', { signal: AbortSignal.timeout(8000) })
      const data = await resp.json()
      return { status: resp.status, st: data.status }
    })()`)
    r3.status === 200 && r3.st === 'ok' ? ok('/plugins/health 鉴权后正常') : bad('health', JSON.stringify(r3))

    /* ── 4. token 已缓存（登录只发生一次）── */
    const r4 = await evalp(`(() => {
      const t = window.__pmwbStore.pmwb_jwt
      return { cached: !!(t && t.token && t.exp > Date.now()) }
    })()`)
    r4.cached ? ok('token 已缓存（12h 内免重复登录）') : bad('token 缓存', JSON.stringify(r4))

    /* ── 5. 未配置凭据场景：清掉凭据后请求 → 401 + 引导文案 ── */
    const r5 = await evalp(`(async () => {
      delete window.__pmwbStore.pmwb_auth
      delete window.__pmwbStore.pmwb_jwt
      _pmwbToken = null; _pmwbTokenExp = 0   // 同步清内存 token（等价于新开 popup）
      const resp = await fetch('http://127.0.0.1:8000/api/v1/plugins/contacts', { signal: AbortSignal.timeout(10000) })
      const data = await resp.json()
      return { status: resp.status, success: data.success, err: data.error || '' }
    })()`)
    r5.status === 401 && !r5.success && r5.err.includes('PMWB 鉴权失败')
      ? ok(`未配置凭据 → 401 + 引导文案（"${r5.err.slice(0, 30)}..."）`)
      : bad('未配置凭据场景', JSON.stringify(r5))

    /* ── 6. 密码错误场景：错凭据 → 401 + 后端真实文案 ── */
    const r6 = await evalp(`(async () => {
      window.__pmwbStore.pmwb_auth = { username: 'chendh', password: 'wrong-password' }
      _pmwbToken = null; _pmwbTokenExp = 0
      const resp = await fetch('http://127.0.0.1:8000/api/v1/plugins/contacts', { signal: AbortSignal.timeout(10000) })
      const data = await resp.json()
      return { status: resp.status, success: data.success, err: data.error || '' }
    })()`)
    r6.status === 401 && r6.err.includes('用户名或密码错误')
      ? ok('错误密码 → 透出后端真实文案')
      : bad('错误密码场景', JSON.stringify(r6))

    /* ── 7. 桌面 PMWB 页面不受影响（守卫直通）── */
    await send('Page.navigate', { url: BASE + '/login' })
    await sleep(4000)
    const r7 = await evalp(`(() => ({ hasCard: !!document.querySelector('.login-card') }))()`)
    r7.hasCard ? ok('PMWB 登录页正常渲染（后端未被插件改动影响）') : bad('PMWB 页面', JSON.stringify(r7))

    console.log(`\n========== 结果: ${pass} PASS / ${fail} FAIL ==========`)
    process.exitCode = fail > 0 ? 1 : 0
  } finally {
    try { chrome.kill() } catch {}
    await rm(profile, { recursive: true, force: true }).catch(() => {})
    process.exit(process.exitCode || 0)
  }
}

main().catch((e) => { console.error('FATAL:', e.message); process.exit(1) })
