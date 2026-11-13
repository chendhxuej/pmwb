/**
 * 客诉专题「主要投诉点」标准名 v2 · 真实 DOM 回归（CDP，零依赖）
 *
 * 验证「页面展示信息已修正」：
 *   1. 列头不再是「功能模块问题（一句话）」，改为「主要投诉点（标准类）」
 *   2. 20 条标准类名零斜杠堆叠、零状态轴词、均为三段式单失效点
 *   3. 「归因锚点」显式可见（台账按此 ID 关联）
 *   4. 口径说明写明状态轴 / 排序同周 / 台账锚点 / 未归类单列
 *   5. 首页看板速览、问题台账锚点同步显示标准类名
 *
 * 用法：
 *   PMWB_BASE=http://127.0.0.1:8000 PMWB_AUTH_USER=chendh PMWB_AUTH_PW=Chenxue520 \
 *     node scripts/verify_complaint_standard_dom.mjs
 *   # 新代码实例（含 dict_version / 台账标准类名）加 PMWB_STRICT=1
 *
 * 断言函数固定签名 (name, cond, extra)，禁止 (n, e='') 恒 PASS 写法。
 */
import { existsSync } from 'node:fs'
import { spawn } from 'node:child_process'
import { mkdtemp, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const CHROME = process.env.CHROME_PATH || [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].find(p => existsSync(p))

const BASE = process.env.PMWB_BASE || 'http://127.0.0.1:8000'
const PORT = Number(process.env.CDP_PORT || 9371)
const USER = process.env.PMWB_AUTH_USER || 'chendh'
const PW = process.env.PMWB_AUTH_PW || ''
const STRICT = process.env.PMWB_STRICT === '1'
// 与后端 constants/complaint_module.py::STATUS_AXIS_TERMS 对齐（测试断言词表）
const STATUS_WORDS = ['在途', '已结单', '已归档', '待回单', '已回复', '已派单',
  '处理中', '已关闭', '已完工', '已竣工', '已回单']

let pass = 0
let fail = 0
const failures = []
const evidence = {}
function ok(name, cond, extra = '') {
  if (cond) {
    pass++
    console.log(`  PASS  ${name}${extra ? '  ' + extra : ''}`)
  } else {
    fail++
    failures.push(name)
    console.log(`  FAIL  ${name}${extra ? '  ' + extra : ''}`)
  }
}
function info(name, text) { console.log(`  INFO  ${name}  ${text}`) }
const sleep = ms => new Promise(r => setTimeout(r, ms))

class CDP {
  constructor(ws) {
    this.ws = ws
    this.id = 0
    this.pending = new Map()
    ws.addEventListener('message', ev => {
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
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || 'eval error')
    return r.result.value
  }
  async goto(url) { await this.send('Page.navigate', { url }) }
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
      if (!els[${idx}]) return false
      els[${idx}].click()
      return true
    })()`)
    if (!r) throw new Error(`click target not found: ${sel}[${idx}]`)
    await sleep(700)
  }
  /** SPA 首导航偶发旧上下文：重试导航，不放宽断言 */
  async gotoReady(path, sel, tries = 3) {
    for (let i = 0; i < tries; i++) {
      await this.goto(`${BASE}${path}`)
      if (await this.waitFor(sel, 22000)) { await sleep(3800); return true }
    }
    return false
  }
}

async function fetchWsUrl() {
  for (let i = 0; i < 40; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/list`)
      const tabs = await res.json()
      const page = tabs.find(t => t.type === 'page')
      if (page) return page.webSocketDebuggerUrl
    } catch {}
    await sleep(500)
  }
  throw new Error('CDP endpoint not ready')
}

async function login(cdp) {
  await cdp.goto(`${BASE}/login`)
  if (!(await cdp.waitFor('.login-card', 20000))) return false
  await sleep(800)
  await cdp.eval(`(() => {
    const inputs = [...document.querySelectorAll('.login-card input')]
    const set = (el, v) => {
      const desc = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value')
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

async function capture(cdp, filename) {
  try {
    const { data } = await cdp.send('Page.captureScreenshot', { format: 'png' })
    const out = join(process.cwd(), 'scripts', filename)
    await writeFile(out, Buffer.from(data, 'base64'))
    console.log('  📸 截图 ' + out)
  } catch (e) { info('截图失败', e.message) }
}

async function main() {
  console.log(`=== 客诉专题标准名 v2 真实 DOM 验收 | BASE=${BASE} STRICT=${STRICT} ===`)
  const profile = await mkdtemp(join(tmpdir(), 'pmwb-std-'))
  const chrome = spawn(CHROME, [
    `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
    '--no-first-run', '--no-default-browser-check', '--window-size=1680,1100',
    'about:blank',
  ], { stdio: 'ignore' })

  try {
    const ws = new WebSocket(await fetchWsUrl())
    await new Promise((res, rej) => {
      ws.addEventListener('open', res, { once: true })
      ws.addEventListener('error', rej, { once: true })
    })
    const cdp = new CDP(ws)
    await cdp.send('Page.enable')

    console.log('\n▶ 登录')
    ok('登录并进入主布局', await login(cdp))

    // ── 页面 1：主要投诉点 ──
    console.log('\n▶ /complaint-center/module-problem')
    ok('主要投诉点页挂载', await cdp.gotoReady('/complaint-center/module-problem', '.module-problem'))
    const s = await cdp.eval(`(() => {
      const root = document.querySelector('.module-problem')
      if (!root) return null
      const tbl = root.querySelector('.el-table')
      const headers = tbl ? [...tbl.querySelectorAll('.el-table__header th')]
        .map(th => (th.innerText || '').replace(/\\s+/g, ' ').trim()) : []
      const rows = tbl ? [...tbl.querySelectorAll('.el-table__body tbody tr')].map(tr => ({
        name: (tr.querySelector('.cls-name')?.innerText || '').trim(),
        anchor: (tr.querySelector('.anchor-tag')?.innerText || '').trim(),
      })) : []
      const kpis = [...root.querySelectorAll('.summary-kpis .pm-stat')].map(c => ({
        label: (c.querySelector('.pm-stat__label')?.innerText || '').trim(),
        val: (c.querySelector('.pm-stat__val')?.innerText || '').trim(),
      }))
      return {
        headers, rows, kpis,
        alert: (root.querySelector('.summary-card .el-alert')?.innerText || ''),
        blockTitle: (root.querySelector('.block-title')?.innerText || '').trim(),
        sub: (root.querySelector('.pm-page-header__subtitle')?.innerText || '').trim(),
        title: (root.querySelector('.pm-page-header__title')?.innerText || '').trim(),
      }
    })()`)
    evidence.moduleProblem = s
    if (!s) {
      ok('DOM 抓取成功', false, 'snap=null')
    } else {
      ok('列头为「主要投诉点（标准类）」',
        s.headers.some(h => h.includes('主要投诉点（标准类）')),
        s.headers.slice(0, 5).join(' | '))
      ok('旧列头「功能模块问题（一句话）」已移除',
        !s.headers.some(h => h.includes('一句话')), s.headers.join(' | '))
      ok('新增「归因锚点」列', s.headers.some(h => h.includes('归因锚点')))
      ok('「累计工单」列为全周期口径标注',
        s.headers.some(h => h.includes('累计工单（全周期）')))
      ok('类表有数据（缺陷类 ≥ 15 行）', s.rows.length >= 15, `rows=${s.rows.length}`)
      const names = s.rows.map(r => r.name).filter(Boolean)
      ok('全部类名零斜杠堆叠', names.length > 0 && names.every(n => !n.includes('/')),
        `names=${names.length}`)
      ok('全部类名零状态轴词',
        names.length > 0 && names.every(n => !STATUS_WORDS.some(w => n.includes(w))))
      ok('全部类名为三段式（模块·对象·性质）',
        names.length > 0 && names.every(n => (n.match(/·/g) || []).length === 2))
      ok('每行有 MP- 前缀归因锚点',
        s.rows.length > 0 && s.rows.every(r => /^MP-/.test(r.anchor)),
        `sample=${s.rows[0]?.anchor}`)
      const close = s.rows.find(r => r.anchor === 'MP-ORDER-CLOSE')
      ok('MP-ORDER-CLOSE 已改为单失效点标准名',
        !!close && close.name.includes('施工单回单') && !close.name.includes('在途'),
        close?.name || 'missing')
      ok('口径说明写明「状态轴 / 不写进类名」',
        s.alert.includes('状态轴') && s.alert.includes('不写进类名'))
      ok('口径说明写明「累计工单不参与排序、不可加总」',
        s.alert.includes('不参与排序') && s.alert.includes('不可与本周单量加总'))
      ok('口径说明写明台账锚点关联与未归类单列',
        s.alert.includes('归因锚点') && s.alert.includes('未归类单列'))
      ok('区块标题为「按所选周单量降序」', s.blockTitle.includes('按所选周单量降序'), s.blockTitle)
      const need = ['总工单', '缺陷已归集', '缺陷类数', '最大单类', '未归类', '咨询类']
      ok('六张 KPI 卡齐全', need.every(n => s.kpis.some(k => k.label.includes(n))))
      const clsKpi = s.kpis.find(k => k.label.includes('缺陷类数'))
      const clsVal = Number(String(clsKpi?.val || '').replace(/[^\d]/g, '')) || 0
      ok('KPI「缺陷类数」= 表格行数（展示/计数同源）', clsVal === s.rows.length,
        `kpi=${clsVal} rows=${s.rows.length}`)
      if (STRICT) {
        ok('副标题带标准口径版本 v2', /标准口径 v\d+/.test(s.sub), s.sub.slice(0, 80))
      } else {
        info('副标题（版本号需重启后端后生效）', s.sub.slice(0, 80))
      }
    }
    await capture(cdp, 'verify_complaint_standard_points.png')

    // ── 页面 2：首页看板速览 ──
    console.log('\n▶ /complaint-center/dashboard')
    ok('看板页挂载', await cdp.gotoReady('/complaint-center/dashboard', '.mp-overview'))
    const d = await cdp.eval(`(() => {
      const root = document.querySelector('.mp-overview')
      if (!root) return null
      return {
        title: (root.querySelector('h3')?.innerText || '').trim(),
        hint: (root.querySelector('.hint')?.innerText || '').trim(),
        topNames: [...root.querySelectorAll('.mp-top__item .mp-name')].map(e => e.innerText.trim()),
      }
    })()`)
    evidence.dashboard = d
    ok('速览标题为「主要投诉点（标准类 · 闭集）」',
      !!d && d.title.includes('标准类') && d.title.includes('闭集'), d?.title || 'missing')
    ok('速览 hint 写明三元组与状态轴',
      !!d && d.hint.includes('失效性质') && d.hint.includes('状态轴'), d?.hint?.slice(0, 80) || '')
    ok('速览 TOP 名称零斜杠堆叠',
      !!d && d.topNames.length > 0 && d.topNames.every(n => !n.includes('/')),
      `n=${d?.topNames.length} sample=${d?.topNames[0]}`)

    // ── 页面 3：问题台账归因锚点 ──
    console.log('\n▶ /complaint-center/problems')
    const ledgerReady = await cdp.gotoReady('/complaint-center/problems', '.el-table')
    ok('台账页挂载', ledgerReady)
    const l = await cdp.eval(`(() => {
      const tags = [...document.querySelectorAll('.el-tag')]
        .map(e => (e.innerText || '').trim())
      const headers = [...document.querySelectorAll('.el-table__header th')]
        .map(e => (e.innerText || '').trim())
      return { tags, headers, bodyText: (document.body.innerText || '').slice(0, 20000) }
    })()`)
    evidence.ledger = { headers: l?.headers, tags: l?.tags?.slice(0, 30) }
    ok('台账列头写明「归因锚点（主要投诉点标准类）」',
      !!l && l.headers.some(h => h.includes('主要投诉点标准类')),
      l?.headers?.slice(0, 8).join(' | '))
    const zhTags = (l?.tags || []).filter(t => t.includes('·') && !t.startsWith('模块·'))
    if (STRICT) {
      ok('台账锚点显示中文标准类名（非仅 ID）', zhTags.length > 0,
        `n=${zhTags.length} sample=${zhTags[0]}`)
    } else {
      info('台账锚点中文名（需重启后端加载新 SQL）', `zh=${zhTags.length} tags=${(l?.tags || []).slice(0, 5).join(',')}`)
    }
    await capture(cdp, 'verify_complaint_standard_ledger.png')

    const out = join(process.cwd(), 'data', 'complaint_standard_dom_result.json')
    await writeFile(out, JSON.stringify({ base: BASE, strict: STRICT, pass, fail, failures, evidence }, null, 2), 'utf8')
    console.log(`\nRESULT pass=${pass} fail=${fail} -> ${out}`)
    if (failures.length) console.log('FAILURES: ' + failures.join(' | '))
  } finally {
    chrome.kill()
  }
  process.exit(fail === 0 ? 0 : 1)
}

main().catch(e => { console.error('FATAL', e); process.exit(2) })
