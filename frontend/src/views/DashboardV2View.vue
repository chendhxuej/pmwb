<template>
  <div class="dv2" v-loading="loading">
    <!-- ═══ 顶部问候栏 ═══ -->
    <header class="dv2-header">
      <div class="dh-left">
        <h1 class="dh-greet">下午好，{{ data.user_name || '陈工' }}</h1>
        <p class="dh-summary">{{ overallSummary }}</p>
      </div>
      <div class="dh-right">
        <div class="dh-metric" v-if="data.efficiency">
          <span class="dhm-val" :class="data.efficiency >= 80 ? 'good' : 'warn'">{{ data.efficiency.toFixed(0) }}%</span>
          <span class="dhm-label">处置效率</span>
        </div>
        <el-button text type="primary" @click="refreshData">
          <el-icon :size="14"><Refresh /></el-icon> 刷新
        </el-button>
      </div>
    </header>

    <!-- ═══ KPI 指标条（6核心指标） ═══ -->
    <section class="dv2-kpi">
      <div class="kpi-card" v-for="(k, i) in kpiItems" :key="i">
        <span class="kpi-label">{{ k.label }}</span>
        <span class="kpi-value">{{ k.value }}</span>
        <span class="kpi-delta" :class="k.dir">{{ k.delta }}</span>
      </div>
    </section>

    <!-- ═══ 任务中心（整行，上移） ═══ -->
    <section class="tc-card-full">
      <div class="card-header">
        <span class="ch-title"><i class="ch-dot c-primary"></i>任务中心</span>
        <div class="tc-head-right">
          <span class="tc-sub">聚合 6 类待办 · 实时分析</span>
          <router-link to="/task-center" class="ch-action">查看全部 →</router-link>
        </div>
      </div>

      <!-- KPI 四格 -->
      <div class="tc-kpis">
        <div class="tk" :class="{ danger: tcOverdue > 0 }">
          <span class="tk-val">{{ tcTotal }}</span><span class="tk-label">全部任务</span>
        </div>
        <div class="tk" :class="{ danger: tcOverdue > 0 }">
          <span class="tk-val">{{ tcOverdue }}</span><span class="tk-label">已超期</span>
        </div>
        <div class="tk" :class="{ warn: tcDueSoon > 0 }">
          <span class="tk-val">{{ tcDueSoon }}</span><span class="tk-label">临期未完</span>
        </div>
        <div class="tk ok">
          <span class="tk-val">{{ tcNormal }}</span><span class="tk-label">正常推进</span>
        </div>
      </div>

      <!-- 三宫格图表 -->
      <div class="tc-charts" v-if="tc">
        <div class="tc-chart">
          <div class="tcc-title">按来源分布</div>
          <ChartPie v-if="tcSourceData.length" :data="tcSourceData" height="170px"
            :center-text="String(tcTotal)" center-sub-text="任务" />
          <div v-else class="chart-empty">暂无数据</div>
          <div class="tcc-legend" v-if="tcSourceData.length">
            <div class="tcc-li" v-for="(d, i) in tcSourceData" :key="i">
              <i class="tcc-dot" :style="{ background: d.color }"></i>
              <span class="tcc-name">{{ d.name }}</span>
              <span class="tcc-num">{{ d.value }}</span>
            </div>
          </div>
        </div>

        <div class="tc-chart">
          <div class="tcc-title">按状态分布</div>
          <ChartBar v-if="tcStatusData.length" :data="tcStatusData" height="200px" />
          <div v-else class="chart-empty">暂无数据</div>
        </div>

        <div class="tc-chart">
          <div class="tcc-title">按优先级分布</div>
          <ChartPie v-if="tcPriorityData.length" :data="tcPriorityData" height="170px" />
          <div v-else class="chart-empty">暂无数据</div>
          <div class="tcc-legend" v-if="tcPriorityData.length">
            <div class="tcc-li" v-for="(d, i) in tcPriorityData" :key="i">
              <i class="tcc-dot" :style="{ background: d.color }"></i>
              <span class="tcc-name">{{ d.name }}</span>
              <span class="tcc-num">{{ d.value }}</span>
            </div>
          </div>
        </div>

        <div class="tc-chart">
          <div class="tcc-title">超期风险率</div>
          <ChartGauge v-if="tcTotal" :value="tcRiskRate" :max="100" unit="%" height="200px" />
          <div v-else class="chart-empty">暂无数据</div>
          <div class="tcc-risk-note" :class="{ danger: tcRiskRate >= 30, warn: tcRiskRate > 0 && tcRiskRate < 30 }">
            {{ tcRiskRate >= 30 ? '⚠ 超期占比偏高' : tcRiskRate > 0 ? '存在少量超期' : '暂无超期' }}
          </div>
        </div>
      </div>

      <!-- 超期任务明细 -->
      <div class="tc-overdue" v-if="tcOverdueItems.length">
        <div class="tco-head">超期任务明细（{{ tcOverdueItems.length }}）</div>
        <div class="tco-list">
          <div class="tco-item" v-for="(o, i) in tcOverdueItems" :key="i">
            <span class="tco-prio" :class="prioClass(o.priority)">{{ o.priority }}</span>
            <span class="tco-title" :title="o.title">{{ o.title }}</span>
            <span class="tco-date" v-if="o.deadline">⏰ {{ o.deadline }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- ═══ 需求与运营 双卡 ═══ -->
    <section class="dv2-feature">
      <!-- 需求与交付 -->
      <div class="card card-req">
        <div class="card-header">
          <span class="ch-title"><i class="ch-dot c-primary"></i>需求与交付</span>
          <router-link to="/requirement-delivery" class="ch-action">进入管理 →</router-link>
        </div>
        <div class="req-kpi-row">
          <div class="rk" v-for="(r, i) in reqKpiRow" :key="i">
            <b>{{ r.val }}</b><span>{{ r.label }}</span>
          </div>
        </div>
        <div class="card-body cb-row cb-split">
          <div class="cb-chart">
            <ChartPie v-if="reqStatusDist.length" :data="reqStatusDist" height="150px" />
            <div v-else class="chart-empty">暂无分布</div>
          </div>
          <div class="cb-list">
            <div class="cl-head">近期变更</div>
            <div class="cl-item" v-for="(r, i) in recentReqs" :key="i">
              <i class="cl-dot" :class="statusDot(r.status)"></i>
              <span class="cl-text" :title="r.name">{{ r.name }}</span>
              <span class="cl-tag">{{ r.status }}</span>
            </div>
            <div class="cl-warn" v-if="(ms?.requirements.overdueDev ?? 0) > 0">
              ⚠ {{ ms.requirements.overdueDev }} 个需求开发中超 20 天
            </div>
          </div>
        </div>
      </div>

      <!-- 运营问题 -->
      <div class="card card-issue">
        <div class="card-header">
          <span class="ch-title"><i class="ch-dot c-danger"></i>运营问题</span>
          <router-link to="/operation/data" class="ch-action">进入 →</router-link>
        </div>
        <div class="issue-kpi-row">
          <div class="ik" v-for="(r, i) in issueKpiRow" :key="i" :class="{ warn: r.warn }">
            <b>{{ r.val }}</b><span>{{ r.label }}</span>
          </div>
        </div>
        <div class="issue-charts">
          <div class="ic-piece">
            <div class="ic-label">类型分布</div>
            <ChartPie v-if="issueTypeDist.length" :data="issueTypeDist" height="130px" />
          </div>
          <div class="ic-piece ic-grow">
            <div class="ic-label">7日趋势</div>
            <ChartLine v-if="issueTrend.length" :xData="issueTrendX" :series="issueTrendS"
              height="130px" :smooth="true" :area="true" />
            <div v-else class="chart-empty">暂无趋势</div>
          </div>
        </div>
        <div class="issue-bars">
          <div class="ib-row" v-for="(d, i) in issueTypeDist" :key="i">
            <span class="ib-name">{{ d.name }}</span>
            <div class="ib-track"><i :style="{ width: pctVal(d.value, issueTotal) + '%', background: d.color }"></i></div>
            <span class="ib-num">{{ d.value }}</span>
          </div>
        </div>
        <div class="card-footer" v-if="(ms?.issues.overdue ?? 0) > 0">
          <i class="cf-dot cf-red"></i>{{ ms.issues.overdue }} 项逾期需关注
        </div>
        <div class="card-footer cf-ok" v-else><i class="cf-dot cf-green"></i>处置率良好</div>
      </div>
    </section>

    <!-- ═══ 其他模块网格 ═══ -->
    <section class="dv2-grid">
      <!-- 会议日程 -->
      <div class="card card-grid card-meet">
        <div class="card-header">
          <span class="ch-title"><i class="ch-dot c-warn"></i>会议日程</span>
          <router-link to="/meeting" class="ch-action">进入 →</router-link>
        </div>
        <div class="meet-kpi-row">
          <div class="mk"><b>{{ ms?.meetings.totalThisWeek ?? 0 }}</b><span>本周</span></div>
          <div class="mk"><b>{{ ms?.meetings.today ?? 0 }}</b><span>今日</span></div>
          <div class="mk"><b>{{ ms?.meetings.upcoming ?? 0 }}</b><span>待开</span></div>
        </div>
        <div class="meet-pending-box" v-if="(ms?.meetings.pendingMinutes ?? 0) > 0">
          <div class="mpb-title">⚠ 待处理纪要 {{ ms.meetings.pendingMinutes }} 场</div>
          <div class="mpb-item" v-for="(p, i) in pendingMeetings.slice(0, 3)" :key="i">{{ p.title }}</div>
        </div>
        <div class="meet-next-box" v-if="nextSchedule">
          <span class="mnb-label">下次日程</span>
          <span class="mnb-text">{{ nextSchedule.time }} {{ nextSchedule.title }}</span>
        </div>
      </div>

      <!-- 重点工作 -->
      <div class="card card-grid card-key">
        <div class="card-header">
          <span class="ch-title"><i class="ch-dot c-purple"></i>重要工作</span>
          <router-link to="/key-works" class="ch-action">进入 →</router-link>
        </div>
        <div class="key-rows" v-if="keyProjects.length">
          <div class="kr-item" v-for="(p, i) in keyProjects.slice(0, 3)" :key="i">
            <div class="kr-top">
              <span class="kr-name" :title="p.name">{{ p.name }}</span>
              <span class="kr-pct">{{ p.percent }}%</span>
            </div>
            <div class="kr-bar-wrap"><i class="kr-bar" :style="{ width: p.percent + '%' }"></i></div>
          </div>
        </div>
        <div class="sm-empty" v-else>暂无进行中的重要工作</div>
      </div>

      <!-- 知识中心 -->
      <div class="card card-grid card-know">
        <div class="card-header">
          <span class="ch-title"><i class="ch-dot c-teal"></i>知识中心</span>
          <router-link to="/knowledge-center" class="ch-action">进入 →</router-link>
        </div>
        <div class="sm-big">{{ ms?.knowledge.total ?? 0 }}<sm>篇文档</sm></div>
        <div class="sm-sub">本月新增 {{ ms?.knowledge.thisWeek ?? 0 }} 篇</div>
        <div class="sm-line"></div>
      </div>

      <!-- 邮件中心 -->
      <div class="card card-grid card-mail">
        <div class="card-header">
          <span class="ch-title"><i class="ch-dot c-blue2"></i>邮件中心</span>
          <router-link to="/mail-center/logs" class="ch-action">进入 →</router-link>
        </div>
        <div class="sm-big">{{ ms?.emails.weekSent ?? 0 }}<sm>封/本周</sm></div>
        <div class="sm-sub">今日 {{ ms?.emails.todaySent ?? 0 }} 封 · 成功率 {{ ((ms?.emails.successRate || 0) * 100).toFixed(0) }}%</div>
        <div class="sm-line"></div>
      </div>

      <!-- 人员中台 -->
      <div class="card card-grid card-staff">
        <div class="card-header">
          <span class="ch-title"><i class="ch-dot c-indigo"></i>人员中台</span>
          <router-link to="/personnel" class="ch-action">进入 →</router-link>
        </div>
        <div class="staff-big" v-if="personnel">
          {{ personnel.staff_count }}<sm>名人员</sm>
        </div>
        <div class="staff-chips" v-if="personnel">
          <span class="schip">{{ personnel.org_count }} 个组织</span>
          <span class="schip ok">{{ personnel.enabled_staff }} 人在编</span>
        </div>
        <div class="staff-orgs" v-if="personnel && personnel.org_list.length">
          <span class="so-tag" v-for="(o, i) in personnel.org_list.slice(0, 8)" :key="i">{{ o }}</span>
          <span class="so-more" v-if="personnel.org_list.length > 8">+{{ personnel.org_list.length - 8 }}</span>
        </div>
        <div class="sm-line" v-if="personnel"></div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { dashboardApi } from '@/api/dashboard'
import ChartLine from '@/components/Charts/ChartLine.vue'
import ChartPie from '@/components/Charts/ChartPie.vue'
import ChartBar from '@/components/Charts/ChartBar.vue'
import ChartGauge from '@/components/Charts/ChartGauge.vue'

/* ─── 色彩系统（全局唯一） ─── */
const C = {
  primary: '#2f6fed',
  success: '#0f9d6b',
  danger: '#e02424',
  warn: '#d98a1f',
  purple: '#946ce6',
  teal: '#2fc9a0',
  blue2: '#6b8afd',
  indigo: '#5b6fe0',
  gray: '#909399',
  bg: '#f5f7fa',
  card: '#ffffff',
  border: '#eef0f4',
  text: '#1a1a2e',
  sub: '#606266',
}
const PALETTE = [C.primary, C.danger, C.success, C.warn, C.purple, C.teal, C.blue2, C.indigo]

/* ─── 数据加载 ─── */
const loading = ref(false)
const data = ref({
  user_name: '陈工', efficiency: 0, todos: [],
  recent_requirements: [], schedule: [], recent_issues: [],
  module_stats: null, trend_charts: null,
  distribution_charts: null, progress_items: null,
  pending_minutes_meetings: [],
  task_center_dist: null, personnel: null,
})

async function load() {
  loading.value = true
  try {
    const res = await dashboardApi.getDashboard()
    if (res) data.value = res
  } catch (e) {
    console.error('看板数据加载失败', e)
  } finally {
    loading.value = false
  }
}
function refreshData() { load() }
onMounted(load)

const ms = computed(() => data.value.module_stats)

/* ─── Hero 总结 ─── */
const overallSummary = computed(() => {
  const m = ms.value
  if (!m) return '数据加载中…'
  const parts = []
  const tc = data.value.task_center_dist
  if (tc) parts.push(`${tc.total} 项任务（${tc.overdue} 超期）`)
  parts.push(`需求 ${m.requirements.total} 个`)
  if (m.issues.total) parts.push(`问题 ${m.issues.total} 条`)
  if (m.meetings.pendingMinutes > 0) parts.push(`${m.meetings.pendingMinutes} 场纪要待补`)
  return parts.join(' · ') || '一切正常'
})

/* ─── KPI 指标（6个核心） ─── */
const kpiItems = computed(() => {
  const m = ms.value; const d = data.value
  const tc = d.task_center_dist
  const ovd = tc ? tc.overdue : 0
  return [
    { label: '任务中心', value: tc?.total ?? 0, dir: ovd > 0 ? 'down' : 'ok', delta: ovd ? `${ovd} 项超期` : '无超期' },
    { label: '需求跟踪', value: m?.requirements.total ?? 0, dir: 'ok', delta: `本周 +${m?.requirements.thisWeek ?? 0}` },
    { label: '运营问题', value: m?.issues.total ?? 0, dir: (m?.issues.overdue ?? 0) > 0 ? 'down' : 'ok', delta: `${m?.issues.overdue ?? 0} 逾期` },
    { label: '本周会议', value: m?.meetings.totalThisWeek ?? 0, dir: (m?.meetings.pendingMinutes ?? 0) > 0 ? 'down' : 'ok', delta: `${m?.meetings.pendingMinutes ?? 0} 待补纪要` },
    { label: '邮件发送', value: m?.emails.weekSent ?? 0, dir: 'ok', delta: `成功率 ${((m?.emails.successRate || 0) * 100).toFixed(0)}%` },
    { label: '处置效率', value: (d.efficiency || 0).toFixed(0) + '%', dir: d.efficiency >= 80 ? 'ok' : 'down', delta: d.efficiency >= 80 ? '达标' : '待提升' },
  ]
})

/* ─── 任务中心分布 ─── */
const tc = computed(() => data.value.task_center_dist || null)
const tcTotal = computed(() => tc.value?.total ?? 0)
const tcOverdue = computed(() => tc.value?.overdue ?? 0)
const tcDueSoon = computed(() => tc.value?.due_soon ?? 0)
const tcNormal = computed(() => Math.max(0, tcTotal.value - tcOverdue.value - tcDueSoon.value))
const tcRiskRate = computed(() => tcTotal.value ? Math.round((tcOverdue.value / tcTotal.value) * 100) : 0)
const tcSourceData = computed(() => (tc.value?.by_source || []).map((d, i) => ({ ...d, color: PALETTE[i % PALETTE.length] })))
const tcStatusData = computed(() => (tc.value?.by_status || []).map((d, i) => ({ ...d, color: PALETTE[i % PALETTE.length] })))
const tcPriorityData = computed(() => (tc.value?.by_priority || []).map((d, i) => ({ ...d, color: PALETTE[i % PALETTE.length] })))
const tcOverdueItems = computed(() => tc.value?.overdue_items || [])
function prioClass(p) {
  if (p === 'P0') return 'p0'
  if (p === 'P1') return 'p1'
  if (p === 'P2') return 'p2'
  if (p === 'P3') return 'p3'
  return 'pX'
}

/* ─── 人员中台 ─── */
const personnel = computed(() => data.value.personnel || null)

/* ─── 需求卡片 ─── */
const reqKpiRow = computed(() => {
  const m = ms.value
  return [
    { val: m?.requirements.total ?? 0, label: '总数' },
    { val: m?.requirements.thisWeek ?? 0, label: '本周新增' },
    { val: m?.requirements.inReview ?? 0, label: '跟踪中' },
    { val: m?.requirements.completed ?? 0, label: '已上线' },
  ]
})
const reqStatusDist = computed(() =>
  (data.value.distribution_charts?.requirementStatusDist || []).map((d, i) => ({ ...d, color: PALETTE[i % PALETTE.length] }))
)
const recentReqs = computed(() => (data.value.recent_requirements || []).slice(0, 4))
function statusDot(s) {
  if (['已上线', 'closed'].includes(s)) return 'st-green'
  if (['已暂停'].includes(s)) return 'st-gray'
  return 'st-blue'
}

/* ─── 运营卡片 ─── */
const issueKpiRow = computed(() => {
  const m = ms.value
  return [
    { val: m?.issues.total ?? 0, label: '总数', warn: false },
    { val: m?.issues.pending ?? 0, label: '待处理', warn: false },
    { val: m?.issues.processing ?? 0, label: '处理中', warn: false },
    { val: m?.issues.overdue ?? 0, label: '逾期', warn: (m?.issues.overdue ?? 0) > 0 },
  ]
})
const issueTypeDist = computed(() =>
  (data.value.distribution_charts?.issueTypeDist || []).map((d, i) => ({ ...d, color: PALETTE[i % PALETTE.length] }))
)
const issueTotal = computed(() => issueTypeDist.value.reduce((s, d) => s + d.value, 0))
function pctVal(v, total) { return total > 0 ? Math.round((v / total) * 100) : 0 }
const issueTrend = computed(() => data.value.trend_charts?.issuesTrend || [])
const issueTrendX = computed(() => issueTrend.value.map(t => t.label))
const issueTrendS = computed(() => [{ name: '问题数', data: issueTrend.value.map(t => t.value) }])

/* ─── 会议 / 重点工作 ─── */
const pendingMeetings = computed(() => data.value.pending_minutes_meetings || [])
const nextSchedule = computed(() => {
  const s = data.value.schedule
  return (s && s.length) ? s[0] : null
})
const keyProjects = computed(() => data.value.progress_items?.keyProjects || [])
</script>

<style scoped>
/* ═══ 全局容器 ═══ */
.dv2 {
  min-height: 100%;
  padding: 20px 24px;
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ═══ 顶部问候栏 ═══ */
.dv2-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(135deg, #e8f0fe 0%, #f0f4ff 100%);
  border-radius: 12px;
  padding: 18px 24px;
  gap: 16px;
}
.dh-left { flex: 1; min-width: 0; }
.dh-greet { margin: 0; font-size: 18px; font-weight: 700; color: #1a1a2e; }
.dh-summary { margin: 4px 0 0; font-size: 13px; color: #606266; line-height: 1.5; }
.dh-right { display: flex; align-items: center; gap: 16px; flex-shrink: 0; }
.dh-metric { text-align: center; }
.dhm-val { font-size: 26px; font-weight: 800; line-height: 1; display: block; }
.dhm-val.good { color: #0f9d6b; }
.dhm-val.warn { color: #e02424; }
.dhm-label { font-size: 11px; color: #909399; margin-top: 2px; }

/* ═══ KPI 指标条 ═══ */
.dv2-kpi {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
}
.kpi-card {
  background: #fff;
  border-radius: 10px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
  transition: box-shadow .2s;
}
.kpi-card:hover { box-shadow: 0 4px 12px rgba(47,111,237,.1); }
.kpi-label { font-size: 12px; color: #909399; }
.kpi-value { font-size: 22px; font-weight: 800; color: #1a1a2e; line-height: 1.15; }
.kpi-delta { font-size: 11px; color: #909399; }
.kpi-delta.ok { color: #0f9d6b; }
.kpi-delta.down { color: #e02424; }

/* ═══ 任务中心整行卡片 ═══ */
.tc-card-full {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0,0,0,.05);
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.tc-card-full:hover { box-shadow: 0 4px 16px rgba(0,0,0,.08); }
.tc-head-right { display: flex; align-items: center; gap: 12px; }
.tc-sub { font-size: 12px; color: #909399; }

.tc-kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.tk {
  background: #f7f9fc;
  border-radius: 10px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  border: 1px solid transparent;
}
.tk.danger { background: #fef2f2; border-color: #fbd5d5; }
.tk.warn { background: #fff8e6; border-color: #f6e2b3; }
.tk.ok { background: #f0fbf5; border-color: #cdeede; }
.tk-val { font-size: 26px; font-weight: 800; color: #1a1a2e; line-height: 1.1; }
.tk.danger .tk-val { color: #e02424; }
.tk.warn .tk-val { color: #d98a1f; }
.tk.ok .tk-val { color: #0f9d6b; }
.tk-label { font-size: 12px; color: #909399; }

.tc-charts {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.tc-chart {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: #fafbfc;
  border-radius: 10px;
  padding: 12px;
}
.tcc-title { font-size: 13px; font-weight: 700; color: #303133; }
.tcc-legend { display: flex; flex-direction: column; gap: 4px; }
.tcc-li { display: flex; align-items: center; gap: 6px; font-size: 12px; }
.tcc-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.tcc-name { color: #606266; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tcc-num { font-weight: 700; color: #303133; }
.tcc-risk-note { font-size: 12px; color: #0f9d6b; text-align: center; margin-top: 2px; }
.tcc-risk-note.warn { color: #d98a1f; }
.tcc-risk-note.danger { color: #e02424; }

.tc-overdue {
  background: #fff8f8;
  border: 1px solid #fbd5d5;
  border-radius: 10px;
  padding: 12px 14px;
}
.tco-head { font-size: 13px; font-weight: 700; color: #e02424; margin-bottom: 8px; }
.tco-list { display: flex; flex-direction: column; gap: 6px; max-height: 132px; overflow-y: auto; }
.tco-item { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.tco-prio {
  font-size: 11px; font-weight: 700; padding: 1px 7px; border-radius: 4px; flex-shrink: 0;
  background: #eef0f4; color: #606266;
}
.tco-prio.p0 { background: #fde2e2; color: #e02424; }
.tco-prio.p1 { background: #fef0db; color: #d98a1f; }
.tco-prio.p2 { background: #e6f0ff; color: #2f6fed; }
.tco-prio.p3 { background: #eef0f4; color: #909399; }
.tco-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #303133; }
.tco-date { font-size: 11px; color: #e02424; flex-shrink: 0; }

/* ═══ 卡片通用 ═══ */
.card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0,0,0,.05);
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  transition: box-shadow .2s;
}
.card:hover { box-shadow: 0 4px 16px rgba(0,0,0,.08); }
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.ch-title { font-size: 15px; font-weight: 700; color: #1a1a2e; display: flex; align-items: center; gap: 7px; }
.ch-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.c-primary { background: #2f6fed; }
.c-danger { background: #e02424; }
.c-warn { background: #d98a1f; }
.c-teal { background: #2fc9a0; }
.c-purple { background: #946ce6; }
.c-blue2 { background: #6b8afd; }
.c-indigo { background: #5b6fe0; }
.ch-action { font-size: 12px; color: #2f6fed; text-decoration: none; white-space: nowrap; }
.ch-action:hover { text-decoration: underline; }

.card-body { display: flex; gap: 16px; flex: 1; min-height: 0; }
.cb-row { flex-direction: row; align-items: stretch; }
.cb-split { align-items: stretch; }
.cb-chart { flex-shrink: 0; }
.cb-info, .cb-list { flex: 1; display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.chart-empty { display: flex; align-items: center; justify-content: center; color: #c0c4cc; font-size: 13px; background: #fafbfc; border-radius: 8px; min-height: 120px; }

/* 需求 - KPI 行 */
.req-kpi-row, .issue-kpi-row, .meet-kpi-row { display: flex; gap: 8px; margin-bottom: 14px; }
.rk, .ik, .mk { flex: 1; display: flex; flex-direction: column; align-items: center; background: #f7f9fc; border-radius: 8px; padding: 8px 4px; }
.rk b, .ik b, .mk b { font-size: 17px; font-weight: 700; color: #1a1a2e; }
.rk span, .ik span, .mk span { font-size: 11px; color: #909399; margin-top: 2px; }
.ik.warn b { color: #e02424; }

/* 需求 - 列表 */
.cl-head { font-size: 12px; font-weight: 600; color: #606266; margin-bottom: 2px; }
.cl-item { display: flex; align-items: center; gap: 6px; font-size: 12px; line-height: 1.7; }
.cl-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.st-blue { background: #2f6fed; } .st-green { background: #0f9d6b; } .st-gray { background: #c0c4cc; }
.cl-text { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #303133; }
.cl-tag { color: #909399; font-size: 11px; flex-shrink: 0; }
.cl-warn { font-size: 11px; color: #e02424; background: #fef2f2; padding: 4px 8px; border-radius: 4px; margin-top: auto; }

/* 运营 - 图表区 */
.issue-charts { display: flex; gap: 12px; margin-bottom: 12px; }
.ic-piece { flex: 0 0 140px; }
.ic-grow { flex: 1; min-width: 0; }
.ic-label { font-size: 11px; color: #909399; margin-bottom: 4px; font-weight: 600; }
.issue-bars { display: flex; flex-direction: column; gap: 5px; }
.ib-row { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.ib-name { width: 64px; color: #606266; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ib-track { flex: 1; height: 6px; background: #eef1f6; border-radius: 3px; overflow: hidden; }
.ib-track i { display: block; height: 100%; border-radius: 3px; transition: width .6s ease; }
.ib-num { width: 24px; text-align: right; font-weight: 600; color: #303133; flex-shrink: 0; }

.card-footer { font-size: 12px; color: #606266; display: flex; align-items: center; gap: 6px; margin-top: auto; padding-top: 10px; border-top: 1px solid #f0f2f5; }
.cf-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.cf-red { background: #e02424; } .cf-green { background: #0f9d6b; }
.cf-ok { color: #0f9d6b; }

/* 会议卡片 */
.meet-pending-box { background: #fff8e6; border-radius: 8px; padding: 10px 12px; margin-top: 8px; }
.mpb-title { font-size: 12px; font-weight: 700; color: #b88200; margin-bottom: 6px; }
.mpb-item { font-size: 12px; color: #606266; padding: 3px 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.meet-next-box { margin-top: 10px; font-size: 12px; }
.mnb-label { color: #909399; }
.mnb-text { color: #2f6fed; font-weight: 600; margin-left: 4px; }

/* ═══ 特征双卡 ═══ */
.dv2-feature {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  align-items: start;
}

/* ═══ 其他模块网格 ═══ */
.dv2-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
}
.card-grid { min-height: 150px; }
.card-meet, .card-key, .card-know { grid-column: span 2; }
.card-mail { grid-column: span 3; }
.card-staff { grid-column: span 3; }

.sm-big { font-size: 28px; font-weight: 800; color: #1a1a2e; line-height: 1.1; }
.sm-big sm { font-size: 12px; font-weight: 400; color: #909399; margin-left: 3px; }
.sm-sub { font-size: 12px; color: #909399; margin-top: 4px; }
.sm-line { margin-top: auto; padding-top: 8px; border-top: 1px solid #f0f2f5; height: 100%; }
.sm-empty { color: #c0c4cc; font-size: 13px; text-align: center; padding: 20px 0; }

/* 重要工作 - 进度条 */
.key-rows { display: flex; flex-direction: column; gap: 10px; flex: 1; justify-content: center; }
.kr-item { display: flex; flex-direction: column; gap: 3px; }
.kr-top { display: flex; justify-content: space-between; font-size: 12px; }
.kr-name { color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 75%; }
.kr-pct { font-weight: 700; color: #946ce6; }
.kr-bar-wrap { height: 5px; background: #efeaf8; border-radius: 3px; overflow: hidden; }
.kr-bar { display: block; height: 100%; background: #946ce6; border-radius: 3px; transition: width .5s ease; }

/* 人员中台 */
.staff-big { font-size: 28px; font-weight: 800; color: #1a1a2e; line-height: 1.1; }
.staff-big sm { font-size: 12px; font-weight: 400; color: #909399; margin-left: 3px; }
.staff-chips { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
.schip { font-size: 12px; background: #eef2ff; color: #5b6fe0; padding: 3px 10px; border-radius: 20px; }
.schip.ok { background: #f0fbf5; color: #0f9d6b; }
.staff-orgs { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.so-tag { font-size: 11px; background: #f5f7fa; color: #606266; padding: 2px 8px; border-radius: 4px; }
.so-more { font-size: 11px; color: #909399; padding: 2px 6px; }

/* ═══ 响应式 ═══ */
@media (max-width: 1200px) {
  .dv2-kpi { grid-template-columns: repeat(3, 1fr); }
  .tc-charts { grid-template-columns: repeat(2, 1fr); }
  .dv2-grid { grid-template-columns: repeat(4, 1fr); }
  .card-meet, .card-key, .card-know, .card-mail, .card-staff { grid-column: span 2; }
}
@media (max-width: 768px) {
  .dv2-kpi { grid-template-columns: repeat(2, 1fr); }
  .tc-kpis { grid-template-columns: repeat(2, 1fr); }
  .tc-charts { grid-template-columns: 1fr; }
  .dv2-feature { grid-template-columns: 1fr; }
  .dv2-grid { grid-template-columns: 1fr; }
  .card-meet, .card-key, .card-know, .card-mail, .card-staff { grid-column: span 1; }
}
</style>
