<template>
  <div class="wla">
    <!-- 异常提示 -->
    <el-alert
      v-if="warnText"
      type="warning"
      :closable="false"
      show-icon
      class="wla-alert"
    >
      <div v-for="(w, i) in data.warnings" :key="i">{{ w }}</div>
    </el-alert>

    <!-- 筛选栏 -->
    <div class="wla-filter">
      <el-date-picker
        v-model="monthRange"
        type="monthrange"
        value-format="YYYY-MM"
        range-separator="至"
        start-placeholder="起始月"
        end-placeholder="结束月"
        :unlink-panels="true"
        style="width: 240px"
        @change="onFilterChange"
      />
      <el-input
        v-model="filters.req_keyword"
        placeholder="需求文号 / 名称"
        clearable
        style="width: 180px"
        @keyup.enter="onFilterChange"
        @clear="onFilterChange"
      />
      <el-input
        v-model="filters.sa"
        placeholder="SA 负责人"
        clearable
        style="width: 130px"
        @keyup.enter="onFilterChange"
        @clear="onFilterChange"
      />
      <el-input
        v-model="filters.system_name"
        placeholder="负责系统"
        clearable
        style="width: 140px"
        @keyup.enter="onFilterChange"
        @clear="onFilterChange"
      />
      <el-checkbox v-model="filters.include_zero" @change="onFilterChange">含 0 人天</el-checkbox>
      <el-button :loading="loading" @click="load"><el-icon><Refresh /></el-icon> 刷新</el-button>
      <el-button :loading="exporting" @click="onExport">导出 Excel</el-button>
    </div>

    <!-- 汇总卡 -->
    <div class="wla-stats">
      <div class="wla-stat">
        <div class="wla-stat-label">覆盖需求</div>
        <div class="wla-stat-num">{{ summary.req_count || 0 }}</div>
      </div>
      <div class="wla-stat">
        <div class="wla-stat-label">评估记录</div>
        <div class="wla-stat-num">{{ summary.eval_count || 0 }}</div>
      </div>
      <div class="wla-stat is-primary">
        <div class="wla-stat-label">总工作量(人天)</div>
        <div class="wla-stat-num">{{ fmtNum(summary.workload_total) }}</div>
      </div>
      <div class="wla-stat">
        <div class="wla-stat-label">月均工作量</div>
        <div class="wla-stat-num">{{ fmtNum(summary.workload_avg) }}</div>
      </div>
      <div class="wla-stat is-success">
        <div class="wla-stat-label">峰值月</div>
        <div class="wla-stat-num sm">
          {{ summary.peak_month ? `${summary.peak_month} · ${fmtNum(summary.peak_month_workload)}` : '—' }}
        </div>
      </div>
      <div class="wla-stat" :class="{ 'is-danger': (summary.missing_workload_req_count || 0) > 0 }">
        <div class="wla-stat-label">工作量缺失</div>
        <div class="wla-stat-num">{{ summary.missing_workload_req_count || 0 }}</div>
      </div>
      <div class="wla-stat" :class="{ 'is-warn': (summary.unmonth_req_count || 0) > 0 }">
        <div class="wla-stat-label">未归月需求</div>
        <div class="wla-stat-num">{{ summary.unmonth_req_count || 0 }}</div>
      </div>
    </div>

    <el-empty v-if="!loading && !hasData" description="所选月份内没有已启动开发的需求" :image-size="80" />

    <template v-if="hasData">
      <!-- 月度趋势 -->
      <div class="wla-card">
        <div class="wla-card-title">月度工作量趋势（人天）</div>
        <ChartBar :data="trendData" height="280px" />
      </div>

      <!-- SA Top10（纯 CSS 条形：ChartBar 做不了横向条形，10 个中文名竖排会挤） -->
      <div class="wla-card">
        <div class="wla-card-title">SA 工作量 Top10</div>
        <div class="wla-bars">
          <div v-for="row in saTop" :key="row.name" class="wla-bar-row">
            <span class="wla-bar-name">{{ row.name }}</span>
            <span class="wla-bar-track">
              <span class="wla-bar-fill" :style="{ width: barWidth(row.workload) }"></span>
            </span>
            <span class="wla-bar-val">{{ fmtNum(row.workload) }} 人天 · {{ row.req_count }} 个需求</span>
            <el-tag v-if="row.unassigned" type="info" size="small">未指派</el-tag>
          </div>
        </div>
      </div>

      <!-- 按 SA 汇总表 -->
      <div class="wla-card">
        <div class="wla-card-title">按 SA 汇总</div>
        <el-table :data="data.by_sa" size="small" border stripe row-key="name">
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="wla-expand">
                <span v-for="(v, m) in row.months" :key="m" class="wla-chip">{{ m }}：{{ fmtNum(v) }}</span>
                <span v-if="!Object.keys(row.months || {}).length" class="text-muted">无月度数据</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="SA 负责人" min-width="110" />
          <el-table-column prop="req_count" label="需求数" width="90" align="center" />
          <el-table-column label="工作量(人天)" width="130" align="center">
            <template #default="{ row }">{{ fmtNum(row.workload) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.unassigned" type="info" size="small">未指派</el-tag>
              <span v-else>—</span>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 需求明细 -->
      <div class="wla-card">
        <div class="wla-card-title">需求明细</div>
        <el-table :data="data.requirements.items" size="small" border stripe row-key="req_id">
          <el-table-column label="需求文号" min-width="150">
            <template #default="{ row }">
              <span class="link-text font-mono" @click="$emit('open-requirement', row.req_id)">
                {{ row.req_id }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="req_name" label="需求名称" min-width="180" show-overflow-tooltip />
          <el-table-column prop="month" label="归月" width="90" align="center" />
          <el-table-column label="启动开发时间" width="150" align="center">
            <template #default="{ row }">
              <span>{{ row.entered_at || '—' }}</span>
              <el-tooltip
                v-if="row.stage_source === 'backfill'"
                content="回填时间·非精确，可手工修正"
                placement="top"
              >
                <el-tag type="warning" size="small" effect="plain">回填</el-tag>
              </el-tooltip>
              <el-tag v-else-if="row.stage_source === 'manual'" size="small" effect="plain">手工</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="SA 负责人" min-width="120">
            <template #default="{ row }">
              {{ row.sa_names.length ? row.sa_names.join('、') : '未指派' }}
            </template>
          </el-table-column>
          <el-table-column label="系统" min-width="110" show-overflow-tooltip>
            <template #default="{ row }">{{ row.systems.join('、') || '—' }}</template>
          </el-table-column>
          <el-table-column label="工作量(人天)" width="130" align="center">
            <template #default="{ row }">
              <span v-if="row.workload_state === 'missing'">—</span>
              <span v-else>{{ fmtNum(row.workload) }}</span>
              <el-tag v-if="row.workload_state === 'missing'" type="info" size="small">未填</el-tag>
              <el-tag v-else-if="row.workload_state === 'zero'" size="small">0 人天</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <div class="wla-pager">
          <el-pagination
            v-model:current-page="page"
            :page-size="pageSize"
            :total="data.requirements.total"
            :page-sizes="[20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            small
            background
            @size-change="onSizeChange"
            @current-change="load"
          />
        </div>
      </div>
    </template>

    <!-- 未归月需求 -->
    <div v-if="unmonthRows.length" class="wla-card">
      <div class="wla-card-title is-warn">未归月需求（{{ unmonthRows.length }}）</div>
      <el-table :data="unmonthRows" size="small" border stripe row-key="req_id">
        <el-table-column prop="req_id" label="需求文号" min-width="150" />
        <el-table-column prop="req_name" label="需求名称" min-width="180" show-overflow-tooltip />
        <el-table-column label="工作量(人天)" width="120" align="center">
          <template #default="{ row }">{{ fmtNum(row.workload) }}</template>
        </el-table-column>
        <el-table-column label="SA 负责人" min-width="120">
          <template #default="{ row }">{{ row.sa_names.length ? row.sa_names.join('、') : '—' }}</template>
        </el-table-column>
        <el-table-column label="原因" min-width="160">
          <template #default="{ row }">
            {{ row.reason === 'no_dev_stage' ? '无启动开发环节记录' : '启动开发时间为空' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openFixDialog(row)">补时间</el-button>
            <el-button link type="info" size="small" @click="$emit('open-requirement', row.req_id)">打开</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 固定脚注 -->
    <div v-if="data.footnote" class="wla-footnote">{{ data.footnote }}</div>

    <!-- 补时间弹窗 -->
    <el-dialog v-model="fixVisible" title="补录「启动开发」时间" width="420px" append-to-body>
      <div class="wla-fix">
        <div class="wla-fix-req font-mono">{{ fixRow.req_id }}</div>
        <div class="wla-fix-name">{{ fixRow.req_name || '（未命名需求）' }}</div>
        <el-date-picker
          v-model="fixTime"
          type="datetime"
          value-format="YYYY-MM-DD HH:mm"
          placeholder="选择进入「启动开发」的时间"
          style="width: 100%"
        />
        <div class="wla-fix-hint">写入后该需求将立即进入所选月份的统计（来源标记为「手工」）。</div>
      </div>
      <template #footer>
        <el-button @click="fixVisible = false">取消</el-button>
        <el-button type="primary" :loading="fixSaving" @click="saveFix">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import ChartBar from '@/components/Charts/ChartBar.vue'
import { getWorkloadStats, exportWorkloadStats } from '@/api/workloadAnalysis.js'
import { updateStageLog } from '@/api/requirement.js'

/**
 * 工作量分析面板（「需求与交付」第 4 个 tab）。
 *
 * 统计的**单一数据源**：所有数字直接来自 GET /workload-analysis/stats，
 * 前端不做任何汇总计算（沿用运营监控 by-handler / 高级别 stats 的口径纪律）。
 */
const emit = defineEmits(['open-requirement'])

const loading = ref(false)
const exporting = ref(false)
const page = ref(1)
const pageSize = ref(20)
const monthRange = ref(defaultRange())
const filters = reactive({ req_keyword: '', sa: '', system_name: '', include_zero: true })

const data = ref({
  range: { month_from: '', month_to: '', months: [] },
  summary: {},
  months: [],
  by_sa: [],
  by_system: [],
  requirements: { total: 0, page: 1, page_size: 20, pages: 1, items: [] },
  unmonth: [],
  warnings: [],
  footnote: '',
})

function defaultRange() {
  const now = new Date()
  const y = now.getFullYear()
  const m = now.getMonth() + 1
  const back = m - 11
  const fy = back <= 0 ? y - 1 : y
  const fm = back <= 0 ? m + 1 : back
  return [`${fy}-${String(fm).padStart(2, '0')}`, `${y}-${String(m).padStart(2, '0')}`]
}

const summary = computed(() => data.value.summary || {})
const hasData = computed(() => (data.value.requirements?.total || 0) > 0)
const warnText = computed(() => (data.value.warnings || []).join('；'))
const unmonthRows = computed(() => data.value.unmonth || [])

const trendData = computed(() =>
  (data.value.months || []).map((m) => ({ name: m.month.slice(2), value: m.workload || 0 })),
)
const saTop = computed(() => (data.value.by_sa || []).slice(0, 10))
const maxSa = computed(() => Math.max(1, ...saTop.value.map((x) => x.workload || 0)))
const barWidth = (v) => `${Math.max(2, ((v || 0) / maxSa.value) * 100)}%`

const fmtNum = (v) => {
  if (v === null || v === undefined) return '—'
  const n = Number(v)
  return Number.isFinite(n) ? String(Math.round(n * 100) / 100) : '—'
}

function queryParams() {
  const [mf, mt] = monthRange.value || []
  const p = {
    month_from: mf,
    month_to: mt,
    include_zero: filters.include_zero,
    page: page.value,
    page_size: pageSize.value,
  }
  if (filters.req_keyword) p.req_keyword = filters.req_keyword
  if (filters.sa) p.sa = filters.sa
  if (filters.system_name) p.system_name = filters.system_name
  return p
}

async function load() {
  loading.value = true
  try {
    data.value = await getWorkloadStats(queryParams())
  } catch (e) {
    ElMessage.error('工作量统计加载失败：' + (e?.message || e))
  } finally {
    loading.value = false
  }
}

function onFilterChange() {
  page.value = 1
  load()
}
function onSizeChange(v) {
  pageSize.value = v
  page.value = 1
  load()
}

async function onExport() {
  exporting.value = true
  try {
    const blob = await exportWorkloadStats(queryParams())
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `工作量分析_${monthRange.value?.[0] || ''}_${monthRange.value?.[1] || ''}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

/* ─────────── 未归月：补录启动开发时间 ─────────── */
const fixVisible = ref(false)
const fixSaving = ref(false)
const fixTime = ref('')
const fixRow = ref({})
function openFixDialog(row) {
  fixRow.value = { ...row }
  fixTime.value = ''
  fixVisible.value = true
}
async function saveFix() {
  if (!fixTime.value) {
    ElMessage.warning('请选择进入「启动开发」的时间')
    return
  }
  fixSaving.value = true
  try {
    await updateStageLog(fixRow.value.req_id, 'dev', { entered_at: fixTime.value })
    ElMessage.success('已补录启动开发时间')
    fixVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error('补录失败')
  } finally {
    fixSaving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.wla {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.wla-alert {
  flex-shrink: 0;
}
.wla-filter {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.wla-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
}
.wla-stat {
  padding: 12px 14px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.wla-stat-label {
  color: var(--text-secondary);
  font-size: 12.5px;
}
.wla-stat-num {
  margin-top: 4px;
  color: var(--text-primary);
  font-size: 22px;
  font-weight: 600;
  line-height: 1.2;
}
.wla-stat-num.sm {
  font-size: 16px;
}
.wla-stat.is-primary .wla-stat-num {
  color: var(--accent);
}
.wla-stat.is-success .wla-stat-num {
  color: var(--success);
}
.wla-stat.is-danger .wla-stat-num {
  color: var(--danger);
}
.wla-stat.is-warn .wla-stat-num {
  color: var(--warning);
}

.wla-card {
  padding: 14px 16px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.wla-card-title {
  margin-bottom: 10px;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
}
.wla-card-title.is-warn {
  color: var(--warning);
}

.wla-bars {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.wla-bar-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.wla-bar-name {
  width: 90px;
  flex-shrink: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary);
  font-size: 13px;
}
.wla-bar-track {
  flex: 1;
  height: 12px;
  border-radius: 999px;
  background: var(--border-subtle);
  overflow: hidden;
}
.wla-bar-fill {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--accent), color-mix(in srgb, var(--accent) 55%, #ffffff));
  transition: width var(--transition-normal);
}
.wla-bar-val {
  width: 190px;
  flex-shrink: 0;
  color: var(--text-secondary);
  font-size: 12.5px;
  text-align: right;
}

.wla-expand {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 6px 10px;
}
.wla-chip {
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--bg-app);
  color: var(--text-secondary);
  font-size: 12px;
}
.wla-pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}
.wla-footnote {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.6;
}
.wla-fix-req {
  color: var(--text-secondary);
  font-size: 12.5px;
}
.wla-fix-name {
  margin: 2px 0 14px;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
}
.wla-fix-hint {
  margin-top: 10px;
  color: var(--text-muted);
  font-size: 12px;
}
.link-text {
  color: var(--accent);
  cursor: pointer;
}
</style>
