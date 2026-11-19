/**
 * 排版管理 · 老大二轮反馈 7 问题真态验证（2026-11-19）
 * 环境：8020 反向代理 = 新 dist 前端 + 8010 新后端代码（不打断 8000）。
 * 真实登录 + 真 API + 真 Chrome DOM，不 mock、不写业务数据、不发真邮件。
 * 铁律：ok(name, cond, extra)，断言必须能真失败。
 * 用法： node scripts/verify_paiban_round2_dom.mjs
 */
import { existsSync } from 'node:fs'
import { spawn } from 'node:child_process'
import { mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const CHROME = ['C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(existsSync)
const BASE = 'http://127.0.0.1:8020'
const API = 'http://127.0.0.1:8010'
const PORT = Number(process.env.CDP_PORT || 9421)
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
  async openRoute(route, readySel = '.pb-page') {
    let ready = false
    for (let i = 0; i < 3 && !ready; i++) {
      await this.goto(`${BASE}${route}?v=${Date.now()}-${i}`)
      ready = await this.waitFor(readySel, 20000)
      if (!ready) await sleep(800)
    }
    await sleep(1800) // 等接口数据回来（waitFor 容器只证明挂载）
    return ready
  }
}
async function wsurl() {
  for (let i = 0; i < 40; i++) {
    try { const r = await fetch(`http://127.0.0.1:${PORT}/json/list`); const p = (await r.json()).find(x => x.type === 'page'); if (p?.webSocketDebuggerUrl) return p.webSocketDebuggerUrl } catch (_) {}
    await sleep(300)
  }
  throw new Error('cdp not ready')
}

// 8010 无需鉴权（AUTH_REQUIRED=false），但仍注入 token 以兼容前端拦截器
const lr = await fetch(`${API}/api/v1/auth/login`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: 'chendh', password: 'Chenxue520' }),
}).catch(() => null)
let token = ''
if (lr) { try { token = (await lr.json()).data?.token || '' } catch (_) {} }

const prof = await mkdtemp(join(tmpdir(), 'pb2-' ))
const ch = spawn(CHROME, [`--remote-debugging-port=${PORT}`, `--user-data-dir=${prof}`,
  '--no-first-run', '--headless=new', '--window-size=1700,1000', 'about:blank'], { stdio: 'ignore' })
try {
  const ws = new WebSocket(await wsurl()); const c = new CDP(ws)
  await new Promise((r, j) => { ws.addEventListener('open', r, { once: true }); ws.addEventListener('error', j, { once: true }) })
  await c.send('Page.enable'); await c.send('Runtime.enable')
  await c.goto(`${BASE}/`); await sleep(900)
  if (token) await c.eval(`localStorage.setItem('pmwb_token',${JSON.stringify(token)});'ok'`)

  // ── 问题3：版本计划默认只列未来计划 ──────────────────────────
  console.log('\n=== 问题3：版本计划默认清单 ===')
  let ready = await c.openRoute('/paiban/versions', '.pb-version')
  ok('3.0 版本计划页渲染', ready)
  let txt = (await c.eval(`document.body.innerText`)) || ''
  ok('3.1 默认勾选「仅未来计划」', await c.eval(`(()=>{const cbs=[...document.querySelectorAll('.el-checkbox')];return cbs.some(x=>x.innerText.includes('仅未来计划')&&x.classList.contains('is-checked'))})()`))
  ok('3.2 清单含已配版本', txt.includes('11月26号统一版本'))
  ok('3.3 默认清单口径提示', txt.includes('计划发布日') && txt.includes('今天'))

  // ── 问题2：枚举转译（版本计划弹窗中文）──────────────────────
  console.log('\n=== 问题2：枚举转译 ===')
  await c.eval(`(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('登记版本计划'));if(b)b.click();return 'ok'})()`)
  await c.waitFor('.el-dialog', 8000); await sleep(800)
  txt = (await c.eval(`document.querySelector('.el-dialog')?.innerText || ''`))
  ok('2.1 版本类型中文「常规版」', txt.includes('常规版'))
  ok('2.2 适用范围中文「统一默认」', txt.includes('统一默认'))
  ok('2.3 无英文枚举原值(regular/draft/open)', !/\b(regular|draft|open|wait_release_n_days)\b/.test(txt), `txt=${txt.slice(0,120)}`)
  await c.eval(`(()=>{const b=[...document.querySelectorAll('.el-dialog button')].find(x=>x.textContent.includes('取消'));if(b)b.click();return 'ok'})()`)
  await sleep(500)

  // ── 问题4：四环节泳道信息 ────────────────────────────────────
  console.log('\n=== 问题4：四环节泳道信息 ===')
  ready = await c.openRoute('/paiban/track', '.pb-page')
  ok('4.0 排版跟踪页渲染', ready)
  await c.waitFor('.pb-lane', 10000); await sleep(1200)
  const lane = await c.eval(`(() => {
    const ls=[...document.querySelectorAll('.pb-lane')];
    return { count:ls.length, heads:ls.map(l=>l.querySelector('.pb-lane-head')?.innerText||''),
      deadlines:ls.map(l=>l.querySelector('.pb-lane-deadline')?.innerText||''),
      cards:ls.reduce((n,l)=>n+l.querySelectorAll('.pb-ticket').length,0),
      timing:(document.querySelector('.pb-ticket-timing')?.innerText||'') };
  })()`)
  ok('4.1 四环节泳道齐全', lane.count === 4, `count=${lane.count}`)
  ok('4.2 泳道头部显示倒排偏移(−15d 等)', lane.heads.some(h=>/−\d+d/.test(h)), `heads=${lane.heads}`)
  ok('4.3 泳道显示环节截止日', lane.deadlines.some(d=>d.includes('截止')), `deadlines=${lane.deadlines}`)
  ok('4.4 泳道卡片有时序信息(截止/剩余/停滞)', /截止|剩|超期|停滞/.test(lane.timing), `timing=${lane.timing}`)
  ok('4.5 有在跟工单卡片', lane.cards > 0, `cards=${lane.cards}`)

  // ── 问题1：候选池待补全分组含 BUG ───────────────────────────
  console.log('\n=== 问题1：候选池 BUG 待补全 ===')
  await c.eval(`(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('从候选池纳入'));if(b)b.click();return 'ok'})()`)
  await c.waitFor('.el-drawer', 8000); await sleep(3500)
  txt = (await c.eval(`document.querySelector('.el-drawer')?.innerText || ''`))
  ok('1.1 候选池有「待补全系统」页签', txt.includes('待补全系统'))
  ok('1.2 待补全计数 >0', /待补全系统（[1-9]/.test(txt), `txt=${txt.slice(0,200)}`)
  // 切到待补全页签
  const tabClicked = await c.eval(`(()=>{const ts=[...document.querySelectorAll('.el-drawer .el-tabs__item')];const t=ts.find(x=>x.textContent.includes('待补全'));if(t){t.click();return true}return false})()`)
  await sleep(900)
  txt = (await c.eval(`document.querySelector('.el-drawer')?.innerText || ''`))
  ok('1.3 待补全页签可切换', tabClicked)
  ok('1.4 待补全列表含 BUG 工单', /BUG-\d{8}-\d+/.test(txt), `has_bug=${/BUG-\d{8}-\d+/.test(txt)}`)
  ok('1.5 待补全说明「进待补全清单」', txt.includes('待补全') && txt.includes('未分配团队'))
  await c.eval(`(()=>{const b=[...document.querySelectorAll('.el-drawer button')].find(x=>x.textContent.includes('关闭')||x.querySelector?.('.el-icon-close'));if(b)b.click();return 'ok'})()`)
  await sleep(400)

  // ── 问题6：团队进展手工调整 ─────────────────────────────────
  console.log('\n=== 问题6：团队进展手工/批量调整 ===')
  ready = await c.openRoute('/paiban/teams', '.pb-page')
  ok('6.0 团队跟踪页渲染', ready)
  await c.waitFor('.el-table', 10000); await sleep(1300)
  txt = (await c.eval(`document.body.innerText`)) || ''
  ok('6.1 下钻有「调整环节」列', txt.includes('调整环节'))
  ok('6.2 有批量调整入口', txt.includes('批量调整'))
  ok('6.3 类型已转译(无 req/bug 原值)', !/\b(req|bug)\b/.test(txt), `sample=${txt.slice(0,100)}`)

  // ── 问题5&7：督办邮件预览编辑 + 风险手工登记 ────────────────
  console.log('\n=== 问题5/7：督办邮件编辑 + 风险登记 ===')
  ready = await c.openRoute('/paiban/risks', '.pb-page')
  ok('5.0 风险与督办页渲染', ready)
  await c.waitFor('.pb-card', 10000); await sleep(1500)
  txt = (await c.eval(`document.body.innerText`)) || ''
  ok('7.1 有「手工登记风险」入口', txt.includes('手工登记风险'))
  ok('5.1 督办组有「预览/编辑邮件」入口', txt.includes('预览 / 编辑邮件'))
  // 打开邮件编辑（找第一个组）
  const mailBtn = await c.eval(`(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('预览 / 编辑邮件'));if(b){b.click();return true}return false})()`)
  await sleep(900)
  const mailDlg = (await c.eval(`[...document.querySelectorAll('.el-dialog')].map(d=>d.innerText).join('|')`)) || ''
  ok('5.2 邮件编辑弹窗打开', mailBtn && mailDlg.includes('预览 / 编辑督办邮件'))
  ok('5.3 弹窗有主题编辑', mailDlg.includes('主题'))
  ok('5.4 弹窗有正文可视化/HTML切换', mailDlg.includes('可视化') && mailDlg.includes('HTML'))
  ok('5.5 弹窗提示回执码锚点不可删', mailDlg.includes('回执码') && mailDlg.includes('保留'))

  console.log(`\n=== PASS ${pass} / FAIL ${fail} ===`)
  if (fail) process.exitCode = 1
} finally { try { ch.kill() } catch (_) {} }
