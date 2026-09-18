<template>
  <div class="operation-overview">
    <div class="bento-grid">
      <!-- 总览：甜甜圈 + 4 项指标 -->
      <div class="card ops-summary">
        <div class="ops-donut">
          <svg width="104" height="104" viewBox="0 0 104 104">
            <circle cx="52" cy="52" r="42" fill="none" stroke="#eef2f7" stroke-width="11" />
            <circle
              cx="52" cy="52" r="42" fill="none" stroke="#2f6fed" stroke-width="11"
              stroke-linecap="round" stroke-dasharray="263.9"
              :stroke-dashoffset="donutOffset"
              transform="rotate(-90 52 52)"
            />
          </svg>
          <div class="ops-donut-center">
            <div class="ops-donut-val">{{ overall.closed_loop_rate || 0 }}%</div>
            <div class="ops-donut-label">整体闭环率</div>
          </div>
        </div>
        <div class="ops-summary-divider"></div>
        <div class="ops-summary-meta">
          <div class="ops-meta-item">
            <div class="ops-meta-num">{{ overall.total }}</div>
            <div class="ops-meta-lab">工单总量</div>
          </div>
          <div class="ops-meta-item">
            <div class="ops-meta-num">{{ overall.processing }}</div>
            <div class="ops-meta-lab">进行中</div>
          </div>
          <div class="ops-meta-item">
            <div class="ops-meta-num" :class="{ warn: overall.overdue > 0 }">{{ overall.overdue }}</div>
            <div class="ops-meta-lab">已逾期</div>
          </div>
          <div class="ops-meta-item">
            <div class="ops-meta-num">{{ closedCount }}</div>
            <div class="ops-meta-lab">已闭环</div>
          </div>
        </div>
      </div>

      <!-- 6 类统计磁贴（点击进入对应工单子页面） -->
      <div class="cat-tiles">
        <div
          v-for="t in tiles"
          :key="t.key"
          class="card cat-tile"
          :class="{ clickable: t.key !== 'all' }"
          @click="openCategory(t.key)"
        >
          <div class="cat-tile-top">
            <span class="cat-name">{{ t.label }}</span>
            <span class="cat-ico" :style="{ background: t.bg, color: t.fg }">
              <el-icon><component :is="t.icon" /></el-icon>
            </span>
          </div>
          <div class="cat-count">{{ t.count }}</div>
          <div class="cat-count-sub">{{ t.sub }}</div>
          <div class="cat-rate">
            <span>闭环率</span>
            <span class="cat-rate-val">{{ t.rate }}%</span>
          </div>
          <div class="cat-bar">
            <div class="cat-bar-fill" :style="{ width: t.rate + '%', background: t.fg }"></div>
          </div>
        </div>
      </div>

      <!-- 责任人分布矩阵：责任人 × 工单类别 × 状态，点击单元格跳对应子页面 -->
      <OwnerMatrix
        class="matrix-span"
        :handlers="handlers"
        :summary="summary"
        :statuses="statuses"
        :categories="WORK_ORDER_CATEGORIES"
        :cat-short="CATEGORY_SHORT"
        :loading="loading"
        :jump="jumpToWorkOrders"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Document, Warning, DataLine, Cpu, List, ChatDotRound } from '@element-plus/icons-vue'
import OwnerMatrix from '@/components/Common/OwnerMatrix.vue'
import { WORK_ORDER_CATEGORIES, CATEGORY_SHORT } from '@/constants/operation.js'
import { operationApi } from '@/api/operation'

const router = useRouter()

const CATEGORIES = [
  { key: 'bug', label: 'BUG 管理', icon: Warning, bg: '#fef2f2', fg: '#d9544d' },
  { key: 'data', label: '数据异常管理', icon: DataLine, bg: '#eff6ff', fg: '#3b82f6' },
  { key: 'prod', label: '主动运营分析', icon: Cpu, bg: '#fef7ed', fg: '#d98a1f' },
  { key: 'task', label: '临时交办任务', icon: List, bg: '#f3e8ff', fg: '#7c3aed' },
  { key: 'complaint', label: '热点投诉', icon: ChatDotRound, bg: '#ecfdf3', fg: '#0f9d6b' },
]

// ---- 指数数据（单一来源：/operation/stats/by-handler）----
// 全局口径与责任人矩阵来自同一次聚合，避免总览数字与矩阵求和互相打架。
const loading = ref(false)
const statsData = ref(null)

const summary = computed(() => statsData.value?.summary || {})
const handlers = computed(() => statsData.value?.handlers || [])
const statuses = computed(() => statsData.value?.statuses || [])
const categoryMatrix = computed(() => statsData.value?.category_matrix || {})

const overall = computed(() => ({
  total: summary.value.total || 0,
  processing: summary.value.processing || 0,
  overdue: summary.value.overdue || 0,
  closed_loop_rate: summary.value.closed_loop_rate || 0,
}))
const closedCount = computed(() => (summary.value.resolved || 0) + (summary.value.closed || 0))

const donutOffset = computed(() => {
  const C = 263.9
  const rate = Number(summary.value.closed_loop_rate) || 0
  return C * (1 - rate / 100)
})

const tiles = computed(() => {
  const all = [
    {
      key: 'all', label: '全部', icon: Document, bg: '#eef2f7', fg: '#64748b',
      count: summary.value.total || 0,
      sub: '全部工单',
      rate: summary.value.closed_loop_rate || 0,
    },
  ]
  for (const c of CATEGORIES) {
    const m = categoryMatrix.value[c.key] || {}
    all.push({
      ...c,
      count: m.total || 0,
      sub: `进行中 ${m.processing || 0}`,
      rate: m.closed_loop_rate || 0,
    })
  }
  return all
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
.ops-summary {
  grid-column: span 12;
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 22px 26px;
}
.ops-donut {
  position: relative;
  width: 104px;
  height: 104px;
  flex-shrink: 0;
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
  font-size: 22px;
  font-weight: 800;
  color: var(--text-primary);
  line-height: 1;
}
.ops-donut-label {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}
.ops-summary-divider {
  width: 1px;
  height: 56px;
  background: var(--border);
}
.ops-summary-meta {
  display: flex;
  gap: 36px;
  flex-wrap: wrap;
}
.ops-meta-num {
  font-size: 26px;
  font-weight: 800;
  font-family: var(--font-mono);
  color: var(--text-primary);
}
.ops-meta-num.warn {
  color: var(--danger);
}
.ops-meta-lab {
  font-size: 12.5px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.cat-tiles {
  grid-column: span 12;
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
}
.cat-tile {
  padding: 18px;
  transition: all var(--transition-fast);
  position: relative;
  overflow: hidden;
}
.cat-tile.clickable {
  cursor: pointer;
}
.cat-tile.clickable:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-elevated);
}
.cat-tile-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.cat-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}
.cat-ico {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.cat-count {
  font-size: 30px;
  font-weight: 800;
  font-family: var(--font-mono);
  color: var(--text-primary);
  line-height: 1;
}
.cat-count-sub {
  font-size: 11.5px;
  color: var(--text-muted);
  margin-top: 3px;
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
  height: 6px;
  border-radius: 6px;
  background: #eef2f7;
  margin-top: 6px;
  overflow: hidden;
}
.cat-bar-fill {
  height: 100%;
  border-radius: 6px;
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
  .cat-tiles {
    grid-template-columns: repeat(3, 1fr);
  }
}
</style>
