<template>
  <div class="wla">
    <!-- 数据质量提示条（取代原 el-alert：需要内嵌可点击 chip + 与 Bento 节奏一致） -->
    <div
      v-if="noticeVisible"
      class="pm-notice"
      :class="qualityOk ? 'is-ok' : ''"
    >
      <span class="pm-notice__ico">
        <el-icon><SuccessFilled v-if="qualityOk" /><WarningFilled v-else /></el-icon>
      </span>
      <div class="pm-notice__text">
        <template v-if="qualityOk">
          数据质量良好：{{ summary.req_count || 0 }} 个需求已全部归月，工作量完整
        </template>
        <template v-else>
          <span
            v-if="unmonthCnt"
            class="pm-notice__chip is-link"
            @click="scrollToUnmonth"
          >
            未归月 {{ unmonthCnt }} 个
            <el-icon><ArrowRight /></el-icon>
          </span>
          <span v-if="missingCnt" class="pm-notice__chip">
            工作量缺失 {{ missingCnt }} 个（已按 0 计入）
          </span>
          <span v-for="(w, i) in extraWarnings" :key="i" class="pm-notice__line">{{ w }}</span>
        </template>
      </div>
    </div>

    <!-- 月份快捷预设（必须放在 .wla-filter 之外：el-radio-button 会渲染 input，
         否则会抢走回归脚本取的 .wla-filter input[0]） -->
    <div class="wla-presets">
      <el-radio-group :model-value="preset" size="small" @change="onPreset">
        <el-radio-button v-for="p in PRESETS" :key="p.key" :value="p.key">{{ p.label }}</el-radio-button>
      </el-radio-group>
      <span class="pm-card-sub">
        默认锚定有「启动开发」记录的月份区间（{{ dataRange.month_from || '—' }} ~ {{ dataRange.month_to || '—' }}）
      </span>
    </div>

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
        @change="onRangeChange"
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

    <!-- ════════ Bento 12 栅格 ════════ -->
    <div class="bento-grid">
      <!-- ── Row1：KPI 4 张主卡（4 × span3 = 12）── -->
      <div class="pm-stat-grid pm-span-full wla-stats">
        <div class="pm-stat wla-stat tone-accent">
          <div class="pm-stat__top">
            <span class="pm-stat__label wla-stat-label">覆盖需求</span>
            <span class="pm-stat__ico"><el-icon><Tickets /></el-icon></span>
          </div>
          <div class="pm-stat__val wla-stat-num">
            {{ summary.req_count || 0 }}<span class="pm-stat__unit">个</span>
          </div>
          <div class="pm-stat__sub">评估记录 {{ summary.eval_count || 0 }} 条</div>
        </div>

        <div class="pm-stat wla-stat tone-accent">
          <div class="pm-stat__top">
            <span class="pm-stat__label wla-stat-label">总工作量(人天)</span>
            <span class="pm-stat__ico"><el-icon><DataLine /></el-icon></span>
          </div>
          <div class="pm-stat__val wla-stat-num is-accent">
            {{ fmtNum(summary.workload_total) }}<span class="pm-stat__unit">人天</span>
          </div>
          <div class="pm-stat__sub">
            {{ range.month_from }} ~ {{ range.month_to }} · {{ (range.months || []).length }} 个月
          </div>
        </div>

        <div class="pm-stat wla-stat tone-accent">
          <div class="pm-stat__top">
            <span class="pm-stat__label wla-stat-label">月均工作量</span>
            <span class="pm-stat__ico"><el-icon><Calendar /></el-icon></span>
          </div>
          <div class="pm-stat__val wla-stat-num">
            {{ fmtNum(summary.workload_avg) }}<span class="pm-stat__unit">人天/月</span>
          </div>
          <div class="pm-stat__sub">仅统计有需求的月份（空月不计入）</div>
        </div>

        <div class="pm-stat wla-stat tone-success">
          <div class="pm-stat__top">
            <span class="pm-stat__label wla-stat-label">峰值月</span>
            <span class="pm-stat__ico"><el-icon><TrendCharts /></el-icon></span>
          </div>
          <div class="pm-stat__val wla-stat-num is-sm">{{ summary.peak_month || '—' }}</div>
          <div class="pm-stat__sub">峰值 {{ fmtNum(summary.peak_month_workload) }} 人天</div>
        </div>
      </div>

      <el-empty
        v-if="!loading && !hasData"
        class="pm-span-full"
        description="所选月份内没有已启动开发的需求"
        :image-size="80"
      />

      <template v-if="hasData">
        <!-- ── Row2：月度趋势（8） + SA Top10（4）── -->
        <section class="card is-static wla-card wla-card--chart pm-col-8">
          <div class="card-header">
            <span class="card-label wla-card-title">月度工作量趋势（人天）</span>
            <span class="pm-card-sub">{{ (range.months || []).length }} 个月</span>
          </div>
          <div class="card-body wla-trend-body">
            <ChartBar
              :data="trendData"
              height="250px"
              :show-label="trendData.length <= 12"
              unit=" 人天"
            />
          </div>
        </section>

        <!-- SA Top10（纯 CSS 条形：ChartBar 做不了横向条形，10 个中文名竖排会挤） -->
        <section class="card is-static wla-card wla-card--side pm-col-4">
          <div class="card-header">
            <span class="card-label wla-card-title">SA 工作量 Top10</span>
            <span class="pm-card-sub">{{ summary.sa_count || 0 }} 位 SA</span>
          </div>
          <div class="card-body wla-side-body">
            <div class="wla-bars">
              <div v-for="row in saTop" :key="row.name" class="wla-bar-row">
                <span class="wla-bar-name">{{ row.name }}</span>
                <span class="wla-bar-track">
                  <span class="wla-bar-fill" :style="{ width: barWidth(row.workload) }"></span>
                </span>
                <span class="wla-bar-val">{{ fmtNum(row.workload) }} 人天 · {{ row.req_count }} 个需求</span>
                <el-tag v-if="row.unassigned" type="info" size="small">未指派</el-tag>
              </div>
              <div v-if="!saTop.length" class="wla-empty-inline">暂无数据</div>
            </div>
          </div>
        </section>

        <!-- ── Row3：按 SA 汇总（7） + 按系统分布（5）── -->
        <section class="card is-static wla-card pm-col-7">
          <div class="card-header">
            <span class="card-label wla-card-title">按 SA 汇总</span>
            <span class="pm-card-sub">展开行可看月度分摊</span>
          </div>
          <div class="card-body wla-table-body">
            <el-table ref="pmTbl1" :data="data.by_sa" size="small" border stripe row-key="name" max-height="300">
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
        </section>

        <section class="card is-static wla-card pm-col-5">
          <div class="card-header">
            <span class="card-label wla-card-title">按系统分布</span>
            <span class="pm-card-sub">{{ sysList.length }} 个系统</span>
          </div>
          <div class="card-body wla-table-body">
            <el-table ref="pmTbl2" :data="sysList" size="small" border stripe row-key="name" max-height="300">
              <el-table-column prop="name" label="负责系统" min-width="130" show-overflow-tooltip />
              <el-table-column prop="req_count" label="需求数" width="76" align="center" />
              <el-table-column label="工作量(人天)" width="108" align="center">
                <template #default="{ row }">{{ fmtNum(row.workload) }}</template>
              </el-table-column>
              <el-table-column label="占比" width="82" align="center">
                <template #default="{ row }">
                  <span class="font-mono">{{ sysPct(row.workload) }}%</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </section>

        <!-- ── Row4：需求明细（12）── -->
        <section class="card is-static wla-card pm-col-12">
          <div class="card-header">
            <span class="card-label wla-card-title">需求明细</span>
            <span class="pm-card-sub">共 {{ data.requirements.total }} 条</span>
          </div>
          <div class="card-body wla-table-body">
            <el-table ref="pmTbl3" :data="data.requirements.items" size="small" border stripe row-key="req_id">
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
        </section>

        <!-- ── Row5：未归月需求（12）── -->
        <section v-if="unmonthRows.length" id="wla-unmonth" class="card is-static wla-card pm-col-12">
          <div class="card-header">
            <span class="card-label wla-card-title is-warn">未归月需求（{{ unmonthRows.length }}）</span>
            <span class="pm-card-sub">无「启动开发」环节时间，未纳入月度统计</span>
          </div>
          <div class="card-body wla-table-body">
            <el-table ref="pmTbl4" :data="unmonthRows" size="small" border stripe row-key="req_id">
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
        </section>
      </template>
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
import {
  Refresh,
  Tickets,
  DataLine,
  Calendar,
  TrendCharts,
  WarningFilled,
  SuccessFilled,
  ArrowRight,
} from '@element-plus/icons-vue'
import ChartBar from '@/components/Charts/ChartBar.vue'
import { getWorkloadStats, exportWorkloadStats } from '@/api/workloadAnalysis.js'
import { updateStageLog } from '@/api/requirement.js'

/**
 * 工作量分析面板（「需求与交付」第 4 个 tab）。
 *
 * 统计的**单一数据源**：所有数字直接来自 GET /workload-analysis/stats，
 * 前端不做任何汇总计算（沿用运营监控 by-handler / 高级别 stats 的口径纪律）。
 *
 * 布局：Bento 12 栅格（与首页看板同语言），卡片视觉走全局 .card / .pm-stat 规范类。
 */
const emit = defineEmits(['open-requirement'])

const loading = ref(false)
const exporting = ref(false)
const page = ref(1)
const pageSize = ref(20)
const monthRange = ref([]) // 首次为空 → 后端用 data_range 锚定
const preset = ref('') // '' = 自定义区间（无 chip 高亮）
const filters = reactive({ req_keyword: '', sa: '', system_name: '', include_zero: true })

const data = ref({
  range: { month_from: '', month_to: '', months: [] },
  data_range: { month_from: null, month_to: null, month_count: 0, has_data: false },
  summary: {},
  months: [],
  by_sa: [],
  by_system: [],
  requirements: { total: 0, page: 1, page_size: 20, pages: 1, items: [] },
  unmonth: [],
  warnings: [],
  footnote: '',
})

/* ─────────── 月份快捷预设 ─────────── */
const PRESETS = [
  { key: 'range', label: '数据区间' },
  { key: '3', label: '近 3 月' },
  { key: '6', label: '近 6 月' },
  { key: '12', label: '近 12 月' },
  { key: 'year', label: '本年' },
]

const dataRange = computed(() => data.value.data_range || { month_from: null, month_to: null, has_data: false })

const mm = (y, m) => `${y}-${String(m).padStart(2, '0')}`
function shiftYM(back) {
  const d = new Date()
  const t = d.getFullYear() * 12 + d.getMonth() - back
  return [Math.floor(t / 12), (t % 12) + 1]
}
function presetRange(key) {
  const d = new Date()
  const y = d.getFullYear()
  const m = d.getMonth() + 1
  if (key === 'year') return [mm(y, 1), mm(y, m)]
  if (key === 'range') {
    const dr = dataRange.value
    return dr.has_data ? [dr.month_from, dr.month_to] : null
  }
  const n = Number(key)
  if (!Number.isFinite(n)) return null
  const [fy, fm] = shiftYM(n - 1)
  return [mm(fy, fm), mm(y, m)]
}
function matchPreset(r) {
  if (!r || !r[0] || !r[1]) return ''
  for (const p of PRESETS) {
    const v = presetRange(p.key)
    if (v && v[0] === r[0] && v[1] === r[1]) return p.key
  }
  return ''
}
function onPreset(key) {
  const r = presetRange(key)
  if (!r || !r[0] || !r[1]) {
    ElMessage.info('暂无「启动开发」记录，无法锚定数据区间')
    return
  }
  preset.value = key
  monthRange.value = r
  page.value = 1
  load()
}
function onRangeChange() {
  if (!monthRange.value || !monthRange.value.length) {
    // 清空 = 回到数据区间锚定
    const dr = dataRange.value
    if (dr.has_data) monthRange.value = [dr.month_from, dr.month_to]
  }
  preset.value = matchPreset(monthRange.value)
  page.value = 1
  load()
}

/* ─────────── 派生 ─────────── */
const summary = computed(() => data.value.summary || {})
const range = computed(() => data.value.range || { month_from: '', month_to: '', months: [] })
const hasData = computed(() => (data.value.requirements?.total || 0) > 0)
const unmonthRows = computed(() => data.value.unmonth || [])
const sysList = computed(() => data.value.by_system || [])

const unmonthCnt = computed(() => summary.value.unmonth_req_count || 0)
const missingCnt = computed(() => summary.value.missing_workload_req_count || 0)
const extraWarnings = computed(() =>
  (data.value.warnings || []).filter(
    (w) => !w.includes('未纳入月度统计') && !w.includes('工作量未填写'),
  ),
)
const qualityOk = computed(
  () => unmonthCnt.value === 0 && missingCnt.value === 0 && extraWarnings.value.length === 0,
)
const noticeVisible = computed(
  () => hasData.value || unmonthCnt.value > 0 || (data.value.warnings || []).length > 0,
)

const trendData = computed(() =>
  (data.value.months || []).map((m) => ({ name: m.month.slice(2), value: m.workload || 0 })),
)
const saTop = computed(() => (data.value.by_sa || []).slice(0, 10))
const maxSa = computed(() => Math.max(1, ...saTop.value.map((x) => x.workload || 0)))
const barWidth = (v) => `${Math.max(2, ((v || 0) / maxSa.value) * 100)}%`

// 占比分母取 by_system 自身合计（非 summary.workload_total —— SA 人人计全额使两者不等）
const sysTotal = computed(() => sysList.value.reduce((s, x) => s + (x.workload || 0), 0))
const sysPct = (v) => (sysTotal.value ? Math.round(((v || 0) / sysTotal.value) * 1000) / 10 : 0)

const fmtNum = (v) => {
  if (v === null || v === undefined) return '—'
  const n = Number(v)
  return Number.isFinite(n) ? String(Math.round(n * 100) / 100) : '—'
}

function queryParams() {
  const [mf, mt] = monthRange.value || []
  const p = {
    include_zero: filters.include_zero,
    page: page.value,
    page_size: pageSize.value,
  }
  // 不传区间 → 后端用 data_range 锚定（避免首屏双请求）
  if (mf && mt) {
    p.month_from = mf
    p.month_to = mt
  }
  if (filters.req_keyword) p.req_keyword = filters.req_keyword
  if (filters.sa) p.sa = filters.sa
  if (filters.system_name) p.system_name = filters.system_name
  return p
}

async function load() {
  loading.value = true
  try {
    const d = await getWorkloadStats(queryParams())
    data.value = d
    // 首次加载：后端已锚定区间，回填控件与预设高亮，保证 UI 与数据一致
    if (!monthRange.value || !monthRange.value.length) {
      if (d.range?.month_from) {
        monthRange.value = [d.range.month_from, d.range.month_to]
        preset.value = matchPreset(monthRange.value)
      }
    }
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
    a.download = `工作量分析_${range.value.month_from || ''}_${range.value.month_to || ''}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

/* ─────────── 未归月：定位 + 补录启动开发时间 ─────────── */
function scrollToUnmonth() {
  const el = document.getElementById('wla-unmonth')
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  el.classList.remove('is-flash')
  void el.offsetWidth // 强制重排，保证重复点击也能重放动画
  el.classList.add('is-flash')
  setTimeout(() => el.classList.remove('is-flash'), 1300)
}

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
  gap: 16px;
  width: 100%;
}

/* 页面级栅格（12 列 / gap 18）由全局 .bento-grid 提供 */
.wla-presets {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.wla-filter {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

/* ── 区块卡：边框/圆角/阴影/入场动画交给全局 .card ── */
.wla-card {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
/* 覆写 .card-label 的 uppercase / letter-spacing（中文标题不需要） */
.wla-card-title {
  text-transform: none;
  letter-spacing: normal;
  font-size: 13.5px;
}
.wla-card-title.is-warn {
  color: var(--warning);
}

.wla-trend-body {
  flex: 1;
  padding: 12px 18px 16px;
}
.wla-side-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 12px 18px 16px;
}
.wla-table-body {
  padding: 10px 16px 14px;
}

/* ── SA Top10 条形 ── */
.wla-bars {
  display: flex;
  flex: 1;
  flex-direction: column;
  justify-content: space-between;
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
.wla-empty-inline {
  padding: 8px 0;
  color: var(--text-muted);
  font-size: 12.5px;
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
