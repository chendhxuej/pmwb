<template>
  <div class="dv2" v-loading="loading">
    <!-- ═══ Hero 区：面包屑 + 标题 + 操作 ═══ -->
    <section class="dv2-hero">
      <div class="dv2-h-left">
        <div class="dv2-breadcrumb">
          <span class="dv2-bc-item">个人工作台</span>
          <span class="dv2-bc-sep">›</span>
          <span class="dv2-bc-item dv2-bc-active">数据总览</span>
        </div>
        <h1 class="dv2-title">产品经理个人工作台</h1>
        <p class="dv2-subtitle">一屏览需求交付、工单运营、会议日程、知识资产与任务全貌</p>
      </div>
      <div class="dv2-h-right">
        <el-button text @click="$router.push('/task-center')">
          <el-icon><List /></el-icon> 查看全部任务
        </el-button>
        <el-button type="primary" @click="refreshData">
          <el-icon><Refresh /></el-icon> 刷新数据
        </el-button>
      </div>
    </section>

    <!-- ═══ KPI 指标行（竖线分隔，无卡片边框） ═══ -->
    <section class="dv2-kpi-row">
      <div class="dv2-kpi" v-for="(k, i) in kpiItems" :key="i">
        <div class="dv2-kpi-label" :style="{ color: k.color }">{{ k.label }}</div>
        <div class="dv2-kpi-val">{{ k.value }}</div>
        <div class="dv2-kpi-delta" :class="'dt-' + k.dir">
          <template v-if="k.dir === 'up'">▲</template>
          <template v-else-if="k.dir === 'down'">▼</template>
          <template v-else>—</template>
          {{ k.delta }}
        </div>
        <div class="dv2-kpi-desc">{{ k.desc }}</div>
      </div>
      <div class="dv2-kpi-divider" v-for="(_, i) in kpiItems.length - 1" :key="'d' + i"></div>
    </section>

    <!-- ═══ 主图表区（三栏） ═══ -->
    <section class="dv2-charts">
      <!-- 左栏：趋势柱状图（宽） -->
      <div class="dv2-chart-card dv2-chart-wide">
        <div class="dv2-card-head">
          <div>
            <div class="dv2-card-title">业务量趋势</div>
            <div class="dv2-card-sub">近 7 天 · 需求 / 运营问题 / 开发工单</div>
          </div>
          <div class="dv2-summary-inline">
            <span class="dv2-si-num">{{ trendTotal }}</span>
            <span class="dv2-si-unit">条累计</span>
            <span class="dv2-si-trend dt-up">周环比 {{ trendDelta }}%</span>
          </div>
        </div>
        <div class="dv2-chart-body">
          <ChartLine
            v-if="trendReady"
            :xData="trendX"
            :series="trendSeries"
            height="280px"
          />
          <div v-else class="dv2-empty">暂无趋势数据</div>
        </div>
      </div>

      <!-- 中栏：累计折线 -->
      <div class="dv2-chart-card dv2-chart-mid">
        <div class="dv2-card-head">
          <div>
            <div class="dv2-card-title">需求累计走势</div>
            <div class="dv2-card-sub">本月新增 {{ reqThisMonth }} 条</div>
          </div>
        </div>
        <div class="dv2-chart-body">
          <ChartLine
            v-if="trendReady"
            :xData="trendX"
            :series="cumulativeSeries"
            height="280px"
            :area="true"
            :smooth="true"
          />
          <div v-else class="dv2-empty">暂无数据</div>
        </div>
      </div>

      <!-- 右栏：环形分布图 + 模块概要数字 -->
      <div class="dv2-chart-card dv2-chart-right">
        <div class="dv2-card-head">
          <div>
            <div class="dv2-card-title">模块分布概览</div>
            <div class="dv2-card-sub">各模块核心指标</div>
          </div>
          <router-link to="/dashboard-v2" class="dv2-link">查看详情 →</router-link>
        </div>
        <div class="dv2-donut-wrap">
          <ChartPie
            v-if="distReady"
            :data="moduleDistData"
            height="200px"
            centerText="String(moduleDistTotal)"
            centerSubText="'模块'"
          />
          <div v-else class="dv2-empty">暂无分布数据</div>
        </div>
        <div class="dv2-dist-summaries">
          <div class="dv2-ds-item" v-for="(m, i) in moduleSummaryNumbers" :key="i">
            <div class="dv2-ds-num" :style="{ color: m.color }">{{ m.value }}</div>
            <div class="dv2-ds-label">{{ m.label }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- ═══ 模块详情卡片区（每模块一卡） ═══ -->
    <section class="dv2-modules">
      <!-- 需求与交付 -->
      <div class="dv2-mod-card">
        <div class="dv2-mod-header">
          <div class="dv2-mod-title">
            <span class="dv2-mod-dot" style="background:#2f6fed"></span>
            需求与交付
          </div>
          <router-link to="/requirement-delivery" class="dv2-link">进入管理 →</router-link>
        </div>
        <div class="dv2-mod-stats">
          <div class="dv2-ms-item"><b>{{ ms?.requirements.total ?? 0 }}</b><span>总数</span></div>
          <div class="dv2-ms-item"><b>{{ ms?.requirements.thisWeek ?? 0 }}</b><span>本周新增</span></div>
          <div class="dv2-ms-item"><b>{{ ms?.requirements.inReview ?? 0 }}</b><span>跟踪中</span></div>
          <div class="dv2-ms-item"><b>{{ ms?.requirements.completed ?? 0 }}</b><span>已上线</span></div>
        </div>
        <div class="dv2-mod-chart">
          <ChartPie v-if="distReady" :data="reqDist" height="160px" centerText="'需求'" :centerSubText="String(reqTotal)" />
        </div>
        <div class="dv2-mod-list" v-if="data.recent_requirements.length">
          <div class="dv2-ml-item" v-for="(r, i) in data.recent_requirements.slice(0, 4)" :key="i">
            <span class="dv2-ml-name">{{ r.name }}</span>
            <span class="dv2-ml-meta">{{ r.status }} · {{ r.date }}</span>
          </div>
        </div>
      </div>

      <!-- 开发工单 -->
      <div class="dv2-mod-card">
        <div class="dv2-mod-header">
          <div class="dv2-mod-title">
            <span class="dv2-mod-dot" style="background:#0f9d6b"></span>
            开发工单
          </div>
          <router-link to="/operation/bug" class="dv2-link">进入管理 →</router-link>
        </div>
        <div class="dv2-mod-stats">
          <div class="dv2-ms-item"><b>{{ ms?.tickets.total ?? 0 }}</b><span>总数</span></div>
          <div class="dv2-ms-item"><b>{{ ms?.tickets.pending ?? 0 }}</b><span>待处理</span></div>
          <div class="dv2-ms-item"><b>{{ ms?.tickets.processing ?? 0 }}</b><span>进行中</span></div>
          <div class="dv2-ms-item"><b>{{ ms?.tickets.resolved ?? 0 }}</b><span>已解决</span></div>
        </div>
        <div class="dv2-mod-progress" v-if="ms">
          <div class="dv2-pg-row" v-for="(row, i) in ticketProgressRows" :key="i">
            <span class="dv2-pg-name">{{ row.name }}</span>
            <div class="dv2-pg-bar-wrap">
              <div class="dv2-pg-bar" :style="{ width: row.pct + '%', background: row.color }"></div>
            </div>
            <span class="dv2-pg-val">{{ row.val }}</span>
            <span class="dv2-pg-pct">{{ row.pct }}%</span>
          </div>
        </div>
      </div>

      <!-- 运营问题 -->
      <div class="dv2-mod-card">
        <div class="dv2-mod-header">
          <div class="dv2-mod-title">
            <span class="dv2-mod-dot" style="background:#e02424"></span>
            运营问题
          </div>
          <router-link to="/operation/data" class="dv2-link">进入管理 →</router-link>
        </div>
        <div class="dv2-mod-stats">
          <div class="dv2-ms-item"><b>{{ ms?.issues.total ?? 0 }}</b><span>总数</span></div>
          <div class="dv2-ms-item"><b>{{ ms?.issues.pending ?? 0 }}</b><span>待处理</span></div>
          <div class="dv2-ms-item"><b>{{ ms?.issues.processing ?? 0 }}</b><span>处理中</span></div>
          <div class="dv2-ms-item dv2-ms-warn" v-if="ms && ms.issues.overdue > 0"><b>{{ ms.issues.overdue }}</b><span>超期 ⚠️</span></div>
        </div>
        <div class="dv2-mod-chart">
          <ChartPie v-if="distReady" :data="issueDist" height="160px" centerText="'问题'" :centerSubText="String(issueTotal)" />
        </div>
      </div>

      <!-- 会议日程 -->
      <div class="dv2-mod-card">
        <div class="dv2-mod-header">
          <div class="dv2-mod-title">
            <span class="dv2-mod-dot" style="background:#d98a1f"></span>
            会议日程
          </div>
          <router-link to="/meeting" class="dv2-link">进入管理 →</router-link>
        </div>
        <div class="dv2-mod-stats">
          <div class="dv2-ms-item"><b>{{ ms?.meetings.totalThisWeek ?? 0 }}</b><span>本周会议</span></div>
          <div class="dv2-ms-item"><b>{{ ms?.meetings.today ?? 0 }}</b><span>今日</span></div>
          <div class="dv2-ms-item"><b>{{ ms?.meetings.upcoming ?? 0 }}</b><span>待开</span></div>
        </div>
        <div class="dv2-mod-list" v-if="data.schedule.length">
          <div class="dv2-ml-item" v-for="(s, i) in data.schedule.slice(0, 5)" :key="i">
            <span class="dv2-ml-time">{{ s.time }}</span>
            <span class="dv2-ml-name">{{ s.title }}</span>
            <span class="dv2-ml-meta">{{ s.loc }}</span>
          </div>
        </div>
        <div v-else class="dv2-empty-sm">今日无会议安排</div>
      </div>

      <!-- 知识中心 -->
      <div class="dv2-mod-card">
        <div class="dv2-mod-header">
          <div class="dv2-mod-title">
            <span class="dv2-mod-dot" style="background:#2fc9a0"></span>
            知识中心
          </div>
          <router-link to="/knowledge-center" class="dv2-link">进入管理 →</router-link>
        </div>
        <div class="dv2-mod-stats">
          <div class="dv2-ms-item"><b>{{ ms?.knowledge.total ?? 0 }}</b><span>文档总数</span></div>
          <div class="dv2-ms-item"><b>{{ ms?.knowledge.thisWeek ?? 0 }}</b><span>本周新增</span></div>
        </div>
        <div class="dv2-empty-sm">知识库持续沉淀中…</div>
      </div>

      <!-- 邮件中心 -->
      <div class="dv2-mod-card">
        <div class="dv2-mod-header">
          <div class="dv2-mod-title">
            <span class="dv2-mod-dot" style="background:#946ce6"></span>
            邮件中心
          </div>
          <router-link to="/mail-center/logs" class="dv2-link">进入管理 →</router-link>
        </div>
        <div class="dv2-mod-stats">
          <div class="dv2-ms-item"><b>{{ ms?.emails.todaySent ?? 0 }}</b><span>今日发送</span></div>
          <div class="dv2-ms-item"><b>{{ ms?.emails.weekSent ?? 0 }}</b><span>本周发送</span></div>
          <div class="dv2-ms-item"><b>{{ (ms?.emails.successRate ?? 0).toFixed(1) }}%</b><span>成功率</span></div>
        </div>
        <div class="dv2-empty-sm">邮件收发正常运转</div>
      </div>
    </section>

    <!-- ═══ 底部：待办 + 预警 + 动态 ═══ -->
    <section class="dv2-bottom">
      <!-- 我的待办 -->
      <div class="dv2-bot-card">
        <div class="dv2-bot-head">
          <span class="dv2-bot-title">我的待办</span>
          <router-link to="/task-center" class="dv2-link">全部任务 →</router-link>
        </div>
        <div class="dv2-todo-list" v-if="data.todos.length">
          <div class="dv2-todo-item" v-for="(t, i) in data.todos.slice(0, 6)" :key="i" :class="{ 'is-over': t.overdue }">
            <span class="dv2-tag" :class="'lv-' + t.priority">{{ t.priority }}</span>
            <span class="dv2-todo-text">{{ t.title }}</span>
            <span class="dv2-todo-date">{{ t.deadline }}</span>
          </div>
        </div>
        <div v-else class="dv2-empty-sm">暂无待办事项 ✅</div>
      </div>

      <!-- 重点任务与预警 -->
      <div class="dv2-bot-card">
        <div class="dv2-bot-head">
          <span class="dv2-bot-title">重点任务与风险</span>
          <router-link to="/key-works" class="dv2-link">全部任务 →</router-link>
        </div>
        <div class="dv2-alert-list" v-if="data.alerts.length || progressItems.length">
          <div class="dv2-alert-item" v-for="(a, i) in data.alerts.slice(0, 4)" :key="'a' + i">
            <span class="dv2-badge" :class="'b-' + a.severity">{{ a.severity }}</span>
            <span class="dv2-alert-text">{{ a.msg }}</span>
            <span class="dv2-alert-count">{{ a.count }}</span>
          </div>
          <div class="dv2-alert-item" v-for="(p, i) in progressItems.slice(0, 4)" :key="'p' + i">
            <span class="dv2-badge b-进行中">进行中</span>
            <span class="dv2-alert-text">{{ p.name }}</span>
            <span class="dv2-alert-count">{{ p.percent }}%</span>
          </div>
        </div>
        <div v-else class="dv2-empty-sm">当前无预警项 🟢</div>
      </div>

      <!-- 近期动态 -->
      <div class="dv2-bot-card">
        <div class="dv2-bot-head">
          <span class="dv2-bot-title">近期动态</span>
        </div>
        <div class="dv2-feed-list">
          <div class="dv2-feed-item" v-for="(item, i) in recentFeed" :key="i">
            <span class="dv2-feed-dot" :style="{ background: item.color }"></span>
            <span class="dv2-feed-text">{{ item.text }}</span>
            <span class="dv2-feed-time">{{ item.time }}</span>
          </div>
        </div>
        <div v-if="!recentFeed.length" class="dv2-empty-sm">暂无动态</div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { List, Refresh } from '@element-plus/icons-vue'
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

// ─── 模块统计快捷引用 ───
const ms = computed(() => data.value.module_stats)

// ─── KPI 指标行 ───
const kpiItems = computed(() => {
  const d = data.value
  const m = d.module_stats
  return [
    {
      label: '待办事项', value: d.todos.length || 0,
      dir: 'neutral', delta: '—',
      desc: '个人待办',
      color: '#2f6fed',
    },
    {
      label: '需求总数', value: m?.requirements.total ?? 0,
      dir: m?.requirements.thisWeek > 0 ? 'up' : 'neutral',
      delta: `+${m?.requirements.thisWeek ?? 0}`,
      desc: '本周新增',
      color: '#2f6fed',
    },
    {
      label: '开发工单', value: m?.tickets.total ?? 0,
      dir: m?.tickets.pending > 0 ? 'down' : 'neutral',
      delta: `${m?.tickets.pending ?? 0} 待处理`,
      desc: '待处理 / 进行中',
      color: '#0f9d6b',
    },
    {
      label: '运营问题', value: m?.issues.total ?? 0,
      dir: m?.issues.overdue > 0 ? 'down' : 'neutral',
      delta: `${m?.issues.overdue ?? 0} 超期`,
      desc: '处置效率 ' + (d.efficiency || 0).toFixed(1) + '%',
      color: '#e02424',
    },
    {
      label: '本周会议', value: m?.meetings.totalThisWeek ?? 0,
      dir: 'neutral', delta: `今日 ${m?.meetings.today ?? 0}`,
      desc: `${m?.meetings.upcoming ?? 0} 场待开`,
      color: '#d98a1f',
    },
    {
      label: '知识文档', value: m?.knowledge.total ?? 0,
      dir: m?.knowledge.thisWeek > 0 ? 'up' : 'neutral',
      delta: `+${m?.knowledge.thisWeek ?? 0}`,
      desc: '本周新增',
      color: '#2fc9a0',
    },
    {
      label: '邮件发送', value: m?.emails.weekSent ?? 0,
      dir: 'neutral', delta: `${(m?.emails.successRate || 0).toFixed(1)}% 成功率`,
      desc: `今日 ${m?.emails.todaySent ?? 0} 封`,
      color: '#946ce6',
    },
    {
      label: '处置效率', value: (d.efficiency || 0).toFixed(1) + '%',
      dir: d.efficiency >= 80 ? 'up' : 'down',
      delta: d.efficiency >= 80 ? '达标' : '需提升',
      desc: '目标 ≥80%',
      color: d.efficiency >= 80 ? '#0f9d6b' : '#e02424',
    },
  ]
})

// ─── 趋势图 ───
const trendReady = computed(() => !!data.value.trend_charts)
const trendX = computed(() => (data.value.trend_charts?.requirementsTrend || []).map((t) => t.label))
const trendSeries = computed(() => {
  const tc = data.value.trend_charts
  if (!tc) return []
  return [
    { name: '需求', data: (tc.requirementsTrend || []).map((t) => t.value) },
    { name: '运营问题', data: (tc.issuesTrend || []).map((t) => t.value) },
    { name: '工单', data: (tc.ticketsTrend || []).map((t) => t.value) },
  ]
})
const cumulativeSeries = computed(() => {
  const reqData = (data.value.trend_charts?.requirementsTrend || []).map((t) => t.value)
  let sum = 0
  const cumul = reqData.map(v => { sum += v; return sum })
  return [{ name: '需求累计', data: cumul }]
})
const trendTotal = computed(() => {
  const tc = data.value.trend_charts
  if (!tc) return 0
  const req = (tc.requirementsTrend || []).reduce((s, t) => s + t.value, 0)
  const iss = (tc.issuesTrend || []).reduce((s, t) => s + t.value, 0)
  const tic = (tc.ticketsTrend || []).reduce((s, t) => s + t.value, 0)
  return req + iss + tic
})
const trendDelta = computed(() => 12.4)
const reqThisMonth = computed(() =>
  (data.value.trend_charts?.requirementsTrend || []).reduce((s, t) => s + t.value, 0)
)

// ─── 分布饼图 ───
const distReady = computed(() => !!data.value.distribution_charts)
const reqDist = computed(() => data.value.distribution_charts?.requirementStatusDist || [])
const issueDist = computed(() => data.value.distribution_charts?.issueTypeDist || [])
const ticketDist = computed(() => data.value.distribution_charts?.ticketPriorityDist || [])
const reqTotal = computed(() => reqDist.value.reduce((s, d) => s + d.value, 0))
const issueTotal = computed(() => issueDist.value.reduce((s, d) => s + d.value, 0))
const ticketTotal = computed(() => ticketDist.value.reduce((s, d) => s + d.value, 0))

// 环形图：模块分布汇总
const moduleDistData = computed(() => [
  { name: '需求', value: ms.value?.requirements.total || 0 },
  { name: '工单', value: ms.value?.tickets.total || 0 },
  { name: '问题', value: ms.value?.issues.total || 0 },
  { name: '会议', value: ms.value?.meetings.totalThisWeek || 0 },
  { name: '知识', value: ms.value?.knowledge.total || 0 },
])
const moduleDistTotal = computed(() =>
  moduleDistData.value.reduce((s, d) => s + d.value, 0)
)
const moduleSummaryNumbers = computed(() => [
  { value: ms.value?.requirements.total || 0, label: '需求', color: '#2f6fed' },
  { value: ms.value?.tickets.total || 0, label: '工单', color: '#0f9d6b' },
  { value: ms.value?.issues.total || 0, label: '问题', color: '#e02424' },
])

// ─── 工单进度条 ───
const ticketProgressRows = computed(() => {
  const t = ms.value?.tickets
  if (!t) return []
  const total = Math.max(t.total, 1)
  return [
    { name: '已解决', val: t.resolved, pct: Math.round(t.resolved / total * 100), color: '#0f9d6b' },
    { name: '进行中', val: t.processing, pct: Math.round(t.processing / total * 100), color: '#2f6fed' },
    { name: '待处理', val: t.pending, pct: Math.round(t.pending / total * 100), color: '#d98a1f' },
  ]
})

// ─── 重点项目进度 ───
const progressItems = computed(() => {
  const pi = data.value.progress_items
  if (!pi?.keyProjects) return []
  return pi.keyProjects.map(p => ({
    name: p.name,
    percent: Math.round(p.percent),
    total: p.total,
  }))
})

// ─── 近期动态聚合 ───
const recentFeed = computed(() => {
  const items = []
  ;(data.value.recent_requirements || []).slice(0, 2).forEach(r => {
    items.push({ text: `需求「${r.name}」${r.status}`, time: r.date, color: '#2f6fed' })
  })
  ;(data.value.schedule || []).slice(0, 2).forEach(s => {
    items.push({ text: `会议：${s.title}`, time: s.time, color: '#d98a1f' })
  })
  ;(data.value.alerts || []).slice(0, 2).forEach(a => {
    items.push({ text: `[${a.severity}] ${a.msg}`, time: a.count, color: '#e02424' })
  })
  return items
})
</script>

<style scoped>
/* ═══ 全局容器 ═══ */
.dv2 {
  min-height: 100%;
  padding: 20px 24px;
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* ═══ Hero 区 ═══ */
.dv2-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  background: linear-gradient(135deg, #e8f0fe 0%, #d4e4fc 50%, #c5d8fa 100%);
  border-radius: 12px;
  padding: 22px 28px;
  gap: 16px;
  flex-wrap: wrap;
}
.dv2-h-left { flex: 1; min-width: 300px; }
.dv2-breadcrumb { display: flex; align-items: center; gap: 6px; font-size: 12px; margin-bottom: 10px; }
.dv2-bc-item { color: #606266; }
.dv2-bc-active { color: #2f6fed; font-weight: 600; }
.dv2-bc-sep { color: #c0c4cc; }
.dv2-title { margin: 0 0 6px; font-size: 22px; font-weight: 700; color: #1a1a2e; }
.dv2-subtitle { margin: 0; font-size: 13px; color: #606266; }
.dv2-h-right { display: flex; align-items: center; gap: 10px; padding-top: 8px; }

/* ═══ KPI 行（参考截图：横向排列、竖线分隔） ═══ */
.dv2-kpi-row {
  display: flex;
  align-items: stretch;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 6px rgba(0,0,0,.06);
  overflow: hidden;
}
.dv2-kpi {
  flex: 1;
  padding: 18px 20px;
  text-align: center;
  position: relative;
  min-width: 0;
}
.dv2-kpi-divider {
  width: 1px;
  background: #ebeef5;
  flex-shrink: 0;
}
.dv2-kpi-label {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 6px;
  letter-spacing: .3px;
}
.dv2-kpi-val {
  font-size: 30px;
  font-weight: 800;
  color: #1a1a2e;
  line-height: 1.15;
}
.dv2-kpi-delta {
  font-size: 12px;
  margin-top: 4px;
  color: #909399;
}
.dt-up { color: #0f9d6b; }
.dt-down { color: #e02424; }
.dt-neutral { color: #c0c4cc; }
.dv2-kpi-desc {
  font-size: 11px;
  color: #b0b3b8;
  margin-top: 3px;
}

/* ═══ 主图表区（三栏） ═══ */
.dv2-charts {
  display: grid;
  grid-template-columns: 1.6fr 1fr 1fr;
  gap: 16px;
}
.dv2-chart-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 6px rgba(0,0,0,.06);
  padding: 20px;
  display: flex;
  flex-direction: column;
}
.dv2-card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 14px;
}
.dv2-card-title { font-size: 15px; font-weight: 700; color: #1a1a2e; }
.dv2-card-sub { font-size: 12px; color: #909399; margin-top: 3px; }
.dv2-link {
  font-size: 12px;
  color: #2f6fed;
  text-decoration: none;
  white-space: nowrap;
}
.dv2-link:hover { text-decoration: underline; }

/* 内联摘要数字（参考截图左上角大数字+趋势） */
.dv2-summary-inline {
  text-align: right;
  white-space: nowrap;
}
.dv2-si-num { font-size: 24px; font-weight: 800; color: #1a1a2e; }
.dv2-si-unit { font-size: 12px; color: #909399; margin-left: 2px; }
.dv2-si-trend { font-size: 12px; margin-left: 6px; }

.dv2-chart-body { flex: 1; min-height: 0; }
.dv2-donut-wrap { display: flex; justify-content: center; }
.dv2-dist-summaries {
  display: flex;
  justify-content: space-around;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid #f0f2f5;
}
.dv2-ds-item { text-align: center; }
.dv2-ds-num { font-size: 20px; font-weight: 700; }
.dv2-ds-label { font-size: 11px; color: #909399; margin-top: 2px; }

.dv2-empty { 
  display: flex; align-items: center; justify-content: center;
  height: 200px; color: #c0c4cc; font-size: 13px; 
}
.dv2-empty-sm {
  padding: 20px; text-align: center; color: #c0c4cc; font-size: 13px;
}

/* ═══ 模块详情卡片区 ═══ */
.dv2-modules {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.dv2-mod-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 6px rgba(0,0,0,.06);
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
}
.dv2-mod-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.dv2-mod-title {
  font-size: 15px;
  font-weight: 700;
  color: #1a1a2e;
  display: flex;
  align-items: center;
  gap: 7px;
}
.dv2-mod-dot {
  width: 8px; height: 8px;
  border-radius: 50%; display: inline-block;
}

/* 模块内 mini 统计数字 */
.dv2-mod-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.dv2-ms-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.dv2-ms-item b {
  font-size: 20px;
  font-weight: 700;
  color: #1a1a2e;
}
.dv2-ms-item span {
  font-size: 11px;
  color: #909399;
}
.dv2-ms-warn b { color: #e02424; }

/* 进度条（工单模块） */
.dv2-mod-progress { display: flex; flex-direction: column; gap: 10px; }
.dv2-pg-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
.dv2-pg-name { width: 52px; color: #606266; flex-shrink: 0; }
.dv2-pg-bar-wrap {
  flex: 1;
  height: 8px;
  background: #f0f2f5;
  border-radius: 4px;
  overflow: hidden;
}
.dv2-pg-bar {
  height: 100%;
  border-radius: 4px;
  transition: width .4s ease;
}
.dv2-pg-val { width: 36px; text-align: right; color: #303133; font-weight: 600; flex-shrink: 0; }
.dv2-pg-pct { width: 32px; color: #909399; flex-shrink: 0; }

/* 模块内列表 */
.dv2-mod-list { display: flex; flex-direction: column; gap: 0; }
.dv2-ml-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 0;
  border-bottom: 1px dashed #f0f2f5;
  font-size: 12px;
}
.dv2-ml-item:last-child { border-bottom: none; }
.dv2-ml-time { color: #2f6fed; font-weight: 600; flex-shrink: 0; }
.dv2-ml-name { flex: 1; color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dv2-ml-meta { color: #b0b3b8; flex-shrink: 0; }

.dv2-mod-chart { display: flex; justify-content: center; }

/* ═══ 底部三栏 ═══ */
.dv2-bottom {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
}
.dv2-bot-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 6px rgba(0,0,0,.06);
  padding: 18px 20px;
}
.dv2-bot-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.dv2-bot-title { font-size: 15px; font-weight: 700; color: #1a1a2e; }

/* 待办列表 */
.dv2-todo-list { display: flex; flex-direction: column; gap: 0; }
.dv2-todo-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px dashed #f0f2f5;
  font-size: 13px;
}
.dv2-todo-item:last-child { border-bottom: none; }
.is-over .dv2-todo-text { color: #e02424; }
.dv2-tag {
  font-size: 11px; padding: 1px 7px; border-radius: 4px;
  background: #eef2fb; color: #2f6fed; flex-shrink: 0;
}
.lv-紧急 { background: #fde2e2; color: #e02424; }
.lv-高优 { background: #fdf0e0; color: #d98a1f; }
.lv-中等 { background: #eef2fb; color: #2f6fed; }
.lv-低优 { background: #e8f7f0; color: #0f9d6b; }
.dv2-todo-text { flex: 1; color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dv2-todo-date { color: #b0b3b8; font-size: 12px; flex-shrink: 0; }

/* 预警列表 */
.dv2-alert-list { display: flex; flex-direction: column; gap: 0; }
.dv2-alert-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 0; border-bottom: 1px dashed #f0f2f5; font-size: 13px;
}
.dv2-alert-item:last-child { border-bottom: none; }
.dv2-badge {
  font-size: 11px; padding: 1px 7px; border-radius: 4px; flex-shrink: 0;
}
.b-严重 { background: #fde2e2; color: #e02424; }
.b-警告 { background: #fdf0e0; color: #d98a1f; }
.b-提醒 { background: #eef2fb; color: #2f6fed; }
.b-正常 { background: #e8f7f0; color: #0f9d6b; }
.b-进行中 { background: #eef2fb; color: #2f6fed; }
.dv2-alert-text { flex: 1; color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dv2-alert-count { color: #b0b3b8; font-size: 12px; flex-shrink: 0; }

/* 动态流 */
.dv2-feed-list { display: flex; flex-direction: column; gap: 0; }
.dv2-feed-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 0; border-bottom: 1px dashed #f0f2f5; font-size: 13px;
}
.dv2-feed-item:last-child { border-bottom: none; }
.dv2-feed-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.dv2-feed-text { flex: 1; color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dv2-feed-time { color: #b0b3b8; font-size: 12px; flex-shrink: 0; }

/* ═══ 响应式 ═══ */
@media (max-width: 1300px) {
  .dv2-charts { grid-template-columns: 1fr 1fr; }
  .dv2-chart-wide { grid-column: span 2; }
  .dv2-modules { grid-template-columns: 1fr 1fr; }
  .dv2-bottom { grid-template-columns: 1fr 1fr; }
  .dv2-bot-card:last-child { grid-column: span 2; }
}
@media (max-width: 900px) {
  .dv2-kpi-row { flex-wrap: wrap; }
  .dv2-kpi { min-width: 33%; }
  .dv2-kpi-divider { display: none; }
  .dv2-charts { grid-template-columns: 1fr; }
  .dv2-chart-wide { grid-column: span 1; }
  .dv2-modules { grid-template-columns: 1fr; }
  .dv2-bottom { grid-template-columns: 1fr; }
  .dv2-bot-card:last-child { grid-column: span 1; }
}
</style>
