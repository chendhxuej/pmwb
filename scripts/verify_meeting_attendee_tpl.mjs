/**
 * verify_meeting_attendee_tpl.mjs —— 参会人预制模板 真实浏览器回归
 *
 * 场景（2026-11-03 会议弹窗优化第四轮）：
 *   模板挂会议类型，会议弹窗内按类型联动下拉，一键批量填入（追加去重）。
 *
 * 断言：
 *   B1 「类型管理」弹窗出现「参会人模板」tab，且渲染该类型下模板行
 *   B2 新增会议弹窗：会议类型=需求讨论时，参会人模板下拉含目标模板
 *   B3 选模板 → 参会人 chips 追加成员（去重：已存在的不重复加）
 *   B4 切换会议类型为「内部例会」→ 模板下拉清空（该类型无模板，联动生效）
 *
 * 用法：PMWB_BASE=http://127.0.0.1:8011 node scripts/verify_meeting_attendee_tpl.mjs
 */
import { existsSync } from 'node:fs'
import { spawn } from 'node:child_process'
import { mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { readFileSync } from 'node:fs'

const BASE = process.env.PMWB_BASE || 'http://127.0.0.1:8011'
const ENV_TXT = readFileSync(new URL('../backend/.env', import.meta.url), 'utf-8')
const USER = process.env.PMWB_AUTH_USER || ENV_TXT.match(/^AUTH_USERNAME=(.*)$/m)?.[1]?.trim() || 'chendh'
const PASS = process.env.PMWB_AUTH_PW || ENV_TXT.match(/^AUTH_PASSWORD=(.*)$/m)?.[1]?.trim() || ''

const TPL_TYPE = '需求讨论'
const TPL_NAME = '回归-需求评审组'
const TPL_MEMBERS = ['陈大海', '张舒明', '王辅松']

let pass = 0
let fail = 0
const ok = (n) => { pass++; console.log(`  ✅ ${n}`) }
const bad = (n, d) => { fail++; console.log(`  ❌ ${n} — ${d}`) }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function main() {
  // ── 0. 准备：登录 + 确保模板存在（幂等）──
  const login = await fetch(`${BASE}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: USER, password: PASS }),
  }).then((r) => r.json())
  if (login.code !== 0) throw new Error('登录失败: ' + JSON.stringify(login))
  const token = login.data.token
  const H = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }

  const exists = await fetch(
    `${BASE}/api/v1/meetings/attendee-templates?meeting_type=${encodeURIComponent(TPL_TYPE)}`,
    { headers: H }
  ).then((r) => r.json())
  for (const t of exists.data || []) {
    if (t.name === TPL_NAME) {
      await fetch(`${BASE}/api/v1/meetings/attendee-templates/${t.id}`, { method: 'DELETE', headers: H })
    }
  }
  const created = await fetch(`${BASE}/api/v1/meetings/attendee-templates`, {
    method: 'POST',
    headers: H,
    body: JSON.stringify({ meeting_type: TPL_TYPE, name: TPL_NAME, members: TPL_MEMBERS, sort_order: 5 }),
  }).then((r) => r.json())
  if (created.code !== 0) throw new Error('准备模板失败: ' + JSON.stringify(created))
  console.log(`  准备：模板「${TPL_NAME}」（${TPL_MEMBERS.length} 人）已就绪，id=${created.data.id}`)

  // ── 1. 浏览器 ──
  const CHROME = [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  ].find(existsSync)
  const prof = await mkdtemp(join(tmpdir(), 'tpl-'))
  const ch = spawn(CHROME, ['--remote-debugging-port=9391', `--user-data-dir=${prof}`, '--no-first-run', '--headless=new', '--window-size=1680,1100', 'about:blank'], { stdio: 'ignore' })
  let ws
  for (let i = 0; i < 40; i++) {
    try {
      const list = await (await fetch('http://127.0.0.1:9391/json/list')).json()
      const page = list.find((x) => x.type === 'page')
      if (page) { ws = new WebSocket(page.webSocketDebuggerUrl); break }
    } catch {}
    await sleep(400)
  }
  await new Promise((r) => ws.addEventListener('open', r, { once: true }))
  let id = 0
  const pend = new Map()
  ws.addEventListener('message', (e) => {
    const m = JSON.parse(e.data)
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id) }
  })
  const send = (method, params = {}) =>
    new Promise((r) => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })) })
  const ev = async (expr) => {
    const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })
    if (r.result?.exceptionDetails) return { __err: r.result.exceptionDetails.text }
    return r.result?.result?.value
  }
  const waitFor = async (expr, timeout = 6000) => {
    const t0 = Date.now()
    while (Date.now() - t0 < timeout) {
      const v = await ev(expr)
      if (v) return v
      await sleep(200)
    }
    return null
  }

  await send('Page.enable')
  await send('Runtime.enable')
  await send('Page.navigate', { url: `${BASE}/login` })
  await sleep(1200)
  await ev(`localStorage.setItem('pmwb_token','${token}');true`)
  await send('Page.navigate', { url: `${BASE}/meeting/list` })
  await sleep(4500)
  // 关掉 transition 便于断言
  await ev(`(()=>{const st=document.createElement('style');st.textContent='*,*::before,*::after{transition:none!important;animation:none!important}';document.head.appendChild(st);return true})()`)

  // ── B1 类型管理弹窗 → 参会人模板 tab ──
  await ev(`(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('类型管理'));b?.click();return !!b})()`)
  await waitFor(`[...document.querySelectorAll('.el-dialog__title')].some(t=>t.textContent.includes('会议类型管理'))`)
  const tabClicked = await ev(`(()=>{
    const tab=[...document.querySelectorAll('.el-dialog .el-tabs__item')].find(t=>t.textContent.includes('参会人模板'))
    if(!tab) return false
    tab.click(); return true
  })()`)
  if (tabClicked) {
    const rows = await waitFor(`(()=>{
      const t=[...document.querySelectorAll('.el-dialog .el-table')].find(tb=>tb.textContent.includes('模板名称'))
      if(!t) return null
      const names=[...t.querySelectorAll('.el-table__body .el-input__inner')].map(i=>i.value).filter(Boolean)
      return names.length ? names : null
    })()`)
    if (rows && rows.includes(TPL_NAME)) ok(`B1 类型管理弹窗「参会人模板」tab 渲染模板（${rows.join('/')}）`)
    else bad('B1 参会人模板 tab 渲染', 'rows=' + JSON.stringify(rows))
  } else {
    bad('B1 参会人模板 tab', '未找到 tab')
  }
  // 关闭弹窗
  await ev(`(()=>{const x=[...document.querySelectorAll('.el-dialog .el-dialog__headerbtn')].pop();x?.click();return 1})()`)
  await sleep(500)

  // ── B2 新增会议弹窗 → 模板下拉按类型联动 ──
  await ev(`(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('新增会议'));b?.click();return 1})()`)
  await waitFor(`!!document.querySelector('.el-dialog .el-form')`)
  await sleep(600)
  const tplSelectInfo = await ev(`(()=>{
    const s=document.querySelector('.el-dialog .attendee-tpl')
    if(!s) return null
    return {exists:true, disabled:s.classList.contains('is-disabled'), text:s.textContent.trim()}
  })()`)
  // 打开模板下拉
  await ev(`(()=>{
    const s=document.querySelector('.el-dialog .attendee-tpl')
    ;(s?.querySelector('.el-select__wrapper')||s)?.click()
    return 1
  })()`)
  await sleep(600)
  const tplOptions = await ev(`[...document.querySelectorAll('.el-select-dropdown')].filter(d=>d.getBoundingClientRect().height>0).flatMap(d=>[...d.querySelectorAll('.el-select-dropdown__item')].map(i=>i.textContent.trim()))`)
  if ((tplOptions || []).some((t) => t.includes(TPL_NAME))) {
    ok(`B2 模板下拉按会议类型联动（选项：${tplOptions.join(' / ')}）`)
  } else {
    bad('B2 模板下拉联动', 'options=' + JSON.stringify(tplOptions))
  }

  // ── B3 一键填入 + 去重 ──
  await ev(`(()=>{
    const items=[...document.querySelectorAll('.el-select-dropdown__item')].filter(i=>i.getBoundingClientRect().height>0)
    const it=items.find(i=>i.textContent.includes(${JSON.stringify(TPL_NAME)}))
    it?.click(); return !!it
  })()`)
  await sleep(700)
  const chips = await ev(`(()=>{
    const row=document.querySelector('.attendee-row')
    return [...row.querySelectorAll('.el-tag')].map(t=>t.textContent.trim())
  })()`)
  const gotAll = TPL_MEMBERS.every((m) => (chips || []).some((c) => c.includes(m)))
  if (gotAll && (chips || []).length === TPL_MEMBERS.length) {
    ok(`B3 一键填入（参会人：${chips.join('/')}，共 ${chips.length} 人）`)
  } else {
    bad('B3 一键填入', 'chips=' + JSON.stringify(chips))
  }
  // 再选一次同一模板 → 不应重复
  await ev(`(()=>{
    const s=document.querySelector('.el-dialog .attendee-tpl')
    ;(s?.querySelector('.el-select__wrapper')||s)?.click()
    return 1
  })()`)
  await sleep(500)
  await ev(`(()=>{
    const items=[...document.querySelectorAll('.el-select-dropdown__item')].filter(i=>i.getBoundingClientRect().height>0)
    const it=items.find(i=>i.textContent.includes(${JSON.stringify(TPL_NAME)}))
    it?.click(); return !!it
  })()`)
  await sleep(700)
  const chips2 = await ev(`[...document.querySelector('.attendee-row').querySelectorAll('.el-tag')].map(t=>t.textContent.trim())`)
  if ((chips2 || []).length === TPL_MEMBERS.length) ok(`B3 重复填入去重（仍 ${chips2.length} 人）`)
  else bad('B3 去重', 'chips=' + JSON.stringify(chips2))

  // ── B4 改会议类型 → 模板下拉联动清空 ──
  await ev(`(()=>{
    const items=[...document.querySelectorAll('.el-dialog .el-form-item')]
    const f=items.find(x=>x.querySelector('.el-form-item__label')?.textContent.includes('会议类型'))
    const s=f?.querySelector('.el-select'); (s?.querySelector('.el-select__wrapper')||s)?.click(); return 1
  })()`)
  await sleep(600)
  await ev(`(()=>{
    const dds=[...document.querySelectorAll('.el-select-dropdown')].filter(d=>d.getBoundingClientRect().height>0)
    const items=dds.flatMap(d=>[...d.querySelectorAll('.el-select-dropdown__item')])
    const it=items.find(i=>i.textContent.trim()==='内部例会')
    it?.click(); return !!it
  })()`)
  await sleep(900)
  await ev(`(()=>{
    const sels=[...document.querySelectorAll('.el-dialog .el-select')]
    const s=sels.find(x=>x.querySelector('input[placeholder="参会人模板"]'))
    ;(s?.querySelector('.el-select__wrapper')||s)?.click(); return 1
  })()`)
  await sleep(600)
  const tplOptions2 = await ev(`[...document.querySelectorAll('.el-select-dropdown')].filter(d=>d.getBoundingClientRect().height>0).flatMap(d=>[...d.querySelectorAll('.el-select-dropdown__item')].map(i=>i.textContent.trim()))`)
  if ((tplOptions2 || []).length === 0 || (tplOptions2 || []).every((t) => t.includes('无数据'))) {
    ok('B4 切换类型后模板下拉联动清空（内部例会无模板）')
  } else {
    bad('B4 类型联动', 'options=' + JSON.stringify(tplOptions2))
  }

  // 清理：删测试模板
  await fetch(`${BASE}/api/v1/meetings/attendee-templates/${created.data.id}`, { method: 'DELETE', headers: H })
  console.log('  清理：测试模板已删除')

  ch.kill()
  console.log(`\n结果：${pass} 通过 / ${fail} 失败`)
  process.exit(fail ? 1 : 0)
}

main().catch((e) => {
  console.log('验证脚本异常:', e.message)
  process.exit(1)
})
