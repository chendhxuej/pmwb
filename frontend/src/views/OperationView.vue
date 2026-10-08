<template>
  <div class="operation-overview">
    <PageHeader title="运营监控总览" subtitle="全量运营工单的闭环态势、类别分布与责任人压力一览">
      <template #actions>
        <span v-if="updatedAt" class="ops-updated">数据更新于 {{ updatedAt }}</span>
        <el-button size="small" :loading="loading" @click="loadStats">刷新</el-button>
      </template>
    </PageHeader>

    <div class="bento-grid">
      <!-- 总览：甜甜圈（整体闭环率） + 4 项指标 -->
      <div class="card ops-summary">
        <div class="card-header ops-header">
          <div class="ops-title-group">
            <span class="ops-title">工单总览</span>
            <span class="ops-sub">全量工单态势一览</span>
          </div>
          <span class="ops-pill"><i class="ops-pill-dot"></i>闭环口径：已解决 + 已关闭</span>
        </div>
        <div class="ops-body">
          <div class="ops-donut-wrap">
            <div class="ops-donut-glow"></div>
            <div class="ops-donut">
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
              <div class="ops-donut-center">
                <div class="ops-donut-val" :class="rateCls(closedRate)">{{ closedRate }}%</div>
                <div class="ops-donut-label">整体闭环率</div>
              </div>
            </div>
          </div>
          <div class="ops-summary-divider"></div>
          <div class="ops-meta-grid">
            <div v-for="m in metaItems" :key="m.key" class="ops-meta-item">
              <span class="ops-meta-dot" :class="'tone-' + m.tone"></span>
              <div>
                <div class="ops-meta-num" :class="{ warn: m.warn }">{{ m.value }}</div>
                <div class="ops-meta-lab">{{ m.label }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 类别磁贴（恒定 6 个：全部 + 5 类，点击进入对应工单列表） -->
      <section class="ops-tiles-section">
        <div class="card-header ops-tiles-header">
          <div class="ops-tiles-header-left">
            <span class="card-label">工单类别</span>
            <span class="ops-tiles-sub">点击磁贴进入对应工单列表</span>
          </div>
        </div>
        <div class="ops-tiles">
          <div
            v-for="t in tiles"
            :key="t.key"
            class="card cat-tile"
            :class="{ clickable: t.key !== 'all', featured: t.key === 'all' }"
            @click="openCategory(t.key)"
          >
            <span class="cat-stripe" :class="'tone-' + t.tone"></span>
            <div class="cat-tile-top">
              <div class="cat-id">
                <span class="cat-ico" :class="'tone-' + t.tone">
                  <el-icon><component :is="t.icon" /></el-icon>
                </span>
                <span class="cat-name">{{ t.label }}</span>
              </div>
              <span class="cat-enter">进入 →</span>
            </div>
            <div class="cat-count">{{ t.count }}</div>
            <div class="cat-count-sub">
              进行中 {{ t.processing }}<template v-if="t.overdue"> · <em class="cat-overdue">逾期 {{ t.overdue }}</em></template>
            </div>
            <div class="cat-rate">
              <span>闭环率</span>
              <span class="cat-rate-val" :class="rateCls(t.rate)">{{ t.rate }}%</span>
            </div>
            <div class="cat-bar">
              <div class="cat-bar-fill" :class="rateCls(t.rate)" :style="{ width: t.rate + '%' }"></div>
            </div>
          </div>
        </div>
      </section>

      <!-- 责任人分布矩阵：责任人 × 工单类别 × 状态，点击单元格跳对应子页面 -->
      <OwnerMatrix
        class="matrix-span"
        :handlers="handlers"
        :summary="summary"
        :statuses="statuses"
        :status-labels="statusLabels"
        :categories="WORK_ORDER_CATEGORIES"
        :cat-short="CATEGORY_SHORT"
        :loading="loading"
        :jump="jumpToWorkOrders"
      />
    </div>
  </div>
</template>

<script setup>
/**
 * 运营监控 ▸ 总览（2026-09-20 视觉同构升级）。
 *
 * 结构：页头 → 总览卡（甜甜圈 + 4 指标）→ 类别磁贴（恒定 6 个）→ 责任人分布矩阵。
 * 与任务中心总览（TaskOverviewView）同构，样式族与设计令牌一致。
 *
 * 单一数据源：GET /operation/stats/by-handler —— 四块内容取同一次聚合，
 * 避免总览数字与矩阵求和互相打架。
 *
 * 文案纪律：状态中文标签唯一来源 = 后端状态注册表 operation 域
 * （constants/operation.js::issueStatusLabels 转发，statusConfig.js hydrate），
 * 必须显式传给 OwnerMatrix（漏传会让组件把状态 key 原文 pending 等直接当成文案渲染）。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Document, Warning, DataLine, Cpu, List, ChatDotRound } from '@element-plus/icons-vue'
import OwnerMatrix from '@/components/Common/OwnerMatrix.vue'
import PageHeader from '@/components/Common/PageHeader.vue'
import {
  WORK_ORDER_CATEGORIES,
  CATEGORY_SHORT,
  CATEGORY_TONE,
  issueStatusLabels,
} from '@/constants/operation.js'
import { operationApi } from '@/api/operation'

const router = useRouter()

// 状态中文标签（注册表驱动，必须在 computed 中取值才能响应 hydrate）
const statusLabels = computed(() => issueStatusLabels())

// 类别 → 图标（标签与色调分别取自 constants 单一源，此处只补 UI 层图标）
const CATEGORY_ICONS = {
  bug: Warning,
  data: DataLine,
  prod: Cpu,
  task: List,
  complaint: ChatDotRound,
}

// ---- 指数数据 ----
const loading = ref(false)
const statsData = ref(null)

const summary = computed(() => statsData.value?.summary || {})
const handlers = computed(() => statsData.value?.handlers || [])
const statuses = computed(() => statsData.value?.statuses || [])
const categoryMatrix = computed(() => statsData.value?.category_matrix || {})

const closedRate = computed(() => Number(summary.value.closed_loop_rate) || 0)
const closedCount = computed(() => (summary.value.resolved || 0) + (summary.value.closed || 0))

const metaItems = computed(() => [
  { key: 'total', label: '工单总量', value: summary.value.total || 0, tone: 'accent' },
  { key: 'processing', label: '进行中', value: summary.value.processing || 0, tone: 'warning' },
  {
    key: 'overdue', label: '已逾期', value: summary.value.overdue || 0, tone: 'danger',
    warn: (summary.value.overdue || 0) > 0,
  },
  { key: 'closed', label: '已闭环', value: closedCount.value, tone: 'success' },
])

// 闭环率分档：甜甜圈 / 磁贴进度条 / 数字文字共用（与责任人矩阵 rateClass 同口径，禁另起阈值）
const rateCls = (rate) => {
  const r = Number(rate) || 0
  if (r >= 80) return 'rd-high'
  if (r >= 50) return 'rd-mid'
  return 'rd-low'
}

// 甜甜圈颜色：闭环率越高越好（与任务总览的超期率方向相反，勿照抄其阈值语义）
const donutColor = computed(() => {
  const cls = rateCls(closedRate.value)
  if (cls === 'rd-high') return 'var(--success)'
  if (cls === 'rd-mid') return 'var(--warning)'
  return 'var(--danger)'
})

const donutOffset = computed(() => 295.3 * (1 - closedRate.value / 100))

// 磁贴：恒定 6 个（全部 + 5 类），无数据的类别也保留，与矩阵行结构保持一致
const tiles = computed(() => {
  const list = [
    {
      key: 'all', label: '全部', icon: Document, tone: 'muted',
      count: summary.value.total || 0,
      processing: summary.value.processing || 0,
      overdue: summary.value.overdue || 0,
      rate: closedRate.value,
    },
  ]
  for (const c of WORK_ORDER_CATEGORIES) {
    const m = categoryMatrix.value[c.key] || {}
    list.push({
      key: c.key,
      label: c.label,
      icon: CATEGORY_ICONS[c.key] || Document,
      tone: CATEGORY_TONE[c.key] || 'muted',
      count: m.total || 0,
      processing: m.processing || 0,
      overdue: m.overdue || 0,
      rate: m.closed_loop_rate || 0,
    })
  }
  return list
})

const updatedAt = computed(() => {
  const raw = statsData.value?.generated_at
  if (!raw) return ''
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return String(raw)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
})

const loadStats = async () => {
  loading.value = true
  try {
    statsData.value = await operationApi.getStatsByHandler()
  } catch (e) {
    ElMessage.error('加载运营总览失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

// 分类磁贴 → 对应工单子页面（「全部」磁贴仅作汇总展示）
const openCategory = (key) => {
  if (!key || key === 'all') return
  router.push(`/operation/${key}`)
}

// 责任人矩阵格子 → 对应工单子页面（深链契约 ?handler=&status=，由 WorkOrderView 反向还原筛选）
const jumpToWorkOrders = (handler, category, status) => {
  router.push({ path: `/operation/${category}`, query: { handler, status } })
}

onMounted(() => {
  loadStats()
})
</script>

<style scoped>
.operation-overview {
  padding: 20px;
}
.ops-updated {
  font-size: 12px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

/* ---- 总览卡 ---- */
.ops-summary {
  grid-column: span 12;
  padding: 0;
}
.ops-header {
  padding: 18px 24px 14px;
  border-bottom: 1px solid var(--border-subtle);
  align-items: center;
}
.ops-title-group {
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.ops-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
}
.ops-sub {
  font-size: 12.5px;
  color: var(--text-muted);
}
.ops-pill {
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
.ops-pill-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
}
.ops-body {
  display: flex;
  align-items: center;
  gap: 28px;
  padding: 24px;
}
.ops-donut-wrap {
  position: relative;
  width: 140px;
  height: 140px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ops-donut-glow {
  position: absolute;
  inset: 6px;
  border-radius: 50%;
  background: radial-gradient(circle at 50% 50%, var(--accent-soft) 0%, transparent 68%);
}
.ops-donut {
  position: relative;
  width: 116px;
  height: 116px;
}
.ops-donut-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.ops-donut-val {
  font-size: 27px;
  font-weight: 800;
  font-family: var(--font-mono);
  color: var(--text-primary);
  line-height: 1;
}
.ops-donut-label {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 5px;
  font-weight: 500;
}
.ops-summary-divider {
  width: 1px;
  height: 72px;
  background: var(--border);
  flex-shrink: 0;
}
.ops-meta-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px 20px;
}
.ops-meta-item {
  display: flex;
  align-items: center;
  gap: 12px;
}
.ops-meta-dot {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  flex-shrink: 0;
}
.ops-meta-dot.tone-accent { background: var(--accent); }
.ops-meta-dot.tone-warning { background: var(--warning); }
.ops-meta-dot.tone-danger { background: var(--danger); }
.ops-meta-dot.tone-success { background: var(--success); }
.ops-meta-num {
  font-size: 25px;
  font-weight: 800;
  font-family: var(--font-mono);
  color: var(--text-primary);
  line-height: 1.1;
}
.ops-meta-num.warn {
  color: var(--danger);
}
.ops-meta-lab {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 3px;
}

/* ---- 类别磁贴区块 ---- */
.ops-tiles-section {
  grid-column: span 12;
}
.ops-tiles-header {
  padding: 14px 4px 12px;
  align-items: center;
}
.ops-tiles-header-left {
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.ops-tiles-sub {
  font-size: 12px;
  color: var(--text-muted);
}
.ops-tiles {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(188px, 1fr));
  gap: 16px;
}
.cat-tile {
  padding: 0 18px 18px;
  position: relative;
  overflow: hidden;
  transition: transform var(--transition-fast), box-shadow var(--transition-fast), border-color var(--transition-fast);
}
.cat-tile.clickable {
  cursor: pointer;
}
.cat-tile.clickable:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-elevated);
}
.cat-tile.featured {
  border-color: var(--accent);
  background: linear-gradient(180deg, var(--accent-soft) 0%, var(--surface) 46%);
}
.cat-stripe {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
}
.cat-stripe.tone-accent { background: var(--accent); }
.cat-stripe.tone-danger { background: var(--danger); }
.cat-stripe.tone-warning { background: var(--warning); }
.cat-stripe.tone-success { background: var(--success); }
.cat-stripe.tone-violet { background: var(--violet); }
.cat-stripe.tone-muted { background: var(--text-muted); }
.cat-tile-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin: 18px 0 14px;
}
.cat-id {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
}
.cat-ico {
  width: 34px;
  height: 34px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
/* 色调一律走设计令牌，禁硬编码十六进制 */
.cat-ico.tone-accent,
.cat-ico.tone-muted {
  background: var(--accent-soft);
  color: var(--accent);
}
.cat-ico.tone-danger {
  background: var(--danger-soft);
  color: var(--danger);
}
.cat-ico.tone-warning {
  background: var(--warning-soft);
  color: var(--warning);
}
.cat-ico.tone-success {
  background: var(--success-soft);
  color: var(--success);
}
.cat-ico.tone-violet {
  background: var(--violet-soft);
  color: var(--violet);
}
.cat-name {
  font-size: 14.5px;
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cat-enter {
  position: absolute;
  top: 15px;
  right: 16px;
  font-size: 11px;
  font-weight: 600;
  color: var(--accent);
  opacity: 0;
  transform: translateX(-5px);
  transition: opacity var(--transition-fast), transform var(--transition-fast);
}
.cat-tile.clickable:hover .cat-enter {
  opacity: 1;
  transform: none;
}
.cat-count {
  font-size: 32px;
  font-weight: 800;
  font-family: var(--font-mono);
  color: var(--text-primary);
  line-height: 1;
}
.cat-count-sub {
  font-size: 11.5px;
  color: var(--text-muted);
  margin-top: 4px;
}
.cat-overdue {
  font-style: normal;
  color: var(--danger);
  font-weight: 600;
}
.cat-rate {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 14px;
  font-size: 11.5px;
  color: var(--text-secondary);
}
.cat-rate-val {
  font-weight: 700;
  font-family: var(--font-mono);
}
.cat-bar {
  height: 5px;
  border-radius: 6px;
  background: var(--border-subtle);
  margin-top: 6px;
  overflow: hidden;
}
.cat-bar-fill {
  height: 100%;
  border-radius: 6px;
  transition: width var(--transition-normal);
}

/* 闭环率分档（与责任人矩阵 rateClass 同口径） */
.ops-donut-val.rd-high,
.cat-rate-val.rd-high { color: var(--success); }
.ops-donut-val.rd-mid,
.cat-rate-val.rd-mid { color: var(--warning); }
.ops-donut-val.rd-low,
.cat-rate-val.rd-low { color: var(--danger); }
.cat-bar-fill.rd-high { background: var(--success); }
.cat-bar-fill.rd-mid { background: var(--warning); }
.cat-bar-fill.rd-low { background: var(--danger); }

.matrix-span {
  grid-column: span 12;
}

.bento-grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 18px;
}

/* 中等屏：指标网格两列，甜甜圈与指标上下排布 */
@media (max-width: 1100px) {
  .ops-body {
    flex-wrap: wrap;
    gap: 20px;
  }
  .ops-summary-divider {
    display: none;
  }
  .ops-meta-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
