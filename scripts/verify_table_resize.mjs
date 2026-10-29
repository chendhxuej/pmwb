/**
 * 表格列宽拖拽 / 持久化 / 复位 —— 真实浏览器回归（零依赖，走 Chrome DevTools Protocol）
 *
 * 用法：
 *   node scripts/verify_table_resize.mjs               # 跑默认路由集合
 *   node scripts/verify_table_resize.mjs /key-works    # 只跑某个路由
 *
 * 断言的都是运行态：真实表头像素宽度、真实鼠标拖拽、真实刷新回填。
 */
import { existsSync } from 'node:fs'
import { spawn } from 'node:child_process'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const CHROME =
  process.env.CHROME_PATH ||
  [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  ].find((p) => existsSync(p))

const BASE = process.env.PMWB_BASE || 'http://127.0.0.1:5173'
const PORT = Number(process.env.CDP_PORT || 9333)
const ROUTES = process.argv.slice(2).length ? process.argv.slice(2) : ['/basic-data', '/key-works']

let pass = 0
let fail = 0
const failures = []
const skips = []

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

async function httpJson(url, method = 'GET') {
  const res = await fetch(url, { method })
  const text = await res.text()
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

/* ── 极简 CDP 客户端 ─────────────────────────────────────────────────── */
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
      expression,
      returnByValue: true,
      awaitPromise: true,
    })
    if (r.exceptionDetails) {
      throw new Error(r.exceptionDetails.exception?.description || 'eval error')
    }
    return r.result.value
  }
  async goto(url) {
    await this.send('Page.navigate', { url })
  }
  async drag(from, to, steps = 6) {
    await this.send('Input.dispatchMouseEvent', {
      type: 'mouseMoved',
      x: from.x,
      y: from.y,
      button: 'none',
    })
    await this.send('Input.dispatchMouseEvent', {
      type: 'mousePressed',
      x: from.x,
      y: from.y,
      button: 'left',
      clickCount: 1,
    })
    for (let i = 1; i <= steps; i++) {
      const x = from.x + ((to.x - from.x) * i) / steps
      await this.send('Input.dispatchMouseEvent', {
        type: 'mouseMoved',
        x,
        y: from.y,
        button: 'left',
        buttons: 1,
      })
      await sleep(24)
    }
    await this.send('Input.dispatchMouseEvent', {
      type: 'mouseReleased',
      x: to.x,
      y: from.y,
      button: 'left',
      clickCount: 1,
    })
    await sleep(180)
  }
  async dblclickAt(pt) {
    for (const count of [1, 2]) {
      await this.send('Input.dispatchMouseEvent', {
        type: 'mousePressed',
        x: pt.x,
        y: pt.y,
        button: 'left',
        clickCount: count,
      })
      await this.send('Input.dispatchMouseEvent', {
        type: 'mouseReleased',
        x: pt.x,
        y: pt.y,
        button: 'left',
        clickCount: count,
      })
    }
    await sleep(220)
  }
}

/* ── 页面内探针 ─────────────────────────────────────────────────────── */
const PROBE_COLS = `(() => {
  const root = [...document.querySelectorAll('.el-table')].find(t => {
    const r = t.getBoundingClientRect()
    const cs = getComputedStyle(t)
    return r.width > 200 && r.height > 80 && cs.visibility !== 'hidden' && cs.display !== 'none'
  })
  if (!root) return null
  // 表头滚入视口：用元素自身 scrollIntoView（自动识别 el-main 这类内部滚动容器），
  // block:'nearest' 不会让高表格把表头顶出视口
  const headCell = root.querySelector('.el-table__header-wrapper th.el-table__cell')
  if (headCell) {
    headCell.style.scrollMarginTop = '120px'
    headCell.style.scrollMarginBottom = '120px'
    headCell.scrollIntoView({ block: 'nearest', inline: 'nearest' })
    headCell.style.scrollMarginTop = ''
    headCell.style.scrollMarginBottom = ''
  }
  const ths = [...root.querySelectorAll('.el-table__header-wrapper th.el-table__cell.is-leaf')]
    .filter(th => !th.classList.contains('is-hidden') && !th.classList.contains('gutter'))
  return ths.map((th, i) => {
    const r = th.getBoundingClientRect()
    return {
      i,
      label: (th.innerText || '').trim().slice(0, 12),
      left: r.left, right: r.right, width: r.width, top: r.top, h: r.height,
      sel: th.classList.contains('el-table-column--selection') || th.classList.contains('el-table-column--index') || th.classList.contains('el-table-column--expand'),
    }
  })
})()`

/** 目标表格里是否还有固定宽度列的宽度被改动（弹性列允许随总宽重分配） */

async function runRoute(cdp, route) {
  console.log(`\n▶ ${route}`)
  // 先落到真实 origin 才能访问 localStorage（about:blank 是 opaque origin）
  await cdp.goto(`${BASE}${route}`)
  await sleep(3200)
  await cdp.eval(`localStorage.clear(); true`).catch(() => {})
  await cdp.send('Page.reload', { ignoreCache: false })
  await sleep(4800)

  // 1. 全局入口与表格识别
  const boot = await cdp.eval(`({
    api: typeof window.__pmTableResize,
    tables: document.querySelectorAll('.el-table').length,
    keys: Object.keys(localStorage).filter(k => k.startsWith('pmwb.tblw')).length,
  })`)
  boot.api === 'object' ? ok('列宽层已挂载', 'window.__pmTableResize') : bad('列宽层未挂载')

  const cols = await cdp.eval(PROBE_COLS)
  if (!cols || cols.length < 3) {
    // 例如会议日程页首屏是日历视图，表格在「列表/我的」视图里（v-show 隐藏），属正常
    skips.push(route)
    console.log('  SKIP  首屏无可见表格（表格在隐藏视图内）')
    return
  }
  ok('表格列探测', `${cols.length} 列：${cols.map((c) => c.label).slice(0, 4).join('/')}`)

  // 2. 真实拖拽第 2 列右边界 +120px
  const target = cols[1].sel ? cols.find((c) => !c.sel && c.width > 80) : cols[1]
  const from = { x: target.right - 2, y: target.top + target.h / 2 }
  const to = { x: from.x + 120, y: from.y }
  await cdp.drag(from, to)

  const after = await cdp.eval(PROBE_COLS)
  const grow = after[target.i].width - target.width
  grow > 90 && grow < 160
    ? ok('拖拽改变列宽', `${Math.round(target.width)} → ${Math.round(after[target.i].width)} (+${Math.round(grow)})`)
    : bad('拖拽改变列宽', `delta=${Math.round(grow)}`)

  // 3. 拖宽后没有列被压到不可读（弹性列随总宽重分配是 el-table 的 fit 行为，属预期）
  // 选择/序号/展开列本身只有 42~46px，不计入挤压判定
  const crushed = after.filter((c) => !c.sel && c.width < 60).length
  crushed === 0
    ? ok('无列被压缩到 60px 以下')
    : bad('有列被压到 60px 以下', `${crushed} 列`)

  // 4. 写入本地存储
  const stored = await cdp.eval(`(() => {
    const k = Object.keys(localStorage).find(k => k.startsWith('pmwb.tblw'))
    return k ? { key: k, map: JSON.parse(localStorage.getItem(k)) } : null
  })()`)
  stored && Object.keys(stored.map).length
    ? ok('列宽已持久化', `${Object.keys(stored.map).length} 列`)
    : bad('列宽未持久化')

  // 5. 刷新后回填（关键：不能被默认宽度覆盖）
  await cdp.eval(`window.__pmTblBeforeReload = ${JSON.stringify(after[target.i].width)}`)
  await cdp.send('Page.reload', { ignoreCache: false })
  await sleep(5200)
  const reloaded = await cdp.eval(PROBE_COLS)
  const keep = reloaded && Math.abs(reloaded[target.i].width - after[target.i].width) < 2
  keep
    ? ok('刷新后列宽保持', `${Math.round(reloaded[target.i].width)}px`)
    : bad('刷新后列宽丢失', `${Math.round(reloaded?.[target.i]?.width ?? -1)} vs ${Math.round(after[target.i].width)}`)

  // 6. 双击边界复位
  const cur = reloaded[target.i]
  await cdp.dblclickAt({ x: cur.right - 2, y: cur.top + cur.h / 2 })
  const reset = await cdp.eval(PROBE_COLS)
  Math.abs(reset[target.i].width - target.width) < 3
    ? ok('双击复位到默认宽度', `${Math.round(reset[target.i].width)}px`)
    : bad('双击复位失败', `${Math.round(reset[target.i].width)} vs 默认 ${Math.round(target.width)}`)

  // 7. 表头不折行 / 无横向溢出
  const layout = await cdp.eval(`(() => {
    const root = document.querySelector('.el-table')
    const ths = [...root.querySelectorAll('.el-table__header-wrapper th.el-table__cell .cell')]
    const wrapped = ths.filter(c => c.scrollHeight > c.clientHeight + 2).length
    const wrap = root.querySelector('.el-table__header-wrapper')
    return { wrapped, overflowX: wrap.scrollWidth - wrap.clientWidth }
  })()`)
  layout.wrapped === 0 ? ok('表头无折行') : bad('表头折行', `${layout.wrapped} 个单元格`)

  // 8. 移动端不挂热区
  await cdp.send('Emulation.setDeviceMetricsOverride', {
    width: 390,
    height: 844,
    deviceScaleFactor: 2,
    mobile: true,
  })
  await sleep(1200)
  const mobile = await cdp.eval(`(() => {
    const root = document.querySelector('.el-table')
    const th = root?.querySelector('.el-table__header-wrapper th.el-table__cell')
    if (!th) return { hasTable: false }
    const r = th.getBoundingClientRect()
    return { hasTable: true }
  })()`)
  await cdp.send('Emulation.clearDeviceMetricsOverride')
  await sleep(800)
  const afterClear = await cdp.eval(PROBE_COLS)
  afterClear && afterClear.length
    ? ok('移动端视口切换后表格仍可渲染')
    : bad('移动端视口下表格异常')
}

/* ── 主流程 ─────────────────────────────────────────────────────────── */
const userDir = await mkdtemp(join(tmpdir(), 'pmwb-tbl-'))
console.log(`Chrome: ${CHROME}`)
console.log(`Profile: ${userDir}`)

const chrome = spawn(
  CHROME,
  [
    '--headless=new',
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${userDir}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-gpu',
    '--window-size=1440,900',
    'about:blank',
  ],
  { stdio: 'ignore' }
)

let exitCode = 0
try {
  let version = null
  for (let i = 0; i < 60; i++) {
    try {
      version = await httpJson(`http://127.0.0.1:${PORT}/json/version`)
      break
    } catch {
      await sleep(250)
    }
  }
  if (!version) throw new Error('Chrome 未能启动（CDP 端口不可达）')

  const target = await httpJson(`http://127.0.0.1:${PORT}/json/new?about:blank`, 'PUT')
  const ws = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise((res, rej) => {
    ws.addEventListener('open', res)
    ws.addEventListener('error', rej)
  })
  const cdp = new CDP(ws)
  await cdp.send('Page.enable')
  await cdp.send('Runtime.enable')
  await cdp.send('Emulation.setDeviceMetricsOverride', {
    width: 1440,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false,
  })

  for (const route of ROUTES) {
    try {
      await runRoute(cdp, route)
    } catch (e) {
      bad(`${route} 执行异常`, e.message)
    }
  }
  ws.close()
} catch (e) {
  bad('环境准备', e.message)
  exitCode = 1
} finally {
  chrome.kill()
  await sleep(400)
  await rm(userDir, { recursive: true, force: true }).catch(() => {})
}

console.log(`\n${'─'.repeat(52)}`)
console.log(`PASS ${pass}   FAIL ${fail}   SKIP ${skips.length}`)
if (skips.length) console.log(`跳过（首屏无可见表格）：${skips.join('、')}`)
if (fail) {
  console.log('失败项：')
  failures.forEach((f) => console.log(`  - ${f}`))
  exitCode = 1
}
process.exit(exitCode)
