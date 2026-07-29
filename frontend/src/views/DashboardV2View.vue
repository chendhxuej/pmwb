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

    <!-- ═══ 主内容区：左右两列 ═══ -->
    <section class="dv2-main">

      <!-- ═══ 左列 ═══ -->
      <div class="dv2-col dv2-col-left">

        <!-- 任务中心 -->
        <div class="card card-task">
          <div class="card-header">
            <span class="ch-title"><i class="ch-dot c-primary"></i>任务中心</span>
            <router-link to="/task-center" class="ch-action">查看全部 →</router-link>
          </div>
          <div class="card-body cb-row">
            <div class="cb-chart">
              <ChartPie v-if="taskDonut.length" :data="taskDonut" height="160px"
                :center-text="String(taskTotal)" center-sub-text="待办" />
              <div v-else class="chart-empty">暂无数据</div>
            </div>
            <div class="cb-info">
              <div class="ci-legend" v-for="(d, i) in taskDonut" :key="i">
                <i class="ci-dot" :style="{ background: d.color }"></i>
                <span class="ci-name">{{ d.name }}</span>
                <span class="ci-num">{{ d.value }}</span>
              </div>
              <div class="ci-alert" v-if="taskOverdue > 0">
                <i class="ca-icon">⚠</i> {{ taskOverdue }} 项超期待办
              </div>
              <div class="ci-ok" v-else><i class="co-icon">✓</i> 运行平稳</div>
            </div>
          </div>
        </div>

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

      </div>

      <!-- ═══ 右列 ═══ -->
      <div class="dv2-col dv2-col-right">

        <!-- 运营问题（拉长丰富） -->
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

        <!-- 会议日程 -->
        <div class="card card-meet">
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
            <div class="mpb-title">⚠ 待处理会议纪要 {{ ms.meetings.pendingMinutes }} 场</div>
            <div class="mpb-item" v-for="(p, i) in pendingMeetings.slice(0, 4)" :key="i">
              {{ p.title }}
            </div>
          </div>
          <div class="meet-next-box" v-if="nextSchedule">
            <span class="mnb-label">下次日程</span>
            <span class="mnb-text">{{ nextSchedule.time }} {{ nextSchedule.title }}</span>
          </div>
        </div>

      </div>
    </section>

    <!-- ═══ 底部三卡片（等高） ═══ -->
    <section class="dv2-bottom">
      <div class="card card-sm card-know">
        <div class="card-header">
          <span class="ch-title"><i class="ch-dot c-teal"></i>知识中心</span>
          <router-link to="/knowledge-center" class="ch-action">进入 →</router-link>
        </div>
        <div class="sm-big">{{ ms?.knowledge.total ?? 0 }}<sm>篇文档</sm></div>
        <div class="sm-sub">本月新增 {{ ms?.knowledge.thisWeek ?? 0 }} 篇</div>
        <div class="sm-line"></div>
      </div>

      <div class="card card-sm card-key">
        <div class="card-header">
          <span class="ch-title"><i class="ch-dot c-purple"></i>重要工作</span>
          <router-link to="/key-works" class="ch-action">进入 →</router-link>
        </div>
        <div class="key-rows" v-if="keyProjects.length">
          <div class="kr-item" v-for="(p, i) in keyProjects.slice(0, 3)" :key="i">
            <span class="kr-name" :title="p.name">{{ p.name }}</span>
            <div class="kr-bar-wrap"><i class="kr-bar" :style="{ width: p.percent + '%' }"></i></div>
            <span class="kr-pct">{{ p.percent }}%</span>
          </div>
        </div>
        <div class="sm-empty" v-else>暂无进行中的重要工作</div>
      </div>

      <div class="card card-sm card-mail">
        <div class="card-header">
          <span class="ch-title"><i class="ch-dot c-blue2"></i>邮件中心</span>
          <router-link to="/mail-center/logs" class="ch-action">进入 →</router-link>
        </div>
        <div class="sm-big">{{ ms?.emails.weekSent ?? 0 }}<sm>封/本周</sm></div>
        <div class="sm-sub">今日 {{ ms?.emails.todaySent ?? 0 }} 封 · 成功率 {{ ((ms?.emails.successRate || 0) * 100).toFixed(0) }}%</div>
        <div class="sm-line"></div>
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

/* ─── 色彩系统（全局唯一） ─── */
const C = {
  primary: '#2f6fed',
  success: '#0f9d6b',
  danger: '#e02424',
  warn: '#d98a1f',
  purple: '#946ce6',
  teal: '#2fc9a0',
  blue2: '#6b8afd',
  gray: '#909399',
  bg: '#f5f7fa',
  card: '#ffffff',
  border: '#eef0f4',
  text: '#1a1a2e',
  sub: '#606266',
}
const PALETTE = [C.primary, C.danger, C.success, C.warn, C.purple, C.teal, C.blue2]

/* ─── 数据加载 ─── */
const loading = ref(false)
const data = ref({
  user_name: '陈工', efficiency: 0, todos: [],
  recent_requirements: [], schedule: [], recent_issues: [],
  module_stats: null, trend_charts: null,
  distribution_charts: null, progress_items: null,
  pending_minutes_meetings: [],
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
  const td = data.value.todos.length || 0
  if (td) parts.push(`${td} 项待办`)
  parts.push(`需求 ${m.requirements.total} 个`)
  if (m.issues.total) parts.push(`问题 ${m.issues.total} 条`)
  if (m.meetings.pendingMinutes > 0) parts.push(`${m.meetings.pendingMinutes} 场纪要待补`)
  return parts.join(' · ') || '一切正常'
})

/* ─── KPI 指标（6个核心） ─── */
const kpiItems = computed(() => {
  const m = ms.value; const d = data.value
  const ovd = (d.todos || []).filter(t => t.overdue).length
  return [
    { label: '我的待办', value: d.todos.length || 0, dir: ovd > 0 ? 'down' : 'ok', delta: ovd ? `${ovd} 项超期` : '无超期' },
    { label: '需求跟踪', value: m?.requirements.total ?? 0, dir: 'ok', delta: `本周 +${m?.requirements.thisWeek ?? 0}` },
    { label: '运营问题', value: m?.issues.total ?? 0, dir: (m?.issues.overdue ?? 0) > 0 ? 'down' : 'ok', delta: `${m?.issues.overdue ?? 0} 逾期` },
    { label: '本周会议', value: m?.meetings.totalThisWeek ?? 0, dir: (m?.meetings.pendingMinutes ?? 0) > 0 ? 'down' : 'ok', delta: `${m?.meetings.pendingMinutes ?? 0} 待补纪要` },
    { label: '邮件发送', value: m?.emails.weekSent ?? 0, dir: 'ok', delta: `成功率 ${((m?.emails.successRate || 0) * 100).toFixed(0)}%` },
    { label: '处置效率', value: (d.efficiency || 0).toFixed(0) + '%', dir: d.efficiency >= 80 ? 'ok' : 'down', delta: d.efficiency >= 80 ? '达标' : '待提升' },
  ]
})

/* ─── 任务中心 ─── */
const taskTotal = computed(() => data.value.todos.length || 0)
const taskOverdue = computed(() => (data.value.todos || []).filter(t => t.overdue).length)
const taskDonut = computed(() => {
  const m = ms.value
  if (!m) return []
  return [
    { name: '需求跟踪', value: m.requirements.inReview || 0, color: C.primary },
    { name: '工单处理', value: (m.tickets.pending || 0) + (m.tickets.processing || 0), color: C.success },
    { name: '问题待理', value: (m.issues.pending || 0) + (m.issues.processing || 0), color: C.danger },
    { name: '会议行动', value: m.meetings.today || 0, color: C.warn },
  ].filter(d => d.value > 0)
})

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

/* ─── 会议卡片 ─── */
const pendingMeetings = computed(() => data.value.pending_minutes_meetings || [])
const nextSchedule = computed(() => {
  const s = data.value.schedule
  return (s && s.length) ? s[0] : null
})

/* ─── 重要工作 ─── */
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

/* ═══ 主内容区：左右两列 ═══ */
.dv2-main {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  align-items: start;
}
.dv2-col { display: flex; flex-direction: column; gap: 16px; }

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
.ch-action { font-size: 12px; color: #2f6fed; text-decoration: none; white-space: nowrap; }
.ch-action:hover { text-decoration: underline; }

/* 卡片内容区通用 */
.card-body { display: flex; gap: 16px; flex: 1; min-height: 0; }
.cb-row { flex-direction: row; align-items: stretch; }
.cb-split { align-items: stretch; }
.cb-chart { flex-shrink: 0; }
.cb-info, .cb-list { flex: 1; display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.chart-empty { display: flex; align-items: center; justify-content: center; color: #c0c4cc; font-size: 13px; background: #fafbfc; border-radius: 8px; }

/* 任务中心 - 图例 */
.ci-legend { display: flex; align-items: center; gap: 7px; font-size: 13px; }
.ci-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.ci-name { color: #606266; flex: 1; }
.ci-num { font-weight: 700; color: #303133; }
.ci-alert { font-size: 12px; color: #e02424; background: #fef2f2; padding: 6px 10px; border-radius: 6px; margin-top: auto; display: flex; align-items: center; gap: 5px; }
.ca-icon { font-style: normal; }
.ci-ok { font-size: 12px; color: #0f9d6b; margin-top: auto; display: flex; align-items: center; gap: 5px; }
.co-icon { font-style: normal; }

/* 需求 - KPI 行 */
.req-kpi-row, .issue-kpi-row, .meet-kpi-row { display: flex; gap: 8px; margin-bottom: 14px; }
.rk, .ik, .mk, .rs, .is, .ms {
  flex: 1; display: flex; flex-direction: column; align-items: center;
  background: #f7f9fc; border-radius: 8px; padding: 8px 4px;
}
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

/* 运营 - 占比条 */
.issue-bars { display: flex; flex-direction: column; gap: 5px; }
.ib-row { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.ib-name { width: 64px; color: #606266; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ib-track { flex: 1; height: 6px; background: #eef1f6; border-radius: 3px; overflow: hidden; }
.ib-track i { display: block; height: 100%; border-radius: 3px; transition: width .6s ease; }
.ib-num { width: 24px; text-align: right; font-weight: 600; color: #303133; flex-shrink: 0; }

/* 卡片底部 */
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

/* ═══ 底部三卡片（等高） ═══ */
.dv2-bottom {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.card-sm { min-height: 120px; }
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

/* ═══ 响应式 ═══ */
@media (max-width: 1200px) {
  .dv2-main { grid-template-columns: 1fr; }
  .dv2-kpi { grid-template-columns: repeat(3, 1fr); }
  .dv2-bottom { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 768px) {
  .dv2-kpi { grid-template-columns: repeat(2, 1fr); }
  .dv2-bottom { grid-template-columns: 1fr; }
  .dv2-header { flex-direction: column; align-items: flex-start; gap: 10px; }
}
</style>
