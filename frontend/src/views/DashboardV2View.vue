<template>
  <div class="dv2" v-loading="loading">
    <!-- ═══ Hero 区：整体总结汇总 ═══ -->
    <section class="dv2-hero">
      <div class="dv2-h-left">
        <div class="dv2-breadcrumb">
          <span class="dv2-bc-item">个人工作台</span>
          <span class="dv2-bc-sep">›</span>
          <span class="dv2-bc-item dv2-bc-active">数据总览</span>
        </div>
        <h1 class="dv2-title">下午好，{{ data.user_name || '陈工' }}</h1>
        <p class="dv2-subtitle">{{ overallSummary }}</p>
      </div>
      <div class="dv2-h-right">
        <div class="dv2-health">
          <svg viewBox="0 0 80 80" class="dv2-ring">
            <circle cx="40" cy="40" r="32" fill="none" stroke="#e6edf7" stroke-width="8" />
            <circle cx="40" cy="40" r="32" fill="none" stroke="#2f6fed" stroke-width="8"
              :stroke-dasharray="healthDash" stroke-dashoffset="0" stroke-linecap="round"
              transform="rotate(-90 40 40)" />
            <text x="40" y="38" text-anchor="middle" class="dv2-ring-num">{{ healthScore }}</text>
            <text x="40" y="54" text-anchor="middle" class="dv2-ring-sub">健康度</text>
          </svg>
        </div>
        <el-button type="primary" @click="refreshData">
          <el-icon><Refresh /></el-icon> 刷新数据
        </el-button>
      </div>
    </section>

    <!-- ═══ KPI 概览条（A 风格：横向、竖线分隔） ═══ -->
    <section class="dv2-kpi-row">
      <div class="dv2-kpi" v-for="(k, i) in kpiItems" :key="i">
        <div class="dv2-kpi-label" :style="{ color: k.color }">{{ k.label }}</div>
        <div class="dv2-kpi-val">{{ k.value }}</div>
        <div class="dv2-kpi-delta" :class="'dt-' + k.dir">{{ k.delta }}</div>
        <div class="dv2-kpi-desc">{{ k.desc }}</div>
      </div>
    </section>

    <!-- ═══ 模块磁贴网格（C 风格：非对称 Bento，任务中心最大块） ═══ -->
    <section class="dv2-bento">
      <!-- 任务中心（大块） -->
      <div class="tile tile-task">
        <div class="tile-head">
          <div class="tile-title"><span class="tile-dot" style="background:#2f6fed"></span>任务中心</div>
          <span class="tile-pill" :class="taskOverdue > 0 ? 'pill-warn' : 'pill-ok'">
            {{ taskOverdue > 0 ? '需关注' : '正常' }}
          </span>
        </div>
        <div class="task-body">
          <div class="task-donut">
            <ChartPie v-if="taskDonut.length" :data="taskDonut" height="180px"
              :center-text="String(taskTotal)" center-sub-text="待办" />
          </div>
          <div class="task-side">
            <div class="task-big">{{ taskTotal }}<span>项待办</span></div>
            <div class="task-legend">
              <div class="tl-row" v-for="(d, i) in taskDonut" :key="i">
                <span class="tl-dot" :style="{ background: d.color }"></span>
                <span class="tl-name">{{ d.name }}</span>
                <span class="tl-val">{{ d.value }}</span>
              </div>
            </div>
          </div>
        </div>
        <div class="tile-foot">
          <div class="tile-focus" v-if="taskOverdue > 0">
            <span class="focus-dot focus-red"></span>重点关注：{{ taskOverdue }} 项超期待办
          </div>
          <div class="tile-focus" v-else>
            <span class="focus-dot focus-green"></span>运行平稳，无超期事项
          </div>
          <router-link to="/task-center" class="tile-enter">进入模块 →</router-link>
        </div>
      </div>

      <!-- 需求与交付（宽块，含趋势图） -->
      <div class="tile tile-req">
        <div class="tile-head">
          <div class="tile-title"><span class="tile-dot" style="background:#2f6fed"></span>需求与交付</div>
          <router-link to="/requirement-delivery" class="tile-enter">进入管理 →</router-link>
        </div>
        <div class="req-chart">
          <ChartLine v-if="reqTrend.length" :xData="reqTrend.map(t => t.label)" :series="reqSeries"
            height="150px" :area="true" :smooth="true" />
        </div>
        <div class="req-foot">
          <div class="rf-item"><b>{{ ms?.requirements.total ?? 0 }}</b><span>总数</span></div>
          <div class="rf-item"><b>{{ ms?.requirements.thisWeek ?? 0 }}</b><span>本周新增</span></div>
          <div class="rf-item"><b>{{ ms?.requirements.inReview ?? 0 }}</b><span>跟踪中</span></div>
          <div class="rf-recent" v-if="data.recent_requirements.length">
            <div class="rf-line" v-for="(r, i) in data.recent_requirements.slice(0, 2)" :key="i">
              · {{ r.name }} · <em>{{ r.status }}</em>
            </div>
          </div>
        </div>
      </div>

      <!-- 开发工单 -->
      <div class="tile tile-ticket">
        <div class="tile-head">
          <div class="tile-title"><span class="tile-dot" style="background:#0f9d6b"></span>开发工单</div>
          <router-link to="/operation/bug" class="tile-enter">进入 →</router-link>
        </div>
        <div class="mini-big">{{ ms?.tickets.total ?? 0 }}<span>单</span></div>
        <svg viewBox="0 0 120 40" class="spark" preserveAspectRatio="none">
          <polyline :points="ticketSparkPoints" fill="none" stroke="#0f9d6b" stroke-width="2" />
        </svg>
        <div class="tile-foot">
          <div class="tile-focus" v-if="(ms?.tickets.pending ?? 0) > 0">
            <span class="focus-dot focus-amber"></span>待评审 {{ ms.tickets.pending }} 单
          </div>
          <div class="tile-focus" v-else><span class="focus-dot focus-green"></span>无积压</div>
        </div>
      </div>

      <!-- 运营问题 -->
      <div class="tile tile-issue">
        <div class="tile-head">
          <div class="tile-title"><span class="tile-dot" style="background:#e02424"></span>运营问题</div>
          <router-link to="/operation/data" class="tile-enter">进入 →</router-link>
        </div>
        <div class="mini-big">{{ ms?.issues.total ?? 0 }}<span>项</span></div>
        <div class="tile-foot">
          <div class="tile-focus" v-if="(ms?.issues.overdue ?? 0) > 0">
            <span class="focus-dot focus-red"></span>逾期 {{ ms.issues.overdue }} 项需关注
          </div>
          <div class="tile-focus" v-else><span class="focus-dot focus-green"></span>处置率良好</div>
          <div class="mini-sub">处置效率 {{ (data.efficiency || 0).toFixed(1) }}%</div>
        </div>
      </div>

      <!-- 会议日程 -->
      <div class="tile tile-meet">
        <div class="tile-head">
          <div class="tile-title"><span class="tile-dot" style="background:#d98a1f"></span>会议日程</div>
          <router-link to="/meeting" class="tile-enter">进入 →</router-link>
        </div>
        <div class="mini-big">{{ ms?.meetings.totalThisWeek ?? 0 }}<span>场/周</span></div>
        <div class="tile-foot">
          <div class="mini-sub">今日 {{ ms?.meetings.today ?? 0 }} · 待开 {{ ms?.meetings.upcoming ?? 0 }}</div>
          <div class="mini-line" v-if="data.schedule.length">下次：{{ data.schedule[0].time }} {{ data.schedule[0].title }}</div>
        </div>
      </div>

      <!-- 知识中心 -->
      <div class="tile tile-know">
        <div class="tile-head">
          <div class="tile-title"><span class="tile-dot" style="background:#2fc9a0"></span>知识中心</div>
          <router-link to="/knowledge-center" class="tile-enter">进入 →</router-link>
        </div>
        <div class="mini-big">{{ ms?.knowledge.total ?? 0 }}<span>篇</span></div>
        <div class="tile-foot">
          <div class="mini-sub">本月新增 {{ ms?.knowledge.thisWeek ?? 0 }} 篇</div>
          <div class="mini-line">持续沉淀中</div>
        </div>
      </div>

      <!-- 邮件中心 -->
      <div class="tile tile-mail">
        <div class="tile-head">
          <div class="tile-title"><span class="tile-dot" style="background:#946ce6"></span>邮件中心</div>
          <router-link to="/mail-center/logs" class="tile-enter">进入 →</router-link>
        </div>
        <div class="mini-big">{{ ms?.emails.weekSent ?? 0 }}<span>封/周</span></div>
        <div class="tile-foot">
          <div class="mini-sub">今日 {{ ms?.emails.todaySent ?? 0 }} 封</div>
          <div class="mini-line">成功率 {{ (ms?.emails.successRate || 0).toFixed(1) }}%</div>
        </div>
      </div>

      <!-- 全局健康 -->
      <div class="tile tile-health">
        <div class="tile-head">
          <div class="tile-title"><span class="tile-dot" style="background:#2f6fed"></span>全局健康</div>
        </div>
        <div class="health-mini">
          <svg viewBox="0 0 80 80" class="dv2-ring">
            <circle cx="40" cy="40" r="32" fill="none" stroke="#e6edf7" stroke-width="8" />
            <circle cx="40" cy="40" r="32" fill="none" stroke="#2f6fed" stroke-width="8"
              :stroke-dasharray="healthDash" transform="rotate(-90 40 40)" stroke-linecap="round" />
            <text x="40" y="46" text-anchor="middle" class="dv2-ring-num">{{ healthScore }}</text>
          </svg>
        </div>
        <div class="tile-foot">
          <div class="mini-sub">处置效率 {{ (data.efficiency || 0).toFixed(1) }}%</div>
          <div class="mini-line">各模块运行平稳</div>
        </div>
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

const loading = ref(false)
const data = ref({
  user_name: '陈工',
  greeting_sub: '',
  efficiency: 0,
  greet_stats: [],
  kpis: [],
  todos: [],
  schedule: [],
  recent_requirements: [],
  alerts: [],
  module_stats: null,
  trend_charts: null,
  distribution_charts: null,
  progress_items: null,
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

// ─── 整体总结汇总 ───
const overallSummary = computed(() => {
  const m = ms.value
  if (!m) return '数据加载中…'
  const overdue = m.issues.overdue || 0
  const pending = m.tickets.pending || 0
  const eff = (data.value.efficiency || 0).toFixed(0)
  let s = `6 个模块运行${overdue > 0 || pending > 0 ? '基本' : ''}平稳`
  if (overdue > 0) s += `，${overdue} 项运营问题逾期需关注`
  if (pending > 0) s += `，${pending} 单开发工单待评审`
  s += `；交付一次成功率 ${eff}%，整体健康度 ${healthScore.value} 分。`
  return s
})

// ─── 健康度环 ───
const healthScore = computed(() => Math.round(data.value.efficiency || 0) || 92)
const healthDash = computed(() => {
  const c = 2 * Math.PI * 32
  return `${(healthScore.value / 100) * c} ${c}`
})

// ─── KPI 概览条 ───
const kpiItems = computed(() => {
  const d = data.value
  const m = d.module_stats
  return [
    { label: '待办事项', value: d.todos.length || 0, dir: 'neutral', delta: '个人待办', desc: '汇总跟踪', color: '#2f6fed' },
    { label: '需求总数', value: m?.requirements.total ?? 0, dir: m?.requirements.thisWeek > 0 ? 'up' : 'neutral', delta: `+${m?.requirements.thisWeek ?? 0} 本周`, desc: '需求侧', color: '#2f6fed' },
    { label: '开发工单', value: m?.tickets.total ?? 0, dir: m?.tickets.pending > 0 ? 'down' : 'neutral', delta: `${m?.tickets.pending ?? 0} 待评审`, desc: '工单侧', color: '#0f9d6b' },
    { label: '运营问题', value: m?.issues.total ?? 0, dir: m?.issues.overdue > 0 ? 'down' : 'neutral', delta: `${m?.issues.overdue ?? 0} 逾期`, desc: '问题侧', color: '#e02424' },
    { label: '本周会议', value: m?.meetings.totalThisWeek ?? 0, dir: 'neutral', delta: `今日 ${m?.meetings.today ?? 0}`, desc: '会议侧', color: '#d98a1f' },
    { label: '知识文档', value: m?.knowledge.total ?? 0, dir: m?.knowledge.thisWeek > 0 ? 'up' : 'neutral', delta: `+${m?.knowledge.thisWeek ?? 0} 本月`, desc: '知识侧', color: '#2fc9a0' },
    { label: '邮件发送', value: m?.emails.weekSent ?? 0, dir: 'neutral', delta: `${(m?.emails.successRate || 0).toFixed(0)}% 成功率`, desc: '邮件侧', color: '#946ce6' },
    { label: '处置效率', value: (d.efficiency || 0).toFixed(0) + '%', dir: d.efficiency >= 80 ? 'up' : 'down', delta: d.efficiency >= 80 ? '达标' : '待提升', desc: '目标≥80%', color: d.efficiency >= 80 ? '#0f9d6b' : '#e02424' },
  ]
})

// ─── 任务中心（大块）───
const taskTotal = computed(() => data.value.todos.length || 0)
const taskOverdue = computed(() => (data.value.todos || []).filter(t => t.overdue).length)
const taskDonut = computed(() => {
  const m = ms.value
  if (!m) return []
  return [
    { name: '需求跟踪', value: m.requirements.inReview || 0, color: '#2f6fed' },
    { name: '工单待处理', value: (m.tickets.pending || 0) + (m.tickets.processing || 0), color: '#0f9d6b' },
    { name: '问题待处理', value: (m.issues.pending || 0) + (m.issues.processing || 0), color: '#e02424' },
    { name: '会议待办', value: m.meetings.today || 0, color: '#d98a1f' },
  ]
})

// ─── 需求趋势 ───
const reqTrend = computed(() => data.value.trend_charts?.requirementsTrend || [])
const reqSeries = computed(() => [{ name: '需求', data: reqTrend.value.map(t => t.value) }])

// ─── 工单迷你折线 ───
const ticketSparkPoints = computed(() => {
  const vals = (data.value.trend_charts?.ticketsTrend || []).map(t => t.value)
  if (vals.length < 2) return ''
  const w = 120, h = 40, max = Math.max(...vals, 1), min = Math.min(...vals, 0)
  const range = max - min || 1
  const step = w / (vals.length - 1)
  return vals.map((v, i) => `${(i * step).toFixed(1)},${(h - ((v - min) / range) * (h - 6) - 3).toFixed(1)}`).join(' ')
})
</script>

<style scoped>
.dv2 {
  min-height: 100%;
  padding: 20px 24px;
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Hero */
.dv2-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(135deg, #e8f0fe 0%, #d4e4fc 100%);
  border-radius: 14px;
  padding: 22px 28px;
  gap: 16px;
  flex-wrap: wrap;
}
.dv2-h-left { flex: 1; min-width: 320px; }
.dv2-breadcrumb { display: flex; align-items: center; gap: 6px; font-size: 12px; margin-bottom: 8px; }
.dv2-bc-item { color: #606266; }
.dv2-bc-active { color: #2f6fed; font-weight: 600; }
.dv2-bc-sep { color: #c0c4cc; }
.dv2-title { margin: 0 0 6px; font-size: 22px; font-weight: 700; color: #1a1a2e; }
.dv2-subtitle { margin: 0; font-size: 13px; color: #4a5568; line-height: 1.6; }
.dv2-h-right { display: flex; align-items: center; gap: 16px; }
.dv2-health { width: 72px; height: 72px; }
.dv2-ring { width: 72px; height: 72px; }
.dv2-ring-num { font-size: 20px; font-weight: 700; fill: #1a1a2e; }
.dv2-ring-sub { font-size: 10px; fill: #909399; }

/* KPI 行 */
.dv2-kpi-row {
  display: flex;
  align-items: stretch;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, .06);
  overflow: hidden;
}
.dv2-kpi {
  flex: 1;
  padding: 16px 14px;
  text-align: center;
  position: relative;
  border-right: 1px solid #eef1f6;
  min-width: 0;
}
.dv2-kpi:last-child { border-right: none; }
.dv2-kpi-label { font-size: 12px; font-weight: 600; margin-bottom: 4px; }
.dv2-kpi-val { font-size: 26px; font-weight: 800; color: #1a1a2e; line-height: 1.15; }
.dv2-kpi-delta { font-size: 11px; margin-top: 3px; color: #909399; }
.dt-up { color: #0f9d6b; }
.dt-down { color: #e02424; }
.dt-neutral { color: #c0c4cc; }
.dv2-kpi-desc { font-size: 11px; color: #b0b3b8; margin-top: 2px; }

/* Bento 磁贴网格 */
.dv2-bento {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  grid-auto-rows: minmax(150px, auto);
  gap: 16px;
}
.tile {
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, .06);
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  transition: transform .2s ease, box-shadow .2s ease;
}
.tile:hover { transform: translateY(-3px); box-shadow: 0 6px 18px rgba(47, 111, 237, .12); }
.tile-task { grid-column: 1 / 3; grid-row: 1 / 3; }
.tile-req { grid-column: 3 / 5; grid-row: 1 / 2; }
.tile-ticket { grid-column: 3 / 4; grid-row: 2 / 3; }
.tile-issue { grid-column: 4 / 5; grid-row: 2 / 3; }
.tile-meet { grid-column: 1 / 2; grid-row: 3 / 4; }
.tile-know { grid-column: 2 / 3; grid-row: 3 / 4; }
.tile-mail { grid-column: 3 / 4; grid-row: 3 / 4; }
.tile-health { grid-column: 4 / 5; grid-row: 3 / 4; }

.tile-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.tile-title { font-size: 15px; font-weight: 700; color: #1a1a2e; display: flex; align-items: center; gap: 7px; }
.tile-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.tile-enter { font-size: 12px; color: #2f6fed; text-decoration: none; white-space: nowrap; }
.tile-enter:hover { text-decoration: underline; }
.tile-pill { font-size: 11px; padding: 2px 9px; border-radius: 10px; }
.pill-ok { background: #e8f7f0; color: #0f9d6b; }
.pill-warn { background: #fde2e2; color: #e02424; }

/* 任务中心大块 */
.task-body { display: flex; gap: 16px; align-items: center; flex: 1; }
.task-donut { width: 180px; flex-shrink: 0; }
.task-side { flex: 1; display: flex; flex-direction: column; gap: 12px; }
.task-big { font-size: 34px; font-weight: 800; color: #1a1a2e; }
.task-big span { font-size: 13px; font-weight: 400; color: #909399; margin-left: 4px; }
.task-legend { display: flex; flex-direction: column; gap: 6px; }
.tl-row { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.tl-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.tl-name { color: #606266; flex: 1; }
.tl-val { font-weight: 600; color: #303133; }

.tile-foot { margin-top: 12px; padding-top: 12px; border-top: 1px solid #f0f2f5; display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
.tile-focus { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #606266; }
.focus-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.focus-red { background: #e02424; }
.focus-amber { background: #d98a1f; }
.focus-green { background: #0f9d6b; }

/* 需求宽块 */
.req-chart { flex: 1; min-height: 0; }
.req-foot { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; margin-top: 6px; }
.rf-item { display: flex; flex-direction: column; align-items: center; }
.rf-item b { font-size: 18px; font-weight: 700; color: #1a1a2e; }
.rf-item span { font-size: 11px; color: #909399; }
.rf-recent { flex: 1; min-width: 160px; font-size: 12px; color: #606266; }
.rf-line { padding: 2px 0; }
.rf-line em { color: #2f6fed; font-style: normal; }

/* 小块通用 */
.mini-big { font-size: 30px; font-weight: 800; color: #1a1a2e; line-height: 1.1; }
.mini-big span { font-size: 12px; font-weight: 400; color: #909399; margin-left: 4px; }
.spark { width: 100%; height: 40px; margin: 6px 0; }
.mini-sub { font-size: 12px; color: #909399; }
.mini-line { font-size: 12px; color: #606266; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.health-mini { display: flex; justify-content: center; padding: 6px 0; }
.health-mini .dv2-ring { width: 84px; height: 84px; }

/* 响应式 */
@media (max-width: 1200px) {
  .dv2-bento { grid-template-columns: repeat(2, 1fr); }
  .tile-task { grid-column: 1 / 3; grid-row: auto; }
  .tile-req { grid-column: 1 / 3; grid-row: auto; }
  .tile-ticket { grid-column: 1 / 2; grid-row: auto; }
  .tile-issue { grid-column: 2 / 3; grid-row: auto; }
  .tile-meet { grid-column: 1 / 2; grid-row: auto; }
  .tile-know { grid-column: 2 / 3; grid-row: auto; }
  .tile-mail { grid-column: 1 / 2; grid-row: auto; }
  .tile-health { grid-column: 2 / 3; grid-row: auto; }
}
@media (max-width: 760px) {
  .dv2-kpi-row { flex-wrap: wrap; }
  .dv2-kpi { min-width: 33%; border-right: none; }
  .dv2-bento { grid-template-columns: 1fr; }
  .tile-task, .tile-req, .tile-ticket, .tile-issue, .tile-meet, .tile-know, .tile-mail, .tile-health {
    grid-column: 1 / 2;
  }
}
</style>
