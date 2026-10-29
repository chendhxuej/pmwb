/**
 * 全站表格列宽：拖拽调整 + 本地持久化 + 复位
 * ---------------------------------------------------------------------------
 * 设计约束（与 PMWB 既有约定对齐）：
 * 1. 零模板结构改动 —— 页面只需给要支持的表加 `ref="pmTblXxx"`，业务代码不动。
 * 2. 不改视觉 —— 不强制 border；热区是表头单元格右缘 8px 的透明区域，
 *    事件委托挂在 header-wrapper 上，不往 th 里插 DOM（表头重渲染不会丢手柄）。
 * 3. 宽度写回 `column.width / realWidth` 再 `doLayout()`，与 Element Plus 内部
 *    拖拽同一路径，横向滚动条宽度、`fixed="right"` 操作列偏移都会同步，不会错位。
 * 4. 存储键 = 路由 path + 列签名 hash（同页多表天然区分），刷新/重载后自动回填。
 * 5. 移动端（≤768px）不挂热区，列宽保持存储值，表格横向滚动。
 *
 * 对外入口：
 *   installTableColumnResize(app)      // main.js 注册一次
 *   window.__pmTableResize.resetAll()       // 清空全站列宽并刷新
 *   window.__pmTableResize.resetTable(ref)  // 复位某个表格
 *   window.__pmTableResize.stats            // 诊断计数
 */
import { unref } from 'vue'

const PREFIX = 'pmwb.tblw.v1:'
const MIN_W = 64
const MAX_W = 800
const EDGE = 8
const MOBILE_BP = 768

/** 表格实例 -> 运行时状态（WeakMap 不阻止回收，重挂载会重新注册） */
const registry = new WeakMap()

/** 诊断计数：排查「某些页面表格没挂上」时用，正常无副作用 */
const stats = { scans: 0, refsSeen: 0, notTable: 0, isEmpty: 0, registered: 0, lastVm: '', byVm: {} }

const isElTable = (v) =>
  !!v && Array.isArray(unref(v.columns)) && typeof v.doLayout === 'function'

const colsOf = (state) => unref(state.ref.columns) || []

const pagePath = () => {
  const { pathname, hash } = window.location
  return pathname + (hash || '')
}

const hashOf = (str) => {
  let h = 5381
  for (let i = 0; i < str.length; i++) h = ((h << 5) + h + str.charCodeAt(i)) | 0
  return (h >>> 0).toString(36)
}

/**
 * 列标识：优先用 property（真数据列唯一），插槽/操作列回退 label；
 * 同表内重名再追加序号，保证「两个状态列」不会互相覆盖。
 */
function buildKeys(cols) {
  const seen = Object.create(null)
  return cols.map((c, i) => {
    const base = c.property || c.label || `col${i}`
    seen[base] = (seen[base] || 0) + 1
    return seen[base] > 1 ? `${base}~${seen[base]}` : base
  })
}

/**
 * 用「路由 + 列签名哈希 + 页面内 DOM 序号」做键。
 * 不用全局递增计数器：SPA 内来回切换路由会让计数器漂移，导致回来的宽度对不上。
 * DOM 序号在一次页面生命周期内稳定，刷新后同位置仍是同一个序号。
 */
function tableKey(cols, el) {
  const sig = cols.map((c) => c.property || c.label || '').join('|')
  const all = el ? [...document.querySelectorAll('.el-table')] : []
  const idx = el ? all.indexOf(el) : -1
  return `${pagePath()}#${hashOf(sig)}${idx >= 0 ? `@${idx}` : ''}`
}

function readStore(key) {
  try {
    const raw = localStorage.getItem(PREFIX + key)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function writeStore(key, map) {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify(map))
  } catch {
    /* 隐私模式/配额满：静默降级为「本次会话有效」 */
  }
}

function snapshot(cols) {
  return cols.map((c) => ({ width: c.width, minWidth: c.minWidth, realWidth: c.realWidth }))
}

function applyWidth(col, w) {
  col.width = w
  col.realWidth = w
}

/** 列是否可拖：fixed 列（操作列）锁定，避免 fixed 偏移计算错乱 */
const draggable = (col) =>
  !col.fixed && col.type !== 'selection' && col.type !== 'index' && col.type !== 'expand'

function applyStored(state) {
  const cols = colsOf(state)
  const keys = buildKeys(cols)
  const saved = readStore(state.key)
  if (!saved) return
  let changed = false
  cols.forEach((col, i) => {
    const w = saved[keys[i]]
    if (typeof w !== 'number' || w < MIN_W || w > MAX_W || !draggable(col)) return
    if (Math.abs((col.width || 0) - w) > 0.5) {
      applyWidth(col, w)
      changed = true
    }
  })
  if (changed) state.ref.doLayout()
}

function persist(state) {
  if (!state.ready) return
  const cols = colsOf(state)
  const keys = buildKeys(cols)
  const map = {}
  cols.forEach((col, i) => {
    if (!draggable(col)) return
    if (typeof col.width === 'number' && col.width >= MIN_W) map[keys[i]] = Math.round(col.width)
  })
  writeStore(state.key, map)
}

/** 单列复位：回到首次注册时看到的样子（原本弹性列会还原成弹性） */
function resetColumn(state, col, idx) {
  const snap = state.defaults[idx]
  if (!snap) return
  col.width = snap.width
  col.realWidth = snap.realWidth
  col.minWidth = snap.minWidth
  state.ref.doLayout()
  persist(state)
}

function resetTable(state) {
  const cols = colsOf(state)
  cols.forEach((col, i) => {
    const snap = state.defaults[i]
    if (!snap) return
    col.width = snap.width
    col.realWidth = snap.realWidth
    col.minWidth = snap.minWidth
  })
  try {
    localStorage.removeItem(PREFIX + state.key)
  } catch {
    /* noop */
  }
  state.ref.doLayout()
}

/* ── 拖拽指示线（一次性编排的反馈，不常驻） ───────────────────────────── */
let guide = null
function showGuide(x) {
  if (!guide) {
    guide = document.createElement('div')
    guide.className = 'pm-col-guide'
    document.body.appendChild(guide)
  }
  guide.style.left = `${x}px`
}
function hideGuide() {
  if (guide) {
    guide.remove()
    guide = null
  }
}

function bind(state) {
  const root = state.ref.$el
  if (!root || root.dataset.pmResizeBound === '1') return
  root.dataset.pmResizeBound = '1'
  state.root = root

  let drag = null
  let raf = 0

  const header = () => root.querySelector('.el-table__header-wrapper')
  const thOf = (ev) => {
    const t = ev.target
    return t && t.closest ? t.closest('th.el-table__cell') : null
  }
  const colOf = (th) => {
    if (!th || !th.classList.contains('is-leaf')) return null
    const cols = colsOf(state)
    return cols.find((c) => c.id && th.classList.contains(c.id)) || null
  }
  const nearEdge = (th, ev) => {
    const r = th.getBoundingClientRect()
    return r.right - ev.clientX <= EDGE && r.right - ev.clientX > -2
  }
  const idxOf = (col) => colsOf(state).indexOf(col)

  let hoverTh = null
  const clearHover = () => {
    if (hoverTh) {
      hoverTh.style.cursor = ''
      hoverTh.classList.remove('pm-col-edge')
      hoverTh = null
    }
  }

  const onMove = (ev) => {
    if (drag) return
    const th = thOf(ev)
    if (!th) {
      clearHover()
      return
    }
    const col = colOf(th)
    const hit = !!col && draggable(col) && nearEdge(th, ev)
    if (hoverTh && hoverTh !== th) clearHover()
    if (hit) {
      th.style.cursor = 'col-resize'
      th.classList.add('pm-col-edge')
      hoverTh = th
    } else if (hoverTh === th) {
      clearHover()
    }
  }

  const onDown = (ev) => {
    if (ev.button !== 0) return
    const th = thOf(ev)
    const col = colOf(th)
    if (!col || !draggable(col) || !nearEdge(th, ev)) return
    ev.preventDefault()
    ev.stopPropagation()
    drag = {
      col,
      idx: idxOf(col),
      startX: ev.clientX,
      startW: col.realWidth || col.width || th.offsetWidth,
    }
    document.body.classList.add('pm-col-resizing')
    showGuide(ev.clientX)
    document.addEventListener('mousemove', onDragMove)
    document.addEventListener('mouseup', onDragUp)
  }

  const onDragMove = (ev) => {
    if (!drag || raf) return
    const { col, startX, startW } = drag
    const w = Math.max(MIN_W, Math.min(MAX_W, startW + (ev.clientX - startX)))
    const x = ev.clientX
    raf = requestAnimationFrame(() => {
      raf = 0
      // 拖拽中表格可能被 v-if 卸载，doLayout 失败不应打断用户
      try {
        applyWidth(col, w)
        state.ref.doLayout()
      } catch {
        /* instance unmounted */
      }
      showGuide(x)
    })
  }

  const onDragUp = () => {
    document.removeEventListener('mousemove', onDragMove)
    document.removeEventListener('mouseup', onDragUp)
    document.body.classList.remove('pm-col-resizing')
    hideGuide()
    if (drag) persist(state)
    drag = null
  }

  const onDblClick = (ev) => {
    const th = thOf(ev)
    const col = colOf(th)
    if (!col || !nearEdge(th, ev)) return
    ev.preventDefault()
    ev.stopPropagation()
    resetColumn(state, col, idxOf(col))
  }

  const wrap = header()
  if (wrap) {
    wrap.addEventListener('mousemove', onMove)
    wrap.addEventListener('mousedown', onDown, true)
    wrap.addEventListener('dblclick', onDblClick, true)
    wrap.addEventListener('mouseleave', () => {
      if (!drag) clearHover()
    })
  }

  state.teardown = () => {
    if (wrap) {
      wrap.removeEventListener('mousemove', onMove)
      wrap.removeEventListener('mousedown', onDown, true)
      wrap.removeEventListener('dblclick', onDblClick, true)
    }
    document.removeEventListener('mousemove', onDragMove)
    document.removeEventListener('mouseup', onDragUp)
    delete root.dataset.pmResizeBound
  }
}

/**
 * 列就绪判定：el-table 的列由子组件挂载时注册到 store，父组件首次 updated 时
 * 可能「表格已在、列还没注册」。所以先登记、后补挂，不因列为空就放弃。
 */
function hydrate(state) {
  if (state.ready) return true
  const cols = colsOf(state)
  if (!cols.length) return false
  state.key = tableKey(cols, state.ref.$el)
  state.defaults = snapshot(cols)
  state.ready = true
  applyStored(state)
  return true
}

function scheduleHydrate(state) {
  let tries = 0
  const tick = () => {
    if (state.ready || tries++ > 25) return
    if (!hydrate(state)) setTimeout(tick, 200)
  }
  setTimeout(tick, 120)
}

function register(ref) {
  const state = { ref, key: '', defaults: [], root: null, teardown: null, ready: false }
  registry.set(ref, state)
  const ready = hydrate(state)
  bind(state)
  if (!ready) scheduleHydrate(state)
  return state
}

const isMobile = () => window.matchMedia(`(max-width: ${MOBILE_BP}px)`).matches

function scan(vm) {
  stats.scans++
  const vmName = vm.$options?.name || vm.$options?.__name || vm.$type?.name || 'anon'
  stats.lastVm = vmName
  stats.byVm[vmName] = (stats.byVm[vmName] || 0) + 1
  if (isMobile()) return
  const refs = vm.$refs
  if (!refs) return
  for (const value of Object.values(refs)) {
    const list = Array.isArray(value) ? value : [value]
    for (const ref of list) {
      if (!ref || typeof ref !== 'object') continue
      stats.refsSeen++
      if (!isElTable(ref)) {
        stats.notTable++
        continue
      }
      if (registry.has(ref)) continue
      register(ref)
      stats.registered++
    }
  }
}

const pendingVm = new Set()
let rafId = 0
function enqueue(vm) {
  pendingVm.add(vm)
  if (rafId) return
  rafId = requestAnimationFrame(() => {
    rafId = 0
    const batch = [...pendingVm]
    pendingVm.clear()
    batch.forEach(scan)
  })
}

function installTableColumnResize(app) {
  app.mixin({
    mounted() {
      this.$nextTick(() => enqueue(this))
    },
    // v-if / tab 切换后新出现的表格；按帧合并，避免内部组件每次更新都全量扫
    updated() {
      enqueue(this)
    },
  })

  window.__pmTableResize = {
    resetAll() {
      Object.keys(localStorage)
        .filter((k) => k.startsWith(PREFIX))
        .forEach((k) => localStorage.removeItem(k))
      location.reload()
    },
    resetTable(ref) {
      const state = ref && registry.get(ref)
      if (state) resetTable(state)
    },
    MIN_W,
    MAX_W,
    PREFIX,
    stats,
  }
}

export default installTableColumnResize
