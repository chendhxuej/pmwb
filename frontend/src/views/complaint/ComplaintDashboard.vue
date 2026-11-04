<template>
  <div class="complaint-dashboard">
    <PageHeader title="投诉现状分析" :subtitle="subTitle">
      <template #actions>
        <el-select v-if="weekOptions.length" v-model="selectedWeek" style="width: 168px" @change="onWeekChange">
          <el-option v-for="w in weekOptions" :key="w" :label="weekLabel(w)" :value="w" />
        </el-select>
        <el-button :icon="Upload" type="primary" plain @click="uploadVisible = true">上传工单数据</el-button>
        <el-button :icon="Download" :disabled="!metrics.week" @click="openReport">查看最新周报</el-button>
        <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
      </template>
    </PageHeader>

    <div v-if="metrics.week" v-loading="loading" class="dashboard-body">
      <!-- 一、本周概览与波动 -->
      <section class="card">
        <div class="card-header">
          <h3>一、本周概览与波动</h3>
          <span class="hint">区间 {{ metrics.range }}</span>
        </div>
        <div class="card-body">
          <div class="pm-stat-grid pm-stat-grid--6">
            <div class="card kpi-card kpi-clickable" title="点击下钻本周工单" @click="drill({ week: metrics.week }, '本周新增投诉工单')">
              <div class="kpi-num blue">{{ metrics.total }}</div>
              <div class="kpi-label">本周新增（单）</div>
            </div>
            <div class="card kpi-card">
              <div class="kpi-num">{{ metrics.daily_avg }}</div>
              <div class="kpi-label">日均（单）</div>
            </div>
            <div class="card kpi-card">
              <div class="kpi-num" :class="wowClass">{{ wowText }}</div>
              <div class="kpi-label">周环比</div>
            </div>
            <div class="card kpi-card kpi-clickable" title="已知问题率越低，说明越在追新火" @click="drill({ week: metrics.week, known_flag: 0 }, '本周新增问题工单')">
              <div class="kpi-num" :class="known.known_rate >= 50 ? 'green' : 'red'">{{ known.known_rate ?? 0 }}%</div>
              <div class="kpi-label">已知问题率</div>
            </div>
            <div class="card kpi-card">
              <div class="kpi-num" :class="(rc.coverage_pct || 0) >= 95 ? 'green' : 'amber'">{{ rc.coverage_pct ?? 0 }}%</div>
              <div class="kpi-label">根因分析覆盖</div>
            </div>
            <div class="card kpi-card">
              <div class="kpi-num">{{ rc.cluster_cnt ?? 0 }}</div>
              <div class="kpi-label">涉及根因簇</div>
            </div>
          </div>

          <div v-if="partialBase" class="pm-note warn">
            上周（{{ metrics.prev_week }}）仅 {{ metrics.prev_days }} 天数据，<b>周环比不可比</b>——
            本页不给环比结论，不用残缺数据硬算（否则会把导入节奏误判成暴涨暴跌）。
          </div>

          <ChartLine :x-data="dailyX" :series="dailySeries" height="240px" />
        </div>
      </section>

      <!-- 二、已知 vs 新增 -->
      <section class="card">
        <div class="card-header">
          <h3>二、已知问题 vs 新增问题（核心指标）</h3>
          <span class="hint">判定：工单 → 根因簇 → 是否被在办问题收纳</span>
        </div>
        <div class="card-body">
          <div class="pm-stat-grid pm-stat-grid--4">
            <div class="card kpi-card">
              <div class="kpi-num" :class="known.known_rate >= 50 ? 'green' : 'red'">{{ known.known_rate ?? 0 }}%</div>
              <div class="kpi-label">已知问题率（分母=已判定单量）</div>
            </div>
            <div class="card kpi-card kpi-clickable" @click="drill({ week: metrics.week, known_flag: 1 }, '已知问题工单')">
              <div class="kpi-num red">{{ known.known_cnt ?? 0 }}</div>
              <div class="kpi-label">已知问题（单）</div>
            </div>
            <div class="card kpi-card kpi-clickable" @click="drill({ week: metrics.week, known_flag: 0 }, '新增问题工单')">
              <div class="kpi-num blue">{{ known.new_cnt ?? 0 }}</div>
              <div class="kpi-label">新增问题（单）</div>
            </div>
            <div class="card kpi-card">
              <div class="kpi-num">{{ known.judged ?? 0 }}/{{ known.total ?? metrics.total }}</div>
              <div class="kpi-label">已判定 / 总量</div>
            </div>
          </div>

          <div class="pm-note">
            候选问题不计为已知——<b>没进台账就等于组织还没认账</b>。
            本周有 <b>{{ known.potential_known_cnt ?? 0 }}</b> 单属于「AI 已识别、待确认入账」，
            当前在办问题 <b>{{ known.inflight_problem_cnt ?? 0 }}</b> 个。
            <span v-if="known.unknown_cnt">另有 {{ known.unknown_cnt }} 单无根因簇，不计入分母。</span>
          </div>

          <div class="sub-h">已知问题（按本周命中单量）</div>
          <el-table :data="known.known_problems || []" size="small" empty-text="本周没有一单能被在办问题解释">
            <el-table-column prop="problem_no" label="问题编号" width="150" />
            <el-table-column prop="title" label="在办问题（根因摘要）" min-width="280" show-overflow-tooltip />
            <el-table-column prop="owner" label="责任人" width="110" />
            <el-table-column label="本周命中" width="96" align="center">
              <template #default="{ row }"><b class="num-red">{{ row.cnt }}</b></template>
            </el-table-column>
            <el-table-column label="状态" width="92" align="center">
              <template #default="{ row }">
                <el-tag :type="row.status === 'resolving' ? 'warning' : 'primary'" size="small" effect="light">
                  {{ row.status === 'resolving' ? '处理中' : '在办' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="88" align="center">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="drill({ week: metrics.week, problem_no: row.problem_no }, '已知问题工单')">下钻</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="sub-h">新增问题（本周出现、台账未收纳 → 应入账）</div>
          <el-table :data="known.new_clusters || []" size="small" empty-text="本周无新增问题">
            <el-table-column label="新增问题（根因簇）" min-width="300" show-overflow-tooltip>
              <template #default="{ row }"><b>{{ row.title || row.rootcause_no || '未归簇' }}</b></template>
            </el-table-column>
            <el-table-column prop="fault_system" label="系统" width="110" />
            <el-table-column prop="fault_stage" label="环节" width="100" />
            <el-table-column label="单量" width="76" align="center">
              <template #default="{ row }"><b class="num-red">{{ row.cnt }}</b></template>
            </el-table-column>
            <el-table-column label="候选状态" width="130" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.in_candidate" type="primary" size="small" effect="light">{{ row.cand_problem_no }}</el-tag>
                <el-tag v-else type="warning" size="small" effect="light">待入账</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="88" align="center">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="drillRootcause(row)">下钻</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </section>

      <!-- 三、分类汇总 -->
      <section class="card">
        <div class="card-header">
          <h3>三、问题族分析（业务链路）</h3>
          <span class="hint">
            环比按日均对比（本周 {{ th.week_days || 0 }} 天 / 上周 {{ th.prev_days || 0 }} 天）
          </span>
        </div>
        <div class="card-body">
          <el-table class="theme-table" :data="themeRows" size="small" empty-text="暂无问题族数据">
            <el-table-column label="问题族（业务链路）" min-width="170">
              <template #default="{ row }">
                <b>{{ row.name }}</b>
                <el-tag v-if="row.is_new" size="small" type="danger" class="rule-tag">本周新增</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="本周" width="70" align="center">
              <template #default="{ row }"><b class="num-red">{{ row.week_cnt }}</b></template>
            </el-table-column>
            <el-table-column label="上周日均" width="86" align="right">
              <template #default="{ row }">{{ row.prev_avg }}</template>
            </el-table-column>
            <el-table-column label="本周日均" width="86" align="right">
              <template #default="{ row }">{{ row.avg }}</template>
            </el-table-column>
            <el-table-column label="日均环比" width="110" align="center">
              <template #default="{ row }">
                <span v-if="row.wow === null || row.wow === undefined" class="text-muted">不可比</span>
                <span v-else :class="row.wow > 0 ? 'num-red' : 'num-green'">
                  {{ row.wow > 0 ? '+' : '' }}{{ row.wow }}%
                </span>
                <el-tag v-if="row.low_sample" size="small" type="info" class="rule-tag">样本小</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="累计" width="72" align="right">
              <template #default="{ row }">{{ row.total_cnt }}</template>
            </el-table-column>
            <el-table-column label="问题簇" width="76" align="center">
              <template #default="{ row }">{{ row.problem_cluster_cnt }}</template>
            </el-table-column>
            <el-table-column label="主要问题（累计 TOP）" min-width="300">
              <template #default="{ row }">
                <div v-for="c in row.top_clusters" :key="c.rc_no" class="top-cluster">
                  <span class="tc-cnt">{{ c.cnt }} 单</span>
                  <span class="tc-title">{{ c.title }}</span>
                </div>
                <span v-if="!row.top_clusters.length" class="text-muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" align="center">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="drillTheme(row)">下钻</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="case-line">
            <el-icon><InfoFilled /></el-icon>
            另有 <b>{{ th.cases?.cluster_cnt || 0 }}</b> 个一次性个案（共
            {{ th.cases?.ticket_cnt || 0 }} 单，仅出现 1 次、无同类可比），不计入族汇总；
            <span v-if="th.new_case_cnt">本周新增 {{ th.new_case_cnt }} 个。</span>
            <el-button v-if="th.cases?.cluster_cnt" size="small" text type="primary"
              @click="drillCases">查看个案明细</el-button>
          </div>
          <div v-if="th.unattributed?.cnt" class="case-line warn">
            未归因工单 {{ th.unattributed.cnt }} 单（根因分析未完成），未摊入任何族。
          </div>

          <div class="sub-h">按投诉性质看（五类，分母 = 已根因分析 {{ rc.covered ?? 0 }} 单）</div>
          <div class="l1-row">
            <div class="l1-chart pm-col-5">
              <ChartPie :data="pieData" donut height="260px" @item-click="p => drill({ week: metrics.week, l1: p.name }, `一级性质「${p.name}」工单`)" />
            </div>
            <div class="l1-table pm-col-7">
              <el-table class="l1-class-table" :data="l1Rows" size="small">
                <el-table-column prop="name" label="一级性质" width="110" />
                <el-table-column prop="meaning" label="含义" min-width="200" show-overflow-tooltip />
                <el-table-column prop="cnt" label="单量" width="80" align="center" />
                <el-table-column prop="pct" label="占比" width="80" align="right">
                  <template #default="{ row }">{{ row.pct }}%</template>
                </el-table-column>
              </el-table>
            </div>
          </div>

          <div class="sub-h">重点根因簇（累计 ≥5 单，可直接立项修复）</div>
          <el-table :data="bigClusters" size="small" empty-text="暂无达到量级的根因簇">
            <el-table-column label="根因簇" min-width="320" show-overflow-tooltip>
              <template #default="{ row }"><b>{{ row.title }}</b></template>
            </el-table-column>
            <el-table-column prop="fault_system" label="系统" width="110" />
            <el-table-column prop="fault_type" label="缺陷性质" width="110" />
            <el-table-column prop="own_party" label="责任归属" width="100" />
            <el-table-column label="累计单量" width="88" align="center">
              <template #default="{ row }"><b class="num-red">{{ row.cnt }}</b></template>
            </el-table-column>
            <el-table-column label="操作" width="88" align="center">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="drillRootcause(row)">下钻</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </section>

      <!-- 四、压降指引 -->
      <section class="card">
        <div class="card-header">
          <h3>四、工单压降分析指引</h3>
          <span class="hint">同根因簇 ≥{{ batchMin }} 单 = 修一处可整批消掉</span>
        </div>
        <div class="card-body">
          <div class="pm-stat-grid pm-stat-grid--4">
            <div class="card kpi-card">
              <div class="kpi-num red">{{ winCnt }}</div>
              <div class="kpi-label">可整批压降单量</div>
            </div>
            <div class="card kpi-card">
              <div class="kpi-num">{{ winPct }}%</div>
              <div class="kpi-label">占已分析单量</div>
            </div>
            <div class="card kpi-card">
              <div class="kpi-num">{{ (rc.batch || []).length }}</div>
              <div class="kpi-label">可修复根因簇</div>
            </div>
            <div class="card kpi-card">
              <div class="kpi-num">{{ rc.quick_win_cnt ?? 0 }}</div>
              <div class="kpi-label">可批量修复/改造单量</div>
            </div>
          </div>

          <el-table :data="rc.batch || []" size="small" empty-text="本周无可整批压降的问题">
            <el-table-column label="根因（改这里即可整批消掉）" min-width="300" show-overflow-tooltip>
              <template #default="{ row }"><b>{{ row.title }}</b></template>
            </el-table-column>
            <el-table-column prop="fault_system" label="系统" width="110" />
            <el-table-column prop="own_party" label="责任方" width="100" />
            <el-table-column label="覆盖单量" width="90" align="center">
              <template #default="{ row }"><b class="num-red">{{ row.cnt }}</b></template>
            </el-table-column>
            <el-table-column prop="fix_mode" label="处置方式" width="100" />
            <el-table-column label="建议动作" min-width="240" show-overflow-tooltip>
              <template #default="{ row }">{{ fixAction(row.fix_mode) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="88" align="center">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="drillRootcause(row)">下钻</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </section>

      <!-- 五、措施进展 -->
      <section class="card">
        <div class="card-header">
          <h3>五、措施跟踪与自动验证</h3>
          <span class="hint">措施绑簇、按簇单量算降幅、每期导入后自动结算</span>
        </div>
        <div class="card-body">
          <el-table :data="metrics.actions || []" size="small" empty-text="尚未登记改进措施">
            <el-table-column prop="action_no" label="措施编号" width="170" />
            <el-table-column prop="title" label="措施" min-width="260" show-overflow-tooltip />
            <el-table-column prop="owner" label="责任人" width="100" />
            <el-table-column label="基线/本周" width="110" align="center">
              <template #default="{ row }">{{ row.baseline_cnt ?? '—' }} / {{ row.last_week_cnt ?? '—' }}</template>
            </el-table-column>
            <el-table-column label="实际降幅" width="96" align="right">
              <template #default="{ row }">
                <b v-if="row.actual_drop_pct !== null" :class="row.actual_drop_pct >= 0 ? 'num-green' : 'num-red'">
                  {{ row.actual_drop_pct > 0 ? '+' : '' }}{{ row.actual_drop_pct }}%
                </b>
                <span v-else class="muted">待基线</span>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100" />
            <el-table-column label="操作" width="88" align="center">
              <template #default>
                <el-button size="small" text type="primary" @click="goActions">去跟踪</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </section>
    </div>

    <el-empty v-else description="暂无投诉数据，请先上传工单" />

    <ComplaintUploadDialog v-model="uploadVisible" @done="loadAll" />
    <TicketDrillDrawer v-model="drillVisible" :filters="drillFilters" :title="drillTitle" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Upload, Download, InfoFilled } from '@element-plus/icons-vue'
import PageHeader from '@/components/Common/PageHeader.vue'
import ChartPie from '@/components/Charts/ChartPie.vue'
import ChartLine from '@/components/Charts/ChartLine.vue'
import ComplaintUploadDialog from './components/ComplaintUploadDialog.vue'
import TicketDrillDrawer from './components/TicketDrillDrawer.vue'
import { complaintApi } from '@/api/complaint'
import { openWithAuth } from '@/utils/download.js'

const router = useRouter()
const loading = ref(false)
const uploadVisible = ref(false)
const metrics = ref({})
const selectedWeek = ref('')
const weekOptions = ref([])
const batchMin = 3

// 一级性质含义（展示用；字典与口径仍在后端唯一源自 pmwb_complaint_category）
const L1_MEANING = {
  系统问题: '系统缺陷，需研发修复',
  流程优化: '流程或规则不合理，需改造',
  数据异常: '数据不一致/错误，需批量修复',
  规则咨询: '客户对政策资费有疑问，解释即可化解',
  操作咨询: '客户不熟悉操作，指引或代办即可化解',
}
const FIX_ACTION = {
  批量修复: '出数据修复脚本，一次性回溯存量错误数据',
  系统改造: '提需求排期改造（评估版本窗口）',
  规则调整: '调整校验规则/配置口径，无需改代码',
  逐单处理: '无法批量，只能逐单兜底（不产生压降空间）',
  解释指引: '完善指引话术，压降重复咨询',
}
function fixAction(mode) {
  return FIX_ACTION[mode] || '逐单核实后再定'
}

const rc = computed(() => metrics.value.rootcause || {})
const known = computed(() => metrics.value.known || {})

const subTitle = computed(() => {
  if (!metrics.value.week) return 'AI 自动分析：本周新增 → 已知/新增 → 五类 → 压降空间'
  return `${metrics.value.week}｜AI 全自动分析，人工只在问题入账时确认一次`
})

const partialBase = computed(() => !!metrics.value.prev_partial)
const wowText = computed(() => {
  if (metrics.value.prev_partial) return '不可比'
  const v = metrics.value.wow_pct
  if (v === null || v === undefined) return '—'
  return `${v > 0 ? '+' : ''}${v}%`
})
const wowClass = computed(() => {
  if (metrics.value.prev_partial) return ''
  const v = metrics.value.wow_pct
  if (v === null || v === undefined) return ''
  return v > 0 ? 'red' : 'green'
})

const pieData = computed(() => (metrics.value.by_l1 || []).map(x => ({ value: x.cnt, name: x.name })))
const l1Rows = computed(() => (metrics.value.by_l1 || []).map(x => ({
  ...x, meaning: L1_MEANING[x.name] || '—',
})))

// 问题族（业务链路）：报表主视角，替代原来平铺根因簇的「散」
const th = computed(() => metrics.value.themes || {})
const themeRows = computed(() => th.value.themes || [])
// 重点根因簇：只有达到量级的才值得单独立项，1~2 单的个案不进这张表
const bigClusters = computed(() => (rc.value.clusters || []).filter(c => (c.cnt || 0) >= 5))

function drillTheme(row) {
  const rcs = row.rc_nos || []
  if (!rcs.length) return ElMessage.info('该族本周无归因工单')
  drill({ rootcause_no: rcs.join(',') }, `问题族「${row.name}」工单`)
}

function drillCases() {
  drill({ rc_max_tickets: 1 }, '一次性个案工单（所在簇仅 1 单）')
}
const dailyX = computed(() => Object.keys(metrics.value.daily || {}).map(k => k.slice(5)))
const dailySeries = computed(() => [{
  name: '当日单量',
  data: Object.values(metrics.value.daily || {}),
}])

const winCnt = computed(() => (rc.value.batch || []).reduce((s, x) => s + (x.cnt || 0), 0))
const winPct = computed(() => {
  const covered = rc.value.covered || 0
  return covered ? Math.round((winCnt.value / covered) * 1000) / 10 : 0
})

function weekLabel(w) {
  return w ? w.replace('-', ' 第') + ' 周' : ''
}

async function loadAll() {
  loading.value = true
  try {
    metrics.value = await complaintApi.getMetrics(selectedWeek.value || undefined)
    if (metrics.value.week) {
      if (!selectedWeek.value) selectedWeek.value = metrics.value.week
      if (!weekOptions.value.includes(metrics.value.week)) {
        weekOptions.value = [...new Set([...(metrics.value.trend || []).map(t => t.week), metrics.value.week])]
          .filter(Boolean).sort().reverse()
      }
    }
  } catch (e) {
    metrics.value = {}
  } finally {
    loading.value = false
  }
}

function onWeekChange(w) {
  selectedWeek.value = w
  loadAll()
}

function drillRootcause(row) {
  if (!row?.rootcause_no) return
  drill({ week: metrics.value.week, rootcause_no: row.rootcause_no },
    `根因簇「${row.title}」工单`)
}

const drillVisible = ref(false)
const drillFilters = ref({})
const drillTitle = ref('')
function drill(filters, title) {
  drillFilters.value = { ...filters }
  drillTitle.value = title || '投诉工单下钻'
  drillVisible.value = true
}

async function openReport() {
  if (!metrics.value.week) return ElMessage.warning('暂无可导出的周报')
  const week = metrics.value.week
  const loadingMsg = ElMessage({ message: '正在准备周报…', duration: 0, type: 'info' })
  try {
    try {
      // 裸 window.open 不带 JWT，开启了鉴权会被 401 拦下
      await openWithAuth(complaintApi.reportDownloadUrl(week))
    } catch (e) {
      // 该周周报文件还没生成（历史周常见）：先让后端生成，再打开
      if (String(e?.message || '').includes('不存在')) {
        await complaintApi.genReport({ week, with_pdf: false })
        await openWithAuth(complaintApi.reportDownloadUrl(week))
      } else {
        throw e
      }
    }
  } catch (e) {
    ElMessage.error('周报打开失败：' + (e?.message || e))
  } finally {
    loadingMsg.close()
  }
}

function goActions() {
  router.push('/complaint-center/actions')
}

onMounted(loadAll)
</script>

<style scoped>
.dashboard-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.hint {
  font-size: 12px;
  color: var(--text-muted);
}
.sub-h {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 18px 0 8px;
}
.pm-note {
  margin: 12px 0;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  border-left: 3px solid var(--accent);
  font-size: 12.5px;
  line-height: 1.8;
  color: var(--text-secondary);
}
.pm-note.warn {
  background: var(--warning-soft);
  border-left-color: var(--warning);
}
.num-red { color: var(--danger); }
.num-green { color: var(--success); }
/* 问题族表：族内 TOP 问题紧凑堆叠，避免撑行高 */
.top-cluster {
  display: flex;
  gap: 8px;
  line-height: 1.6;
  font-size: 12px;
}
.top-cluster .tc-cnt {
  flex: 0 0 44px;
  color: var(--danger);
  font-variant-numeric: tabular-nums;
}
.top-cluster .tc-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-secondary);
}
/* 个案/未归因提示行 */
.case-line {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  background: var(--bg-app);
  font-size: 12px;
  color: var(--text-secondary);
}
.case-line.warn {
  background: var(--warning-soft);
  color: var(--warning);
}
.muted { color: var(--text-muted); }
.l1-row {
  display: grid;
  grid-template-columns: 5fr 7fr;
  gap: 16px;
  align-items: center;
}
.kpi-clickable { cursor: pointer; }
@media (max-width: 960px) {
  .l1-row { grid-template-columns: 1fr; }
}
</style>
