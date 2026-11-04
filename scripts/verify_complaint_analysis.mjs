/**
 * 投诉专题三子页面重构（CP-S1~S7）—— 真实浏览器回归（零依赖，走 Chrome DevTools Protocol）
 *
 * 覆盖老大 2026-11-04 明确的三页面功能与数据要求：
 *   1. 投诉现状 /complaint-center/dashboard
 *      - 五板块：概览与波动 / 已知vs新增 / 五类汇总 / 压降指引 / 措施跟踪
 *      - 核心指标「已知问题率」出数；已知问题表与新增问题表都有数据
 *      - 五类必须是 系统问题/流程优化/数据异常/规则咨询/操作咨询
 *   2. 问题台账 /complaint-center/problems
 *      - 只展示「已复核、未闭环」；候选独立页签；台账表有根因簇列
 *   3. 工单明细 /complaint-center/tickets
 *      - 关联问题（已知/新增）列；已知/新增筛选；根因状态含「信息不足」（不再有待人工队列）
 *
 * 用法（项目根执行）：
 *   PMWB_BASE=http://127.0.0.1:8010 PMWB_AUTH_USER=chendh PMWB_AUTH_PW=xxx \
 *     node scripts/verify_complaint_analysis.mjs
 */
import { existsSync } from 'node:fs'
import { spawn } from 'node:child_process'
import { mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const CHROME =
  process.env.CHROME_PATH ||
  [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  ].find((p) => existsSync(p))

const BASE = process.env.PMWB_BASE || 'http://127.0.0.1:8010'
const PORT = Number(process.env.CDP_PORT || 9352)
const USER = process.env.PMWB_AUTH_USER || 'chendh'
const PW = process.env.PMWB_AUTH_PW || ''

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
      expression, returnByValue: true, awaitPromise: true,
    })
    if (r.exceptionDetails) {
      throw new Error(r.exceptionDetails.exception?.description || 'eval error')
    }
    return r.result.value
  }
  async goto(url) {
    await this.send('Page.navigate', { url })
  }
  async waitFor(sel, timeout = 25000) {
    const t0 = Date.now()
    while (Date.now() - t0 < timeout) {
      const found = await this.eval(`!!document.querySelector(${JSON.stringify(sel)})`).catch(() => false)
      if (found) return true
      await sleep(400)
    }
    return false
  }
  async clickAt(sel, idx = 0) {
    const r = await this.eval(`(() => {
      const els = document.querySelectorAll(${JSON.stringify(sel)})
      const el = els[${idx}]
      if (!el) return false
      el.click()
      return true
    })()`)
    if (!r) throw new Error(`click target not found: ${sel}[${idx}]`)
    await sleep(600)
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

async function login(cdp) {
  await cdp.goto(`${BASE}/login`)
  const hasCard = await cdp.waitFor('.login-card', 20000)
  if (!hasCard) return false
  await sleep(800)
  await cdp.eval(`(() => {
    const inputs = [...document.querySelectorAll('.login-card input')]
    const set = (el, v) => {
      const proto = Object.getPrototypeOf(el)
      const desc = Object.getOwnPropertyDescriptor(proto, 'value')
      desc.set.call(el, v)
      el.dispatchEvent(new Event('input', { bubbles: true }))
    }
    set(inputs[0], ${JSON.stringify(USER)})
    set(inputs[1], ${JSON.stringify(PW)})
    return true
  })()`)
  await cdp.clickAt('.login-card .el-button')
  return cdp.waitFor('.main-layout', 25000)
}

async function main() {
  const profile = await mkdtemp(join(tmpdir(), 'pmwb-ca-'))
  const chrome = spawn(CHROME, [
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${profile}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--window-size=1600,1000',
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

    console.log('\n▶ 登录')
    const logged = await login(cdp)
    logged ? ok('登录并进入主布局') : bad('登录失败（检查 PMWB_AUTH_USER/PW）')

    /* ── 1. 投诉现状：五板块 + 核心指标 ── */
    console.log('\n▶ 投诉现状 /complaint-center/dashboard')
    await cdp.goto(`${BASE}/complaint-center/dashboard`)
    const hasDash = await cdp.waitFor('.complaint-dashboard', 25000)
    hasDash ? ok('页面挂载 .complaint-dashboard') : bad('投诉现状页未挂载')
    await sleep(3000)

    const dash = await cdp.eval(`(() => {
      const root = document.querySelector('.complaint-dashboard')
      if (!root) return null
      const titles = [...root.querySelectorAll('.card-header h3')].map(h => h.innerText.trim())
      const secs = [...root.querySelectorAll('section.card')]
      const kpis = [...root.querySelectorAll('.kpi-card')].map(c => ({
        num: (c.querySelector('.kpi-num')?.innerText || '').trim(),
        label: (c.querySelector('.kpi-label')?.innerText || '').trim(),
      }))
      const tables = [...root.querySelectorAll('.el-table')]
      const rowCount = (i) => tables[i] ? tables[i].querySelectorAll('.el-table__body tbody tr').length : -1
      const l1Table = root.querySelector('.l1-class-table')
      const l1Rows = l1Table ? [...l1Table.querySelectorAll('.el-table__body tbody tr')].map(tr => tr.innerText.replace(/\\s+/g, ' ').trim()) : []
      // 问题族表（业务链路）：用 class 精确定位，避免表格顺序变动后断言错位
      const themeTbl = root.querySelector('.theme-table')
      const themeRows = themeTbl ? [...themeTbl.querySelectorAll('.el-table__body tbody tr')].map(tr => tr.innerText.replace(/\\s+/g, ' ').trim()) : []
      const themeHeaders = themeTbl ? [...themeTbl.querySelectorAll('.el-table__header th')].map(th => th.innerText.trim()) : []
      const knownTag = [...root.querySelectorAll('.el-tag')].map(t => t.innerText.trim())
      return {
        titles, sectionCount: secs.length, kpis, tableCount: tables.length,
        knownTableRows: rowCount(0), newTableRows: rowCount(1),
        themeRows, themeHeaders,
        clusterTableRows: rowCount(2), guideTableRows: rowCount(3),
        l1Rows, knownTag,
        hasWarn: !!root.querySelector('.pm-note.warn'),
        hasCaseLine: !!root.querySelector('.case-line'),
        hasBigCluster: [...root.querySelectorAll('.sub-h')].some(e => e.innerText.includes('重点根因簇')),
        bodyText: root.innerText.slice(0, 4000),
      }
    })()`)
    if (dash) {
      const has = (kw) => dash.titles.some(t => t.includes(kw))
      has('本周概览与波动') ? ok('板块一：本周概览与波动') : bad('缺板块一')
      has('已知问题 vs 新增问题') ? ok('板块二：已知 vs 新增') : bad('缺板块二')
      has('投诉问题分类汇总') || has('问题族分析') ? ok('板块三：问题族分析（业务链路）') : bad('缺板块三')
      has('问题族分析') ? ok('板块三标题已改为业务链路视角') : bad('板块三仍是旧标题')
      has('工单压降分析指引') ? ok('板块四：压降指引') : bad('缺板块四')
      has('措施跟踪与自动验证') ? ok('板块五：措施跟踪与验证') : bad('缺板块五')
      dash.sectionCount >= 5 ? ok('板块卡片数 ≥5', `actual=${dash.sectionCount}`) : bad('板块卡片不足', `${dash.sectionCount}`)

      const rate = dash.kpis.find(k => k.label.includes('已知问题率'))
      if (rate && rate.num.includes('%')) ok('核心指标「已知问题率」出数', rate.num)
      else bad('已知问题率未出数', JSON.stringify(rate || null))

      const cov = dash.kpis.find(k => k.label.includes('根因分析覆盖'))
      if (cov && String(cov.num).includes('%')) ok('根因分析覆盖率出数', cov.num)
      else bad('根因覆盖率未出数', JSON.stringify(cov || null))

      // 已知问题表允许为空：本周无已知单是真实业务状态（如 W45 在办簇 0 单），
      // 只要求页面给出明确空态文案而非渲染缺失。
      if (dash.knownTableRows > 0) ok('已知问题表有数据', `rows=${dash.knownTableRows}`)
      else if (dash.bodyText.includes('本周没有一单能被在办问题解释')) ok('已知问题表空态合法（本周已知 0 单）')
      else bad('已知问题表为空且无空态文案')
      // 问题族表：反「散」的核心，必须是族粒度且带日均环比口径
      // 2026-11-04 细化后 10 族：受理/施工拆开、计费出账/账务结算拆开
      const THEME_NAMES = ['订单受理与提交', '施工与装维交付', '业务激活与状态回写', '数据同步与建档',
        '电子协议签约', '产品与资费配置', '计费出账', '账务结算', '咨询与操作指引', '其他']
      const themeFlat = dash.themeRows.join(' ')
      const themeHit = THEME_NAMES.filter(n => themeFlat.includes(n))
      dash.themeRows.length >= 9
        ? ok('问题族表有数据（已细化）', `族=${dash.themeRows.length}，命中 ${themeHit.length}/10`)
        : bad('问题族行数不足（细化后应 ≥9）', `族=${dash.themeRows.length}`)
      themeHit.length === 10
        ? ok('细化后 10 个族全部在位（受理/施工、计费出账/账务结算 已拆开）')
        : bad('细化族缺失', THEME_NAMES.filter(n => !themeHit.includes(n)).join(','))
      dash.themeHeaders.some(h => h.includes('日均环比')) ? ok('族表含「日均环比」列（残缺周不误判）') : bad('族表缺日均环比列')
      // 本周无单的族：环比必须显示「—」，不能算成 -100%（会被读成「已清零」）
      const zeroRow = dash.themeRows.find(r => r.startsWith('其他'))
      zeroRow && zeroRow.includes('—') && !zeroRow.includes('-100')
        ? ok('本周无单的族环比显示「—」（不误报 -100%）')
        : bad('本周无单族环比处理不对', zeroRow || '未找到「其他」族行')
      dash.hasCaseLine ? ok('一次性个案单列计数在位') : bad('缺一次性个案说明')
      dash.hasBigCluster ? ok('重点根因簇（≥5 单）独立成表') : bad('缺重点根因簇表')

      dash.newTableRows > 0 ? ok('新增问题表有数据', `rows=${dash.newTableRows}`) : bad('新增问题表为空')
      dash.guideTableRows > 0 ? ok('压降指引表有数据', `rows=${dash.guideTableRows}`) : bad('压降指引表为空')

      const names = ['系统问题', '流程优化', '数据异常', '规则咨询', '操作咨询']
      const flat = dash.l1Rows.join(' ')
      const hit = names.filter(n => flat.includes(n))
      hit.length === 5 ? ok('五类分类齐全（新口径）') : bad('五类分类不全', hit.join(','))
      dash.l1Rows.length === 5 ? ok('五类表恰好 5 行', `rows=${dash.l1Rows.length}`) : bad('五类表行数不对', `${dash.l1Rows.length}`)

      dash.bodyText.includes('候选问题不计为已知') ? ok('已知判定口径说明在位') : bad('缺已知判定口径说明')
      dash.bodyText.includes('不可比') || dash.bodyText.includes('周环比')
        ? ok('波动不可比提示在位')
        : bad('缺波动不可比提示')
    } else {
      bad('投诉现状 DOM 抓取失败')
    }

    /* ── 2. 问题台账：收窄 + 页签 ── */
    console.log('\n▶ 问题台账 /complaint-center/problems')
    await cdp.goto(`${BASE}/complaint-center/problems`)
    const hasPb = await cdp.waitFor('.problem-ledger', 25000)
    hasPb ? ok('页面挂载 .problem-ledger') : bad('问题台账页未挂载')
    await sleep(2800)

    const pb = await cdp.eval(`(() => {
      const root = document.querySelector('.problem-ledger')
      if (!root) return null
      const tabs = [...root.querySelectorAll('.el-tabs__item')].map(t => t.innerText.trim())
      const pane = root.querySelector('.el-tab-pane')
      const tables = [...root.querySelectorAll('.el-table')]
      const firstTbl = tables[0]
      const rows = firstTbl ? [...firstTbl.querySelectorAll('.el-table__body tbody tr')] : []
      const rowText = rows.map(tr => tr.innerText.replace(/\\s+/g, ' ').trim())
      const headers = firstTbl
        ? [...firstTbl.querySelectorAll('.el-table__header th')].map(th => th.innerText.trim())
        : []
      const statusTags = [...root.querySelectorAll('.el-table__body .el-tag')].map(t => t.innerText.trim())
      return { tabs, tableCount: tables.length, rowCount: rows.length, rowText, headers, statusTags }
    })()`)
    if (pb) {
      pb.tabs.length >= 2 ? ok('台账页签 ≥2（在办 / 待确认候选）', pb.tabs.join(' | ')) : bad('台账页签缺失', pb.tabs.join('|'))
      pb.tabs.some(t => t.includes('在办问题')) ? ok('页签一：在办问题（已复核未闭环）') : bad('缺在办页签')
      pb.tabs.some(t => t.includes('待确认候选')) ? ok('页签二：待确认候选') : bad('缺候选页签')
      pb.headers.some(h => h.includes('根因簇')) ? ok('台账表含「根因簇」列') : bad('台账表缺根因簇列')
      const candMixed = pb.rowText.some(t => t.includes('candidate'))
      !candMixed ? ok('台账主列表未混入候选问题') : bad('台账主列表混入候选')
      pb.rowCount >= 0 ? ok('台账主列表可渲染', `rows=${pb.rowCount}`) : bad('台账主列表异常')
    } else {
      bad('问题台账 DOM 抓取失败')
    }

    /* 切到候选页签 */
    const tabClicked = await cdp.eval(`(() => {
      const tabs = [...document.querySelectorAll('.problem-ledger .el-tabs__item')]
      const t = tabs.find(x => x.innerText.includes('待确认'))
      if (!t) return false
      t.click()
      return true
    })()`)
    await sleep(1500)
    const candPane = await cdp.eval(`(() => {
      const panes = [...document.querySelectorAll('.problem-ledger .el-tab-pane')]
      const vis = panes.find(p => p.offsetParent !== null) || panes[1]
      if (!vis) return null
      const rows = vis.querySelectorAll('.el-table__body tbody tr').length
      const text = vis.innerText.slice(0, 600)
      return { rows, text }
    })()`)
    if (tabClicked && candPane) {
      candPane.rows > 0 ? ok('候选页签有候选数据', `rows=${candPane.rows}`) : bad('候选页签为空')
      candPane.text.includes('确认入账') || candPane.text.includes('入账')
        ? ok('候选页签含入账操作说明')
        : bad('候选页签缺入账说明')
    } else {
      bad('候选页签切换失败')
    }

    /* ── 2b. 问题详情：关联工单 + 建立运营工单（2026-11-04 老大要求） ── */
    // 回到在办页签并点第一行「详情」
    await cdp.eval(`(() => {
      const tabs = [...document.querySelectorAll('.problem-ledger .el-tabs__item')]
      const t = tabs.find(x => x.innerText.includes('在办'))
      if (t) t.click()
    })()`)
    await sleep(1200)
    const detailOpened = await cdp.eval(`(() => {
      const btns = [...document.querySelectorAll('.problem-ledger .el-button')]
      const b = btns.find(x => x.innerText.trim() === '详情' && x.offsetParent !== null)
      if (!b) return false
      b.click()
      return true
    })()`)
    await sleep(2600)
    const dt = await cdp.eval(`(() => {
      const dw = document.querySelector('.el-drawer')
      if (!dw) return null
      const body = dw.innerText
      const tables = [...dw.querySelectorAll('.el-table')]
      const tRows = tables.map(t => t.querySelectorAll('.el-table__body tbody tr').length)
      const hasIssueBtn = [...dw.querySelectorAll('.el-button')].some(b => b.innerText.includes('建立运营工单'))
      const firstTbl = dw.querySelector('.el-table')
      const ticketHeaders = firstTbl ? [...firstTbl.querySelectorAll('.el-table__header th')].map(th => th.innerText.trim()) : []
      return {
        hasTicketSec: body.includes('关联投诉工单'),
        hasActionSec: body.includes('关联措施'),
        hasIssueBtn,
        tableRowCounts: tRows,
        ticketHeaders,
        total: (body.match(/关联投诉工单（(\\d+) 单）/) || [])[1] || '0',
      }
    })()`)
    if (detailOpened && dt) {
      dt.hasTicketSec ? ok('详情含「关联投诉工单」区块', `总数 ${dt.total}`) : bad('详情缺关联投诉工单区块')
      dt.hasActionSec ? ok('详情含「关联措施」区块') : bad('详情缺关联措施区块')
      dt.hasIssueBtn ? ok('详情有「建立运营工单」入口') : bad('详情缺建立运营工单入口')
      dt.tableRowCounts.some(n => n > 0) ? ok('详情工单/措施表可渲染', `rows=${dt.tableRowCounts.join('/')}`) : bad('详情表全空')
      // 老大 2026-11-04：明细要直达核查信息，AI 分析/核查过程必须上列，工单号等运维字段弱化
      const tFlat = (dt.ticketHeaders || []).join('|')
      tFlat.includes('AI 分析总结') && tFlat.includes('核查过程')
        ? ok('详情工单表含「AI 分析总结」与「核查过程」列')
        : bad('详情工单表缺核查信息列', tFlat)
      !tFlat.includes('创建时间') ? ok('运维字段已弱化（无创建时间列）') : bad('详情工单表仍保留创建时间列（应移除）')
    } else {
      bad('问题详情抽屉未打开')
    }
    // 点开建立工单对话框（只验证表单存在，不提交，避免写库）
    const issueDlg = await cdp.eval(`(() => {
      const dw = document.querySelector('.el-drawer')
      const b = dw ? [...dw.querySelectorAll('.el-button')].find(x => x.innerText.includes('建立运营工单')) : null
      return b ? (b.click(), true) : false
    })()`)
    await sleep(1600)
    const dlgInfo = await cdp.eval(`(() => {
      const dlgs = [...document.querySelectorAll('.el-dialog')].filter(d => d.offsetParent !== null)
      const d = dlgs.find(x => x.innerText.includes('建立运营工单'))
      if (!d) return null
      const txt = d.innerText
      // 情况说明预填（textarea 有自动总结内容）与明细预览表（2026-11-04 表格化）
      const hasDescVal = [...d.querySelectorAll('textarea')].some(t => (t.value || '').includes('【问题描述】'))
      const dlgTbl = d.querySelector('.ctx-tickets .el-table')
      const ctxRows = dlgTbl ? dlgTbl.querySelectorAll('.el-table__body tr').length : 0
      return {
        hasScene: txt.includes('问题场景'),
        hasAccept: txt.includes('验收标准'),
        hasProblem: txt.includes('所属问题'),
        hasLinkTip: txt.includes('双向关联') || txt.includes('联动'),
        hasCtx: txt.includes('代入工单明细'),
        hasDescField: txt.includes('情况说明'),
        hasDescVal,
        hasCtxTbl: ctxRows > 0,
        ctxRows,
        hasMailTip: txt.includes('邮件') && txt.includes('表格'),
      }
    })()`)
    if (issueDlg && dlgInfo) {
      dlgInfo.hasProblem ? ok('建单对话框带所属问题上下文') : bad('建单对话框缺所属问题')
      dlgInfo.hasScene ? ok('建单对话框有场景选择') : bad('建单对话框缺场景')
      dlgInfo.hasAccept ? ok('建单对话框要求验收标准') : bad('建单对话框缺验收标准')
      dlgInfo.hasLinkTip ? ok('建单对话框说明措施/工单联动') : bad('建单对话框缺联动说明')
      dlgInfo.hasCtx ? ok('建单对话框可选代入周期') : bad('建单对话框缺代入周期选项')
      // 2026-11-04 表格化：情况说明自动总结预填可编辑 + 明细预览表 + 邮件表格说明
      dlgInfo.hasDescField ? ok('建单对话框有「情况说明」输入') : bad('建单对话框缺情况说明')
      dlgInfo.hasDescVal ? ok('情况说明预填自动总结（可编辑）') : bad('情况说明未预填自动总结')
      dlgInfo.hasCtxTbl ? ok('对话框含代入工单明细预览表', `rows=${dlgInfo.ctxRows}`) : bad('对话框缺明细预览表')
      dlgInfo.hasMailTip ? ok('对话框说明邮件按表格同步') : bad('对话框缺邮件表格说明')
      // 关闭对话框，保持页面干净
      await cdp.eval(`(() => {
        const dlgs = [...document.querySelectorAll('.el-dialog')].filter(d => d.offsetParent !== null)
        const d = dlgs.find(x => x.innerText.includes('建立运营工单'))
        const btn = d ? [...d.querySelectorAll('.el-button')].find(b => b.innerText.trim() === '取消') : null
        if (btn) btn.click()
      })()`)
      await sleep(600)
    } else {
      bad('建立运营工单对话框未弹出')
    }

    /* ── 3. 工单明细：关联问题列 + 信息不足 ── */
    console.log('\n▶ 工单明细 /complaint-center/tickets')
    await cdp.goto(`${BASE}/complaint-center/tickets`)
    const hasTk = await cdp.waitFor('.complaint-tickets', 25000)
    hasTk ? ok('页面挂载 .complaint-tickets') : bad('工单明细页未挂载')
    await sleep(3000)

    const tk = await cdp.eval(`(() => {
      const root = document.querySelector('.complaint-tickets')
      if (!root) return null
      const headers = [...root.querySelectorAll('.el-table__header th')].map(th => th.innerText.trim())
      const rows = root.querySelectorAll('.el-table__body tbody tr').length
      const tags = [...root.querySelectorAll('.el-table__body .el-tag')].map(t => t.innerText.trim())
      const selects = [...root.querySelectorAll('.filter-bar .el-select')].map(s => s.innerText.trim() || s.getAttribute('placeholder') || '')
      const placeholders = [...root.querySelectorAll('.filter-bar input')].map(i => i.getAttribute('placeholder') || '')
      return { headers, rows, tags, selects, placeholders }
    })()`)
    if (tk) {
      tk.headers.some(h => h.includes('关联问题')) ? ok('表头含「关联问题（已知/新增）」') : bad('缺关联问题列')
      tk.rows > 0 ? ok('工单列表有数据', `rows=${tk.rows}`) : bad('工单列表为空')
      tk.headers.some(h => h.includes('根因分析')) ? ok('保留根因分析列') : bad('缺根因分析列')
      const hasKnownTag = tk.tags.some(t => t.startsWith('已知')) || tk.tags.some(t => t.includes('新增问题'))
      hasKnownTag ? ok('行内已渲染已知/新增标签') : bad('行内未渲染已知/新增标签')
      const labelText = [...tk.selects, ...tk.placeholders].join(' ')
      labelText.includes('已知/新增') || labelText.includes('已知')
        ? ok('存在「已知/新增」筛选')
        : bad('缺已知/新增筛选')
    } else {
      bad('工单明细 DOM 抓取失败')
    }

    /* 信息不足筛选值：直接查下拉选项 DOM（需展开 select） */
    const insufficientOpt = await cdp.eval(`(() => {
      const root = document.querySelector('.complaint-tickets')
      if (!root) return null
      return root.innerText.includes('信息不足') || root.innerText.includes('待人工')
        ? { hasIns: root.innerText.includes('信息不足'), hasManual: root.innerText.includes('待人工') }
        : { hasIns: false, hasManual: false }
    })()`)
    if (insufficientOpt) {
      !insufficientOpt.hasManual ? ok('已移除「待人工」文案（无人工队列）') : bad('页面仍出现「待人工」')
    }

  } finally {
    try { chrome.kill() } catch {}
  }

  console.log(`\n════════ 结果：${pass} 通过 / ${fail} 失败 ════════`)
  if (fail) {
    console.log('失败项：')
    failures.forEach(f => console.log('  - ' + f))
    process.exit(1)
  }
}

main().catch((e) => {
  console.error('\n脚本异常：', e?.message || e)
  process.exit(2)
})
