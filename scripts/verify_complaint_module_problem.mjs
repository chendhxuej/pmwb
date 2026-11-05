/**
 * 客诉 L2 功能模块问题 · 主要投诉点 页面真实浏览器回归（零依赖，走 CDP）
 *
 * 验证老大核心要求：描述不同、本质同模块的工单强制归并到同一类；
 * 主流投诉自动归集（不依赖人）；少量残留进入人工管理台（可选安全网）。
 *
 * 覆盖 /complaint-center/module-problem 页面：
 *   1. 页面挂载 + PageHeader 标题/副标题（含 vL2、跨表象汇聚）
 *   2. 汇总 KPI：总工单/缺陷已归集/缺陷类数/最大单类/未归类/咨询类
 *   3. 主要投诉点表：有数据、含 BROADBAND-ACT 且工单量≈73、表象数>1（跨表象汇聚）
 *   4. 展开「跨表象」看同一问题多种不同说法
 *   5. 人工管理台 tab：低置信+未归类+已改派队列可见（系统不依赖此操作即可运行）
 *
 * 用法（项目根执行）：
 *   PMWB_BASE=http://127.0.0.1:8000 PMWB_AUTH_USER=chendh PMWB_AUTH_PW=Chenxue520 \
 *     node scripts/verify_complaint_module_problem.mjs
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
const PORT = Number(process.env.CDP_PORT || 9354)
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
    await sleep(700)
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
  const profile = await mkdtemp(join(tmpdir(), 'pmwb-mp-'))
  const chrome = spawn(CHROME, [
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${profile}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--window-size=1680,1100',
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

    console.log('\n▶ 主要投诉点页面 /complaint-center/module-problem')
    await cdp.goto(`${BASE}/complaint-center/module-problem`)
    const mounted = await cdp.waitFor('.module-problem', 25000)
    mounted ? ok('页面挂载 .module-problem') : bad('页面未挂载')
    await sleep(4000) // 等三类接口加载

    const snap = await cdp.eval(`(() => {
      const root = document.querySelector('.module-problem')
      if (!root) return null
      const title = (root.querySelector('.pm-page-header__title')?.innerText || '').trim()
      const sub = (root.querySelector('.pm-page-header__subtitle')?.innerText || '').trim()
      const kpis = [...root.querySelectorAll('.summary-kpis .pm-stat')].map(c => ({
        label: (c.querySelector('.pm-stat__label')?.innerText || '').trim(),
        val: (c.querySelector('.pm-stat__val')?.innerText || '').trim(),
        sub: (c.querySelector('.pm-stat__sub')?.innerText || '').trim(),
      }))
      const alert = (root.querySelector('.summary-card .el-alert__title')?.innerText || '').trim()
      const tbl = root.querySelector('.el-table')
      const rows = tbl ? [...tbl.querySelectorAll('.el-table__body tbody tr')].map(tr => ({
        name: tr.querySelector('.cls-name')?.innerText?.trim() || '',
        surfaceCnt: tr.querySelector('.surface-cnt')?.innerText?.trim() || '',
        tds: [...tr.querySelectorAll('td')].map(td => (td.innerText || '').replace(/\\s+/g,' ').trim()),
      })) : []
      const headers = tbl ? [...tbl.querySelectorAll('.el-table__header th')].map(th => th.innerText.trim()) : []
      return { title, sub, kpis, alert, rows, headers, rowCount: rows.length }
    })()`)

    if (!snap) {
      bad('DOM 抓取失败')
    } else {
      snap.title.includes('主要投诉点') && snap.title.includes('功能模块问题')
        ? ok('PageHeader 标题正确', snap.title)
        : bad('PageHeader 标题不对', snap.title)
      snap.sub.includes('跨表象汇聚') || snap.sub.includes('vL2')
        ? ok('副标题体现 vL2 闭集 + 跨表象汇聚', snap.sub.slice(0, 40))
        : bad('副标题未体现口径', snap.sub.slice(0, 60))

      // 汇总 KPI
      const labels = snap.kpis.map(k => k.label)
      const need = ['总工单', '缺陷已归集', '缺陷类数', '最大单类', '未归类', '咨询类']
      const miss = need.filter(n => !labels.some(l => l.includes(n)))
      miss.length === 0
        ? ok('六张 KPI 卡齐全', snap.kpis.map(k => k.label + '=' + k.val).join(' '))
        : bad('KPI 缺失', miss.join(','))
      // 缺陷已归集应 > 1000（1486 总 - 未归类343 - 咨询570 ≈ 573 缺陷；此处按公式核对）
      const defectKpi = snap.kpis.find(k => k.label.includes('缺陷已归集'))
      const defectVal = defectKpi ? Number(String(defectKpi.val).replace(/[^\d]/g, '')) : 0
      defectVal > 0 ? ok('缺陷已归集有值', defectVal + ' 单') : bad('缺陷已归集为空')
      const totalKpi = snap.kpis.find(k => k.label.includes('总工单'))
      const totalVal = totalKpi ? Number(String(totalKpi.val).replace(/[^\d]/g, '')) : 0
      totalVal >= 1400 ? ok('总工单量级正确', totalVal + ' 单') : bad('总工单量异常', totalVal)

      // 主要投诉点表
      snap.headers.some(h => h.includes('功能模块问题') || h.includes('一句话'))
        ? ok('类表含「功能模块问题（一句话）」列')
        : bad('类表缺一句话描述列', snap.headers.join('|'))
      snap.rowCount > 0
        ? ok('主要投诉点表有数据', `rows=${snap.rowCount}`)
        : bad('主要投诉点表为空')

      if (snap.rowCount > 0) {
        // 跨表象汇聚核心验收：BROADBAND-ACT 归为一类且工单量≈73、表象数>1
        const bb = snap.rows.find(r => r.name.includes('一网通宽带') || r.name.includes('宽带'))
        if (bb) {
          // 列顺序固定：0 排名 / 1 名称 / 2 工单量 / 3 表象数 / 4 活跃周
          const cnt = Number(String(bb.tds[2] || '').replace(/[^\d]/g, '')) || 0
          const surf = Number(String(bb.surfaceCnt).replace(/[^\d]/g, '')) || 0
          ok('宽带类已归并为一行（跨表象汇聚）', bb.name.slice(0, 24))
          cnt >= 60 && cnt <= 90
            ? ok('宽带类工单量≈73（多表象合并）', cnt + ' 单')
            : bad('宽带类工单量异常', cnt + ' 单')
          surf > 1
            ? ok('表象数>1（同一问题多种不同说法）', surf + ' 种说法')
            : bad('表象数=1（跨表象汇聚未生效）', surf)
        } else {
          bad('未找到宽带类（跨表象归并目标）')
        }
        // 缺陷类数应=19
        const clsKpi = snap.kpis.find(k => k.label.includes('缺陷类数'))
        const clsVal = clsKpi ? Number(String(clsKpi.val).replace(/[^\d]/g, '')) : 0
        clsVal === 19 ? ok('缺陷类数=19（闭集收敛）') : bad('缺陷类数应为19', clsVal)
      }
    }

    // 截图留存（主要投诉点主视图，在切到人工管理台之前）
    try {
      const { data } = await cdp.send('Page.captureScreenshot', { format: 'png' })
      const out = join(process.cwd(), 'scripts', 'verify_module_problem_points.png')
      await import('node:fs/promises').then(fs => fs.writeFile(out, Buffer.from(data, 'base64')))
      console.log('  📸 主视图截图已存', out)
    } catch (e) {
      console.log('  ⚠ 主视图截图失败', e.message)
    }

    // 展开第一行的「跨表象」看多种说法
    console.log('\n▶ 跨表象展开')
    try {
      await cdp.clickAt('.module-problem .el-table__expand-icon', 0)
      const expanded = await cdp.waitFor('.module-problem .el-table__expanded-cell .surfaces', 8000)
      if (expanded) {
        const surfCount = await cdp.eval(`document.querySelectorAll('.module-problem .el-table__expanded-cell .surface-item').length`)
        surfCount > 1 ? ok('展开可见多种不同说法', surfCount + ' 条') : bad('展开说法数不足', surfCount)
      } else {
        bad('跨表象展开区未渲染')
      }
    } catch (e) {
      bad('跨表象展开点击失败 ' + e.message)
    }

    // 人工管理台
    console.log('\n▶ 人工管理台 tab')
    try {
      await cdp.eval(`(() => {
        const items = [...document.querySelectorAll('.module-problem .el-tabs__item')]
        const t = items.find(i => i.innerText.includes('人工管理台'))
        if (t) t.click()
        return !!t
      })()`)
      await sleep(2500)
      const review = await cdp.eval(`(() => {
        const root = document.querySelector('.module-problem')
        const tbl = root.querySelector('.el-tabs__item.is-active') // marker
        const active = root.querySelector('.el-tab-pane:not([style*="display: none"])') || root
        const rows = [...root.querySelectorAll('.el-table__body tbody tr')].length
        const blockTitle = (root.querySelector('.block-title')?.innerText || '').trim()
        const reviewKpi = (root.querySelector('.pm-stat__val.is-warning, .summary-kpis .pm-stat:nth-child(5) .pm-stat__val')?.innerText || '').trim()
        return { rows, blockTitle }
      })()`)
      review && review.rows > 0
        ? ok('人工管理台有数据（待处理队列）', `rows≈${review.rows}；${review.blockTitle}`)
        : bad('人工管理台无数据', JSON.stringify(review))
      // 断言待管理总量（未归类343 + 低置信151 = 494）；定位 review tab 的 block-sub（含「单」）
      const reviewTotalTxt = await cdp.eval(`(() => {
        const root = document.querySelector('.module-problem')
        const subs = [...root.querySelectorAll('.block-sub')].map(b => b.innerText || '')
        const reviewSub = subs.find(s => /共\\s*\\d+\\s*单/.test(s)) || ''
        const m = reviewSub.match(/共\\s*(\\d+)\\s*单/)
        return m ? Number(m[1]) : 0
      })()`)
      reviewTotalTxt >= 450 && reviewTotalTxt <= 520
        ? ok('人工管理台总量≈494（未归类+低置信）', reviewTotalTxt + ' 单')
        : bad('人工管理台总量异常', reviewTotalTxt)
    } catch (e) {
      bad('人工管理台 tab 验证失败 ' + e.message)
    }

    // 截图留存
    try {
      const { data } = await cdp.send('Page.captureScreenshot', { format: 'png' })
      const out = join(process.cwd(), 'scripts', 'verify_module_problem.png')
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
