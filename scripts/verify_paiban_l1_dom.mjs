/**
 * 排版管理 pb-1 / L1 · 真实页面 DOM 冒烟（2026-11-19）
 *
 * 用 CDP 起真实 Chrome 打开 vite dev（5173）的「版本计划」页；
 * /api/v1/* 请求由 CDP Fetch 拦截喂内存 fixture —— 页面是真实 Vue 渲染，
 * 但**不触碰运行态后端 / 数据库、不写任何真实表**。
 * 后端真实 API 口径由 backend/tests/test_paiban_version.py（12 条）覆盖；
 * 完整业务交互 DOM（准入/顺延/督办/反馈）由 pb-9 / L8 补。
 *
 * 用法： node scripts/verify_paiban_l1_dom.mjs
 * 可覆盖： PMWB_WEB=http://127.0.0.1:5173  CDP_PORT=9369  CHROME_PATH=...
 *
 * 铁律：ok(name, cond, extra)，写成 (n, e='') 会全部恒 PASS。
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
const WEB = process.env.PMWB_WEB || 'http://127.0.0.1:5173'
const PORT = Number(process.env.CDP_PORT || 9369)

let pass = 0, fail = 0
const failures = []
const ok = (n, cond, e = '') => {
  if (cond) { pass++; console.log(`  PASS  ${n}${e ? '  ' + e : ''}`) }
  else { fail++; failures.push(n); console.log(`  FAIL  ${n}${e ? '  ' + e : ''}`) }
}
const sleep = ms => new Promise(r => setTimeout(r, ms))

// ── 内存 fixture（仅用于本次 DOM 渲染；不是第二份口径实现）──────────
const STAGES = [
  { key: 'plan_confirm', label: '方案确认中', offset_days: -15, deadline: '2026-12-05' },
  { key: 'dev', label: '开发中', offset_days: -8, deadline: '2026-12-12' },
  { key: 'test', label: '测试中', offset_days: -3, deadline: '2026-12-17' },
  { key: 'wait_release', label: '等待发布', offset_days: -1, deadline: '2026-12-19' },
]
const DEADLINES = { release_date: '2026-12-20', freeze_date: '2026-12-05', stages: STAGES }
const CRM = {
  id: 1, version_no: 'CRM 2026-12 常规版', scope_type: 'system', scope_label: '指定系统',
  system_name: 'CRM', system_verified: 1, version_type: 'regular', version_type_label: '常规版',
  release_date: '2026-12-20', status: 'confirmed', status_label: '已确认',
  admit_mode: 'wait_release_n_days', admit_mode_label: '提前 N 天进入等待发布才准入',
  admit_lead_days: 7, allow_temp_merge: 0, next_version_id: null, remark: '',
  created_at: '', updated_at: '', deadlines: DEADLINES, admit_gate_at: '2026-12-13', is_crm: true,
}
const DEFAULT_PLAN = {
  ...CRM, id: 2, version_no: '2026-12 统一版', scope_type: 'default', scope_label: '统一默认',
  system_name: '', version_type_label: '常规版', admit_mode: 'open',
  admit_mode_label: '开放（无提前准入闸门）', admit_lead_days: 0, allow_temp_merge: 1,
  admit_gate_at: '', is_crm: false,
}
const META = {
  stages: STAGES.map(({ key, label, offset_days }) => ({ key, label, offset_days })),
  freeze_offset_days: -15,
  scope_types: [{ value: 'default', label: '统一默认' }, { value: 'system', label: '指定系统' }],
  version_types: [{ value: 'regular', label: '常规版' }, { value: 'emergency', label: '紧急补丁' }, { value: 'ad_hoc', label: '临时加版' }],
  plan_statuses: [{ value: 'draft', label: '拟定' }, { value: 'confirmed', label: '已确认' }, { value: 'published', label: '已发布' }],
  admit_modes: [{ value: 'open', label: '开放（无提前准入闸门）' }, { value: 'wait_release_n_days', label: '提前 N 天进入等待发布才准入' }],
  exception_reasons: [], default_admit_lead_days: 7, crm_system_key: 'CRM',
  system_options: ['CRM', '订单中心'], dict_degraded: false, labels: {},
}
const wrap = data => ({ code: 0, message: 'success', data })

function mockFor(url, method) {
  if (url.includes('/auth/me')) return wrap({ username: 'tester' })
  if (url.includes('/paiban/meta')) return wrap(META)
  if (url.includes('/paiban/deadlines/preview')) return wrap({ deadlines: DEADLINES, admit_gate_at: '2026-12-13', admit_lead_days: 7 })
  if (url.includes('/paiban/resolve')) return wrap({
    system: '订单中心', source: 'default', source_label: '统一默认', overdue: false,
    plan: DEFAULT_PLAN, hint: '该系统未单独配置版本计划，已回落统一默认计划。',
  })
  if (/\/paiban\/versions\/\d+/.test(url)) return wrap({ ...CRM, change_logs: [{
    id: 9, plan_id: 1, version_no: 'CRM 2026-12 常规版', change_type: 'update',
    field: 'release_date', old_value: '2026-12-18', new_value: '2026-12-20',
    affected_count: 3, operator: '老大', changed_at: '2026-11-19T08:00:00', remark: '',
  }], next_plan: DEFAULT_PLAN })
  if (url.includes('/paiban/versions')) {
    if (method === 'POST' || method === 'PATCH') return wrap(CRM)
    return wrap({ items: [CRM, DEFAULT_PLAN], total: 2, default_count: 1, crm_gate_count: 1 })
  }
  return wrap({})   // 其它 /api/v1/* 一律 200，避免 401 把页面踢回登录
}

class CDP {
  constructor(ws, onEvent) {
    this.ws = ws; this.id = 0; this.pending = new Map()
    ws.addEventListener('message', ev => {
      const m = JSON.parse(ev.data)
      if (m.method && onEvent) { onEvent(m); return }
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
}

async function fetchWsUrl() {
  for (let i = 0; i < 40; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/list`)
      const pages = await res.json()
      const p = pages.find(x => x.type === 'page')
      if (p?.webSocketDebuggerUrl) return p.webSocketDebuggerUrl
    } catch (_) { /* chrome 尚未就绪 */ }
    await sleep(300)
  }
  throw new Error('CDP endpoint not ready')
}

async function main() {
  if (!CHROME) throw new Error('未找到 Chrome / Edge，可用 CHROME_PATH 指定')
  const profile = await mkdtemp(join(tmpdir(), 'pmwb-pb1-dom-'))
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
      const p = m.params
      const body = Buffer.from(JSON.stringify(mockFor(p.request.url, p.request.method))).toString('base64')
      cdp.send('Fetch.fulfillRequest', {
        requestId: p.requestId, responseCode: 200,
        responseHeaders: [
          { name: 'Content-Type', value: 'application/json; charset=utf-8' },
          { name: 'Access-Control-Allow-Origin', value: '*' },
        ],
        body,
      }).catch(() => {})
    }
    cdp = new CDP(ws, onEvent)
    await new Promise((res, rej) => { ws.addEventListener('open', res, { once: true }); ws.addEventListener('error', rej, { once: true }) })
    await cdp.send('Page.enable')
    await cdp.send('Runtime.enable')
    await cdp.send('Fetch.enable', { patterns: [{ urlPattern: '*api/v1*', requestStage: 'Request' }] })

    // SPA 首导航偶发旧上下文 → 重试一次（不放宽断言）
    let ready = false
    for (let attempt = 0; attempt < 2 && !ready; attempt++) {
      await cdp.goto(`${WEB}/paiban/versions`)
      ready = await cdp.waitFor('.pb-version', 20000)
      if (!ready) await sleep(800)
    }
    console.log('\n▶ A 页面骨架与菜单')
    ok('A1 主布局挂载', await cdp.waitFor('.main-layout', 10000))
    ok('A2 版本计划页挂载', ready)
    const bodyText = await cdp.eval('document.body.innerText').catch(() => '')
    const iTask = bodyText.indexOf('任务中心'), iPb = bodyText.indexOf('排版管理'), iReq = bodyText.indexOf('需求与交付')
    ok('A3 菜单位置：任务中心 < 排版管理 < 需求与交付',
      iTask >= 0 && iPb > iTask && iReq > iPb, `idx=${iTask}/${iPb}/${iReq}`)
    ok('A4 五个二级页签齐全',
      ['排版跟踪', '版本计划', '团队跟踪', '风险与督办', '反馈同步'].every(t => bodyText.includes(t)))
    ok('A5 口径提示（统一倒排 + 不落副本）',
      bodyText.includes('四环节截止由计划发布日统一倒排') && bodyText.includes('不落副本'))

    console.log('\n▶ B 指标、表格与派生截止')
    const statCount = await cdp.eval(`document.querySelectorAll('.pb-version .pm-stat').length`)
    ok('B1 指标卡 4 张', statCount === 4, `count=${statCount}`)
    const tableText = await cdp.eval(`document.querySelector('.pb-version .el-table')?.innerText || ''`)
    ok('B2 CRM 计划渲染', tableText.includes('CRM 2026-12 常规版'))
    ok('B3 默认计划渲染并标统一默认', tableText.includes('2026-12 统一版') && tableText.includes('统一默认'))
    // 表格内 tag 用 deadline.slice(5) 显示短日期（12-05），完整日期只在冻结日/准入时点行
    ok('B4 四环节派生截止展示（短日期）',
      ['12-05', '12-12', '12-17', '12-19'].every(d => tableText.includes(d)),
      `sample=${tableText.slice(0, 120).replace(/\n/g, '|')}`)
    ok('B5 准入时点与冻结日展示', tableText.includes('2026-12-13'))
    ok('B6 CRM 禁止临时合入（默认自动顺延）', tableText.includes('禁止（默认自动顺延）'))
    const rowCount = await cdp.eval(`document.querySelectorAll('.pb-version .el-table__body tr').length`)
    ok('B7 表格行数 = fixture 2', rowCount === 2, `rows=${rowCount}`)

    console.log('\n▶ C 回落解析 / 登记弹窗 / 变更日志')
    ok('C1 回落预览控件存在', await cdp.eval(`!!document.querySelector('.pb-resolve-bar .el-select')`))
    await cdp.eval(`[...document.querySelectorAll('.pb-version button')].find(b=>b.innerText.includes('登记版本计划'))?.click(); true`)
    const dlgVisible = await cdp.eval(`[...document.querySelectorAll('.el-dialog')].some(d=>d.offsetParent!==null)`)
    ok('C2 登记弹窗可见', dlgVisible)
    const dlgText = await cdp.eval(`(() => { const d=[...document.querySelectorAll('.el-dialog')].find(x=>x.offsetParent!==null); return d?d.innerText:'' })()`)
    ok('C3 表单字段齐全', ['适用范围', '版本标识', '计划发布日', '准入模式', '允许临时合入', '操作人', '派生预览'].every(t => dlgText.includes(t)),
      `len=${dlgText.length}`)
    await cdp.eval(`(() => { const d=[...document.querySelectorAll('.el-dialog')].find(x=>x.offsetParent!==null); const b=[...d.querySelectorAll('button')].find(x=>x.innerText.includes('取消')); if(b) b.click(); return true })()`)
    await sleep(400)
    await cdp.eval(`[...document.querySelectorAll('.pb-version .el-table button')].find(b=>b.innerText.includes('变更日志'))?.click(); true`)
    await sleep(600)
    const drawerText = await cdp.eval(`(() => { const d=[...document.querySelectorAll('.el-drawer')].find(x=>x.offsetParent!==null); return d?d.innerText:'' })()`)
    ok('C4 变更日志抽屉打开且有留痕',
      drawerText.includes('release_date') && drawerText.includes('2026-12-18') && drawerText.includes('老大'),
      `len=${drawerText.length}`)

    console.log(`\n=== pb-1 L1 DOM: ${pass} PASS / ${fail} FAIL ===`)
    if (fail) { console.log('失败项：' + failures.join(' | ')); process.exitCode = 1 }
  } finally {
    chrome.kill()
  }
}

main().catch(e => { console.error('FATAL', e); process.exit(1) })
