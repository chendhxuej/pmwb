/**
 * 客诉工单 · AI 分析全文 + 导出按钮 前端 DOM 回归（2026-11-10）
 *
 * 验证老大三问里「AI分析字段展示不完整」与「下钻页面支持导出」在真实页面上生效：
 *   1. 工单明细台账：导出按钮 + 根因列「查看完整 AI 分析」入口 + 工单内容「全文」入口
 *   2. AI 分析全文弹窗：根因全文 / 依据 / 缺口 / 投诉内容 / 处理过程均完整可见 + 复制/导出
 *   3. 下钻抽屉（看板 TOP 点击）：导出按钮 + AI 分析列可展开
 *   4. 周报按钮：显示周次与新鲜度提示
 *
 * 用法（项目根执行；前端 dev 5173 或后端托管 dist 均可）：
 *   PMWB_BASE=http://localhost:5173 PMWB_AUTH_USER=chendh PMWB_AUTH_PW=*** \
 *     node scripts/verify_complaint_ai_export.mjs
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
const PORT = Number(process.env.CDP_PORT || 9367)
const USER = process.env.PMWB_AUTH_USER || 'chendh'
const PW = process.env.PMWB_AUTH_PW || ''

let pass = 0, fail = 0
const failures = []
const ok = (n, e = '') => { pass++; console.log(`  PASS  ${n}${e ? '  ' + e : ''}`) }
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
    await sleep(800)
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

async function main() {
  const profile = await mkdtemp(join(tmpdir(), 'pmwb-aiexp-'))
  const chrome = spawn(CHROME, [
    `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
    '--no-first-run', '--no-default-browser-check', '--window-size=1680,1100', 'about:blank',
  ], { stdio: 'ignore' })
  try {
    const cdp = new CDP(new WebSocket(await fetchWsUrl()))
    await new Promise((res, rej) => { cdp.ws.addEventListener('open', res, { once: true }); cdp.ws.addEventListener('error', rej, { once: true }) })
    await cdp.send('Page.enable')

    console.log('\n▶ 登录')
    await login(cdp) ? ok('登录并进入主布局') : bad('登录失败（检查 PMWB_AUTH_USER/PW）')

    // ── 1. 工单明细台账 ──
    console.log('\n▶ 工单明细台账 /complaint-center/tickets')
    await cdp.goto(`${BASE}/complaint-center/tickets`)
    const pageOk = await cdp.waitFor('.complaint-tickets', 25000)
    pageOk ? ok('工单台账页挂载') : bad('工单台账页未挂载')
    await sleep(3000)
    const bar = await cdp.eval(`(() => {
      const btns = [...document.querySelectorAll('.complaint-tickets button')].map(b => b.textContent.trim())
      return { export: btns.some(t => t.includes('导出明细')),
               aiLinks: document.querySelectorAll('.complaint-tickets .rc-full').length }
    })()`).catch(() => ({ export: false, aiLinks: 0 }))
    bar.export ? ok('台账页有「导出明细」按钮') : bad('台账页缺导出按钮')
    bar.aiLinks > 0 ? ok(`「查看完整 AI 分析 / 全文」入口 ${bar.aiLinks} 处`) : bad('台账页无 AI 全文入口')

    // ── 2. AI 分析全文弹窗 ──
    console.log('\n▶ AI 分析全文弹窗')
    await cdp.clickAt('.complaint-tickets .rc-full')
    const dlgOk = await cdp.waitFor('.ai-full', 10000)
    dlgOk ? ok('点击后弹出 AI 分析全文弹窗') : bad('AI 全文弹窗未弹出')
    await sleep(1200)
    const dlg = await cdp.eval(`(() => {
      const root = document.querySelector('.ai-full')
      if (!root) return {}
      const h = [...root.querySelectorAll('.ai-full__h')].map(x => x.textContent.trim())
      const pres = [...root.querySelectorAll('.ai-full__pre')].map(p => (p.textContent || '').trim())
      const btns = [...document.querySelectorAll('.el-dialog button')].map(b => b.textContent.trim())
      return { h, preCount: pres.length, maxLen: Math.max(0, ...pres.map(p => p.length)),
               copy: btns.some(t => t.includes('复制全文')), exportOne: btns.some(t => t.includes('导出本单明细')),
               // Element Plus 单元格类名是 el-descriptions__cell（非 el-descriptions-item）
               descItems: root.querySelectorAll('.el-descriptions__label').length }
    })()`).catch(() => ({}))
    dlg.preCount >= 5 ? ok(`全文块 ${dlg.preCount} 个（根因/依据/缺口/内容/处理过程）`) : bad('全文块不足', String(dlg.preCount))
    dlg.maxLen > 30 ? ok(`最长文本 ${dlg.maxLen} 字，未截断`) : bad('文本疑似截断', String(dlg.maxLen))
    dlg.copy ? ok('有「复制全文」按钮') : bad('缺复制全文按钮')
    dlg.exportOne ? ok('有「导出本单明细」按钮') : bad('缺导出本单按钮')
    dlg.descItems >= 10 ? ok(`结构化字段 ${dlg.descItems} 项`) : bad('结构化字段不足', String(dlg.descItems))
    dlg.h && dlg.h.some(x => x.includes('AI 分析总结')) ? ok('标题含「AI 分析总结（根因全文）」') : bad('缺 AI 分析标题')

    // 关闭弹窗避免遮挡后续抽屉
    await cdp.eval(`(() => { const b=[...document.querySelectorAll('.el-dialog button')].find(x=>x.textContent.includes('关闭')); if(b)b.click(); return true })()`)
    await sleep(600)

    // ── 3. 下钻抽屉（看板 TOP 点击） ──
    console.log('\n▶ 看板下钻抽屉')
    await cdp.goto(`${BASE}/complaint-center/dashboard`)
    await cdp.waitFor('.complaint-dashboard .mp-overview', 25000)
    await sleep(3000)
    await cdp.clickAt('.complaint-dashboard .mp-overview .mp-top__item')
    const drawerOk = await cdp.waitFor('.el-drawer', 10000)
    drawerOk ? ok('下钻抽屉弹出') : bad('下钻抽屉未弹出')
    await sleep(2000)
    const dr = await cdp.eval(`(() => {
      const btns = [...document.querySelectorAll('.el-drawer button')].map(b => b.textContent.trim())
      return { export: btns.some(t => t.includes('导出明细')),
               aiCells: document.querySelectorAll('.el-drawer .ai-cell').length,
               aiMore: [...document.querySelectorAll('.el-drawer .ai-cell__more')].length }
    })()`).catch(() => ({ export: false, aiCells: 0, aiMore: 0 }))
    dr.export ? ok('下钻抽屉有「导出明细」按钮') : bad('下钻抽屉缺导出按钮')
    dr.aiCells > 0 ? ok(`AI 分析列多行展示 ${dr.aiCells} 行`) : bad('下钻抽屉无 AI 分析单元格')
    dr.aiMore > 0 ? ok(`「查看完整分析 →」入口 ${dr.aiMore} 处`) : bad('下钻抽屉无完整分析入口')

    // ── 4. 周报按钮 ──
    console.log('\n▶ 周报按钮')
    const wk = await cdp.eval(`(() => { const b=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('周报')); return b?b.textContent.trim():'' })()`).catch(() => '')
    wk.includes('2026-W') ? ok('按钮显示周次', wk) : bad('周报按钮未显示周次', wk)

    console.log(`\n════════ 结果：${pass} 通过 / ${fail} 失败 ════════`)
    if (failures.length) { console.log('失败项：' + failures.join('；')); process.exitCode = 1 }
  } finally {
    try { chrome.kill() } catch {}
  }
}
main().catch(e => { console.error('FATAL:', e.message); process.exit(1) })
