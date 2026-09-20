<template>
  <div class="task-overview">
    <div class="bento-grid">
      <!-- 总览：甜甜圈（整体超期率） + 4 项指标 -->
      <div class="card to-summary">
        <div class="card-header to-header">
          <div class="to-title-group">
            <span class="to-title">任务总览</span>
            <span class="to-sub">未完结工作态势一览</span>
          </div>
          <span class="to-pill"><i class="to-pill-dot"></i>未完结口径</span>
        </div>
        <div class="to-body">
          <div class="to-donut-wrap">
            <div class="to-donut-glow"></div>
            <div class="to-donut">
              <svg width="116" height="116" viewBox="0 0 116 116">
                <circle cx="58" cy="58" r="47" fill="none" stroke="var(--border-subtle)" stroke-width="12" />
                <circle
                  cx="58" cy="58" r="47" fill="none"
                  :stroke="donutColor"
                  stroke-width="12"
                  stroke-linecap="round" stroke-dasharray="295.3"
                  :stroke-dashoffset="donutOffset"
                  transform="rotate(-90 58 58)"
                />
              </svg>
              <div class="to-donut-center">
                <div class="to-donut-val" :class="{ warn: overall.overdue_rate >= 30 }">{{ overall.overdue_rate || 0 }}%</div>
                <div class="to-donut-label">整体超期率</div>
              </div>
            </div>
          </div>
          <div class="to-summary-divider"></div>
          <div class="to-meta-grid">
            <div class="to-meta-item">
              <span class="to-meta-dot accent"></span>
              <div class="to-meta-text">
                <div class="to-meta-num">{{ overall.total }}</div>
                <div class="to-meta-lab">未完结总量</div>
              </div>
            </div>
            <div class="to-meta-item">
              <span class="to-meta-dot danger"></span>
              <div class="to-meta-text">
                <div class="to-meta-num" :class="{ warn: overall.overdue > 0 }">{{ overall.overdue }}</div>
                <div class="to-meta-lab">已超期</div>
              </div>
            </div>
            <div class="to-meta-item">
              <span class="to-meta-dot warning"></span>
              <div class="to-meta-text">
                <div class="to-meta-num" :class="{ block: overall.blocked_total > 0 }">{{ overall.blocked_total }}</div>
                <div class="to-meta-lab">阻塞挂起</div>
              </div>
            </div>
            <div class="to-meta-item">
              <span class="to-meta-dot muted"></span>
              <div class="to-meta-text">
                <div class="to-meta-num">{{ overall.due_soon }}</div>
                <div class="to-meta-lab">临期(3天内)</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 来源磁贴（点击进入全部任务页并按来源自动设置检索条件） -->
      <section class="src-section">
        <div class="card-header src-header">
          <div class="src-header-left">
            <span class="card-label">任务来源</span>
            <span class="src-header-sub">点击磁贴进入全部任务页 · 按来源自动检索</span>
          </div>
        </div>
        <div class="src-tiles">
          <div
            v-for="t in tiles"
            :key="t.key"
            class="card src-tile"
            :class="['clickable', { featured: t.key === 'all' }]"
            @click="openSource(t.key)"
          >
            <span class="src-stripe" :class="'tone-' + t.tone"></span>
            <div class="src-tile-top">
              <div class="src-id">
                <span class="src-ico" :class="'tone-' + t.tone">
                  <el-icon><component :is="t.icon" /></el-icon>
                </span>
                <span class="src-name">{{ t.label }}</span>
              </div>
              <span class="src-enter">进入 →</span>
            </div>
            <div class="src-count">{{ t.count }}</div>
            <div class="src-count-sub">
              在办 {{ t.active }}<template v-if="t.overdue"> · <em class="src-overdue">超期 {{ t.overdue }}</em></template>
            </div>
            <div class="src-rate">
              <span>超期率</span>
              <span class="src-rate-val" :class="rateCls(t.rate)">{{ t.rate }}%</span>
            </div>
            <div class="src-bar">
              <div class="src-bar-fill" :class="rateCls(t.rate)" :style="{ width: t.rate + '%' }"></div>
            </div>
          </div>
        </div>
      </section>

      <!-- 责任人分布矩阵：责任人 × 任务来源 × 状态，点击单元格深链到对应来源列表 -->
      <OwnerMatrix
        class="matrix-span"
        :handlers="owners"
        :summary="summary"
        :statuses="MATRIX_STATUSES"
        :status-labels="STATUS_LABELS"
        :categories="categoryRows"
        :cat-short="SOURCE_SHORT"
        :labels="MATRIX_LABELS"
        rate-key="overdue_rate"
        risk-metric="overdue"
        :loading="loading"
        :jump="jumpToTasks"
        supervise-label="督办"
        @supervise="openSupervise"
      />
    </div>

    <!-- 批量督办弹窗：人员卡片督办入口 -->
    <TaskBatchSuperviseDialog
      v-model="superviseVisible"
      :owner-name="superviseOwner"
    />
  </div>
</template>

<script setup>
/**
 * 任务总览（2026-09-18 新增，2026-09-19 改未完结口径）。
 *
 * 结构与运营监控总览（OperationView）保持同构：甜甜圈 + 4 指标 / 来源磁贴 / 责任人矩阵。
 * 单一数据源：GET /task-center/stats/by-owner（默认未完结口径）—— 三块内容取同一次聚合。
 *
 * 口径（2026-09-19 老大拍板）：未完结 = pending + in_progress，排除 done 与 blocked；
 * 因此甜甜圈主指标改为「整体超期率」（红系），直击超期痛点；blocked_total 作为旁注暴露被卡任务。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Document, Check, Warning, Search, Tools, Calendar, Files, Bell, MagicStick,
} from '@element-plus/icons-vue'
import OwnerMatrix from '@/components/Common/OwnerMatrix.vue'
import TaskBatchSuperviseDialog from '@/components/Common/TaskBatchSuperviseDialog.vue'
import { getTaskStatsByOwner } from '@/api/taskCenter.js'

const router = useRouter()

const STATUS_LABELS = {
  pending: '待处理',
  in_progress: '进行中',
  done: '已完成',
  blocked: '阻塞/挂起',
}

// 矩阵状态列：仅展示未完结两态（done/blocked 已排除，恒为 0 不占位）
const MATRIX_STATUSES = ['pending', 'in_progress']

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
  rateLabel: '超期率',
  riskLabel: '超期最多',
  itemLabel: '任务',
  listLabel: '任务列表',
  activeLabel: '未完结',
  unassignedLabel: '未指派',
  unassignedTip: '未指派任务无责任人，无法按人检索',
  sortByTotal: '按任务量',
  sortByRisk: '按超期量',
  sortByRate: '按超期率',
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
  blocked_total: summary.value.blocked_total || 0,
  due_soon: summary.value.due_soon || 0,
  overdue_rate: summary.value.overdue_rate || 0,
}))

const donutOffset = computed(() => {
  const C = 295.3
  const rate = Number(summary.value.overdue_rate) || 0
  return C * (1 - rate / 100)
})

// 甜甜圈颜色：超期率 ≥30% 红 / ≥10% 橙 / 否则绿
const donutColor = computed(() => {
  const r = Number(summary.value.overdue_rate) || 0
  if (r >= 30) return 'var(--danger)'
  if (r >= 10) return 'var(--warning)'
  return 'var(--success)'
})

// 超期率分档（文字色 + 进度条色共用）
const rateCls = (rate) => {
  const r = Number(rate) || 0
  if (r >= 30) return 'rd-high'
  if (r >= 10) return 'rd-mid'
  return 'rd-low'
}

// 磁贴：全部 + 仅当前有数据的来源（如开发工单为 0 时不占位，与矩阵行一致）
const tiles = computed(() => {
  const list = [
    {
      key: 'all', label: '全部', icon: Document, tone: 'muted',
      count: summary.value.total || 0,
      active: summary.value.active || 0,
      overdue: summary.value.overdue || 0,
      rate: summary.value.overdue_rate || 0,
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
      rate: m.overdue_rate || 0,
    })
  }
  return list
})

// 矩阵行 = 有数据的来源，顺序与磁贴一致
const categoryRows = computed(() =>
  SOURCE_META.filter((m) => activeSources.value.includes(m.key))
    .map((m) => ({ key: m.key, label: m.label }))
)

// 来源磁贴 → 全部任务页并按来源自动设置检索条件（2026-09-20 精简：不再进来源子页）
const openSource = (key) => {
  if (!key || key === 'all') return
  router.push({ path: '/task-center/all', query: { source: key } })
}

// 矩阵格子 → 全部任务页并按来源/责任人/状态自动设置检索条件（深链契约 ?source=&owner=&status=）
const jumpToTasks = (owner, source, status) => {
  router.push({ path: '/task-center/all', query: { source, owner, status } })
}

// 人员卡片督办入口 → 打开批量督办弹窗（弹窗内部按责任人拉取在途任务）
const superviseVisible = ref(false)
const superviseOwner = ref('')
const openSupervise = (name) => {
  if (!name) return
  superviseOwner.value = name
  superviseVisible.value = true
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
  padding: 0;
  overflow: visible;
}
.to-header {
  padding: 18px 24px 14px;
  border-bottom: 1px solid var(--border-subtle);
  align-items: center;
}
.to-title-group {
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.to-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
}
.to-sub {
  font-size: 12.5px;
  color: var(--text-muted);
}
.to-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 11px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 11.5px;
  font-weight: 600;
}
.to-pill-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
}
.to-body {
  display: flex;
  align-items: center;
  gap: 28px;
  padding: 24px;
}
.to-donut-wrap {
  position: relative;
  width: 140px;
  height: 140px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.to-donut-glow {
  position: absolute;
  inset: 6px;
  border-radius: 50%;
  background: radial-gradient(circle at 50% 50%, var(--accent-soft) 0%, rgba(234, 241, 254, 0) 68%);
}
.to-donut {
  position: relative;
  width: 116px;
  height: 116px;
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
  font-size: 27px;
  font-weight: 800;
  color: var(--text-primary);
  line-height: 1;
  font-family: var(--font-mono);
}
.to-donut-val.warn {
  color: var(--danger);
}
.to-donut-label {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 5px;
  font-weight: 500;
}
.to-summary-divider {
  width: 1px;
  height: 72px;
  background: var(--border);
  flex-shrink: 0;
}
.to-meta-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px 20px;
}
.to-meta-item {
  display: flex;
  align-items: center;
  gap: 12px;
}
.to-meta-dot {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  flex-shrink: 0;
}
.to-meta-dot.accent { background: var(--accent); }
.to-meta-dot.danger { background: var(--danger); }
.to-meta-dot.warning { background: var(--warning); }
.to-meta-dot.muted { background: var(--text-muted); }
.to-meta-num {
  font-size: 25px;
  font-weight: 800;
  font-family: var(--font-mono);
  color: var(--text-primary);
  line-height: 1.1;
}
.to-meta-num.warn {
  color: var(--danger);
}
.to-meta-num.block {
  color: var(--warning);
}
.to-meta-lab {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 3px;
}

/* ---- 来源磁贴区块 ---- */
.src-section {
  grid-column: span 12;
}
.src-header {
  padding: 14px 4px 12px;
  align-items: center;
}
.src-header-left {
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.src-header-sub {
  font-size: 12px;
  color: var(--text-muted);
}
.src-tiles {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(188px, 1fr));
  gap: 16px;
}
.src-tile {
  padding: 0 18px 18px;
  transition: transform var(--transition-fast), box-shadow var(--transition-fast), border-color var(--transition-fast);
  position: relative;
  overflow: hidden;
}
.src-tile.clickable {
  cursor: pointer;
}
.src-tile.clickable:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-elevated);
}
.src-tile.featured {
  border-color: var(--accent);
  background: linear-gradient(180deg, var(--accent-soft) 0%, var(--surface) 46%);
}
.src-stripe {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
}
.src-stripe.tone-accent { background: var(--accent); }
.src-stripe.tone-danger { background: var(--danger); }
.src-stripe.tone-warning { background: var(--warning); }
.src-stripe.tone-success { background: var(--success); }
.src-stripe.tone-muted { background: var(--text-muted); }
.src-tile-top {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  margin: 18px 0 14px;
  gap: 8px;
}
.src-id {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
  flex: 1;
}
.src-ico {
  width: 34px;
  height: 34px;
  border-radius: 11px;
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
.src-name {
  font-size: 14.5px;
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.src-enter {
  position: absolute;
  top: 15px;
  right: 16px;
  font-size: 11px;
  color: var(--accent);
  font-weight: 600;
  opacity: 0;
  transform: translateX(-5px);
  transition: opacity var(--transition-fast), transform var(--transition-fast);
}
.src-tile.clickable:hover .src-enter {
  opacity: 1;
  transform: none;
}
.src-count {
  font-size: 32px;
  font-weight: 800;
  font-family: var(--font-mono);
  color: var(--text-primary);
  line-height: 1;
}
.src-count-sub {
  font-size: 11.5px;
  color: var(--text-muted);
  margin-top: 4px;
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
.src-rate-val.rd-high { color: var(--danger); }
.src-rate-val.rd-mid { color: var(--warning); }
.src-rate-val.rd-low { color: var(--success); }
.src-bar {
  height: 5px;
  border-radius: 6px;
  background: var(--border-subtle);
  margin-top: 6px;
  overflow: hidden;
}
.src-bar-fill {
  height: 100%;
  border-radius: 6px;
  transition: width var(--transition-normal);
}
.src-bar-fill.rd-high { background: var(--danger); }
.src-bar-fill.rd-mid { background: var(--warning); }
.src-bar-fill.rd-low { background: var(--success); }

.matrix-span {
  grid-column: span 12;
}

.bento-grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 18px;
}

/* 中等屏：指标网格仍保持两列，甜甜圈与指标上下略紧凑 */
@media (max-width: 1100px) {
  .to-body {
    flex-wrap: wrap;
    gap: 20px;
  }
  .to-summary-divider {
    display: none;
  }
  .to-meta-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
