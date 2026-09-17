<template>
  <div class="card hm-card">
    <div class="card-header" style="padding: 18px 20px 0">
      <div>
        <div class="hm-title">责任人分布</div>
        <div class="hm-sub">
          {{ handlerCount }} 位责任人 · 工单 {{ (summary && summary.total) || 0 }} 条 · 点击任一单元格查看对应工单
        </div>
      </div>
      <div class="hm-tools">
        <EnlargeInput
          v-model="keyword"
          placeholder="搜索责任人"
          clearable
          size="small"
          style="width: 170px"
        />
        <el-select v-model="sortBy" size="small" style="width: 148px">
          <el-option v-for="o in SORT_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
      </div>
    </div>

    <div class="hm-legend">
      <span v-for="s in statuses" :key="s.key" class="hm-lg">
        <i :class="'hm-dot dot-' + s.key"></i>{{ s.label }}
      </span>
      <span class="hm-legend-hint">「–」表示该组合暂无工单</span>
    </div>

    <div class="hm-grid" v-loading="loading">
      <div v-for="h in visibleHandlers" :key="h.name" class="hm-block">
        <div class="hm-block-head">
          <span class="hm-avatar">{{ avatarOf(h.name) }}</span>
          <span class="hm-name">{{ h.name }}</span>
          <span class="hm-kpi">工单 <b>{{ h.total }}</b></span>
          <span class="hm-kpi">未闭环 <b>{{ h.active }}</b></span>
          <span class="hm-kpi">闭环率 <b>{{ h.closed_loop_rate }}%</b></span>
          <el-tag v-if="h.overdue" size="small" type="danger" effect="plain">逾期 {{ h.overdue }}</el-tag>
          <el-tag v-if="h.unassigned" size="small" type="info" effect="plain">未指派</el-tag>
        </div>

        <table class="hm-table">
          <thead>
            <tr>
              <th class="hm-th-cat">工单类别</th>
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
                  :class="{ 'cell-disabled': h.unassigned }"
                  :title="h.unassigned ? '未指派工单无责任人，无法按人检索' : `查看 ${h.name} 的${c.label} · ${s.label}工单`"
                  @click="openCategory(h, c.key, s.key)"
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
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { WORK_ORDER_CATEGORIES } from '@/constants/operation.js'

const props = defineProps({
  // 后端 /operation/stats/by-handler 的 data.handlers
  handlers: { type: Array, default: () => [] },
  // 同上接口的 data.summary
  summary: { type: Object, default: () => ({}) },
  // 同接口的 data.statuses（缺省时用本地兜底，保证列结构永远一致）
  statuses: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

const router = useRouter()

const STATUS_META = [
  { key: 'pending', label: '待处理' },
  { key: 'processing', label: '处理中' },
  { key: 'verify', label: '验证中' },
  { key: 'resolved', label: '已解决' },
  { key: 'closed', label: '已关闭' },
  { key: 'suspended', label: '已挂起' },
]

const SORT_OPTIONS = [
  { label: '按工单量', value: 'total' },
  { label: '按未闭环量', value: 'active' },
  { label: '按闭环率', value: 'rate' },
  { label: '按姓名', value: 'name' },
]

// 状态列固定 6 列：即使某状态当前无数据也保留，保证各责任人区块横向可比
const statuses = computed(() => {
  const incoming = props.statuses || []
  if (!incoming.length) return STATUS_META
  return incoming.map((k) => STATUS_META.find((s) => s.key === k) || { key: k, label: k })
})

const categories = WORK_ORDER_CATEGORIES

const keyword = ref('')
const sortBy = ref('total')

const handlerCount = computed(() => props.handlers.filter((h) => !h.unassigned).length)

const visibleHandlers = computed(() => {
  const kw = keyword.value.trim()
  const list = props.handlers.filter((h) => !kw || String(h.name || '').includes(kw))
  // 「未指派」始终沉底（无责任人，不可按人检索）
  const bySort = {
    total: (a, b) => b.total - a.total,
    active: (a, b) => b.active - a.active,
    rate: (a, b) => b.closed_loop_rate - a.closed_loop_rate,
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

const avatarOf = (name) => String(name || '?').slice(0, 1)

const cellOf = (h, category, status) => {
  const row = h.matrix && h.matrix[category]
  if (!row) return 0
  return row[status] || 0
}

const openCategory = (h, category, status) => {
  if (h.unassigned) return
  router.push({
    path: `/operation/${category}`,
    query: { handler: h.name, status },
  })
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
.dot-pending { background: var(--danger); }
.dot-processing { background: var(--warning); }
.dot-verify { background: var(--accent); }
.dot-resolved { background: var(--success); }
.dot-closed { background: var(--text-muted); }
.dot-suspended { background: var(--text-muted); }
.hm-legend-hint {
  margin-left: auto;
  color: var(--text-muted);
}
.hm-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 14px;
  padding: 14px 20px 20px;
}
.hm-block {
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 12px 14px 10px;
  background: var(--surface);
  transition: border-color var(--transition-fast);
}
.hm-block:hover {
  border-color: var(--border);
}
.hm-block-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
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
.hm-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}
.hm-kpi {
  font-size: 12px;
  color: var(--text-secondary);
}
.hm-kpi b {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--text-primary);
}
.hm-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 12px;
}
.hm-table th {
  font-weight: 500;
  color: var(--text-muted);
  padding: 4px 2px;
  text-align: center;
}
.hm-th-cat {
  text-align: left !important;
  width: 78px;
}
.hm-th-sum {
  width: 34px;
}
.hm-table td {
  padding: 3px 2px;
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
  display: block;
  border-radius: 6px;
  padding: 3px 0;
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--text-primary);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.hm-cell:hover {
  background: var(--accent-soft);
  color: var(--accent);
}
.hm-cell-empty {
  color: var(--text-muted);
  font-weight: 400;
  cursor: default;
}
.hm-cell-empty:hover {
  background: transparent;
  color: var(--text-muted);
}
.cell-disabled {
  cursor: default;
}
.cell-disabled:hover {
  background: transparent;
  color: var(--text-primary);
}
.hm-row-sum td {
  border-top: 1px solid var(--border);
  color: var(--text-secondary);
}
.hm-row-sum .hm-td-cat {
  color: var(--text-secondary);
}

@media (max-width: 1280px) {
  .hm-grid {
    grid-template-columns: 1fr;
  }
}
</style>
