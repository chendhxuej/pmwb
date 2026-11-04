/**
 * 客诉 v4.2 问题点类页面真实浏览器回归（零依赖，走 Chrome DevTools Protocol）
 *
 * 验证老大核心要求：投诉问题点描述具体、工单与归类准确、分析过程不依赖人。
 * 覆盖 /complaint-center/problem-v42 页面：
 *   1. 页面挂载 + PageHeader 标题
 *   2. 验收状态卡：发布结论 / 六项指标 / 关键 KPI
 *   3. 问题点类表：有数据、描述为「一句话具体投诉问题点」（非抽象标签）
 *   4. 未归类清单：逐单写明缺口原因
 *
 * 用法（项目根执行）：
 *   PMWB_BASE=http://127.0.0.1:8000 PMWB_AUTH_USER=chendh PMWB_AUTH_PW=Chenxue520 \
 *     node scripts/verify_complaint_problem_v42.mjs
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

const BASE = process.env.PMWB_BASE || 'http://127.0.0.1:8000'
const PORT = Number(process.env.CDP_PORT || 9353)
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

// 抽象标签黑名单：v4.0 之前的问题点描述常含这些「泛词」，需被本回归拦截。
// 注意：须用中文边界判定，避免「在其他地方」「咨询他人」等正常句中子串误杀。
const ABSTRACT_TERMS = ['其他', '使用咨询', '配置错误', '规则不合理', '系统异常', '待人工', '批量投诉']
const _CJK = /[一-鿿]/
function _hasBareTerm(text, term) {
  // 任一处出现「前后不同时被中文字符夹住」即视为命中抽象类（standalone 或「其他类问题」都算，
  // 但「在其他地方」「咨询他人」这类正常句子不算）。
  let i = text.indexOf(term)
  while (i >= 0) {
    const before = i > 0 ? text[i - 1] : ''
    const after = i + term.length < text.length ? text[i + term.length] : ''
    if (!(_CJK.test(before) && _CJK.test(after))) return true
    i = text.indexOf(term, i + 1)
  }
  return false
}

async function main() {
  const profile = await mkdtemp(join(tmpdir(), 'pmwb-pv42-'))
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

    console.log('\n▶ 问题点类页面 /complaint-center/problem-v42')
    await cdp.goto(`${BASE}/complaint-center/problem-v42`)
    const mounted = await cdp.waitFor('.problem-v42', 25000)
    mounted ? ok('页面挂载 .problem-v42') : bad('页面未挂载')
    await sleep(3500) // 等数据加载

    const snap = await cdp.eval(`(() => {
      const root = document.querySelector('.problem-v42')
      if (!root) return null
      const title = (root.querySelector('.pm-page-header__title')?.innerText || '').trim()
      const sub = (root.querySelector('.pm-page-header__subtitle')?.innerText || '').trim()
      const statusCard = root.querySelector('.status-card')
      const kpis = statusCard
        ? [...statusCard.querySelectorAll('.pm-stat')].map(c => ({
            label: (c.querySelector('.pm-stat__label')?.innerText || '').trim(),
            val: (c.querySelector('.pm-stat__val')?.innerText || '').trim(),
          }))
        : []
      const publishTag = statusCard ? (statusCard.querySelector('.el-tag')?.innerText || '').trim() : ''
      const tables = [...root.querySelectorAll('.el-table')]
      const clsTbl = tables[0]
      const clsRows = clsTbl
        ? [...clsTbl.querySelectorAll('.el-table__body tbody tr')].map(tr => tr.innerText.replace(/\\s+/g, ' ').trim())
        : []
      const clsHeaders = clsTbl
        ? [...clsTbl.querySelectorAll('.el-table__header th')].map(th => th.innerText.trim())
        : []
      const uncTbl = tables[1]
      const uncRows = uncTbl
        ? [...uncTbl.querySelectorAll('.el-table__body tbody tr')].map(tr => tr.innerText.replace(/\\s+/g, ' ').trim())
        : []
      const alerts = [...root.querySelectorAll('.el-alert')].map(a => a.innerText.replace(/\\s+/g, ' ').trim())
      return { title, sub, kpis, publishTag, clsRows, clsHeaders, uncRows, alerts,
               clsCount: clsRows.length, uncCount: uncRows.length }
    })()`)

    if (!snap) {
      bad('DOM 抓取失败')
    } else {
      snap.title.includes('问题点类') && snap.title.includes('v4.2')
        ? ok('PageHeader 标题正确', snap.title)
        : bad('PageHeader 标题不对', snap.title)
      snap.sub.includes('不依赖人')
        ? ok('副标题含「分析过程不依赖人」')
        : bad('副标题未体现不依赖人', snap.sub.slice(0, 60))

      // 验收状态卡
      snap.publishTag ? ok('验收结论标签渲染', snap.publishTag) : bad('缺验收结论标签')
      const kpiLabels = snap.kpis.map(k => k.label)
      const needKpis = ['工单总数', '已生成问题点', '问题点类', '未归类', '待自动补跑']
      const hit = needKpis.filter(n => kpiLabels.some(l => l.includes(n)))
      hit.length === needKpis.length
        ? ok('状态卡五项 KPI 齐全', snap.kpis.map(k => k.label + '=' + k.val).join(' '))
        : bad('状态卡 KPI 缺失', needKpis.filter(n => !hit.includes(n)).join(','))
      snap.kpis.some(k => k.label.includes('问题点类') && Number(String(k.val || '').replace(/[^\d]/g, '')) > 0)
        ? ok('问题点类计数有值')
        : bad('问题点类计数为空')

      // 问题点类表：核心验收
      snap.clsHeaders.some(h => h.includes('投诉问题点') || h.includes('具体描述'))
        ? ok('类表含「具体投诉问题点」列')
        : bad('类表缺具体描述列', snap.clsHeaders.join('|'))
      snap.clsCount > 0
        ? ok('问题点类表有数据', `rows=${snap.clsCount}`)
        : bad('问题点类表为空')

      if (snap.clsCount > 0) {
        const descs = snap.clsRows.map(r => {
          // 取每行第一列之后的描述文本（去掉类编号前缀）
          const m = r.replace(/^\\S+\\s+/, '')
          return m
        })
        const avgLen = descs.reduce((s, d) => s + d.length, 0) / descs.length
        avgLen >= 12
          ? ok('问题点描述平均长度达标（具体）', `avgLen=${avgLen.toFixed(1)}`)
          : bad('问题点描述过短（可能仍抽象）', `avgLen=${avgLen.toFixed(1)}`)
        const abstractHit = descs.filter(d => ABSTRACT_TERMS.some(t => _hasBareTerm(d, t)))
        abstractHit.length === 0
          ? ok('无抽象泛词描述（已收敛为具体一句话）')
          : bad('仍存在抽象泛词描述', abstractHit.slice(0, 3).join(' / '))
        // 描述应含可观察失败或业务动作信号（报错/未/无法/拦截/申请/办理/查询/开通/派/回单…）
        const concrete = descs.filter(d => /(报错|未|无法|拦截|失败|缺失|不一致|申请|办理|查询|开通|派|回单|异常|超时|锁|拒|退|改|装|催)/.test(d))
        const ratio = concrete.length / descs.length
        ratio >= 0.6
          ? ok('描述具体率达标（含可观察失败/动作）', `ratio=${(ratio * 100).toFixed(0)}%`)
          : bad('描述具体率偏低', `ratio=${(ratio * 100).toFixed(0)}%`)
      }

      // 未归类清单
      snap.uncCount > 0
        ? ok('未归类清单有数据', `rows=${snap.uncCount}`)
        : ok('未归类清单为空（全部已归类）')
      if (snap.uncCount > 0) {
        const hasReason = snap.uncRows.every(r => r.length > 12)
        hasReason ? ok('未归类清单逐单写明缺口') : bad('未归类清单缺口说明缺失')
      }

      snap.alerts.length ? ok('异常/观测告警渲染', snap.alerts.length + ' 条') : ok('无异常告警')
    }

    // 截图留存
    try {
      const { data } = await cdp.send('Page.captureScreenshot', { format: 'png' })
      const out = join(process.cwd(), 'scripts', 'verify_problem_v42.png')
      await import('node:fs/promises').then(fs => fs.writeFile(out, Buffer.from(data, 'base64')))
      console.log('  📸 截图已存', out)
    } catch (e) {
      console.log('  ⚠ 截图失败', e.message)
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
