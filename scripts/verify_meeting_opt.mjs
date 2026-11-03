/**
 * verify_meeting_opt.mjs —— 会议模块三项优化 真实浏览器回归
 *
 * 场景（2026-11-03 会议模块优化）：
 *   ① 连续多天会议登记 + 月历逐日连续标记
 *   ② 会议类型字典管理（/meetings/types CRUD + 页面「类型管理」弹窗）
 *   ③ 开始/结束时间手输（HH:mm 校验 + 1430→14:30 快捷补全）
 *
 * 断言：
 *   A1 类型管理弹窗打开且渲染字典表（≥7 行，首行为「需求讨论」）
 *   A2 会议类型下拉从接口 hydrate（选项含「需求讨论」「问题分析」）
 *   A3 多天会议在月历 11/5、11/6、11/7 三天连续打点；点 11/6 右栏出「跨天」标注与「跨 3 天」时长
 *   A4 时间手输：1430 失焦补全为 14:30；99:99 触发格式校验红字
 *
 * 用法：node scripts/verify_meeting_opt.mjs [BASE]
 *   BASE 默认 http://127.0.0.1:8010（须为加载新代码的后端，8000 若未重启请用 8010）
 */
import { existsSync } from 'node:fs'
import { spawn } from 'node:child_process'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { readFileSync } from 'node:fs'

const BASE = process.env.PMWB_BASE || 'http://127.0.0.1:8010'
// 登录凭据：默认从 backend/.env 读取，避免硬编码
const ENV_TXT = readFileSync(new URL('../backend/.env', import.meta.url), 'utf-8')
const USER = process.env.PMWB_AUTH_USER || ENV_TXT.match(/^AUTH_USERNAME=(.*)$/m)?.[1]?.trim() || 'chendh'
const PASS = process.env.PMWB_AUTH_PW || ENV_TXT.match(/^AUTH_PASSWORD=(.*)$/m)?.[1]?.trim() || ''

let pass = 0
let fail = 0
const ok = (name) => { pass++; console.log(`  ✅ ${name}`) }
const bad = (name, detail) => { fail++; console.log(`  ❌ ${name} — ${detail}`) }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function main() {
  // ── 0. 准备数据：登录 + 建多天会议 ──
  const loginRes = await fetch(`${BASE}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: USER, password: PASS }),
  }).then((r) => r.json())
  if (loginRes.code !== 0) throw new Error('登录失败: ' + JSON.stringify(loginRes))
  const token = loginRes.data.token
  const H = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }

  // 清理旧验证数据
  const list = await fetch(`${BASE}/api/v1/meetings?page=1&page_size=999`, { headers: H }).then((r) => r.json())
  for (const m of list.data?.items || []) {
    if (m.meeting_id === 'MEET-VERIFY-1103') {
      await fetch(`${BASE}/api/v1/meetings/${m.id}`, { method: 'DELETE', headers: H })
    }
  }
  const created = await fetch(`${BASE}/api/v1/meetings`, {
    method: 'POST',
    headers: H,
    body: JSON.stringify({
      meeting_id: 'MEET-VERIFY-1103',
      title: '验证-跨天会议(可删)',
      meeting_type: '需求讨论',
      status: 'planned',
      start_time: '2026-11-05 14:00:00',
      end_time: '2026-11-07 17:30:00',
      host: '陈大海',
      domain_code: 'smoke',
      attendees: [{ name: '陈大海', is_required: 1 }],
    }),
  }).then((r) => r.json())
  if (created.code !== 0) throw new Error('创建多天会议失败: ' + JSON.stringify(created))
  console.log('  准备：多天会议 11-05 14:00 ~ 11-07 17:30 已创建')

  // ── 1. 启动 Chrome（CDP）──
  const CHROME = [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  ].find(existsSync)
  if (!CHROME) throw new Error('Chrome/Edge not found')
  const profile = await mkdtemp(join(tmpdir(), 'pmwb-meet-'))
  const chrome = spawn(CHROME, [
    '--remote-debugging-port=9347',
    `--user-data-dir=${profile}`,
    '--no-first-run',
    '--headless=new',
    '--window-size=1600,1000',
    'about:blank',
  ], { stdio: 'ignore' })

  try {
    let wsUrl
    for (let i = 0; i < 40; i++) {
      try {
        const targets = await (await fetch('http://127.0.0.1:9347/json/list')).json()
        const page = targets.find((x) => x.type === 'page')
        if (page) { wsUrl = page.webSocketDebuggerUrl; break }
      } catch {}
      await sleep(400)
    }
    if (!wsUrl) throw new Error('CDP not reachable')
    const ws = new WebSocket(wsUrl)
    await new Promise((res, rej) => {
      ws.addEventListener('open', res, { once: true })
      ws.addEventListener('error', rej, { once: true })
    })
    let id = 0
    const pend = new Map()
    ws.addEventListener('message', (ev) => {
      const m = JSON.parse(ev.data)
      if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id) }
    })
    const send = (method, params = {}) => new Promise((r) => {
      const i = ++id
      pend.set(i, r)
      ws.send(JSON.stringify({ id: i, method, params }))
    })
    const evalJs = async (expr) => {
      const r = await send('Runtime.evaluate', {
        expression: expr,
        awaitPromise: true,
        returnByValue: true,
      })
      if (r.result?.exceptionDetails) throw new Error('page eval error: ' + JSON.stringify(r.result.exceptionDetails.exception?.description || r.result.exceptionDetails.text))
      return r.result?.result?.value
    }
    const nav = async (url) => {
      await send('Page.navigate', { url })
      for (let i = 0; i < 60; i++) {
        const ready = await evalJs(`document.readyState === 'complete'`)
        if (ready) break
        await sleep(300)
      }
      await sleep(600)
    }
    const waitFor = async (expr, ms = 8000) => {
      const end = Date.now() + ms
      while (Date.now() < end) {
        const v = await evalJs(expr)
        if (v) return v
        await sleep(300)
      }
      return null
    }
    const clickByText = async (sel, text) => {
      const r = await evalJs(`(() => {
        const els = [...document.querySelectorAll('${sel}')]
        const el = els.find((e) => e.textContent.trim().includes('${text}'))
        if (!el) return false
        el.click()
        return true
      })()`)
      if (!r) throw new Error(`click fail: ${sel} "${text}"`)
      await sleep(500)
      return r
    }

    await send('Page.enable')
    await send('Runtime.enable')

    // ── 2. 种 token 后进入会议页 ──
    await nav(`${BASE}/login`)
    await evalJs(`localStorage.setItem('pmwb_token', ${JSON.stringify(token)}); localStorage.setItem('pmwb_username', ${JSON.stringify(USER)}); true`)
    await nav(`${BASE}/meeting/list`)
    const loaded = await waitFor(`!!document.querySelector('.meeting-view')`)
    if (!loaded) throw new Error('会议页未加载')
    ok('会议页加载（/meeting/list，token 免登录直入）')

    // ── A2 类型下拉 hydrate：打开新增会议，展开会议类型下拉 ──
    await clickByText('button', '新增会议')
    const dlgOpen = await waitFor(`!!document.querySelector('.el-dialog .el-form')`)
    if (!dlgOpen) throw new Error('新增会议弹窗未打开')
    // 点「会议类型」select（表单内第 2 个 el-select：状态在前? 顺序：状态、类型——按 label 找）
    const selOpened = await evalJs(`(() => {
      const items = [...document.querySelectorAll('.el-dialog .el-form-item')]
      const item = items.find((i) => i.querySelector('.el-form-item__label')?.textContent.includes('会议类型'))
      if (!item) return false
      item.querySelector('.el-select__wrapper, .el-select')?.click()
      return true
    })()`)
    if (!selOpened) throw new Error('找不到会议类型下拉')
    await sleep(600)
    const opts = await evalJs(`(() => {
      const drops = [...document.querySelectorAll('.el-select-dropdown')]
      const visible = drops.find((d) => d.offsetParent !== null || getComputedStyle(d).display !== 'none')
      return visible ? [...visible.querySelectorAll('.el-select-dropdown__item span')].map((s) => s.textContent.trim()) : []
    })()`)
    if (opts.includes('需求讨论') && opts.includes('问题分析') && opts.includes('其他')) {
      ok(`A2 会议类型下拉接口化（${opts.length} 个选项：${opts.join('/')}）`)
    } else {
      bad('A2 会议类型下拉接口化', '选项=' + JSON.stringify(opts))
    }
    // 关闭下拉与弹窗
    await evalJs(`document.body.click(); true`)
    await sleep(300)
    await clickByText('.el-dialog__footer button', '取消')

    // ── A1 类型管理弹窗 ──
    await clickByText('button', '类型管理')
    const mgrOpen = await waitFor(`!!document.querySelector('.el-dialog') && [...document.querySelectorAll('.el-dialog__title')].some((t) => t.textContent.includes('会议类型管理'))`)
    if (mgrOpen) {
      const rows = await waitFor(`(() => {
        const dlg = [...document.querySelectorAll('.el-dialog')].find((d) => d.querySelector('.el-dialog__title')?.textContent.includes('会议类型管理'))
        if (!dlg) return null
        const trs = [...dlg.querySelectorAll('.el-table__body-wrapper tbody tr')]
        if (trs.length < 7) return null
        return trs.map((tr) => tr.querySelector('.el-input__inner')?.value || '')
      })()`)
      if (rows && rows[0] === '需求讨论') {
        ok(`A1 类型管理弹窗渲染字典表（${rows.length} 行：${rows.join('/')}）`)
      } else {
        bad('A1 类型管理弹窗渲染字典表', 'rows=' + JSON.stringify(rows))
      }
      await evalJs(`(() => {
        const dlg = [...document.querySelectorAll('.el-dialog')].find((d) => d.querySelector('.el-dialog__title')?.textContent.includes('会议类型管理'))
        dlg?.querySelector('.el-dialog__headerbtn')?.click()
        return true
      })()`)
      await sleep(500)
    } else {
      bad('A1 类型管理弹窗打开', '未见「会议类型管理」标题')
    }

    // ── A3 月历连续标记 ──
    await sleep(500)
    const calOk = await waitFor(`(() => {
      const cells = [...document.querySelectorAll('.cal-cell')]
      const days = ['5', '6', '7'].map((d) => {
        const cell = cells.find((c) => c.querySelector('.cal-day')?.textContent.trim() === d)
        return cell ? cell.querySelectorAll('.cal-dot').length : -1
      })
      return days.every((n) => n >= 1) ? days : null
    })()`, 10000)
    if (calOk) {
      ok(`A3 月历 11/5、11/6、11/7 连续打点（各 ${calOk.join('、')} 个点）`)
    } else {
      bad('A3 月历连续打点', '三天中存在无 dot 的日期')
    }
    // 点 11/6 → 右栏跨天标注
    await evalJs(`(() => {
      const cells = [...document.querySelectorAll('.cal-cell')].filter((c) => !c.classList.contains('other'))
      const cell = cells.find((c) => c.querySelector('.cal-day')?.textContent.trim() === '6')
      cell?.click()
      return true
    })()`)
    await sleep(700)
    const multiTag = await evalJs(`(() => {
      const rows = [...document.querySelectorAll('.today-card .mt-row')]
      const row = rows.find((r) => r.textContent.includes('验证-跨天会议'))
      if (!row) return { noRow: true, rows: rows.map((r) => r.textContent.replace(/\\s+/g, ' ').trim().slice(0, 70)) }
      return {
        tag: row.querySelector('.mt-tag.multi')?.textContent.trim() || null,
        dur: row.querySelector('.mt-dur')?.textContent.trim() || null,
      }
    })()`)
    if (multiTag && multiTag.tag && multiTag.tag.includes('11/05') && multiTag.tag.includes('11/07') && /跨\s*3\s*天/.test(multiTag.dur || '')) {
      ok(`A3 跨天标注与时长（tag="${multiTag.tag}" dur="${multiTag.dur}"）`)
    } else {
      bad('A3 跨天标注与时长', JSON.stringify(multiTag))
    }

    // ── A4 时间手输：补全 + 校验 ──
    await clickByText('button', '新增会议')
    await waitFor(`!!document.querySelector('.el-dialog .el-form')`)
    const hm = await evalJs(`(() => {
      const items = [...document.querySelectorAll('.el-dialog .el-form-item')]
      const startItem = items.find((i) => i.querySelector('.el-form-item__label')?.textContent.includes('开始日期'))
      const hmInput = startItem?.parentElement?.querySelector('.el-input__inner[placeholder="HH:mm"]')
        || [...document.querySelectorAll('.el-dialog .el-input__inner')].find((i) => i.placeholder === 'HH:mm')
      if (!hmInput) return null
      const setVal = (v) => {
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
        setter.call(hmInput, v)
        hmInput.dispatchEvent(new Event('input', { bubbles: true }))
        hmInput.dispatchEvent(new Event('change', { bubbles: true }))
        hmInput.focus()
        hmInput.dispatchEvent(new Event('blur'))
      }
      setVal('1430')
      return true
    })()`)
    if (!hm) throw new Error('找不到时间输入框')
    await sleep(400)
    const normalized = await evalJs(`[...document.querySelectorAll('.el-dialog .el-input__inner')].find((i) => i.placeholder === 'HH:mm')?.value`)
    if (normalized === '14:30') {
      ok('A4 时间手输 1430 失焦补全为 14:30')
    } else {
      bad('A4 时间手输补全', 'value=' + normalized)
    }
    // 非法值校验：99:99
    await evalJs(`(() => {
      const hmInput = [...document.querySelectorAll('.el-dialog .el-input__inner')].find((i) => i.placeholder === 'HH:mm')
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
      setter.call(hmInput, '99:99')
      hmInput.dispatchEvent(new Event('input', { bubbles: true }))
      hmInput.dispatchEvent(new Event('change', { bubbles: true }))
      hmInput.focus()
      hmInput.dispatchEvent(new Event('blur'))
      return true
    })()`)
    await sleep(500)
    const err = await evalJs(`(() => {
      const items = [...document.querySelectorAll('.el-dialog .el-form-item')]
      const item = items.find((i) => [...i.querySelectorAll('.el-input__inner')].some((x) => x.placeholder === 'HH:mm'))
      return item?.querySelector('.el-form-item__error')?.textContent.trim() || null
    })()`)
    if (err && err.includes('HH:mm')) {
      ok(`A4 非法时间校验红字（"${err}"）`)
    } else {
      bad('A4 非法时间校验', 'error=' + JSON.stringify(err))
    }

    // 清理验证数据
    await fetch(`${BASE}/api/v1/meetings?page=1&page_size=999`, { headers: H }).then((r) => r.json()).then(async (l) => {
      for (const m of l.data?.items || []) {
        if (m.meeting_id === 'MEET-VERIFY-1103') {
          await fetch(`${BASE}/api/v1/meetings/${m.id}`, { method: 'DELETE', headers: H })
        }
      }
    })
    console.log('  清理：验证会议已删除')
  } finally {
    chrome.kill()
    await rm(profile, { recursive: true, force: true }).catch(() => {})
  }

  console.log(`\n结果：${pass} 通过 / ${fail} 失败`)
  process.exit(fail ? 1 : 0)
}

main().catch((e) => {
  console.error('验证脚本异常:', e.message)
  process.exit(2)
})
