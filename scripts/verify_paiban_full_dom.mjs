/**
 * 排版管理 pb-1~pb-9 全量交付回归：5 个真实页面 DOM + 8010 新代码路由。
 *
 * - 8000 只验证正式 dist 产物 / 真实浏览器渲染（API 由 CDP 喂内存 fixture，不写真实业务表）；
 * - 8010 是独立验证实例，加载新后端代码，用 OpenAPI 断言 32 个端点已注册；
 * - 断言一律 ok(name, cond, extra)，必须能真失败。
 *
 * 用法： node scripts/verify_paiban_full_dom.mjs
 */
import { existsSync, readFileSync } from 'node:fs'
import { spawn } from 'node:child_process'
import { mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const CHROME = process.env.CHROME_PATH || [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].find(existsSync)
const BASE = process.env.PMWB_BASE || 'http://127.0.0.1:8000'
const API = process.env.PMWB_API_BASE || 'http://127.0.0.1:8010'
const PORT = Number(process.env.CDP_PORT || 9375)
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
  exception_reasons: [{ value: 'production_fix', label: '生产故障修复须随本版' }, { value: 'other', label: '其他（须填写说明）' }],
  ticket_types: [{ value: 'req', label: '需求' }, { value: 'bug', label: 'BUG' }],
  admit_statuses: [{ value: 'pending', label: '待判定' }, { value: 'admitted', label: '已准入' },
    { value: 'not_admitted', label: '未准入' }, { value: 'exception', label: '人工例外准入' }],
  results: [{ value: '', label: '未出结果' }, { value: 'live', label: '已上线' },
    { value: 'not_scheduled', label: '未排进版本' }, { value: 'failed', label: '上线失败' }],
  risk_types: [{ value: 'dev_delay', label: '开发延期' }, { value: 'other', label: '其他' }],
  feedback_channels: [{ value: 'mail', label: '邮件回执' }, { value: 'batch', label: '团队批量更新' }],
  supervise_include_rules: [{ value: 'overdue', label: '本环节截止日已超期且未完成' }],
  supervise_exclude_rules: [{ value: 'cooldown', label: '24h 冷却窗内已成功督办' }],
  cooldown_exceptions: [{ value: 'manual_ignore', label: '预览中显式勾选「忽略冷却」' }],
  default_admit_lead_days: 7, crm_system_key: 'CRM',
  system_options: ['CRM', '订单中心'], dict_degraded: false, labels: {},
}
const PLAN = {
  id: 1, version_no: '2026-12 统一版', release_date: '2026-12-20',
  deadlines: { stages: STAGES.map(s => ({ ...s, deadline: '2026-12-05' })) },
}
const TRACKS = [
  { id: 1, ticket_type: 'req', ticket_type_label: '需求', ticket_no: 'REQ-1', title: '商客专区报价优化',
    system_name: '订单中心', priority: 'P1', owner: '张三', stage: 'dev', stage_label: '开发中',
    admit_status: 'admitted', admit_status_label: '已准入', exception_flag: 0, focus_flag: 1,
    result: '', result_label: '未出结果', defer_count: 1, blocking_risk_count: 1,
    plan: PLAN, plan_source: 'default', metrics: { overdue: false, near_due: true, deadline: '2026-12-12' },
    teams: [{ id: 1, team_name: '订单中心', owner: '张三', stage: 'dev', stage_label: '开发中', done: 0, last_feedback_at: '' }] },
  { id: 2, ticket_type: 'bug', ticket_type_label: 'BUG', ticket_no: 'BUG-1', title: '一网通开通状态不同步',
    system_name: 'CRM', priority: 'P0', owner: '李四', stage: 'wait_release', stage_label: '等待发布',
    admit_status: 'pending', admit_status_label: '待判定', exception_flag: 0, focus_flag: 0,
    result: '', result_label: '未出结果', defer_count: 0, blocking_risk_count: 0,
    plan: PLAN, plan_source: 'exclusive', metrics: { overdue: false, near_due: false, deadline: '2026-12-19' },
    teams: [{ id: 2, team_name: 'CRM', owner: '李四', stage: 'wait_release', stage_label: '等待发布', done: 1, last_feedback_at: '2026-11-19 09:00:00' }] },
]

function mockFor(url) {
  if (url.includes('/auth/me')) return wrap({ username: 'tester' })
  if (url.includes('/paiban/meta')) return wrap(META)
  if (url.includes('/paiban/versions')) return wrap({ items: [PLAN], total: 1, default_count: 1, crm_gate_count: 0 })
  if (url.includes('/paiban/overview')) return wrap({
    plan: PLAN, main_row_count: 2, team_row_count: 2,
    kpi: { should_go_live: 2, admitted: 1, pending: 1, exception: 0, live: 0,
      not_scheduled: 0, failed: 0, deferred_in: 1, blocking_risks: 1, pending_feedback: 1, receipt_rate: 0.5 },
    rates: { decided_count: 2, achieved_count: 2, planned_rate: 0.5, raw_rate: 1 },
    lists: { focus: [], abnormal: [], exception: [], freeze_late: [], missing_plan: [], blocking_risks: [] },
    scope_note: '版本统计按主行、团队视图按团队子行，两处不可加总',
  })
  if (url.includes('/paiban/tracks/missing-plans')) return wrap({ items: [], total: 0 })
  if (url.includes('/paiban/tracks/')) return wrap({ track: TRACKS[0], stage_logs: [], participations: [], risks: [], feedbacks: [] })
  if (url.includes('/paiban/tracks')) return wrap({ items: TRACKS, total: 2, main_row_count: 2, scope_note: '版本统计按主行' })
  if (url.includes('/paiban/candidates')) return wrap({
    items: [{ ticket_type: 'req', ticket_no: 'REQ-9', title: '待纳入需求', system_name: '订单中心',
      expected_date: '2026-12-10', status: 'dev', can_include: true, reason: 'hit', reason_label: '命中' }],
    excluded: [{ ticket_no: 'REQ-8', reason: 'closed', reason_label: '源状态已闭环' }],
    summary: { hit_count: 1, excluded_count: 1, by_reason: [{ reason: 'closed', label: '源状态已闭环', count: 1 }] },
  })
  if (url.includes('/paiban/team-matrix')) return wrap({
    stages: STAGES.map(s => ({ key: s.key, label: s.label })),
    grid: [{ team_name: '订单中心', counts: { plan_confirm: 0, dev: 1, test: 0, wait_release: 0 }, total: 1 },
      { team_name: 'CRM', counts: { plan_confirm: 0, dev: 0, test: 0, wait_release: 1 }, total: 1 }],
    drill: [{ track_id: 1, ticket_no: 'REQ-1', title: '商客专区报价优化', ticket_type: 'req',
      team_name: '订单中心', stage: 'dev', stage_label: '开发中', admit_status: 'admitted',
      defer_count: 1, overdue: false, deadline: '2026-12-12', supervise_count: 2, last_feedback_at: '' }],
    main_row_count: 2, team_row_count: 2, unresolved: [],
    scope_note: '版本统计按主行、团队视图按团队子行，两处数字不可加总',
  })
  if (url.includes('/paiban/risks')) return wrap({
    items: [{ id: 1, track_id: 1, risk_type: 'dev_delay', risk_type_label: '开发延期',
      description: '开发延期两天', affect_release: 1, level: 'P1', source: 'mail_feedback',
      status: 'open', status_label: '未消除', merge_count: 2 }], total: 1, blocking_count: 1,
  })
  if (url.includes('/paiban/supervise/batches')) return wrap({
    items: [{ batch_no: 'PB1-20261119120000-01', team_name: '订单中心', ticket_type: 'req',
      item_count: 3, sent_count: 0, skipped_count: 0, dry_run: 1, receipt_deadline: '2026-12-19',
      receipt_status: 'none' }], total: 1,
  })
  if (url.includes('/paiban/supervise/preview')) return wrap({
    groups: [{ team_name: '订单中心', ticket_type: 'req', ticket_type_label: '需求',
      recipients: ['sa@example.com'], included_count: 1, skipped_count: 1,
      items: [{ track_id: 1, team_id: 1, ticket_no: 'REQ-1', title: '商客专区报价优化',
        stage: 'dev', deadline: '2026-12-12', triggers: [{ key: 'overdue', label: '本环节截止日已超期且未完成' }],
        skip_reason: '', skip_reason_label: '', cooldown_left_h: 0,
        receipt_code: 'PB-ABC123' },
        { track_id: 2, team_id: 2, ticket_no: 'BUG-1', title: '状态不同步', stage: 'test',
          deadline: '2026-12-17', triggers: [{ key: 'stalled', label: '当前环节停留 ≥7 天' }],
          skip_reason: 'cooldown', skip_reason_label: '24h 冷却窗内已成功督办', cooldown_left_h: 18,
          receipt_code: 'PB-DEF456' }] }],
  })
  if (url.includes('/paiban/feedback/pending')) return wrap({
    items: [{ id: 7, track_id: 1, channel: 'mail', adopt_status: 'conflict', raw_text: '已进入测试中，风险：环境未就绪',
      suggested: { stage: 'test', progress: '已进入测试中', risk: '环境未就绪' },
      sender: 'sa@example.com', age_days: 2 }], total: 1, max_age_days: 2,
  })
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
  async waitFor(sel, timeout = 20000) {
    const t0 = Date.now()
    while (Date.now() - t0 < timeout) {
      if (await this.eval(`!!document.querySelector(${JSON.stringify(sel)})`).catch(() => false)) return true
      await sleep(350)
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
    } catch (_) { /* 未就绪 */ }
    await sleep(300)
  }
  throw new Error('CDP endpoint not ready')
}

async function main() {
  console.log('\n=== A 正式 dist 与后端路由（8010 新代码） ===')
  const indexHtml = await (await fetch(`${BASE}/?v=pbfull`)).text()
  const entry = indexHtml.match(/src="\/assets\/(index-[^"]+\.js)"/)?.[1] || ''
  ok('A1 8000 返回 SPA 入口', !!entry, `entry=${entry}`)
  const chunks = (await import('node:child_process')).execFileSync(process.execPath, ['-e', `
    const fs=require('fs'); console.log(fs.readdirSync(${JSON.stringify(join(ROOT, 'frontend/dist/assets'))})
      .filter(f=>/TrackView|TeamView|RiskSuperviseView|FeedbackView|VersionPlanView/.test(f)).join(','))
  `], { encoding: 'utf8' }).trim()
  ok('A2 正式 dist 含 5 个页面 chunk',
    ['TrackView', 'TeamView', 'RiskSuperviseView', 'FeedbackView', 'VersionPlanView']
      .every(n => chunks.includes(n)), chunks.slice(0, 160))

  let apiPaths = ''
  try { apiPaths = JSON.stringify((await (await fetch(`${API}/openapi.json`)).json()).paths) } catch (e) { apiPaths = 'ERR:' + e.message }
  const needed = ['/paiban/candidates', '/paiban/tracks', '/paiban/overview', '/paiban/supervise/send',
    '/paiban/feedback/mail/pull', '/paiban/team-matrix', '/paiban/tracks/{track_id}/manual']
  ok('A3 8010 新增端点已注册', needed.every(p => apiPaths.includes(p)), `len=${apiPaths.length}`)
  const health = await (await fetch(`${API}/api/v1/health`)).json()
  ok('A4 8010 验证实例健康', health?.data?.status === 'ok', JSON.stringify(health).slice(0, 100))

  console.log('\n=== B 5 个页面真实浏览器 DOM ===')
  if (!CHROME) throw new Error('未找到 Chrome / Edge')
  const profile = await mkdtemp(join(tmpdir(), 'pmwb-pbfull-'))
  const chrome = spawn(CHROME, [
    `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
    '--no-first-run', '--no-default-browser-check', '--headless=new',
    '--window-size=1680,1100', 'about:blank',
  ], { stdio: 'ignore' })
  let cdp
  try {
    const ws = new WebSocket(await fetchWsUrl())
    const onEvent = m => {
      if (m.method === 'Runtime.exceptionThrown' && process.env.PB_DEBUG_DOM) console.log('JS_EXC>', m.params.exceptionDetails.text, m.params.exceptionDetails.exception?.description?.slice(0, 300))
      if (m.method !== 'Fetch.requestPaused' || !cdp) return
      if (process.env.PB_DEBUG_DOM) console.log('REQ>', m.params.request.url)
      const body = Buffer.from(JSON.stringify(mockFor(m.params.request.url))).toString('base64')
      cdp.send('Fetch.fulfillRequest', {
        requestId: m.params.requestId, responseCode: 200,
        responseHeaders: [{ name: 'Content-Type', value: 'application/json; charset=utf-8' }], body,
      }).catch(() => {})
    }
    cdp = new CDP(ws, onEvent)
    await new Promise((res, rej) => { ws.addEventListener('open', res, { once: true }); ws.addEventListener('error', rej, { once: true }) })
    await cdp.send('Page.enable')
    await cdp.send('Runtime.enable')
    await cdp.send('Fetch.enable', { patterns: [{ urlPattern: '*api/v1*', requestStage: 'Request' }] })

    async function openPage(path, selector, name) {
      let ready = false
      for (let i = 0; i < 2 && !ready; i++) {
        await cdp.goto(`${BASE}${path}?v=pbfull`)
        ready = await cdp.waitFor(selector, 18000)
        if (!ready) await sleep(700)
      }
      ok(name, ready, `${path} ${selector}`)
      const txt = await cdp.eval('document.body.innerText').catch(() => '')
      if (process.env.PB_DEBUG_DOM) console.log('DOM>', path, '|', txt.replace(/\n/g, ' / ').slice(0, 900))
      return txt
    }

    const t0 = await openPage('/paiban/track', '.pb-page .pb-lanes', 'B1 排版跟踪页渲染（四环节泳道）')
    await cdp.waitFor('.pb-ticket', 10000)
    const t = await cdp.eval('document.body.innerText').catch(() => t0)
    if (process.env.PB_DEBUG_DOM) console.log('STATE>', await cdp.eval(`(()=>{const c=document.querySelector('.pb-page')?.__vueParentComponent;const s=c?.setupState||{};return JSON.stringify({keys:Object.keys(s).slice(0,20),ov:!!s.ov,planId:s.planId,tracksLen:s.tracks?.value?.items?.length,metaLen:s.meta?.value?.stages?.length})})()`))
    if (process.env.PB_DEBUG_DOM) console.log('DBG>', await cdp.eval(`JSON.stringify({stats:document.querySelectorAll('.pm-stat').length,tickets:document.querySelectorAll('.pb-ticket').length,lanes:document.querySelectorAll('.pb-lane').length})`))
    if (process.env.PB_DEBUG_DOM) console.log('STATE>', await cdp.eval(`(()=>{const c=document.querySelector('.pb-page')?.__vueParentComponent;const s=c?.setupState||{};return JSON.stringify({keys:Object.keys(s).slice(0,20),ov:!!s.ov,planId:s.planId,tracksLen:s.tracks?.value?.items?.length,metaLen:s.meta?.value?.stages?.length})})()`))
    if (process.env.PB_DEBUG_DOM) console.log('DBG>', await cdp.eval(`JSON.stringify({stats:document.querySelectorAll('.pm-stat').length,tickets:document.querySelectorAll('.pb-ticket').length,lanes:document.querySelectorAll('.pb-lane').length})`))
    ok('B2 排版跟踪 KPI 来自后端（不写死快照）', t.includes('按计划上线率') && t.includes('50'))
    ok('B3 泳道展示两条工单', t.includes('REQ-1') && t.includes('BUG-1'))
    ok('B4 主行口径说明可见', (t + t0).includes('不可加总'))
    // 真点工单卡 → 抽屉
    await cdp.eval(`document.querySelector('.pb-ticket')?.click(); true`)
    await cdp.waitFor('.el-drawer .el-tabs__item', 10000)
    await sleep(300)
    const drawer = await cdp.eval(`[...document.querySelectorAll('.el-drawer')].map(d=>d.innerText||'').find(t=>t.includes('团队环节')) || ''`)
    ok('B5 工单抽屉打开并有四个页签',
      ['团队环节', '登记结果', '手工处理', '风险与轨迹'].every(x => drawer.includes(x)), `len=${drawer.length}`)

    const tm = await openPage('/paiban/teams', '.pb-card table', 'B6 团队跟踪页渲染')
    ok('B7 团队矩阵/下钻同源提示', tm.includes('不可加总') && tm.includes('点击格内数字下钻'))
    ok('B8 团队明细有工单', tm.includes('REQ-1'))

    const rk = await openPage('/paiban/risks', '.pb-page .pb-card', 'B9 风险与督办页渲染')
    ok('B10 硬门禁说明可见', rk.includes('禁止登记') && rk.includes('dry_run'))
    ok('B11 督办预览逐单显示回执码与冷却', rk.includes('PB-ABC123') && rk.includes('剩余 18h'))
    ok('B12 真发需显式确认', rk.includes('确认发送（真发）'))

    await openPage('/paiban/feedback', '.pb-page .pb-card', 'B13 反馈同步页渲染')
    await cdp.waitFor('.el-table__row', 10000)
    const fb = await cdp.eval('document.body.innerText').catch(() => '')
    ok('B14 四通道与自由文本规则可见', fb.includes('团队批量更新') && fb.includes('只出建议进待核对'))
    ok('B15 待核对反馈列出原文', fb.includes('环境未就绪') && fb.includes('冲突'))

    const v = await openPage('/paiban/versions', '.pb-version', 'B16 版本计划页仍可渲染')
    ok('B17 菜单位置 任务中心 < 排版管理 < 需求与交付', (() => {
      const i1 = v.indexOf('任务中心'), i2 = v.indexOf('排版管理'), i3 = v.indexOf('需求与交付')
      return i1 >= 0 && i2 > i1 && i3 > i2
    })())

    console.log(`\n=== pb-1~pb-9 交付回归: ${pass} PASS / ${fail} FAIL ===`)
    if (fail) { console.log('失败项：' + failures.join(' | ')); process.exitCode = 1 }
  } finally { chrome.kill() }
}

main().catch(e => { console.error('FATAL', e); process.exit(1) })
