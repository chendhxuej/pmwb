/**
 * 重点工作「从邮件导入」页面回归（零依赖，走 CDP）
 *
 * 验证页面化方案 C 的核心闭环：
 *   API：status 读得到邮件中心 / preview 出变更草案且不写库 / 快照标识稳定 / 回退被拦 / 提示标记
 *   DOM：工具栏入口 → 抽屉打开 → 六张概要卡 → 状态变更/备注/新增/存疑/邮件 五个分区 →
 *        默认勾选规则（例行任务/仍待办不勾、状态回退不可选）→ 全不选时按钮置灰
 *
 * 用法（项目根执行）：
 *   PMWB_BASE=http://127.0.0.1:8000 PMWB_AUTH_USER=chendh PMWB_AUTH_PW=xxx \
 *     node scripts/verify_keywork_mail_import.mjs
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
const PORT = Number(process.env.CDP_PORT || 9366)
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
    const r = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || 'eval error')
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
  async clickText(selector, text) {
    const r = await this.eval(`(() => {
      const els = [...document.querySelectorAll(${JSON.stringify(selector)})]
      const el = els.find(e => (e.innerText || '').trim().includes(${JSON.stringify(text)}))
      if (!el) return false
      el.click(); return true
    })()`)
    await sleep(800)
    return r
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
  const hasCard = await cdp.waitFor('.login-card', 15000)
  if (!hasCard) return true // 本地免登录
  await sleep(800)
  await cdp.eval(`(() => {
    const inputs = [...document.querySelectorAll('.login-card input')]
    const set = (el, v) => {
      const proto = Object.getPrototypeOf(el)
      Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v)
      el.dispatchEvent(new Event('input', { bubbles: true }))
    }
    set(inputs[0], ${JSON.stringify(USER)})
    set(inputs[1], ${JSON.stringify(PW)})
    return true
  })()`)
  await cdp.clickText('.login-card .el-button', '')
  return cdp.waitFor('.main-layout', 25000)
}

async function apiLogin() {
  const r = await fetch(`${BASE}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: USER, password: PW }),
  })
  const d = await r.json()
  return d?.data?.token || ''
}

async function main() {
  console.log(`\n▶ 接口层（${BASE}）`)
  const token = await apiLogin()
  const H = token ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }
  const auth = (p, init = {}) => fetch(`${BASE}/api/v1${p}`, { ...init, headers: { ...H, ...(init.headers || {}) } }).then((r) => r.json())

  const st = (await auth('/key-works/mail-import/status')).data || {}
  st.mail_db_ready ? ok('邮件中心收件箱库可读', st.mail_db_path || '') : bad('邮件中心不可读', st.mail_db_reason)
  st.last_run ? ok('上次收口日可取', st.last_run) : bad('收口日为空')

  const since = st.last_run || '2026-10-29'
  const prev = (
    await auth('/key-works/mail-import/preview', { method: 'POST', body: JSON.stringify({ since }) })
  ).data
  if (!prev) {
    bad('preview 无返回')
  } else {
    const s = prev.summary || {}
    s.mail_count > 0 ? ok('解析到周反馈邮件', `${s.mail_count} 封`) : bad('未解析到邮件', JSON.stringify(s))
    (prev.changes || []).every((c) => c.key && c.kind && c.id)
      ? ok('变更条目字段完整（key/kind/id）', `${prev.changes.length} 条`)
      : bad('变更条目缺字段')
    prev.snapshot_id && prev.snapshot_id.length === 16
      ? ok('快照标识生成', prev.snapshot_id)
      : bad('快照标识异常', prev.snapshot_id)
    const blocked = (prev.changes || []).filter((c) => c.blocked_from)
    s.blocked_count === blocked.length
      ? ok('回退被拦条目计数一致', `${blocked.length} 条`)
      : bad('回退计数不一致', `${s.blocked_count} vs ${blocked.length}`)
    const hinted = (prev.changes || []).filter((c) => c.hint)
    hinted.length
      ? ok('提示标记生效（例行/仍待办）', hinted.map((h) => `${h.kind}#${h.id}:${h.hint}`).join(' '))
      : bad('无提示标记（例行任务应被识别）')
    ;(prev.doubts || []).every((d) => d.key && d.score >= 0.6 && d.score < 0.82)
      ? ok('存疑条目相似度落在 0.6~0.82', `${prev.doubts.length} 条`)
      : bad('存疑相似度越界')
    Array.isArray(prev.unmatched_mails) ? ok('未匹配专题清单返回结构正确') : bad('缺 unmatched_mails')
  }

  const badSnap = await auth('/key-works/mail-import/apply', {
    method: 'POST',
    body: JSON.stringify({ since, snapshot_id: 'deadbeef' }),
  })
  badSnap.code !== 0 ? ok('快照不符时拒绝落库', badSnap.message) : bad('快照校验未生效（有脏写风险）')

  // ── DOM ──
  console.log('\n▶ 页面层 /key-works')
  const profile = await mkdtemp(join(tmpdir(), 'pmwb-kwmi-'))
  const chrome = spawn(
    CHROME,
    [
      `--remote-debugging-port=${PORT}`,
      `--user-data-dir=${profile}`,
      '--no-first-run',
      '--no-default-browser-check',
      '--window-size=1680,1100',
      'about:blank',
    ],
    { stdio: 'ignore' },
  )
  try {
    const ws = new WebSocket(await fetchWsUrl())
    await new Promise((res, rej) => {
      ws.addEventListener('open', res, { once: true })
      ws.addEventListener('error', rej, { once: true })
    })
    const cdp = new CDP(ws)
    await cdp.send('Page.enable')

    const logged = await login(cdp)
    logged ? ok('登录并进入主布局') : bad('登录失败（检查 PMWB_AUTH_USER/PW）')

    await cdp.goto(`${BASE}/key-works`)
    ;(await cdp.waitFor('.table-toolbar', 25000)) ? ok('重点工作页挂载') : bad('重点工作页未挂载')
    await sleep(1500)

    const clicked = await cdp.clickText('.page-actions button, .table-toolbar button', '从邮件导入')
    clicked ? ok('工具栏「从邮件导入」入口存在并可点') : bad('找不到「从邮件导入」按钮')

    const opened = await cdp.waitFor('.mi-head', 20000)
    opened ? ok('导入抽屉打开') : bad('抽屉未打开')
    if (opened) {
      await sleep(4000) // 等 preview 返回
      const snap = await cdp.eval(`(() => {
        const head = document.querySelector('.mi-head')
        const title = head?.querySelector('.pm-drawer-title')?.innerText?.trim() || ''
        const sub = head?.querySelector('.mi-head-sub')?.innerText?.trim() || ''
        const stats = [...document.querySelectorAll('.mi-stat')].map(s => ({
          label: (s.querySelector('.mi-stat-label')?.innerText || '').trim(),
          val: (s.querySelector('.mi-stat-num')?.innerText || '').trim(),
        }))
        const tabs = [...document.querySelectorAll('.mi-tabs .el-tabs__item')].map(t => t.innerText.trim())
        const rows = [...document.querySelectorAll('.mi-tabs .el-tab-pane')][0]
          ? [...document.querySelectorAll('.mi-tabs .el-tab-pane')][0].querySelectorAll('.el-table__body tbody tr').length
          : 0
        const range = document.querySelector('.mi-bar .el-range-input')?.value || ''
        return { title, sub, stats, tabs, rows, range }
      })()`)
      snap.title.includes('从邮件导入周反馈') ? ok('抽屉标题正确', snap.title) : bad('抽屉标题不对', snap.title)
      snap.sub.includes('周反馈请求') ? ok('副标题说明来源') : bad('副标题缺说明')
      snap.stats.length === 6
        ? ok('六张概要卡齐全', snap.stats.map((s) => `${s.label}=${s.val}`).join(' '))
        : bad('概要卡数量异常', String(snap.stats.length))
      const labels = snap.stats.map((s) => s.label).join('|')
      ;['邮件', '状态变更', '进展备注', '拟新增', '存疑', '回退被拦'].every((k) => labels.includes(k))
        ? ok('概要卡覆盖全部分类')
        : bad('概要卡分类缺失', labels)
      snap.tabs.some((t) => t.includes('状态变更')) && snap.tabs.some((t) => t.includes('存疑'))
        ? ok('五个分区 tab 渲染', snap.tabs.join(' / '))
        : bad('分区 tab 缺失', snap.tabs.join(' / '))
      snap.rows > 0 ? ok('状态变更表有数据', `rows=${snap.rows}`) : bad('状态变更表为空')

      // 默认勾选规则
      const checks = await cdp.eval(`(() => {
        const pane = document.querySelectorAll('.mi-tabs .el-tab-pane')[0]
        if (!pane) return null
        const rows = [...pane.querySelectorAll('.el-table__body tbody tr')]
        const isChecked = (tr) => !!tr.querySelector('.el-checkbox.is-checked, .el-checkbox__input.is-checked')
        const map = (tr) => ({
          text: (tr.innerText || '').replace(/\\s+/g, ' ').slice(0, 60),
          checked: isChecked(tr),
        })
        return {
          routine: rows.filter(tr => (tr.innerText || '').includes('例行任务')).map(map),
          total: rows.length,
          checkedCount: rows.filter(isChecked).length,
          allChecked: [...document.querySelectorAll('.mi-tabs .el-tab-pane')]
            .reduce((n, pane) => n + pane.querySelectorAll('.el-checkbox.is-checked, .el-checkbox__input.is-checked').length, 0),
          blockedDisabled: rows
            .filter(tr => (tr.innerText || '').includes('已是终点'))
            .every(tr => !!tr.querySelector('.el-checkbox.is-disabled, .el-checkbox__input.is-disabled')),
        }
      })()`)
      if (!checks) bad('默认勾选状态抓取失败')
      else {
        checks.allChecked > 0 ? ok('可执行条目默认勾选', `${checks.allChecked} 条`) : bad('没有任何条目被默认勾选')
        checks.routine.length
          ? checks.routine.every((r) => !r.checked)
            ? ok('例行任务默认不勾（等人判断）', checks.routine[0].text.slice(0, 34))
            : bad('例行任务被默认勾选', JSON.stringify(checks.routine))
          : bad('状态变更表里没找到例行任务行')
        checks.blockedDisabled ? ok('已是终点的条目不允勾选（状态只进不退）') : bad('回退条目仍可勾选')
      }

      // 存疑 tab 默认忽略
      await cdp.clickText('.mi-tabs .el-tabs__item', '存疑')
      await sleep(600)
      const doubtRows = await cdp.eval(`(() => {
        const items = [...document.querySelectorAll('.mi-tabs .el-tabs__item')]
        const idx = items.findIndex(t => t.innerText.includes('存疑'))
        const pane = document.querySelectorAll('.mi-tabs .el-tab-pane')[idx]
        if (!pane) return 0
        return pane.querySelectorAll('.el-table__body tbody tr').length
      })()`)
      doubtRows > 0 ? ok('存疑分区有数据', `rows=${doubtRows}`) : bad('存疑分区为空')

      // 全不选 → 按钮置灰
      const uncheckAll = async (tabName) => {
        await cdp.clickText('.mi-tabs .el-tabs__item', tabName)
        await sleep(400)
        await cdp.eval(`(() => {
          const tabs = [...document.querySelectorAll('.mi-tabs .el-tabs__item')]
          const idx = tabs.findIndex(t => t.innerText.includes(${JSON.stringify(tabName)}))
          const pane = document.querySelectorAll('.mi-tabs .el-tab-pane')[idx]
          if (!pane) return false
          const btn = [...pane.querySelectorAll('button')].find(b => (b.innerText || '').includes('全不选'))
          if (!btn) return false
          btn.click(); return true
        })()`)
        await sleep(400)
      }
      await uncheckAll('状态变更')
      await uncheckAll('拟新增')
      await uncheckAll('进展备注')
      await sleep(400)
      const footer = await cdp.eval(`(() => {
        const btn = [...document.querySelectorAll('.mi-footer button')].find(b => (b.innerText||'').includes('执行导入'))
        const hint = document.querySelector('.mi-footer .mi-hint')?.innerText || ''
        return { exists: !!btn, disabled: btn ? btn.disabled || btn.classList.contains('is-disabled') : null, hint }
      })()`)
      footer.exists ? ok('底部执行区渲染', footer.hint) : bad('底部执行区缺失')
      footer.disabled ? ok('全部取消后「执行导入」置灰（防空跑）') : bad('无选中仍可执行', footer.hint)
    }
  } finally {
    chrome.kill()
  }

  console.log(`\n===== ${pass} 通过 / ${fail} 失败 =====`)
  if (fail) {
    console.log('失败项：\n  - ' + failures.join('\n  - '))
    process.exit(1)
  }
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
