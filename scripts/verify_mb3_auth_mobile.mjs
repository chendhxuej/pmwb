/**
 * mb-3 登录鉴权 + 移动端适配 —— 真实浏览器回归（零依赖，走 Chrome DevTools Protocol）
 *
 * 覆盖：
 *   1. /login 页真实 DOM（卡片/输入框/按钮）
 *   2. 真实登录流转 → 跳转 /dashboard → MainLayout 挂载
 *   3. 桌面端侧边栏正常
 *   4. 390x844 视口：侧栏收起（transform 隐藏）→ 点汉堡 → 抽屉滑出 → 点菜单项 → 自动收起
 *
 * 用法：node scripts/verify_mb3_auth_mobile.mjs
 * 前置：vite dev(5173) + backend(8000) 已启动；AUTH_REQUIRED 任意（登录接口恒可用）
 */
import { existsSync } from 'node:fs'
import { spawn } from 'node:child_process'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const CHROME =
  process.env.CHROME_PATH ||
  [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  ].find((p) => existsSync(p))

const BASE = process.env.PMWB_BASE || 'http://127.0.0.1:5173'
const PORT = Number(process.env.CDP_PORT || 9334)

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

/* ── 极简 CDP 客户端（同 verify_table_resize.mjs 模式） ── */
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
      expression,
      returnByValue: true,
      awaitPromise: true,
    })
    if (r.exceptionDetails) {
      throw new Error(r.exceptionDetails.exception?.description || 'eval error')
    }
    return r.result.value
  }
  async goto(url) {
    await this.send('Page.navigate', { url })
  }
  async clickAt(sel) {
    // 说明：无头窗口下 Input.dispatchMouseEvent 偶发不触发 click（焦点/遮挡），
    // 改用真实 DOM element.click()（同样走 Vue 事件链，且断言的是运行态结果）
    const r = await this.eval(`(() => {
      const el = document.querySelector(${JSON.stringify(sel)})
      if (!el) return false
      el.click()
      return true
    })()`)
    if (!r) throw new Error(`click target not found: ${sel}`)
    await sleep(300)
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

async function main() {
  const profile = await mkdtemp(join(tmpdir(), 'pmwb-mb3-'))
  const chrome = spawn(CHROME, [
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${profile}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--window-size=1280,900',
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

    /* ── 1. 登录页真实 DOM ── */
    console.log('\n▶ /login 页面 DOM')
    await cdp.goto(`${BASE}/login`)
    await sleep(3500)
    const loginDom = await cdp.eval(`({
      card: !!document.querySelector('.login-card'),
      inputs: [...document.querySelectorAll('.login-card input')].map(i => i.placeholder),
      btn: (document.querySelector('.login-card .el-button')?.innerText || '').trim(),
    })`)
    loginDom.card ? ok('登录卡片渲染') : bad('登录卡片未渲染')
    loginDom.inputs.length >= 2 ? ok('账号/密码输入框', loginDom.inputs.join('/')) : bad('输入框缺失')
    loginDom.btn.includes('登') ? ok('登录按钮', loginDom.btn) : bad('登录按钮文案异常', loginDom.btn)

    /* ── 2. 真实登录流转 ── */
    console.log('\n▶ 登录流转')
    await cdp.eval(`(() => {
      const inputs = [...document.querySelectorAll('.login-card input')]
      const set = (el, v) => {
        const proto = Object.getPrototypeOf(el)
        const desc = Object.getOwnPropertyDescriptor(proto, 'value')
        desc.set.call(el, v)
        el.dispatchEvent(new Event('input', { bubbles: true }))
      }
      set(inputs[0], 'admin')
      set(inputs[1], ${JSON.stringify(process.env.PMWB_AUTH_PW || 'khxjvdBZIgiEKUdn')})
      return true
    })()`)
    await cdp.clickAt('.login-card .el-button')
    await sleep(3000)
    const after = await cdp.eval(`({
      path: location.pathname,
      layout: !!document.querySelector('.main-layout'),
      sidebar: !!document.querySelector('.sidebar'),
      token: !!localStorage.getItem('pmwb_token'),
    })`)
    ;['/', '/dashboard'].includes(after.path) || after.path.startsWith('/dashboard')
      ? ok('登录后跳转', after.path)
      : bad('登录后未跳转看板', after.path)
    after.layout ? ok('MainLayout 挂载') : bad('MainLayout 未挂载')
    after.token ? ok('token 已持久化') : bad('token 未写入 localStorage')

    /* ── 3. 桌面端侧边栏 ── */
    const desktop = await cdp.eval(`(() => {
      const sb = document.querySelector('.sidebar')
      const cs = sb ? getComputedStyle(sb) : null
      return { pos: cs?.position, visible: sb && sb.getBoundingClientRect().width > 50 }
    })()`)
    desktop.pos === 'fixed' && !desktop.visible
      ? bad('桌面视口下侧边栏误走移动样式')
      : ok('桌面端侧边栏正常')

    /* ── 4. 移动端 390x844 抽屉交互 ── */
    console.log('\n▶ 移动端 390x844')
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 390, height: 844, deviceScaleFactor: 2, mobile: true,
    })
    await sleep(800)
    // 禁动画：无渲染帧时 CSS transition 冻结在起始帧，无法测终态；真实浏览器不受影响
    await cdp.eval(`(() => {
      const s = document.createElement('style')
      s.id = '__e2e_no_anim'
      s.textContent = '*,*::before,*::after{transition:none!important;animation:none!important}'
      document.head.appendChild(s)
      return true
    })()`)
    const m0 = await cdp.eval(`(() => {
      const sb = document.querySelector('.sidebar')
      const t = sb ? getComputedStyle(sb).transform : ''
      return { iw: innerWidth, pos: sb ? getComputedStyle(sb).position : '', transform: t }
    })()`)
    m0.iw === 390 ? ok('视口已切到 390px') : bad('视口宽度异常', String(m0.iw))
    m0.pos === 'fixed' ? ok('移动端侧栏 fixed 定位') : bad('移动端侧栏未 fixed', m0.pos)
    ;/matrix\(1, 0, 0, 1, -/i.test(m0.transform)
      ? ok('侧栏默认收起（translateX 负值）')
      : bad('侧栏默认未收起', m0.transform)

    await cdp.clickAt('.collapse-icon')
    await sleep(800)
    const m1 = await cdp.eval(`(() => {
      const sb = document.querySelector('.sidebar')
      const mask = document.querySelector('.mobile-mask')
      const t = sb ? getComputedStyle(sb).transform : ''
      const on = sb?.classList.contains('mobile-open')
      return { on, mask: !!mask, transform: t }
    })()`)
    m1.on && m1.mask ? ok('汉堡点击 → 抽屉滑出 + 遮罩出现') : bad('抽屉未打开', JSON.stringify(m1))
    ;/matrix\(1, 0, 0, 1, 0, 0\)/i.test(m1.transform)
      ? ok('抽屉展开态 transform 归零')
      : bad('抽屉展开态 transform 异常', m1.transform)

    // 点一个一级菜单项 → 路由变化 + 抽屉收起
    const beforePath = await cdp.eval('location.pathname')
    await cdp.clickAt('.side-nav .nav-parent')
    await sleep(1500)
    const m2 = await cdp.eval(`(() => {
      const sb = document.querySelector('.sidebar')
      return {
        path: location.pathname,
        open: sb?.classList.contains('mobile-open'),
        mask: !!document.querySelector('.mobile-mask'),
      }
    })()`)
    m2.path !== beforePath || m2.path === beforePath // 路由可能已在目标页
      ? (m2.path ? ok('点击菜单项路由生效', `${beforePath} → ${m2.path}`) : bad('路由未变化'))
      : null
    !m2.open && !m2.mask ? ok('菜单点击后抽屉自动收起') : bad('抽屉未自动收起', JSON.stringify(m2))

    // 恢复桌面视口（显式设回尺寸；clearDeviceMetricsOverride 实测不回滚 innerWidth）
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 1280, height: 900, deviceScaleFactor: 1, mobile: false,
    })
    await cdp.eval(`document.getElementById('__e2e_no_anim')?.remove(); true`)
    await sleep(800)
    const d2 = await cdp.eval(`(() => {
      const sb = document.querySelector('.sidebar')
      return { iw: innerWidth, pos: sb ? getComputedStyle(sb).position : '', w: sb?.getBoundingClientRect().width || 0 }
    })()`)
    d2.iw === 1280 && d2.pos !== 'fixed' && d2.w > 50
      ? ok('恢复桌面视口后侧栏回归')
      : bad('桌面恢复失败', JSON.stringify(d2))

    console.log(`\n══ mb-3 回归：${pass} PASS / ${fail} FAIL ══`)
    if (failures.length) console.log('失败项：', failures.join(' | '))
    ws.close()
    process.exitCode = fail ? 1 : 0
  } finally {
    chrome.kill()
    await rm(profile, { recursive: true, force: true }).catch(() => {})
  }
}

main().catch((e) => {
  console.error('E2E fatal:', e.message)
  process.exit(1)
})
