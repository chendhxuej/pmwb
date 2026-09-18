<template>
  <div class="task-overview">
    <div class="bento-grid">
      <!-- 总览：甜甜圈（整体完成率） + 4 项指标 -->
      <div class="card to-summary">
        <div class="to-donut">
          <svg width="104" height="104" viewBox="0 0 104 104">
            <circle cx="52" cy="52" r="42" fill="none" stroke="#eef2f7" stroke-width="11" />
            <circle
              cx="52" cy="52" r="42" fill="none" stroke="#2f6fed" stroke-width="11"
              stroke-linecap="round" stroke-dasharray="263.9"
              :stroke-dashoffset="donutOffset"
              transform="rotate(-90 52 52)"
            />
          </svg>
          <div class="to-donut-center">
            <div class="to-donut-val">{{ overall.completion_rate || 0 }}%</div>
            <div class="to-donut-label">整体完成率</div>
          </div>
        </div>
        <div class="to-summary-divider"></div>
        <div class="to-summary-meta">
          <div class="to-meta-item">
            <div class="to-meta-num">{{ overall.total }}</div>
            <div class="to-meta-lab">任务总量</div>
          </div>
          <div class="to-meta-item">
            <div class="to-meta-num">{{ overall.active }}</div>
            <div class="to-meta-lab">在办</div>
          </div>
          <div class="to-meta-item">
            <div class="to-meta-num" :class="{ warn: overall.overdue > 0 }">{{ overall.overdue }}</div>
            <div class="to-meta-lab">已超期</div>
          </div>
          <div class="to-meta-item">
            <div class="to-meta-num">{{ overall.done }}</div>
            <div class="to-meta-lab">已完成</div>
          </div>
        </div>
        <div class="to-summary-note">
          <span class="to-note-tag">全量口径</span>
          含已完成 / 阻塞挂起，与子页签「在办」口径不同
        </div>
      </div>

      <!-- 来源磁贴（点击进入对应来源子页面） -->
      <div class="src-tiles">
        <div
          v-for="t in tiles"
          :key="t.key"
          class="card src-tile"
          :class="{ clickable: t.key !== 'all' }"
          @click="openSource(t.key)"
        >
          <div class="src-tile-top">
            <span class="src-name">{{ t.label }}</span>
            <span class="src-ico" :class="'tone-' + t.tone">
              <el-icon><component :is="t.icon" /></el-icon>
            </span>
          </div>
          <div class="src-count">{{ t.count }}</div>
          <div class="src-count-sub">
            在办 {{ t.active }}<template v-if="t.overdue"> · <em class="src-overdue">超期 {{ t.overdue }}</em></template>
          </div>
          <div class="src-rate">
            <span>完成率</span>
            <span class="src-rate-val">{{ t.rate }}%</span>
          </div>
          <div class="src-bar">
            <div class="src-bar-fill" :class="'tone-' + t.tone" :style="{ width: t.rate + '%' }"></div>
          </div>
        </div>
      </div>

      <!-- 责任人分布矩阵：责任人 × 任务来源 × 状态，点击单元格深链到对应来源列表 -->
      <OwnerMatrix
        class="matrix-span"
        :handlers="owners"
        :summary="summary"
        :statuses="statuses"
        :status-labels="STATUS_LABELS"
        :categories="categoryRows"
        :cat-short="SOURCE_SHORT"
        :labels="MATRIX_LABELS"
        rate-key="completion_rate"
        risk-metric="overdue"
        :loading="loading"
        :jump="jumpToTasks"
      />
    </div>
  </div>
</template>

<script setup>
/**
 * 任务总览（2026-09-18 新增）。
 *
 * 结构与运营监控总览（OperationView）保持同构：甜甜圈 + 4 指标 / 来源磁贴 / 责任人矩阵。
 * 单一数据源：GET /task-center/stats/by-owner —— 三块内容取同一次聚合，
 * 避免总览数字与矩阵求和互相打架（与 /operation/stats/by-handler 的做法一致）。
 *
 * 口径差异（刻意设计，勿"修正"）：
 * - 全量口径（含已完成/阻塞），故完成率可算；子页签沿用「在办」口径；
 * - 超期为实时计算（运营工单依赖库字段，实测恒为 0），因此本页把超期作为风险锚点。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Document, Check, Warning, Search, Tools, Calendar, Files, Bell, MagicStick,
} from '@element-plus/icons-vue'
import OwnerMatrix from '@/components/Common/OwnerMatrix.vue'
import { getTaskStatsByOwner } from '@/api/taskCenter.js'

const router = useRouter()

const STATUS_LABELS = {
  pending: '待处理',
  in_progress: '进行中',
  done: '已完成',
  blocked: '阻塞/挂起',
}

// 来源元数据：图标 + 色调（色调走设计令牌，组件内禁硬编码十六进制）+ 二级路由 slug
const SOURCE_META = [
  { key: 'todo', label: '个人待办', icon: Check, tone: 'accent', slug: 'todo' },
  { key: 'operation_issue', label: '运营问题', icon: Warning, tone: 'danger', slug: 'operation-issue' },
  { key: 'research_issue', label: '一线调研', icon: Search, tone: 'accent', slug: 'research-issue' },
  { key: 'dev_ticket', label: '开发工单', icon: Tools, tone: 'warning', slug: 'dev-ticket' },
  { key: 'meeting_action', label: '会议行动项', icon: Calendar, tone: 'success', slug: 'meeting-action' },
  { key: 'key_work', label: '重点工作', icon: Files, tone: 'accent', slug: 'key-work' },
  { key: 'requirement_urge', label: '需求催办', icon: Bell, tone: 'warning', slug: 'requirement-urge' },
  { key: 'active_optimization', label: '主动优化', icon: MagicStick, tone: 'success', slug: 'active-optimization' },
]

// 摘要 chips 用的来源简称（控制宽度）
const SOURCE_SHORT = {
  todo: '待办',
  operation_issue: '运营',
  research_issue: '调研',
  dev_ticket: '开发',
  meeting_action: '会议',
  key_work: '重点',
  requirement_urge: '催办',
  active_optimization: '优化',
}

// 矩阵文案：与运营监控「责任人分布」区分开（维度是任务来源而非工单类别）
const MATRIX_LABELS = {
  title: '责任人分布',
  catHeader: '任务来源',
  rateLabel: '完成率',
  riskLabel: '超期最多',
  itemLabel: '任务',
  listLabel: '任务列表',
  activeLabel: '在办',
  unassignedLabel: '未指派',
  unassignedTip: '未指派任务无责任人，无法按人检索',
  sortByTotal: '按任务量',
  sortByRisk: '按超期量',
  sortByRate: '按完成率',
}

const loading = ref(false)
const statsData = ref(null)

const summary = computed(() => statsData.value?.summary || {})
const owners = computed(() => statsData.value?.owners || [])
const statuses = computed(() => statsData.value?.statuses || [])
const sourceMatrix = computed(() => statsData.value?.source_matrix || {})
const activeSources = computed(() => statsData.value?.sources || [])

const overall = computed(() => ({
  total: summary.value.total || 0,
  active: summary.value.active || 0,
  overdue: summary.value.overdue || 0,
  done: summary.value.done || 0,
  completion_rate: summary.value.completion_rate || 0,
}))

const donutOffset = computed(() => {
  const C = 263.9
  const rate = Number(summary.value.completion_rate) || 0
  return C * (1 - rate / 100)
})

// 磁贴：全部 + 仅当前有数据的来源（如开发工单为 0 时不占位，与矩阵行一致）
const tiles = computed(() => {
  const list = [
    {
      key: 'all', label: '全部', icon: Document, tone: 'muted',
      count: summary.value.total || 0,
      active: summary.value.active || 0,
      overdue: summary.value.overdue || 0,
      rate: summary.value.completion_rate || 0,
    },
  ]
  for (const meta of SOURCE_META) {
    if (!activeSources.value.includes(meta.key)) continue
    const m = sourceMatrix.value[meta.key] || {}
    list.push({
      key: meta.key,
      label: meta.label,
      icon: meta.icon,
      tone: meta.tone,
      count: m.total || 0,
      active: m.active || 0,
      overdue: m.overdue || 0,
      rate: m.completion_rate || 0,
    })
  }
  return list
})

// 矩阵行 = 有数据的来源，顺序与磁贴一致
const categoryRows = computed(() =>
  SOURCE_META.filter((m) => activeSources.value.includes(m.key))
    .map((m) => ({ key: m.key, label: m.label }))
)

const slugOf = (source) => (SOURCE_META.find((m) => m.key === source) || {}).slug || 'all'

// 来源磁贴 → 对应来源子页面（「全部」磁贴仅作汇总展示）
const openSource = (key) => {
  if (!key || key === 'all') return
  router.push(`/task-center/${slugOf(key)}`)
}

// 矩阵格子 → 对应来源子页面并按人/状态下钻（深链契约 ?owner=&status=）
const jumpToTasks = (owner, source, status) => {
  router.push({ path: `/task-center/${slugOf(source)}`, query: { owner, status } })
}

const loadStats = async () => {
  loading.value = true
  try {
    statsData.value = await getTaskStatsByOwner()
  } catch (e) {
    ElMessage.error('加载任务总览失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadStats()
})
</script>

<style scoped>
.task-overview {
  padding: 20px;
}

/* ---- 总览卡 ---- */
.to-summary {
  grid-column: span 12;
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 22px 26px;
  position: relative;
}
.to-donut {
  position: relative;
  width: 104px;
  height: 104px;
  flex-shrink: 0;
}
.to-donut-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.to-donut-val {
  font-size: 22px;
  font-weight: 800;
  color: var(--text-primary);
  line-height: 1;
}
.to-donut-label {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}
.to-summary-divider {
  width: 1px;
  height: 56px;
  background: var(--border);
}
.to-summary-meta {
  display: flex;
  gap: 36px;
  flex-wrap: wrap;
}
.to-meta-num {
  font-size: 26px;
  font-weight: 800;
  font-family: var(--font-mono);
  color: var(--text-primary);
}
.to-meta-num.warn {
  color: var(--danger);
}
.to-meta-lab {
  font-size: 12.5px;
  color: var(--text-secondary);
  margin-top: 2px;
}
/* 口径提示：告诉使用者本页是全量口径，与子页签的「在办」不一致是预期的 */
.to-summary-note {
  position: absolute;
  right: 26px;
  top: 20px;
  font-size: 11.5px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 7px;
}
.to-note-tag {
  padding: 1px 8px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 600;
}

/* ---- 来源磁贴 ---- */
.src-tiles {
  grid-column: span 12;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(168px, 1fr));
  gap: 16px;
}
.src-tile {
  padding: 18px;
  transition: all var(--transition-fast);
  position: relative;
  overflow: hidden;
}
.src-tile.clickable {
  cursor: pointer;
}
.src-tile.clickable:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-elevated);
}
.src-tile-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
  gap: 8px;
}
.src-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.src-ico {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
/* 色调走设计令牌（禁硬编码十六进制） */
.src-ico.tone-accent,
.src-ico.tone-muted {
  background: var(--accent-soft);
  color: var(--accent);
}
.src-ico.tone-danger {
  background: var(--danger-soft);
  color: var(--danger);
}
.src-ico.tone-warning {
  background: var(--warning-soft);
  color: var(--warning);
}
.src-ico.tone-success {
  background: var(--success-soft);
  color: var(--success);
}
.src-count {
  font-size: 30px;
  font-weight: 800;
  font-family: var(--font-mono);
  color: var(--text-primary);
  line-height: 1;
}
.src-count-sub {
  font-size: 11.5px;
  color: var(--text-muted);
  margin-top: 3px;
}
.src-overdue {
  font-style: normal;
  color: var(--danger);
  font-weight: 600;
}
.src-rate {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 14px;
  font-size: 11.5px;
  color: var(--text-secondary);
}
.src-rate-val {
  font-weight: 700;
  font-family: var(--font-mono);
}
.src-bar {
  height: 6px;
  border-radius: 6px;
  background: #eef2f7;
  margin-top: 6px;
  overflow: hidden;
}
.src-bar-fill {
  height: 100%;
  border-radius: 6px;
  background: var(--accent);
}
.src-bar-fill.tone-danger {
  background: var(--danger);
}
.src-bar-fill.tone-warning {
  background: var(--warning);
}
.src-bar-fill.tone-success {
  background: var(--success);
}
.src-bar-fill.tone-muted {
  background: var(--text-secondary);
}

.matrix-span {
  grid-column: span 12;
}

.bento-grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 18px;
}
@media (max-width: 1280px) {
  .to-summary-note {
    display: none;
  }
}
</style>
