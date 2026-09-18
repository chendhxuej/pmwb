<template>
  <div class="card hm-card">
    <div class="card-header" style="padding: 18px 20px 0">
      <div>
        <div class="hm-title">{{ L.title }}</div>
        <div class="hm-sub">
          {{ handlerCount }} 位{{ L.entityLabel }}责任人 · {{ L.itemLabel }} {{ (summary && summary.total) || 0 }} 条 · 点击责任人卡片展开明细，点彩色格子直达{{ L.listLabel }}
        </div>
      </div>
      <div class="hm-tools">
        <EnlargeInput
          v-model="keyword"
          :placeholder="L.searchPlaceholder"
          clearable
          size="small"
          style="width: 170px"
        />
        <el-select v-model="sortBy" size="small" style="width: 148px">
          <el-option v-for="o in sortOptions" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-button size="small" @click="toggleAll">
          {{ allOpen ? '全部收起' : '全部展开' }}
        </el-button>
      </div>
    </div>

    <div class="hm-legend">
      <span v-for="s in statuses" :key="s.key" class="hm-lg">
        <i :class="'hm-dot st-' + s.key"></i>{{ s.label }}
      </span>
      <span class="hm-lg-note">颜色=状态，深浅=数量</span>
      <span class="hm-legend-hint">「–」表示该组合暂无{{ L.itemLabel }}</span>
    </div>

    <div class="hm-grid" v-loading="loading">
      <div
        v-for="h in visibleHandlers"
        :key="h.name"
        class="hm-block"
        :class="{ 'is-open': isOpen(h), 'is-risk': isTopRisk(h) }"
      >
        <!-- 摘要头：默认态即完整摘要，点击展开热力矩阵 -->
        <div class="hm-head" @click="toggleOpen(h.name)">
          <span class="hm-avatar">{{ avatarOf(h.name) }}</span>
          <div class="hm-head-main">
            <div class="hm-head-row1">
              <span class="hm-name">{{ h.name }}</span>
              <el-tag v-if="h.overdue" size="small" type="danger" effect="plain">逾期 {{ h.overdue }}</el-tag>
              <span v-if="isTopRisk(h)" class="hm-risk-tag">{{ L.riskLabel }}</span>
              <span v-if="h.unassigned" class="hm-unassigned-tag">{{ L.unassignedLabel }}</span>
            </div>
            <div class="hm-head-row2">
              <span class="hm-rate" :title="L.rateLabel + ' ' + rateOf(h) + '%'">
                <i class="hm-rate-bar"><b :class="rateClass(h)" :style="{ width: rateOf(h) + '%' }"></b></i>
                <em>{{ rateOf(h) }}%</em>
              </span>
              <span class="hm-stat">{{ L.itemLabel }} <b>{{ h.total }}</b></span>
              <span class="hm-stat">{{ L.activeLabel }} <b class="hm-active-num">{{ h.active }}</b></span>
            </div>
          </div>
          <el-icon class="hm-chev" :class="{ open: isOpen(h) }"><ArrowDown /></el-icon>
        </div>

        <!-- 非零格子 chips：颜色=状态，点击直达（未指派除外） -->
        <div class="hm-chips" @click="toggleOpen(h.name)">
          <span
            v-for="ch in chipsOf(h).shown"
            :key="ch.cat + ch.st"
            class="hm-chip"
            :class="['st-' + ch.st, { 'chip-disabled': h.unassigned }]"
            :title="cellTip(h, ch.cat, ch.st)"
            @click.stop="!h.unassigned && openCategory(h, ch.cat, ch.st)"
          >{{ ch.label }} {{ ch.v }}</span>
          <span v-if="chipsOf(h).hidden" class="hm-chip-more">+{{ chipsOf(h).hidden }}</span>
          <span v-if="!chipsOf(h).shown.length" class="hm-chips-none">暂无{{ L.itemLabel }}</span>
        </div>

        <!-- 展开态：热力矩阵（行=类别，列=状态，颜色=状态、深浅=数量） -->
        <table v-show="isOpen(h)" class="hm-table">
          <thead>
            <tr>
              <th class="hm-th-cat">{{ L.catHeader }}</th>
              <th v-for="s in statuses" :key="s.key">{{ s.label }}</th>
              <th class="hm-th-sum">合计</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in categories" :key="c.key">
              <td class="hm-td-cat">{{ c.label }}</td>
              <td v-for="s in statuses" :key="s.key" class="hm-td-num">
                <span
                  v-if="cellOf(h, c.key, s.key)"
                  class="hm-cell"
                  :class="['st-' + s.key, lvClass(cellOf(h, c.key, s.key))]"
                  :title="cellTip(h, c.key, s.key)"
                  @click.stop="!h.unassigned && openCategory(h, c.key, s.key)"
                >{{ cellOf(h, c.key, s.key) }}</span>
                <span v-else class="hm-cell hm-cell-empty">–</span>
              </td>
              <td class="hm-td-sum">{{ (h.cat_totals && h.cat_totals[c.key]) || 0 }}</td>
            </tr>
            <tr class="hm-row-sum">
              <td class="hm-td-cat">合计</td>
              <td v-for="s in statuses" :key="s.key">{{ (h.status_totals && h.status_totals[s.key]) || 0 }}</td>
              <td class="hm-td-sum">{{ h.total }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <el-empty
        v-if="!loading && !visibleHandlers.length"
        :description="keyword ? '没有匹配的责任人' : '暂无责任人数据'"
        :image-size="60"
      />
    </div>
  </div>
</template>

<script setup>
/**
 * 通用「责任人分布矩阵」组件（2026-09-18 从 Operation/HandlerMatrix 泛化）。
 *
 * 结构：责任人摘要卡（头像+姓名+风险标签+完成率迷你条+非零状态 chips）
 *      → 点击展开「类别 × 状态」热力矩阵（颜色=状态、深浅=数量）→ 点格子深链下钻。
 *
 * 单一实现纪律：运营监控总览与任务中心总览共用本组件，禁止再写第二份热力矩阵。
 * 两侧差异（类别维度 / 状态维度 / 跳转路径 / 率指标 / 文案）全部通过 props 注入，
 * 运营侧不传时使用与改造前完全一致的默认值（行为零变化）。
 */
import { computed, ref } from 'vue'
import EnlargeInput from '@/components/Common/EnlargeInput.vue'
import { ArrowDown } from '@element-plus/icons-vue'

// 默认文案 = 运营监控总览现状（保证既有页面零变化）
const DEFAULT_LABELS = {
  title: '责任人分布',
  catHeader: '工单类别',
  rateLabel: '闭环率',
  riskLabel: '压单最多',
  itemLabel: '工单',
  listLabel: '工单列表',
  entityLabel: '',            // 「103 位工单责任人」中的冗余词，运营侧为空
  activeLabel: '未闭环',
  unassignedLabel: '未指派',
  unassignedTip: '未指派工单无责任人，无法按人检索',
  searchPlaceholder: '搜索责任人',
  sortByTotal: '按工单量',
  sortByRisk: '按超期量',
  sortByRate: '按闭环率',
}

const props = defineProps({
  // 后端统计接口的 data.handlers（责任人块数组）
  handlers: { type: Array, default: () => [] },
  // 同接口的 data.summary
  summary: { type: Object, default: () => ({}) },
  // 同接口的 data.statuses（状态 key 数组，缺省时用 statusLabels 的键）
  statuses: { type: Array, default: () => [] },
  // 状态 key → 中文（两侧语义不同，必须由调用方提供）
  statusLabels: { type: Object, default: () => ({}) },
  // 矩阵行维度：[{ key, label }]，运营=工单类别 / 任务中心=任务来源
  categories: { type: Array, default: () => [] },
  // 摘要 chips 用的类别简称：{ key: 简称 }
  catShort: { type: Object, default: () => ({}) },
  // 文案覆盖（浅合并到 DEFAULT_LABELS）
  labels: { type: Object, default: () => ({}) },
  // 完成率字段名：运营 closed_loop_rate / 任务中心 completion_rate
  rateKey: { type: String, default: 'closed_loop_rate' },
  // 风险前置指标：运营 active（未闭环最多）/ 任务中心 overdue（超期最多）
  riskMetric: { type: String, default: 'active' },
  loading: { type: Boolean, default: false },
  // 深链跳转：(ownerName, categoryKey, statusKey) => void
  jump: { type: Function, default: null },
})

const L = computed(() => ({ ...DEFAULT_LABELS, ...props.labels }))

// 排序项：按量 / 按风险 / 按率 / 按姓名（后两项文案由 labels 定制）
const sortOptions = computed(() => [
  { label: L.value.sortByTotal, value: 'total' },
  { label: L.value.sortByRisk, value: 'risk' },
  { label: L.value.sortByRate, value: 'rate' },
  { label: '按姓名', value: 'name' },
])

// 摘要 chips 上限，超出折叠为 +n
const CHIP_LIMIT = 8

// 状态列固定展示：即使某状态当前无数据也保留，保证各责任人区块横向可比
const statuses = computed(() => {
  const keys =
    props.statuses && props.statuses.length
      ? props.statuses
      : Object.keys(props.statusLabels || {})
  return keys.map((k) => ({ key: k, label: props.statusLabels[k] || k }))
})

const categories = computed(() => props.categories || [])

const keyword = ref('')
const sortBy = ref('total')
const openSet = ref(new Set())

const handlerCount = computed(() => props.handlers.filter((h) => !h.unassigned).length)

const rateOf = (h) => Number(h[props.rateKey]) || 0
const riskOf = (h) => Number(h[props.riskMetric]) || 0

const visibleHandlers = computed(() => {
  const kw = keyword.value.trim()
  const list = props.handlers.filter((h) => !kw || String(h.name || '').includes(kw))
  // 「未指派」始终沉底（无责任人，不可按人检索）
  const bySort = {
    total: (a, b) => b.total - a.total,
    risk: (a, b) => riskOf(b) - riskOf(a) || b.total - a.total,
    rate: (a, b) => rateOf(b) - rateOf(a),
    name: (a, b) => String(a.name).localeCompare(String(b.name), 'zh'),
  }
  const cmp = bySort[sortBy.value] || bySort.total
  return [...list].sort((a, b) => {
    const ua = a.unassigned ? 1 : 0
    const ub = b.unassigned ? 1 : 0
    if (ua !== ub) return ua - ub
    return cmp(a, b)
  })
})

// 风险前置：风险指标最高的责任人（并列时取排序首位），描红边 + 标记
const maxRisk = computed(() =>
  props.handlers.reduce((m, h) => (!h.unassigned && riskOf(h) > m ? riskOf(h) : m), 0)
)
const isTopRisk = (h) => !h.unassigned && riskOf(h) > 0 && riskOf(h) === maxRisk.value

const isOpen = (h) => openSet.value.has(h.name)
const toggleOpen = (name) => {
  const next = new Set(openSet.value)
  next.has(name) ? next.delete(name) : next.add(name)
  openSet.value = next
}
const allOpen = computed(
  () => visibleHandlers.value.length > 0 && visibleHandlers.value.every((h) => openSet.value.has(h.name))
)
const toggleAll = () => {
  openSet.value = allOpen.value ? new Set() : new Set(visibleHandlers.value.map((h) => h.name))
}

const avatarOf = (name) => String(name || '?').slice(0, 1)
const catLabel = (k) => (categories.value.find((c) => c.key === k) || {}).label || k
const statusLabel = (k) => (statuses.value.find((s) => s.key === k) || {}).label || k

const cellOf = (h, category, status) => {
  const row = h.matrix && h.matrix[category]
  if (!row) return 0
  return row[status] || 0
}

const cellTip = (h, category, status) =>
  h.unassigned
    ? L.value.unassignedTip
    : `查看 ${h.name} 的${catLabel(category)} · ${statusLabel(status)}${L.value.itemLabel}`

// 摘要 chips：状态优先（未闭环类在前），同一状态内按类别顺序
const chipsOf = (h) => {
  const list = []
  for (const s of statuses.value) {
    for (const c of categories.value) {
      const v = cellOf(h, c.key, s.key)
      if (v) list.push({ cat: c.key, st: s.key, label: props.catShort[c.key] || c.label, v })
    }
  }
  return { shown: list.slice(0, CHIP_LIMIT), hidden: Math.max(0, list.length - CHIP_LIMIT) }
}

// 热力分档：1 档浅 / 2~5 档中 / ≥6 档深
const lvClass = (v) => (v <= 1 ? 'lv-1' : v <= 5 ? 'lv-2' : 'lv-3')

// 完成率进度条颜色：≥80 绿 / ≥50 橙 / <50 红
const rateClass = (h) => (rateOf(h) >= 80 ? 'rc-good' : rateOf(h) >= 50 ? 'rc-mid' : 'rc-low')

const openCategory = (h, category, status) => {
  if (h.unassigned || !props.jump) return
  props.jump(h.name, category, status)
}
</script>

<style scoped>
.hm-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}
.hm-sub {
  font-size: 12.5px;
  color: var(--text-muted);
  margin-top: 3px;
}
.hm-tools {
  display: flex;
  align-items: center;
  gap: 8px;
}
.hm-legend {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  padding: 12px 20px 0;
  font-size: 12px;
  color: var(--text-secondary);
}
.hm-lg {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.hm-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
}
.hm-dot.st-pending { background: var(--danger); }
.hm-dot.st-processing { background: var(--warning); }
.hm-dot.st-verify { background: var(--accent); }
.hm-dot.st-resolved,
.hm-dot.st-closed,
.hm-dot.st-suspended { background: var(--success); }
/* 任务中心统一状态（4 态） */
.hm-dot.st-in_progress { background: var(--warning); }
.hm-dot.st-done { background: var(--success); }
.hm-dot.st-blocked { background: var(--text-muted); }
.hm-lg-note {
  padding: 1px 8px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--accent) 8%, #fff);
  color: var(--accent);
  font-size: 11.5px;
}
.hm-legend-hint {
  margin-left: auto;
  color: var(--text-muted);
}

/* ---- 摘要卡网格：默认态更紧凑，一屏可见更多责任人 ---- */
.hm-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 12px;
  padding: 14px 20px 20px;
}
.hm-block {
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 10px 12px 9px;
  background: var(--surface);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.hm-block:hover {
  border-color: var(--border);
}
.hm-block.is-open {
  border-color: color-mix(in srgb, var(--accent) 35%, var(--border-subtle));
}
/* 风险前置：风险指标最高的人整卡描红边 */
.hm-block.is-risk {
  border-color: color-mix(in srgb, var(--danger) 55%, var(--border-subtle));
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--danger) 25%, transparent);
}

/* ---- 摘要头 ---- */
.hm-head {
  display: flex;
  align-items: center;
  gap: 9px;
  cursor: pointer;
  user-select: none;
}
.hm-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 12.5px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.hm-head-main {
  flex: 1;
  min-width: 0;
}
.hm-head-row1 {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.hm-name {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--text-primary);
}
.hm-risk-tag {
  font-size: 10.5px;
  line-height: 1;
  padding: 3px 6px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--danger) 12%, #fff);
  color: var(--danger);
  font-weight: 600;
}
.hm-unassigned-tag {
  font-size: 10.5px;
  line-height: 1;
  padding: 3px 6px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--text-muted) 12%, #fff);
  color: var(--text-secondary);
}
.hm-head-row2 {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 4px;
  font-size: 11.5px;
  color: var(--text-secondary);
}
.hm-rate {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.hm-rate-bar {
  display: inline-block;
  width: 64px;
  height: 5px;
  border-radius: 3px;
  background: #eef2f7;
  overflow: hidden;
}
.hm-rate-bar b {
  display: block;
  height: 100%;
  border-radius: 3px;
}
.hm-rate-bar b.rc-good { background: var(--success); }
.hm-rate-bar b.rc-mid { background: var(--warning); }
.hm-rate-bar b.rc-low { background: var(--danger); }
.hm-rate em {
  font-style: normal;
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--text-primary);
}
.hm-stat b {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--text-primary);
}
.hm-stat .hm-active-num {
  color: var(--danger);
}
.hm-chev {
  color: var(--text-muted);
  transition: transform var(--transition-fast);
  flex-shrink: 0;
}
.hm-chev.open {
  transform: rotate(180deg);
}

/* ---- 摘要 chips：颜色=状态 ---- */
.hm-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 9px;
  cursor: pointer;
}
.hm-chip {
  font-size: 11px;
  line-height: 1;
  padding: 4px 7px;
  border-radius: 5px;
  font-family: var(--font-mono);
  font-weight: 700;
  cursor: pointer;
  transition: filter var(--transition-fast), transform var(--transition-fast);
  --st: var(--text-muted);
}
.hm-chip.st-pending {
  --st: var(--danger);
}
.hm-chip.st-processing {
  --st: var(--warning);
}
.hm-chip.st-verify {
  --st: var(--accent);
}
.hm-chip.st-resolved,
.hm-chip.st-closed,
.hm-chip.st-suspended {
  --st: var(--success);
}
/* 任务中心统一状态（4 态） */
.hm-chip.st-in_progress {
  --st: var(--warning);
}
.hm-chip.st-done {
  --st: var(--success);
}
.hm-chip.st-blocked {
  --st: var(--text-muted);
}
.hm-chip {
  background: color-mix(in srgb, var(--st) 12%, #fff);
  color: color-mix(in srgb, var(--st) 80%, #000);
  border: 1px solid color-mix(in srgb, var(--st) 26%, transparent);
}
.hm-chip:hover {
  filter: brightness(0.96);
  transform: translateY(-1px);
}
.hm-chip.chip-disabled {
  cursor: default;
  filter: grayscale(0.9);
  opacity: 0.6;
}
.hm-chip.chip-disabled:hover {
  transform: none;
}
.hm-chip-more {
  font-size: 11px;
  padding: 4px 6px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}
.hm-chips-none {
  font-size: 11.5px;
  color: var(--text-muted);
}

/* ---- 展开态：热力矩阵 ---- */
.hm-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 11.5px;
  margin-top: 10px;
  cursor: default;
}
.hm-table th {
  font-weight: 500;
  color: var(--text-muted);
  padding: 3px 2px;
  text-align: center;
}
.hm-th-cat {
  text-align: left !important;
  width: 80px;
}
.hm-th-sum {
  width: 34px;
}
.hm-table td {
  padding: 2px 2px;
  text-align: center;
  border-top: 1px solid var(--border-subtle);
}
.hm-td-cat {
  text-align: left;
  color: var(--text-secondary);
  white-space: nowrap;
}
.hm-td-sum {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--text-primary);
}
.hm-cell {
  --st: var(--text-muted);
  display: block;
  border-radius: 5px;
  padding: 3px 0;
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--text-primary);
  cursor: pointer;
  transition: filter var(--transition-fast);
}
.hm-cell.st-pending { --st: var(--danger); }
.hm-cell.st-processing { --st: var(--warning); }
.hm-cell.st-verify { --st: var(--accent); }
.hm-cell.st-resolved,
.hm-cell.st-closed,
.hm-cell.st-suspended { --st: var(--success); }
/* 任务中心统一状态（4 态） */
.hm-cell.st-in_progress { --st: var(--warning); }
.hm-cell.st-done { --st: var(--success); }
.hm-cell.st-blocked { --st: var(--text-muted); }
.hm-cell.lv-1 {
  background: color-mix(in srgb, var(--st) 10%, #fff);
  color: color-mix(in srgb, var(--st) 72%, #000);
}
.hm-cell.lv-2 {
  background: color-mix(in srgb, var(--st) 20%, #fff);
  color: color-mix(in srgb, var(--st) 82%, #000);
}
.hm-cell.lv-3 {
  background: color-mix(in srgb, var(--st) 34%, #fff);
  color: color-mix(in srgb, var(--st) 90%, #000);
}
.hm-cell:hover {
  filter: brightness(0.94);
}
.hm-cell-empty {
  color: color-mix(in srgb, var(--text-muted) 45%, #fff);
  font-weight: 400;
  cursor: default;
}
.hm-cell-empty:hover {
  filter: none;
}
.hm-row-sum td {
  border-top: 1px solid var(--border);
  color: var(--text-secondary);
}

@media (max-width: 1280px) {
  .hm-grid {
    grid-template-columns: 1fr;
  }
}
</style>
