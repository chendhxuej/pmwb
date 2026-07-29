<template>
  <div class="dashboard-v2">
    <div class="dv2-header">
      <h1>看板 v2</h1>
      <router-link to="/" class="dv2-back">← 返回旧版首页</router-link>
    </div>

    <div class="dv2-grid">

      <!-- ══ ROW 1: KPI 大数字卡片（db-3） ══ -->
      <KpiCardRow :columns="kpiCols">
        <KpiCard
          v-for="(k, i) in kpis"
          :key="'kpi' + i"
          :title="k.label"
          :value="k.num"
          :trend="k.trendNum"
          :trend-type="k.deltaType"
          :trend-label="k.delta"
          :color="k.color"
          :icon="k.icon"
        />
      </KpiCardRow>

      <!-- ══ module_stats 卡片（db-3） ══ -->
      <KpiCardRow v-if="msCards.length" title="模块统计" :columns="msCols">
        <KpiCard
          v-for="(m, i) in msCards"
          :key="'ms' + i"
          :title="m.label"
          :value="m.value"
          :unit="m.unit"
          :trend="m.trend"
          :trend-type="m.deltaType"
          :color="m.color"
          :icon="m.icon"
        />
      </KpiCardRow>

      <!-- ══ ROW 2: 趋势组合图（db-4） ══ -->
      <BentoCard title="近7天各模块活跃趋势" :span="8">
        <template #action><a class="card-action">导出</a></template>
        <div class="chart-combo">
          <ChartBar :x-data="trendXLabels" :series="trendBarSeries" height="200px" />
          <ChartLine :x-data="trendXLabels" :series="trendLineSeries" height="160px" />
        </div>
      </BentoCard>

      <!-- ══ ROW 2b: 分布饼图组（db-4） ══ -->
      <BentoCard title="数据概览分布" :span="4">
        <div class="pie-group">
          <div class="pie-item">
            <div class="pie-label">需求状态</div>
            <ChartPie :data="pieReqData" height="130px" />
          </div>
          <div class="pie-item">
            <div class="pie-label">问题类型</div>
            <ChartPie :data="pieIssueData" height="130px" />
          </div>
          <div class="pie-item">
            <div class="pie-label">工单优先级</div>
            <ChartPie :data="pieTicketData" height="130px" />
          </div>
        </div>
      </BentoCard>

      <!-- ══ ROW 3: 进度条区（db-4） ══ -->
      <BentoCard title="重点任务进度" :span="12" v-if="progressItems.length">
        <div class="progress-section">
          <div class="progress-card" v-for="(item, i) in progressItems" :key="i">
            <div class="progress-header">
              <span class="progress-name">{{ item.name }}</span>
              <span class="progress-pct">{{ item.percent }}%</span>
            </div>
            <ChartProgress :value="item.percent" height="24px" />
            <div class="progress-meta">{{ item.current }}/{{ item.total }} 目标</div>
          </div>
        </div>
      </BentoCard>

      <!-- ══ ROW 4: 模块详情区（db-5） ══ -->
      <div class="module-detail-grid">
        <ModuleStatCard title="智能优先级 · 我的待办" icon="&#9776;" color="blue" action="更多">
          <ul class="todo-list">
            <li class="todo-item" v-for="(t, i) in todos" :key="i">
              <span class="todo-priority" :class="t.priorityClass">{{ t.priority }}</span>
              <div class="todo-body">
                <div class="todo-title">{{ t.title }}</div>
                <div class="todo-meta">
                  <span v-if="t.deadline" :class="t.overdue ? 'todo-overdue' : 'todo-deadline'">{{ t.deadline }}</span>
                  <span v-if="t.owner">· 负责人 {{ t.owner }}</span>
                </div>
              </div>
            </li>
          </ul>
        </ModuleStatCard>

        <ModuleStatCard title="运营预警中心" icon="&#9888;" color="red" action="查看全部">
          <ul class="alert-list">
            <li class="alert-item" v-for="(a, i) in alerts" :key="i">
              <span class="alert-sev" :class="a.sevClass">{{ a.sev }}</span>
              <div class="alert-body">
                <div class="alert-msg">{{ a.msg }}</div>
                <div class="alert-count">{{ a.count }}</div>
              </div>
            </li>
          </ul>
        </ModuleStatCard>

        <ModuleStatCard title="最近需求" icon="&#128196;" color="green" action="更多">
          <div class="req-mini">
            <div class="req-mini-item" v-for="(r, i) in recentReqs" :key="i">
              <span class="req-mini-name" :title="r.name">{{ r.name }}</span>
              <span class="status-tag" :class="r.statusClass">{{ r.status }}</span>
            </div>
          </div>
        </ModuleStatCard>

        <ModuleStatCard title="今日日程" icon="&#128197;" color="purple" action="日历">
          <ul class="sched-list">
            <li class="sched-item" v-for="(s, i) in schedule" :key="i">
              <span class="sched-time">{{ s.time }}</span>
              <div class="sched-info">
                <div class="sched-title">{{ s.title }}</div>
                <div class="sched-loc">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>
                  {{ s.loc }}
                </div>
              </div>
            </li>
          </ul>
        </ModuleStatCard>

        <ModuleStatCard title="邮件统计" icon="&#9993;" color="teal" action="详情">
          <div class="mail-stat-body">
            <div class="mail-stat-row">
              <span class="mail-stat-key">今日发送</span>
              <span class="mail-stat-val">{{ mailStats.todaySent }}</span>
            </div>
            <div class="mail-stat-row">
              <span class="mail-stat-key">本周发送</span>
              <span class="mail-stat-val">{{ mailStats.weekSent }}</span>
            </div>
            <div class="mail-stat-row">
              <span class="mail-stat-key">送达成功率</span>
              <span class="mail-stat-val" :class="mailStats.successRateClass">{{ mailStats.successRate }}%</span>
            </div>
          </div>
        </ModuleStatCard>

        <ModuleStatCard title="模块快捷入口" icon="&#9881;" color="amber" scrollable>
          <div class="qa-grid">
            <router-link class="qa-btn" v-for="(q, i) in quickAccess" :key="i" :to="q.path">
              <div class="qa-icon" :style="{ background: q.bg, color: q.color }" v-html="q.icon"></div>
              <span class="qa-label">{{ q.label }}</span>
            </router-link>
          </div>
        </ModuleStatCard>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import BentoCard from '@/components/Common/BentoCard.vue'
import KpiCard from '@/components/Dashboard/KpiCard.vue'
import KpiCardRow from '@/components/Dashboard/KpiCardRow.vue'
import ModuleStatCard from '@/components/Dashboard/ModuleStatCard.vue'
import ChartBar from '@/components/Charts/ChartBar.vue'
import ChartLine from '@/components/Charts/ChartLine.vue'
import ChartPie from '@/components/Charts/ChartPie.vue'
import ChartProgress from '@/components/Charts/ChartProgress.vue'
import { dashboardApi } from '@/api/dashboard'

const dayLabels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

/* ═══ Data ═══ */
const kpis = ref([
  { num: 14, color: 'blue', label: '我的待办', delta: '+3 较昨日', deltaType: 'up', trendNum: 3 },
  { num: 38, color: 'amber', label: '本周新增需求', delta: '评审中 11', deltaType: 'neutral', trendNum: null },
  { num: 9, color: 'blue', label: '进行中工单', delta: '本周完成 23', deltaType: 'up', trendNum: 5 },
  { num: 5, color: 'red', label: '运营预警', delta: '超期 2 条', deltaType: 'down', trendNum: -2 },
])

const moduleStats = ref(null)
const trendCharts = ref(null)
const distributionCharts = ref(null)
const progressItems = ref([])
const mailStats = ref({ todaySent: 0, weekSent: 0, successRate: 0 })

const todos = ref([
  { priority: '紧急', priorityClass: 'tp-urgent', title: '政企宽带续费流程优化需求评审', deadline: '今天 17:00 截止', owner: '李文倩', overdue: false },
  { priority: '高优', priorityClass: 'tp-high', title: '热点投诉跟进：某园区5G信号弱', deadline: '超期 1 天', owner: '王海涛', overdue: true },
  { priority: '中等', priorityClass: 'tp-med', title: '数据异常核查：B域用户画像校准缺失', deadline: '周三前完成', owner: '张明哲', overdue: false },
  { priority: '中等', priorityClass: 'tp-med', title: '周报材料汇总（政企业务线 Q3）', deadline: '周五下班前提交', owner: '', overdue: false },
  { priority: '低优', priorityClass: 'tp-low', title: '知识库补充：极客业务常见 FAQ 整理', deadline: '下周一前', owner: '', overdue: false },
])

const alerts = ref([
  { sev: '严重', sevClass: 'as-red', msg: '超期未处理工单', count: '2 条（BUG类）' },
  { sev: '严重', sevClass: 'as-red', msg: '热点投诉升级中', count: '1 起（南京园区）' },
  { sev: '警告', sevClass: 'as-amber', msg: '数据异常待核查', count: '3 起（B域画像）' },
  { sev: '正常', sevClass: 'as-green', msg: '系统巡检', count: '所有服务运行正常' },
  { sev: '提醒', sevClass: 'as-amber', msg: '本周待办逾期风险', count: '3 项临近截止' },
])

const quickAccess = ref([
  { label: '需求与交付', path: '/requirement-delivery', bg: 'var(--accent-soft)', color: 'var(--accent)',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="12" r="3"/><path d="M9 6h3a3 3 0 013 3v0"/><path d="M9 18h3a3 3 0 003-3"/></svg>' },
  { label: '运营监控', path: '/operation', bg: 'var(--danger-soft)', color: 'var(--danger)',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06A1.65 1.65 0 0015 19.4a1.65 1.65 0 00-1.82-.33h-.06A2 2 0 0011 21h-1a2 2 0 00-2 2 1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.6 15a1.65 1.65 0 00.33-1.82v-.06A2 2 0 003 11v-1a2 2 0 00-2-1.82 1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06A1.65 1.65 0 009 4.6a1.65 1.65 0 001.82.33H11a2 2 0 002-2h1a2 2 0 002 1.82 1.65 1.65 0 001.82.33l.06.06a2 2 0 012.83-2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 00-.33 1.82V11a2 2 0 002 1.82z"/></svg>' },
  { label: '会议日程', path: '/meeting', bg: '#f0e6ff', color: '#7c3aed',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>' },
  { label: '知识库', path: '/knowledge', bg: '#ecfdf5', color: '#059669',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/></svg>' },
])

const recentReqs = ref([
  { name: '政企宽带续费流程优化', owner: '李文倩', status: '评审中', statusClass: 'st-review', date: '07-15' },
  { name: '云MAS短信通道容量扩容', owner: '王海涛', status: '开发中', statusClass: 'st-dev', date: '07-14' },
  { name: '物联网卡实名校验规则增强', owner: '张明哲', status: '待排期', statusClass: 'st-backlog', date: '07-12' },
  { name: '政企业务APP首页改版 v2.3', owner: '陈思远', status: '已上线', statusClass: 'st-live', date: '07-10' },
  { name: '集团客户电子签章对接（OA集成）', owner: '周敏', status: '评审中', statusClass: 'st-review', date: '07-09' },
])

const schedule = ref([
  { time: '09:30', title: '政企业务线 周例会', loc: '会议室 3F-02' },
  { time: '14:00', title: '极客业务需求评审（Q3 迭代）', loc: '线上 · Tencent Meeting' },
  { time: '16:30', title: '运营问题复盘会（超期工单）', loc: '会议室 5F-01' },
  { time: '18:00', title: '1对1 导师辅导', loc: '茶水间' },
])

/* ═══ Computed ═══ */
const kpiCols = computed(() => Math.min(kpis.value.length || 4, 8))

const msCards = computed(() => {
  const ms = moduleStats.value
  if (!ms) return []
  const cards = []
  if (ms.requirements) {
    cards.push({ label: '需求总数', value: ms.requirements.total, unit: '', color: 'blue', icon: '', trend: null, deltaType: 'neutral' })
    cards.push({ label: '本周新增', value: ms.requirements.thisWeek, unit: '', color: 'blue', icon: '', trend: null, deltaType: ms.requirements.thisWeek > 0 ? 'up' : 'neutral' })
  }
  if (ms.tickets) {
    cards.push({ label: '工单总数', value: ms.tickets.total, unit: '', color: 'purple', icon: '', trend: null, deltaType: 'neutral' })
    cards.push({ label: '已解决', value: ms.tickets.resolved, unit: '', color: 'purple', icon: '', trend: null, deltaType: ms.tickets.processing > 0 ? 'up' : 'neutral' })
  }
  if (ms.issues) {
    cards.push({ label: '运营问题', value: ms.issues.total, unit: '', color: 'red', icon: '', trend: null, deltaType: ms.issues.overdue > 0 ? 'down' : 'neutral' })
  }
  if (ms.meetings) {
    cards.push({ label: '本周会议', value: ms.meetings.totalThisWeek, unit: '场', color: 'teal', icon: '', trend: null, deltaType: 'neutral' })
  }
  if (ms.knowledge) {
    cards.push({ label: '知识条目', value: ms.knowledge.total, unit: '', color: 'green', icon: '', trend: null, deltaType: 'neutral' })
  }
  if (ms.emails) {
    cards.push({ label: '今日发信', value: ms.emails.todaySent, unit: '封', color: 'teal', icon: '', trend: null, deltaType: 'neutral' })
  }
  return cards
})

const msCols = computed(() => Math.min(msCards.value.length || 4, 8))

/* 趋势组合图 */
const trendXLabels = computed(() => {
  const tc = trendCharts.value
  if (tc && tc.requirementsTrend && tc.requirementsTrend.length) {
    return tc.requirementsTrend.map((p) => p.label) || dayLabels
  }
  return dayLabels
})

const trendBarSeries = computed(() => {
  const tc = trendCharts.value
  if (!tc) {
    return [
      { name: '需求新增量', data: [18, 24, 21, 33, 29, 38, 42], color: '#2f6fed' },
      { name: '工单完成量', data: [10, 14, 12, 18, 20, 22, 25], color: '#0f9d6b' },
    ]
  }
  const series = []
  if (tc.requirementsTrend) series.push({ name: '需求新增量', data: tc.requirementsTrend.map((p) => p.value), color: '#2f6fed' })
  if (tc.ticketsTrend) series.push({ name: '工单完成量', data: tc.ticketsTrend.map((p) => p.value), color: '#0f9d6b' })
  return series
})

const trendLineSeries = computed(() => {
  const tc = trendCharts.value
  if (!tc) return [{ name: '运营问题', data: [3, 5, 4, 8, 6, 9, 7], color: '#d98a1f' }]
  const series = []
  if (tc.issuesTrend) series.push({ name: '运营问题', data: tc.issuesTrend.map((p) => p.value), color: '#d98a1f' })
  return series
})

/* 分布饼图 */
function _buildPieData(arr) {
  if (!arr || !arr.length) return []
  return arr.map((item) => ({ name: item.name, value: item.value }))
}

const pieReqData = computed(() => {
  const dc = distributionCharts.value
  if (dc && dc.requirementStatusDist && dc.requirementStatusDist.length) return _buildPieData(dc.requirementStatusDist)
  return [{ name: '待排期', value: 5 }, { name: '评审中', value: 8 }, { name: '开发中', value: 12 }, { name: '已上线', value: 18 }, { name: '已暂停', value: 3 }]
})

const pieIssueData = computed(() => {
  const dc = distributionCharts.value
  if (dc && dc.issueTypeDist && dc.issueTypeDist.length) return _buildPieData(dc.issueTypeDist)
  return [{ name: '数据异常', value: 8 }, { name: '系统错误', value: 5 }, { name: '流程阻塞', value: 3 }, { name: '需求变更', value: 6 }, { name: '其他', value: 2 }]
})

const pieTicketData = computed(() => {
  const dc = distributionCharts.value
  if (dc && dc.ticketPriorityDist && dc.ticketPriorityDist.length) return _buildPieData(dc.ticketPriorityDist)
  return [{ name: '紧急', value: 3 }, { name: '高优', value: 8 }, { name: '中等', value: 15 }, { name: '低优', value: 6 }]
})

/* ═══ API ═══ */
function mergeDashboard(res) {
  if (!res || typeof res !== 'object') return

  if (Array.isArray(res.kpis) && res.kpis.length) {
    kpis.value = res.kpis.map((k) => ({
      num: k.value ?? k.num ?? 0,
      color: k.color || 'blue',
      label: k.label || '',
      delta: k.delta || '',
      deltaType: k.delta_type || k.trend || 'neutral',
      trendNum: k.trend_num ?? null,
      icon: k.icon || '',
    }))
  }

  if (res.module_stats && typeof res.module_stats === 'object') moduleStats.value = res.module_stats
  if (res.trend_charts && typeof res.trend_charts === 'object') trendCharts.value = res.trend_charts
  if (res.distribution_charts && typeof res.distribution_charts === 'object') distributionCharts.value = res.distribution_charts

  if (res.progress_items && typeof res.progress_items === 'object' && res.progress_items.keyProjects) {
    progressItems.value = res.progress_items.keyProjects
  }

  if (res.module_stats && res.module_stats.emails) {
    const e = res.module_stats.emails
    const sr = e.successRate ?? 0
    mailStats.value = { todaySent: e.todaySent ?? 0, weekSent: e.weekSent ?? 0, successRate: sr, successRateClass: sr >= 95 ? 'mail-stat-up' : sr >= 80 ? 'mail-stat-warn' : 'mail-stat-down' }
  }

  if (Array.isArray(res.todos) && res.todos.length) {
    const pMap = { '紧急': 'tp-urgent', '高优': 'tp-high', '中等': 'tp-med', '低优': 'tp-low' }
    todos.value = res.todos.map((t) => {
      const p = t.priority || '中等'
      return { priority: p, priorityClass: pMap[p] || 'tp-med', title: t.title || '未命名待办', deadline: t.deadline || '', owner: t.owner || '', overdue: !!t.overdue }
    })
  }

  if (Array.isArray(res.alerts) && res.alerts.length) {
    const sMap = { '严重': 'as-red', '警告': 'as-amber', '正常': 'as-green', '提醒': 'as-amber' }
    alerts.value = res.alerts.map((a) => {
      const s = a.severity || a.sev || '提醒'
      return { sev: s, sevClass: sMap[s] || 'as-amber', msg: a.msg || a.message || '', count: a.count || '' }
    })
  }

  if (Array.isArray(res.recent_requirements) && res.recent_requirements.length) {
    const stMap = { '评审中': 'st-review', '开发中': 'st-dev', '待排期': 'st-backlog', '已上线': 'st-live', '已完成': 'st-live' }
    recentReqs.value = res.recent_requirements.map((r) => {
      const st = r.status || ''
      return { name: r.name || r.title || '', owner: r.owner || '', status: st, statusClass: stMap[st] || 'st-backlog', date: r.date || r.updated_at || '' }
    })
  }

  if (Array.isArray(res.schedule) && res.schedule.length) {
    schedule.value = res.schedule.map((s) => ({ time: s.time || '', title: s.title || '', loc: s.loc || s.location || '' }))
  }
}

async function loadData() {
  try {
    const res = await dashboardApi.getDashboard()
    mergeDashboard(res)
  } catch (err) {
    console.warn('[DashboardV2] 看板接口不可用，已回退至本地 demo 数据', err)
  }
}

onMounted(() => { loadData() })
</script>

<style scoped>
.dashboard-v2 {
  padding: 28px 32px 40px;
  max-width: 1440px;
  width: 100%;
}

.dv2-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.dv2-header h1 {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.dv2-back {
  font-size: 13px;
  color: var(--accent);
  text-decoration: none;
}
.dv2-back:hover { text-decoration: underline; }

.dv2-grid {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* 趋势组合图 */
.chart-combo {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 8px 8px;
}

/* 饼图组 */
.pie-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 12px 12px;
}
.pie-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.pie-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: .03em;
  text-transform: uppercase;
  margin-bottom: 2px;
}

/* 进度条区 */
.progress-section {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
  padding: 12px 22px 18px;
}
.progress-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.progress-header { display: flex; justify-content: space-between; align-items: center; }
.progress-name { font-size: 13px; font-weight: 500; color: var(--text-primary); }
.progress-pct { font-size: 12px; font-weight: 700; font-family: var(--font-mono); color: var(--accent); }
.progress-meta { font-size: 11px; color: var(--text-muted); }

/* 模块详情区 */
.module-detail-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-top: 8px;
}
@media (max-width: 1024px) { .module-detail-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 640px) { .module-detail-grid { grid-template-columns: 1fr; } }

/* ModuleStatCard 内部样式 */
.todo-list { list-style: none; padding: 0 16px 6px; margin: 0; }
.todo-item { display: flex; align-items: flex-start; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--border-subtle); }
.todo-item:last-child { border-bottom: none; }
.todo-priority { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 5px; flex-shrink: 0; line-height: 1.5; white-space: nowrap; margin-top: 1px; }
.tp-urgent { background: var(--danger-soft); color: var(--danger); }
.tp-high { background: var(--warning-soft); color: var(--warning); }
.tp-med { background: var(--accent-soft); color: var(--accent); }
.tp-low { background: var(--border-subtle); color: var(--text-muted); }
.todo-body { flex: 1; min-width: 0; }
.todo-title { font-size: 13px; color: var(--text-primary); line-height: 1.4; word-break: break-word; }
.todo-meta { font-size: 11.5px; color: var(--text-muted); margin-top: 3px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.todo-deadline { color: var(--danger); font-weight: 500; }
.todo-overdue { color: var(--danger); background: var(--danger-soft); padding: 0 6px; border-radius: 4px; }

.alert-list { list-style: none; padding: 0 16px 6px; margin: 0; }
.alert-item { display: flex; align-items: center; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--border-subtle); }
.alert-item:last-child { border-bottom: none; }
.alert-sev { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 5px; flex-shrink: 0; white-space: nowrap; }
.as-red { background: var(--danger-soft); color: var(--danger); }
.as-amber { background: var(--warning-soft); color: var(--warning); }
.as-green { background: var(--success-soft); color: var(--success); }
.alert-body { flex: 1; min-width: 0; }
.alert-msg { font-size: 13px; color: var(--text-primary); }
.alert-count { font-size: 12px; font-family: var(--font-mono); font-weight: 600; margin-top: 2px; color: var(--text-secondary); }

.req-mini { padding: 0 16px 6px; }
.req-mini-item { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 9px 0; border-bottom: 1px solid var(--border-subtle); font-size: 13px; }
.req-mini-item:last-child { border-bottom: none; }
.req-mini-name { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--text-primary); }
.status-tag { display: inline-block; font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 6px; flex-shrink: 0; }
.st-review { background: #fef3c7; color: #92400e; }
.st-dev { background: #dbeafe; color: #1e40af; }
.st-backlog { background: var(--border-subtle); color: var(--text-muted); }
.st-live { background: #d1fae5; color: #065f46; }

.sched-list { list-style: none; padding: 0 16px 6px; margin: 0; }
.sched-item { display: flex; align-items: flex-start; gap: 12px; padding: 9px 0; border-bottom: 1px solid var(--border-subtle); }
.sched-item:last-child { border-bottom: none; }
.sched-time { font-size: 12px; font-weight: 700; font-family: var(--font-mono); color: var(--text-secondary); padding-top: 1px; flex-shrink: 0; width: 44px; }
.sched-info { flex: 1; min-width: 0; }
.sched-title { font-size: 13px; color: var(--text-primary); font-weight: 500; }
.sched-loc { font-size: 11.5px; color: var(--text-muted); margin-top: 2px; display: flex; align-items: center; gap: 4px; }
.sched-loc svg { flex-shrink: 0; width: 13px; height: 13px; }

.mail-stat-body { padding: 4px 16px 10px; display: flex; flex-direction: column; gap: 8px; }
.mail-stat-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--border-subtle); }
.mail-stat-row:last-child { border-bottom: none; }
.mail-stat-key { font-size: 13px; color: var(--text-secondary); }
.mail-stat-val { font-size: 18px; font-weight: 700; font-family: var(--font-mono); color: var(--text-primary); }
.mail-stat-up { color: var(--success); }
.mail-stat-warn { color: var(--warning); }
.mail-stat-down { color: var(--danger); }

.qa-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 4px 16px 10px; }
.qa-btn { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 12px 8px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--surface); cursor: pointer; transition: all var(--transition-fast); text-decoration: none; }
.qa-btn:hover { border-color: var(--accent); background: var(--accent-soft); transform: translateY(-1px); }
.qa-icon { width: 32px; height: 32px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 15px; }
.qa-label { font-size: 11px; color: var(--text-secondary); font-weight: 500; text-align: center; }
</style>
