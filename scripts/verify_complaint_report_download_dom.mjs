/**
 * 客诉周报「下载 HTML 文件」· 真实 DOM + 浏览器真实落盘回归（2026-11-11）
 *
 * 验证的不是「接口能返回 HTML」，而是老大点一下按钮后浏览器真的把文件保存下来：
 *   · 看板头部新增「下载 HTML」，原「周报 Wxx」预览按钮仍在且行为不变；
 *   · 预览按钮 → 新标签页（window.open），不落盘；
 *   · 下载按钮 → a[download] 触发保存，文件名 = 客诉周报_<周次>.html；
 *   · 保存下来的文件含全周期投诉全貌 / v3 模板 / 内联 ECharts；
 *   · 离线用 file:// 打开该下载件，4 张图表都能渲染（不依赖 CDN）。
 *
 * 用法：
 *   PMWB_BASE=http://127.0.0.1:8000 PMWB_AUTH_USER=chendh PMWB_AUTH_PW=*** \
 *     node scripts/verify_complaint_report_download_dom.mjs
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { spawn } from 'node:child_process'
import { mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

const CHROME = process.env.CHROME_PATH || [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].find(existsSync)
const BASE = process.env.PMWB_BASE || 'http://127.0.0.1:8000'
const PORT = Number(process.env.CDP_PORT || 9385)
const USER = process.env.PMWB_AUTH_USER || 'chendh'
const PW = process.env.PMWB_AUTH_PW || ''

let pass = 0, fail = 0
const failures = []
// 断言签名必须是 (name, cond, extra)；写成 (n, e='') 会全部恒 PASS（假绿）。
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
      setTimeout(() => {
        if (this.pending.has(id)) { this.pending.delete(id); reject(new Error('CDP timeout ' + method)) }
      }, 30000)
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
  await cdp.eval(`(() => { const b=document.querySelector('.login-card .el-button'); if(!b)return false; b.click(); return true })()`)
  await sleep(900)
  return cdp.waitFor('.main-layout', 25000)
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

function htmlFiles(dir) {
  try { return readdirSync(dir).filter(n => n.toLowerCase().endsWith('.html')) }
  catch { return [] }
}

async function main() {
  const profile = await mkdtemp(join(tmpdir(), 'pmwb-rptdl-profile-'))
  const dlDir = await mkdtemp(join(tmpdir(), 'pmwb-rptdl-files-'))
  const chrome = spawn(CHROME, [
    `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
    '--no-first-run', '--no-default-browser-check', '--window-size=1680,1100', 'about:blank',
  ], { stdio: 'ignore' })
  try {
    const cdp = new CDP(new WebSocket(await fetchWsUrl()))
    await new Promise((res, rej) => {
      cdp.ws.addEventListener('open', res, { once: true })
      cdp.ws.addEventListener('error', rej, { once: true })
    })
    await cdp.send('Page.enable')

    console.log('\n▶ 登录 / 打开投诉现状')
    ok('登录并进入主布局', await login(cdp))
    let dlMode = ''
    try {
      await cdp.send('Browser.setDownloadBehavior',
        { behavior: 'allow', downloadPath: dlDir, eventsEnabled: true })
      dlMode = 'Browser.setDownloadBehavior'
    } catch (e) {
      try {
        await cdp.send('Page.setDownloadBehavior', { behavior: 'allow', downloadPath: dlDir })
        dlMode = 'Page.setDownloadBehavior'
      } catch (e2) { /* 两种都不支持 → 落盘断言会真失败，不放宽 */ }
    }
    ok('CDP 允许下载到临时目录', !!dlMode, dlMode || '浏览器不支持设置下载目录')
    ok('看板页加载（dist 含整体区）', await openDashboard(cdp))
    await sleep(2000)

    // ── 1. 按钮存在性与原预览入口未破坏 ──
    console.log('\n▶ 头部按钮')
    const btns = await cdp.eval(`(() => {
      const dl = document.querySelector('.report-html-download')
      const preview = [...document.querySelectorAll('button')]
        .find(b => b.textContent.trim().startsWith('周报 2026'))
      return {
        hasDl: !!dl,
        dlText: dl ? dl.textContent.trim() : '',
        dlDisabled: dl ? !!dl.disabled : true,
        previewText: preview ? preview.textContent.trim() : '',
      }
    })()`).catch(() => ({ hasDl: false, dlText: '', dlDisabled: true, previewText: '' }))
    ok('新增「下载 HTML」按钮', btns.hasDl && btns.dlText.includes('下载 HTML'), btns.dlText)
    ok('下载按钮可用（当前已选中周次）', btns.dlDisabled === false)
    ok('原「周报 Wxx」预览按钮仍在', /2026-W\d+/.test(btns.previewText), btns.previewText)
    const week = (btns.previewText.match(/2026-W\d+/) || [''])[0]
    ok('能取到当前周次', !!week, week)

    // ── 2. 预览按钮仍是「新标签页打开」，不落盘 ──
    console.log('\n▶ 预览入口行为未变')
    await cdp.eval(`(() => {
      window.__pmwbOpenCalls = 0
      window.open = function () {
        window.__pmwbOpenCalls++
        return { location: { href: '' }, close: function () {} }
      }
      const b = [...document.querySelectorAll('button')]
        .find(x => x.textContent.trim().startsWith('周报 2026'))
      if (!b) return false
      b.click(); return true
    })()`).catch(() => false)
    await sleep(2500)
    const openCalls = await cdp.eval('window.__pmwbOpenCalls || 0').catch(() => 0)
    ok('预览按钮走 window.open（新标签页）', openCalls === 1, String(openCalls))
    ok('预览不会保存文件', htmlFiles(dlDir).length === 0, htmlFiles(dlDir).join(','))

    // ── 3. 下载按钮 → 浏览器真实落盘 ──
    console.log('\n▶ 下载 HTML 文件')
    const clicked = await cdp.eval(`(() => {
      const b = document.querySelector('.report-html-download')
      if (!b) return false
      b.click(); return true
    })()`).catch(() => false)
    ok('下载按钮可点击', clicked === true)
    let file = ''
    for (let i = 0; i < 90; i++) {
      const fs = htmlFiles(dlDir)
      if (fs.length) { file = fs[0]; break }
      await sleep(1000)
    }
    ok('浏览器实际保存了 HTML 文件', !!file, file || readdirSync(dlDir).join(','))
    if (!file) {
      console.log('  （无法落盘，后续文件内容断言跳过）')
      return
    }
    ok('保存文件名 = 客诉周报_<周次>.html',
      file === `客诉周报_${week}.html`, `${file} / 期望 客诉周报_${week}.html`)

    const html = readFileSync(join(dlDir, file), 'utf-8')
    ok('下载件含「全周期投诉全貌」章', html.includes('全周期投诉全貌'))
    ok('下载件含 16 周趋势图容器', html.includes('id="ovTrend"'))
    ok('下载件为当前模板 v3',
      html.includes('<meta name="pmwb-report-version" content="3">'))
    ok('下载件 ECharts 内联（>500KB 自包含，离线不缺资源）', html.length > 500000,
      `${html.length} chars`)
    ok('下载件无外链脚本',
      !/<script[^>]+src="https?:\/\//.test(html) && !html.includes('src="assets/echarts.min.js"'))

    // ── 4. 离线打开下载件，图表仍能渲染 ──
    console.log('\n▶ 离线打开下载件')
    await cdp.goto(pathToFileURL(join(dlDir, file)).href)
    let canvases = 0
    for (let i = 0; i < 25; i++) {
      canvases = await cdp.eval(`document.querySelectorAll('canvas').length`).catch(() => 0)
      if (canvases >= 4) break
      await sleep(500)
    }
    ok('离线 file:// 渲染 4 张图表（全貌/每日/分类/近8周）', canvases === 4, String(canvases))

    // ── 5. 头部多一个按钮后在各断点不横向溢出 ──
    console.log('\n▶ 头部响应式（新增按钮不挤破布局）')
    await cdp.goto(`${BASE}/complaint-center/dashboard`)
    await sleep(1500)
    await cdp.waitFor('.report-html-download', 20000)
    for (const w of [1400, 1100, 960]) {
      await cdp.send('Emulation.setDeviceMetricsOverride',
        { width: w, height: 900, deviceScaleFactor: 1, mobile: false })
      await sleep(450)
      const box = await cdp.eval(`(() => {
        const h = document.querySelector('.pm-page-header')
        return h ? { sw: h.scrollWidth, cw: h.clientWidth } : null
      })()`).catch(() => null)
      ok(`${w}px 视口页头不横向溢出`, !!box && box.sw <= box.cw + 2,
        box ? `scroll=${box.sw} client=${box.cw}` : 'no header')
    }
    await cdp.send('Emulation.clearDeviceMetricsOverride')
  } finally {
    try { chrome.kill() } catch {}
    console.log(`\n${'═'.repeat(62)}`)
    console.log(`结果：${pass} 通过 / ${fail} 失败`)
    if (failures.length) console.log('失败项：' + failures.join('；'))
    else console.log('ALL_PASS')
    process.exitCode = fail ? 1 : 0
  }
}

main().catch(e => { console.error(e); process.exitCode = 1 })
