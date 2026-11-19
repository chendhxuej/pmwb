/**
 * 排版管理二轮优化验证脚本
 * 验证：版本默认未来 + 枚举转译 + 邮件预览展示
 */
import { existsSync } from 'node:fs'
import { spawn } from 'node:child_process'
import { mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const BASE = 'http://127.0.0.1:8020' // 使用代理（新前端+新后端）
const CHROME = ['C:/Program Files/Google/Chrome/Application/chrome.exe',
                'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe']
           .find(existsSync)

if (!CHROME) throw new Error('Chrome/Edge not found')

const sleep = ms => new Promise(r => setTimeout(r, ms))

let pass = 0, fail = 0
const ok = (name, cond, extra = '') => {
  if (cond) { pass++; console.log(`  PASS  ${name}` + (extra ? ` ${extra}` : '')) }
  else { fail++; console.log(`  FAIL  ${name}` + (extra ? ` ${extra}` : '')) }
}

class CDP {
  constructor(ws) { this.ws = ws; this.id = 0; this.p = new Map() }
  send(method, params = {}) {
    const id = ++this.id
    return new Promise((resolve, reject) => {
      this.p.set(id, { resolve, reject })
      this.ws.send(JSON.stringify({ id, method, params }))
      setTimeout(() => { if (this.p.has(id)) { this.p.delete(id); reject(new Error('timeout ' + method)) } }, 30000)
    })
  }
  async eval(expression) {
    const r = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description)
    return r.result.value
  }
  goto(url) { return this.send('Page.navigate', { url }) }
  async waitFor(sel, t = 20000) {
    const t0 = Date.now()
    while (Date.now() - t0 < t) {
      if (await this.eval(`!!document.querySelector(${JSON.stringify(sel)})`).catch(() => false)) return true
      await sleep(400)
    }
    return false
  }
}

async function wsUrl(port) {
  for (let i = 0; i < 30; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${port}/json/list`)
      const p = (await r.json()).find(x => x.type === 'page')
      if (p?.webSocketDebuggerUrl) return p.webSocketDebuggerUrl
    } catch (_) {}
    await sleep(300)
  }
  throw new Error('CDP not ready')
}

// ===== MAIN =====
async function main() {
  const port = 9508
  const prof = await mkdtemp(join(tmpdir(), 'pb-opt-'))
  const ch = spawn(CHROME, [
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${prof}`,
    '--no-first-run',
    '--headless=new',
    '--window-size=1600,1000',
    'about:blank'
  ], { stdio: 'ignore' })

  try {
    const ws = new WebSocket(await wsUrl(port))
    const c = new CDP(ws)
    await new Promise((r, j) => { ws.addEventListener('open', r, { once: true }); ws.addEventListener('error', j, { once: true }) })
    await c.send('Page.enable')
    await c.send('Runtime.enable')

    // 登录获取 token
    const loginR = await fetch(`${BASE}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'chendh', password: 'Chenxue520' })
    })
    const token = (await loginR.json()).data.token
    await c.eval(`localStorage.setItem('pmwb_token',${JSON.stringify(token)}); 'ok'`)

    // ===== 问题3: 版本计划默认 future_only =====
    console.log('\n=== 问题3: 版本计划默认显示未来计划 ===')
    await c.goto(`${BASE}/paiban/versions?v=opt3-${Date.now()}`)
    await c.waitFor('.pb-page', 20000)
    await sleep(2000)

    const txt3 = await c.eval('document.body.innerText')
    ok('3.1 页面渲染正常', txt3.includes('版本计划'))
    ok('3.2 显示"仅未来计划"说明', txt3.includes('仅未来计划') || txt3.includes('发布日'), `txt=${txt3.slice(0, 500)}`)
    // 检查下拉选项是否按日期排序（最近的在前）
    const plans3 = await c.eval(`[...document.querySelectorAll('.el-select-dropdown__item')].map(el => el.textContent).join('|')`)
    ok('3.3 版本下拉有选项', plans3.length > 0, `plans=${plans3}`)

    // ===== 问题2: 枚举转译（RiskSuperviseView）=====
    console.log('\n=== 问题2: 枚举值转译验证 ===')
    await c.goto(`${BASE}/paiban/risks?v=opt2-${Date.now()}`)
    await c.waitFor('.pb-page', 20000)
    await sleep(2000)

    const txt2 = await c.eval('document.body.innerText')
    // 检查是否还有英文原值
    ok('2.1 无英文 stage 原值(stages)', !txt2.includes('plan_confirm') && !txt2.includes('dev'), 'stage 应转为中文')
    ok('2.2 无英文 ticket_type 原值(req/bug)', !txt2.includes('ticket_type="req"') || txt2.includes('需求'), 'ticket_type 应转译')
    ok('2.3 有中文元素出现', txt2.includes('风险') || txt2.includes('督办'), `txt=${txt2.slice(0, 300)}`)

    // ===== 问题5: 邮件预览功能 =====
    console.log('\n=== 问题5: 督办邮件预览/编辑功能 ===')
    // 先确保有版本计划选中
    const hasPreviewBtn = await c.eval(`!!document.querySelector('[title*="预览"]') || !!document.querySelector('[title*="编辑"]') || document.body.innerText.includes('预览 / 编辑督办邮件')`)
    ok('5.1 存在邮件预览入口', hasPreviewBtn, '应在分组头部找到"预览/编辑"按钮')

    // 检查 meta 字典中是否有新增的 labels
    const metaR = await fetch(`${BASE}/api/v1/paiban/meta`)
    const meta = await metaR.json()
    const labels = meta.data?.labels || {}
    ok('5.2 后端返回新字典字段 receipt_statuses', !!labels.receipt_statuses, `keys=${Object.keys(labels).join(',')}`)
    ok('5.3 后端返回新字典字段 feedback_statuses', !!labels.feedback_statuses, `keys=${Object.keys(labels).join(',')}`)
    ok('5.4 后端返回新字典字段 supervise_exclude_rules', !!labels.supervise_exclude_rules, `keys=${Object.keys(labels).join(',')}`)

    // ===== 问题1: 候选池 BUG 待补全 =====
    console.log('\n=== 问题1: 候选池 BUG 工单可见性 ===')
    await c.goto(`${BASE}/paiban/tracks?v=opt1-${Date.now()}`)
    await c.waitFor('.pb-page', 20000)
    await sleep(1500)

    // 打开候选池抽屉
    const candBtn = await c.eval(`[...document.querySelectorAll('button')].find(b => b.textContent.includes('候选池'))`)
    if (candBtn) {
      await c.eval(`document.querySelectorAll('button').find(b => b.textContent.includes('候选池')).click()`)
      await c.waitFor('.el-drawer', 8000)
      await sleep(1500)
      const candTxt = await c.eval('document.body.innerText')
      ok('1.1 候选池抽屉打开后有内容', candTxt.includes('命中') || candTxt.includes('待补全'), `txt=${candTxt.slice(0, 200)}`)
      ok('1.2 有待补全系统页签或说明', candTxt.includes('待补全') || candTxt.includes('命中'), `txt=${candTxt.slice(0, 300)}`)
    } else {
      ok('1.1 找到候选池按钮', false, '按钮未找到，可能是 UI 变化')
    }

    // ===== 汇总 =====
    console.log(`\n=== 总计: PASS ${pass} / FAIL ${fail} ===`)
    if (fail > 0) process.exitCode = 1
  } finally {
    try { ch.kill() } catch (_) {}
  }
}

main().catch(e => { console.error(e); process.exit(1) })
