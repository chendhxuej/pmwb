/**
 * 排版管理 · 8000 真实运行态 DOM/静态页冒烟（2026-11-19）
 *
 * 背景：老大重启后反馈「网页访问没看到 demo 展示信息」。根因是正式 frontend/dist
 * 仍是旧构建（服务重启不会自动 build），且交互 Demo 是独立静态原型、并非系统页面。
 * 本脚本验证修复后的 8000 真态：新构建入口、菜单位置、5 页、Demo 入口与静态页可达。
 *
 * 说明：/api/v1/* 由 CDP Fetch 喂内存 fixture（只为让 Vue 页面渲染，不触碰真实业务表）；
 *       真实 API 可达性另用「无 token 返回 401 而非 404」断言路由已注册；
 *       迁移真态另用只读 SQLAlchemy 检查 MySQL 表。
 *
 * 用法： node scripts/verify_paiban_8000_dom.mjs
 * 可覆盖： PMWB_BASE=http://127.0.0.1:8000  CDP_PORT=9371  CHROME_PATH=...
 *
 * 铁律：ok(name, cond, extra)；断言必须能真失败。
 */
import { existsSync, readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { spawn, execFileSync } from 'node:child_process'
import { mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const CHROME = process.env.CHROME_PATH || [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].find(existsSync)
const BASE = process.env.PMWB_BASE || 'http://127.0.0.1:8000'
const PORT = Number(process.env.CDP_PORT || 9371)
const ROOT = resolve(import.meta.dirname || '.', '..')

let pass = 0, fail = 0
const failures = []
const ok = (n, cond, e = '') => {
  if (cond) { pass++; console.log(`  PASS  ${n}${e ? '  ' + e : ''}`) }
  else { fail++; failures.push(n); console.log(`  FAIL  ${n}${e ? '  ' + e : ''}`) }
}
const sleep = ms => new Promise(r => setTimeout(r, ms))
const wrap = data => ({ code: 0, message: 'success', data })

const STAGES = [
  { key: 'plan_confirm', label: '方案确认中', offset_days: -15 },
  { key: 'dev', label: '开发中', offset_days: -8 },
  { key: 'test', label: '测试中', offset_days: -3 },
  { key: 'wait_release', label: '等待发布', offset_days: -1 },
]
const META = {
  stages: STAGES, freeze_offset_days: -15,
  scope_types: [{ value: 'default', label: '统一默认' }, { value: 'system', label: '指定系统' }],
  version_types: [{ value: 'regular', label: '常规版' }],
  plan_statuses: [{ value: 'draft', label: '拟定' }, { value: 'confirmed', label: '已确认' }],
  admit_modes: [{ value: 'open', label: '开放' }, { value: 'wait_release_n_days', label: '提前 N 天进入等待发布才准入' }],
  exception_reasons: [], default_admit_lead_days: 7, crm_system_key: 'CRM',
  system_options: ['CRM', '订单中心'], dict_degraded: false, labels: {},
}
function mockFor(url) {
  if (url.includes('/auth/me')) return wrap({ username: 'tester' })
  if (url.includes('/paiban/meta')) return wrap(META)
  if (url.includes('/paiban/versions')) return wrap({ items: [], total: 0, default_count: 0, crm_gate_count: 0 })
  return wrap({})
}

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
  console.log('\n=== A 8000 静态产物与迁移真态（无需浏览器） ===')
  const indexHtml = await (await fetch(`${BASE}/?v=pbcheck`)).text()
  const entryMatch = indexHtml.match(/src="\/assets\/(index-[^"]+\.js)"/)
  const distEntry = entryMatch?.[1] || ''
  ok('A1 8000 返回 SPA 入口', !!distEntry, `entry=${distEntry}`)
  const distExists = existsSync(join(ROOT, 'frontend/dist/assets', distEntry))
  ok('A2 入口 JS 在正式 dist 中真实存在', distExists)
  ok('A3 已脱离 11-13 旧入口', !indexHtml.includes('index-DE-m7B3P.js'), `entry=${distEntry}`)
  const distIndex = readFileSync(join(ROOT, 'frontend/dist/index.html'), 'utf8')
  ok('A4 dist/index.html 与 8000 同源', distIndex.includes(distEntry))
  const chunkNames = execFileSync(process.execPath, ['-e', `
    const fs=require('fs'); const p=${JSON.stringify(join(ROOT, 'frontend/dist/assets'))};
    console.log(fs.readdirSync(p).filter(f=>/paiban|VersionPlan/i.test(f)).join(','));
  `], { encoding: 'utf8' }).trim()
  ok('A5 正式 dist 含排版管理 chunk',
    chunkNames.includes('PaibanLayout') && chunkNames.includes('VersionPlanView'), chunkNames)

  // 只读检查 MySQL 迁移真态（不写任何表）
  let pbTables = ''
  try {
    pbTables = execFileSync(join(ROOT, 'backend/venv/Scripts/python.exe'), ['-c', `
import sys; sys.path.insert(0,'.')
from sqlalchemy import create_engine, inspect
from core.config import settings
with create_engine(settings.DATABASE_URL, pool_pre_ping=True, connect_args={'connect_timeout':5}).connect() as c:
    print(','.join(sorted(n for n in inspect(c).get_table_names() if n.startswith('pmwb_pb_'))))
`], { cwd: join(ROOT, 'backend'), encoding: 'utf8' }).trim()
  } catch (e) { pbTables = 'ERR:' + String(e.message).slice(0, 80) }
  ok('A6 MySQL 迁移已生效（两张 pb 表）',
    pbTables.includes('pmwb_pb_version_plan') && pbTables.includes('pmwb_pb_version_change_log'), pbTables)

  // 路由已注册：无 token 应 401（鉴权拦截），未注册则会 404
  const apiStatus = (await fetch(`${BASE}/api/v1/paiban/versions`)).status
  ok('A7 /api/v1/paiban/versions 路由已注册', apiStatus === 401, `HTTP=${apiStatus}`)

  console.log('\n=== B Demo 静态页可从 8000 直接访问 ===')
  const demoResp = await fetch(`${BASE}/paiban-demo.html`)
  const demoHtml = await demoResp.text()
  ok('B1 Demo 静态页 HTTP 200', demoResp.status === 200, `HTTP=${demoResp.status}`)
  const demoBytes = Buffer.byteLength(demoHtml, 'utf8')
  ok('B2 Demo 是零外链单文件', demoBytes > 90000 && !/<script[^>]+src=/.test(demoHtml), `bytes=${demoBytes}`)
  ok('B3 Demo 五个页面文案齐全',
    ['排版跟踪', '版本计划', '团队跟踪', '风险与督办', '反馈同步'].every(t => demoHtml.includes(t)))
  ok('B4 Demo 关键交互文案齐全',
    ['准入模拟器', '自动顺延', '手工处理', '批量督办', '反馈同步', '决策结论'].every(t => demoHtml.includes(t)))
  ok('B5 Demo 为 v1.2（含手工例外放行）', demoHtml.includes('例外放行') || demoHtml.includes('人工例外'))
  const sha = p => createHash('sha256').update(readFileSync(join(ROOT, p))).digest('hex')
  const srcHash = sha('docs/排版管理_页面Demo.html')
  ok('B6 public 源 / dist 副本与 docs 原稿逐字节一致',
    sha('frontend/public/paiban-demo.html') === srcHash
      && sha('frontend/dist/paiban-demo.html') === srcHash,
    `sha=${srcHash.slice(0, 12)}`)

  console.log('\n=== C 真实浏览器 DOM：菜单 / 版本计划页 / Demo 入口 ===')
  if (!CHROME) throw new Error('未找到 Chrome / Edge')
  const profile = await mkdtemp(join(tmpdir(), 'pmwb-pb8000-'))
  const chrome = spawn(CHROME, [
    `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
    '--no-first-run', '--no-default-browser-check', '--headless=new',
    '--window-size=1680,1100', 'about:blank',
  ], { stdio: 'ignore' })
  let cdp
  try {
    const ws = new WebSocket(await fetchWsUrl())
    const onEvent = m => {
      if (m.method !== 'Fetch.requestPaused' || !cdp) return
      const body = Buffer.from(JSON.stringify(mockFor(m.params.request.url))).toString('base64')
      cdp.send('Fetch.fulfillRequest', {
        requestId: m.params.requestId, responseCode: 200,
        responseHeaders: [
          { name: 'Content-Type', value: 'application/json; charset=utf-8' },
          { name: 'Access-Control-Allow-Origin', value: '*' },
        ], body,
      }).catch(() => {})
    }
    cdp = new CDP(ws, onEvent)
    await new Promise((res, rej) => { ws.addEventListener('open', res, { once: true }); ws.addEventListener('error', rej, { once: true }) })
    await cdp.send('Page.enable')
    await cdp.send('Runtime.enable')
    await cdp.send('Fetch.enable', { patterns: [{ urlPattern: '*api/v1*', requestStage: 'Request' }] })

    let ready = false
    for (let i = 0; i < 2 && !ready; i++) {
      await cdp.goto(`${BASE}/paiban/versions?v=pbcheck`)
      ready = await cdp.waitFor('.pb-version', 20000)
      if (!ready) await sleep(800)
    }
    ok('C1 版本计划页真实渲染', ready)
    ok('C2 主布局挂载', await cdp.waitFor('.main-layout', 10000))
    const bodyText = await cdp.eval('document.body.innerText').catch(() => '')
    const iTask = bodyText.indexOf('任务中心'), iPb = bodyText.indexOf('排版管理'), iReq = bodyText.indexOf('需求与交付')
    ok('C3 菜单位置 任务中心 < 排版管理 < 需求与交付',
      iTask >= 0 && iPb > iTask && iReq > iPb, `idx=${iTask}/${iPb}/${iReq}`)
    ok('C4 五个二级页签齐全',
      ['排版跟踪', '版本计划', '团队跟踪', '风险与督办', '反馈同步'].every(t => bodyText.includes(t)))
    const demoBtn = await cdp.eval(`[...document.querySelectorAll('.pb-version button')].some(b => b.innerText.includes('交互原型 Demo'))`)
    ok('C5 版本计划页有「交互原型 Demo」入口', demoBtn)
    ok('C6 空态正常（迁移后 0 行计划，不是接口报错）',
      bodyText.includes('有效计划') && !bodyText.includes('表不存在'), `len=${bodyText.length}`)

    console.log('\n=== D 占位页也有 Demo 入口，且 Demo 页浏览器真渲染 ===')
    let phReady = false
    for (let i = 0; i < 2 && !phReady; i++) {
      await cdp.goto(`${BASE}/paiban/track?v=pbcheck`)
      phReady = await cdp.waitFor('.pb-placeholder', 20000)
      if (!phReady) await sleep(800)
    }
    ok('D1 排版跟踪占位页渲染', phReady)
    const phText = await cdp.eval('document.body.innerText').catch(() => '')
    ok('D2 占位页有「打开交互原型 Demo」', phText.includes('打开交互原型 Demo'))
    ok('D3 占位页明确标注静态示意 / 不读写业务表',
      phText.includes('不读写业务表') && phText.includes('结构占位'))

    await cdp.goto(`${BASE}/paiban-demo.html`)
    const demoReady = await cdp.waitFor('#app, body', 15000)
    await sleep(600)
    const demoDomText = await cdp.eval('document.body.innerText').catch(() => '')
    ok('D4 Demo 在浏览器真实渲染', demoReady && demoDomText.includes('排版管理'), `len=${demoDomText.length}`)
    if (process.env.PB_DEBUG_DOM) console.log('DEMO_DOM_HEAD=', demoDomText.slice(0, 1200).replace(/\n/g, ' | '))
    // Demo v1.2 文案：该区块叫「决策点 / 四环节泳道」，不要按「准入模拟器」字面断言
    ok('D5 Demo 默认落地排版跟踪且准入/顺延规则可见',
      demoDomText.includes('四环节泳道') && demoDomText.includes('默认动作 = 自动顺延')
        && demoDomText.includes('手工处理'), `len=${demoDomText.length}`)

    console.log(`\n=== pb-1 / 8000 运行态: ${pass} PASS / ${fail} FAIL ===`)
    if (fail) { console.log('失败项：' + failures.join(' | ')); process.exitCode = 1 }
  } finally {
    chrome.kill()
  }
}

main().catch(e => { console.error('FATAL', e); process.exit(1) })
