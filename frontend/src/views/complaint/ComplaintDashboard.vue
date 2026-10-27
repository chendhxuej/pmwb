<template>
  <div class="complaint-dashboard">
    <PageHeader title="客诉压降看板" :subtitle="subTitle">
      <template #actions>
        <el-button :icon="Upload" type="primary" plain @click="uploadVisible = true">上传周报数据</el-button>
        <el-button :icon="Download" :disabled="!metrics.week" @click="openReport">查看最新周报</el-button>
        <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
      </template>
    </PageHeader>

    <div v-if="metrics.week" class="dashboard-body">
      <!-- KPI 区 -->
      <div class="pm-stat-grid pm-stat-grid--6">
        <div class="card kpi-card">
          <div class="kpi-num blue">{{ metrics.total }}</div>
          <div class="kpi-label">本周总量（单）</div>
        </div>
        <div class="card kpi-card">
          <div class="kpi-num" :class="wowClass">{{ wowText }}</div>
          <div class="kpi-label">周环比</div>
        </div>
        <div class="card kpi-card">
          <div class="kpi-num" :class="metrics.batch.cluster_count ? 'red' : 'green'">
            {{ metrics.batch.cluster_count }}
          </div>
          <div class="kpi-label">批量异常簇</div>
        </div>
        <div class="card kpi-card">
          <div class="kpi-num" :class="metrics.batch.fix_rate < 50 && metrics.batch.cluster_count ? 'amber' : 'green'">
            {{ metrics.batch.fix_rate }}%
          </div>
          <div class="kpi-label">批量组织修复率</div>
        </div>
        <div class="card kpi-card">
          <div class="kpi-num" :class="metrics.efficiency.retention ? 'red' : 'green'">
            {{ metrics.efficiency.retention }}
          </div>
          <div class="kpi-label">超期未结单</div>
        </div>
        <div class="card kpi-card">
          <div class="kpi-num" :class="metrics.recur.cnt ? 'red' : 'green'">{{ metrics.recur.cnt }}</div>
          <div class="kpi-label">措施后复发（单）</div>
        </div>
      </div>

      <!-- 图表区：性质结构 + 8 周趋势 -->
      <div class="chart-row">
        <section class="card pm-col-5">
          <div class="card-header"><h3>问题性质结构（一级）</h3></div>
          <div class="card-body">
            <ChartPie :data="pieData" donut height="280px" />
          </div>
        </section>
        <section class="card pm-col-7">
          <div class="card-header"><h3>近 8 周趋势（总量 / 批量簇单量）</h3></div>
          <div class="card-body">
            <ChartLine
              :x-data="trendWeeks"
              :series="trendSeries"
              height="280px"
            />
          </div>
        </section>
      </div>

      <!-- 批量簇 + 效率指标 -->
      <div class="chart-row">
        <section class="card pm-col-7">
          <div class="card-header">
            <h3>批量数据异常专题（压降主战场）</h3>
            <el-tag v-if="metrics.batch.ticket_pct" type="danger" size="small">
              簇内 {{ metrics.batch.ticket_cnt }} 单 / {{ metrics.batch.ticket_pct }}%
            </el-tag>
          </div>
          <div class="card-body">
            <el-table :data="metrics.batch.clusters" size="small" empty-text="本周未出现同场景单日 ≥5 单的批量簇">
              <el-table-column prop="l2" label="场景" min-width="150" show-overflow-tooltip />
              <el-table-column prop="date" label="发现日" width="100" />
              <el-table-column prop="cnt" label="单量" width="64" align="center">
                <template #default="{ row }">
                  <b class="cnt-danger">{{ row.cnt }}</b>
                </template>
              </el-table-column>
              <el-table-column prop="cities" label="涉及地市" min-width="110" show-overflow-tooltip />
              <el-table-column label="组织修复" width="100" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.fixed ? 'success' : 'danger'" size="small">
                    {{ row.fixed ? '已批量处置' : '逐单兜底' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </section>
        <section class="card pm-col-5">
          <div class="card-header"><h3>支撑时效与效率</h3></div>
          <div class="card-body">
            <div class="eff-list">
              <div v-for="e in effItems" :key="e.label" class="eff-item">
                <span class="eff-label">{{ e.label }}</span>
                <span class="eff-value" :class="e.cls">{{ e.value }}</span>
              </div>
            </div>
          </div>
        </section>
      </div>

      <!-- 措施台账概览 -->
      <section class="card">
        <div class="card-header">
          <h3>措施跟踪（压降闭环）</h3>
          <el-button size="small" text type="primary" @click="$router.push('/operation/complaint-center/actions')">
            进入措施台账 →
          </el-button>
        </div>
        <div class="card-body">
          <div class="pm-stat-grid pm-stat-grid--4">
            <div v-for="s in actionStatItems" :key="s.label" class="pm-stat">
              <div class="pm-stat__top" :style="{ color: s.color }">{{ s.cnt }}</div>
              <div class="pm-stat__label">{{ s.label }}</div>
            </div>
          </div>
        </div>
      </section>
    </div>

    <el-empty v-else-if="!loading" description="暂无客诉数据：请先上传小信工单导出 xlsx" />

    <ComplaintUploadDialog v-model="uploadVisible" @imported="loadAll" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Upload, Download } from '@element-plus/icons-vue'
import PageHeader from '@/components/Common/PageHeader.vue'
import ChartPie from '@/components/Charts/ChartPie.vue'
import ChartLine from '@/components/Charts/ChartLine.vue'
import ComplaintUploadDialog from './components/ComplaintUploadDialog.vue'
import { complaintApi } from '@/api/complaint'

const router = useRouter()
const loading = ref(false)
const uploadVisible = ref(false)
const metrics = ref({})

const subTitle = computed(() =>
  metrics.value.week
    ? `统计区间 ${metrics.value.range}｜自然周口径｜数据源：小信工单逐单入库`
    : '每周上传小信工单导出 xlsx，自动归档入库并生成压降看板'
)

const wowClass = computed(() => {
  const v = metrics.value.wow_pct
  if (v === null || v === undefined) return ''
  return v > 0 ? 'red' : (v < 0 ? 'green' : '')
})
const wowText = computed(() => {
  const m = metrics.value
  if (m.wow_pct === null || m.wow_pct === undefined) {
    return m.prev_partial ? '不可比' : '—'
  }
  const arrow = m.wow_pct > 0 ? '↑' : (m.wow_pct < 0 ? '↓' : '→')
  return `${arrow} ${Math.abs(m.wow_pct)}%`
})

const pieData = computed(() =>
  (metrics.value.by_l1 || []).map(x => ({ name: x.name, value: x.cnt }))
)
const trendWeeks = computed(() =>
  (metrics.value.trend || []).map(t => t.week.split('-')[1])
)
const trendSeries = computed(() => [
  { name: '总量', type: 'line', data: (metrics.value.trend || []).map(t => t.total) },
  { name: '批量簇单量', type: 'bar', data: (metrics.value.trend || []).map(t => t.batch) },
])

const effItems = computed(() => {
  const e = metrics.value.efficiency || {}
  return [
    { label: '平均经手环节', value: `${e.avg_opinions ?? '—'} 条/单`, cls: '' },
    { label: '重复派单', value: `${e.repeat_dispatch ?? 0} 单（${e.repeat_dispatch_pct ?? 0}%）`, cls: e.repeat_dispatch_pct >= 10 ? 'warn' : '' },
    { label: '首轮返工', value: `${e.rework ?? 0} 单（${e.rework_pct ?? 0}%）`, cls: e.rework_pct >= 15 ? 'warn' : '' },
    { label: '互推外部', value: `${e.pushout ?? 0} 单（${e.pushout_pct ?? 0}%）`, cls: e.pushout_pct >= 5 ? 'warn' : '' },
    { label: '未结单合计', value: `${e.unclosed ?? 0} 单（${e.unclosed_pct ?? 0}%）`, cls: e.unclosed_pct >= 50 ? 'warn' : '' },
    { label: '长链条（≥5 环节）', value: `${e.long_chain ?? 0} 单`, cls: '' },
  ]
})

const actionStatItems = computed(() => {
  const st = metrics.value.action_stats || {}
  const by = st.by_status || {}
  return [
    { label: '措施总数', cnt: st.total ?? 0, color: 'var(--accent)' },
    { label: '推进中/验证中', cnt: (by.in_progress || 0) + (by.verifying || 0), color: 'var(--warning)' },
    { label: '已验证有效', cnt: by.effective || 0, color: 'var(--success)' },
    { label: '验证未达标', cnt: by.ineffective || 0, color: 'var(--danger)' },
  ]
})

async function loadAll() {
  loading.value = true
  try {
    metrics.value = await complaintApi.getMetrics()
  } catch (e) {
    metrics.value = {}
  } finally {
    loading.value = false
  }
}

function openReport() {
  if (!metrics.value.week) return
  window.open(complaintApi.reportDownloadUrl(metrics.value.week, 'html'), '_blank')
}

onMounted(loadAll)
</script>

<style scoped>
.complaint-dashboard {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.dashboard-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.chart-row {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 16px;
}
.chart-row .card {
  min-width: 0;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.card-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}
.cnt-danger {
  color: var(--danger);
}
.eff-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.eff-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12.5px;
  padding: 6px 10px;
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
}
.eff-label {
  color: var(--text-secondary);
}
.eff-value {
  font-family: var(--font-mono);
  color: var(--text-primary);
}
.eff-value.warn {
  color: var(--danger);
  font-weight: 600;
}
</style>
