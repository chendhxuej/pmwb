<template>
  <div class="dash-v2" v-loading="loading">
    <!-- ══ 顶部问候区 ══ -->
    <section class="dv-header">
      <div class="dv-h-left">
        <div class="dv-hello">{{ greeting.sub || '欢迎使用产品经理工作台' }}</div>
        <div class="dv-eff">
          <span class="dv-eff-val">{{ (data.efficiency ?? 0) }}<i>%</i></span>
          <span class="dv-eff-key">运营问题处置效率</span>
        </div>
      </div>
      <div class="dv-h-stats">
        <div class="dv-h-stat" v-for="(s, i) in data.greet_stats" :key="i">
          <span class="dv-h-val">{{ s.value }}</span>
          <span class="dv-h-key">{{ s.key }}</span>
        </div>
      </div>
    </section>

    <!-- ══ KPI 指标条 ══ -->
    <section class="dv-kpi-row">
      <div class="dv-kpi" v-for="(k, i) in data.kpis" :key="i" :class="'c-' + k.color">
        <div class="dv-kpi-val">{{ k.value }}</div>
        <div class="dv-kpi-label">{{ k.label }}</div>
        <div class="dv-kpi-delta" :class="'dt-' + k.delta_type">
          <span v-if="k.delta_type === 'up'">▲</span>
          <span v-else-if="k.delta_type === 'down'">▼</span>
          {{ k.delta }}
        </div>
      </div>
    </section>

    <!-- ══ 图表区 ══ -->
    <section class="dv-grid">
      <el-card class="dv-card span-2" shadow="hover">
        <template #header><span class="dv-card-title">近 7 天趋势（需求 / 运营问题 / 工单）</span></template>
        <ChartLine
          v-if="trendReady"
          :xData="trendX"
          :series="trendSeries"
          height="300px"
        />
        <el-empty v-else description="暂无趋势数据" :image-size="60" />
      </el-card>

      <el-card class="dv-card" shadow="hover">
        <template #header><span class="dv-card-title">重点任务进度</span></template>
        <ChartProgress
          v-if="progressReady"
          :data="progressData"
          height="300px"
        />
        <el-empty v-else description="暂无进行中项目" :image-size="60" />
      </el-card>

      <el-card class="dv-card" shadow="hover">
        <template #header><span class="dv-card-title">需求状态分布</span></template>
        <ChartPie v-if="distReady" :data="reqDist" height="240px" centerText="需求" :centerSubText="String(reqTotal)" />
      </el-card>

      <el-card class="dv-card" shadow="hover">
        <template #header><span class="dv-card-title">运营问题类型</span></template>
        <ChartPie v-if="distReady" :data="issueDist" height="240px" centerText="问题" :centerSubText="String(issueTotal)" />
      </el-card>

      <el-card class="dv-card" shadow="hover">
        <template #header><span class="dv-card-title">工单优先级</span></template>
        <ChartPie v-if="distReady" :data="ticketDist" height="240px" centerText="工单" :centerSubText="String(ticketTotal)" />
      </el-card>
    </section>

    <!-- ══ 模块统计卡片 ══ -->
    <section class="dv-mod-row">
      <el-card
        v-for="m in modules"
        :key="m.name"
        class="dv-mod"
        shadow="hover"
      >
        <div class="dv-mod-name">
          <span class="dv-mod-dot" :style="{ background: m.color }"></span>{{ m.name }}
        </div>
        <div class="dv-mod-stats">
          <div class="dv-mod-stat" v-for="(st, i) in m.stats" :key="i">
            <span class="dv-mod-num">{{ st[1] }}</span>
            <span class="dv-mod-key">{{ st[0] }}</span>
          </div>
        </div>
      </el-card>
    </section>

    <!-- ══ 底部近期列表 ══ -->
    <section class="dv-list-row">
      <el-card class="dv-card" shadow="hover">
        <template #header><span class="dv-card-title">我的待办</span></template>
        <ul class="dv-ul">
          <li v-for="(t, i) in data.todos" :key="i" :class="{ 'is-over': t.overdue }">
            <span class="dv-tag" :class="'lv-' + t.priority">{{ t.priority }}</span>
            <span class="dv-li-title">{{ t.title }}</span>
            <span class="dv-li-sub">{{ t.deadline }}</span>
          </li>
          <li v-if="!data.todos.length" class="dv-empty">暂无待办</li>
        </ul>
      </el-card>

      <el-card class="dv-card" shadow="hover">
        <template #header><span class="dv-card-title">今日日程</span></template>
        <ul class="dv-ul">
          <li v-for="(s, i) in data.schedule" :key="i">
            <span class="dv-time">{{ s.time }}</span>
            <span class="dv-li-title">{{ s.title }}</span>
            <span class="dv-li-sub">{{ s.loc }}</span>
          </li>
          <li v-if="!data.schedule.length" class="dv-empty">今日无会议</li>
        </ul>
      </el-card>

      <el-card class="dv-card" shadow="hover">
        <template #header><span class="dv-card-title">最新需求</span></template>
        <ul class="dv-ul">
          <li v-for="(r, i) in data.recent_requirements" :key="i">
            <span class="dv-li-title">{{ r.name }}</span>
            <span class="dv-li-sub">{{ r.status }} · {{ r.date }}</span>
          </li>
          <li v-if="!data.recent_requirements.length" class="dv-empty">暂无需求</li>
        </ul>
      </el-card>

      <el-card class="dv-card" shadow="hover">
        <template #header><span class="dv-card-title">运行提醒</span></template>
        <ul class="dv-ul">
          <li v-for="(a, i) in data.alerts" :key="i">
            <span class="dv-badge" :class="'b-' + a.severity">{{ a.severity }}</span>
            <span class="dv-li-title">{{ a.msg }}</span>
            <span class="dv-li-sub">{{ a.count }}</span>
          </li>
          <li v-if="!data.alerts.length" class="dv-empty">暂无提醒</li>
        </ul>
      </el-card>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { dashboardApi } from '@/api/dashboard'
import ChartLine from '@/components/Charts/ChartLine.vue'
import ChartPie from '@/components/Charts/ChartPie.vue'
import ChartProgress from '@/components/Charts/ChartProgress.vue'

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

onMounted(load)

// —— 趋势图：三系列对比 ——
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

// —— 分布饼图 ——
const distReady = computed(() => !!data.value.distribution_charts)
const reqDist = computed(() => data.value.distribution_charts?.requirementStatusDist || [])
const issueDist = computed(() => data.value.distribution_charts?.issueTypeDist || [])
const ticketDist = computed(() => data.value.distribution_charts?.ticketPriorityDist || [])
const reqTotal = computed(() => reqDist.value.reduce((s, d) => s + d.value, 0))
const issueTotal = computed(() => issueDist.value.reduce((s, d) => s + d.value, 0))
const ticketTotal = computed(() => ticketDist.value.reduce((s, d) => s + d.value, 0))

// —— 进度条 ——
const progressReady = computed(() => (data.value.progress_items?.keyProjects || []).length > 0)
const progressData = computed(() =>
  (data.value.progress_items?.keyProjects || []).map((p) => ({
    name: p.name,
    value: p.percent,
    total: p.total,
  })),
)

// —— 模块统计卡片 ——
const modules = computed(() => {
  const ms = data.value.module_stats
  if (!ms) return []
  return [
    {
      name: '需求与交付',
      color: '#2f6fed',
      stats: [
        ['总数', ms.requirements.total],
        ['本周新增', ms.requirements.thisWeek],
        ['跟踪中', ms.requirements.inReview],
        ['已上线', ms.requirements.completed],
      ],
    },
    {
      name: '开发工单',
      color: '#0f9d6b',
      stats: [
        ['总数', ms.tickets.total],
        ['待处理', ms.tickets.pending],
        ['进行中', ms.tickets.processing],
        ['已上线', ms.tickets.resolved],
      ],
    },
    {
      name: '运营问题',
      color: '#e02424',
      stats: [
        ['总数', ms.issues.total],
        ['待处理', ms.issues.pending],
        ['处理中', ms.issues.processing],
        ['超期', ms.issues.overdue],
      ],
    },
    {
      name: '会议日程',
      color: '#d98a1f',
      stats: [
        ['本周', ms.meetings.totalThisWeek],
        ['今日', ms.meetings.today],
        ['待开', ms.meetings.upcoming],
      ],
    },
    {
      name: '知识中心',
      color: '#2fc9a0',
      stats: [
        ['总数', ms.knowledge.total],
        ['本周', ms.knowledge.thisWeek],
      ],
    },
    {
      name: '邮件中心',
      color: '#946ce6',
      stats: [
        ['今日发送', ms.emails.todaySent],
        ['本周发送', ms.emails.weekSent],
        ['成功率', ms.emails.successRate + '%'],
      ],
    },
  ]
})
</script>

<style scoped>
.dash-v2 {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.dv-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(120deg, #2f6fed 0%, #6b9aff 100%);
  border-radius: 14px;
  padding: 20px 24px;
  color: #fff;
  flex-wrap: wrap;
  gap: 12px;
}
.dv-hello { font-size: 20px; font-weight: 700; }
.dv-eff { margin-top: 8px; display: flex; align-items: baseline; gap: 8px; }
.dv-eff-val { font-size: 28px; font-weight: 800; }
.dv-eff-val i { font-size: 14px; font-style: normal; margin-left: 2px; }
.dv-eff-key { font-size: 12px; opacity: 0.85; }
.dv-h-stats { display: flex; gap: 24px; }
.dv-h-stat { text-align: center; }
.dv-h-val { display: block; font-size: 22px; font-weight: 700; }
.dv-h-key { font-size: 12px; opacity: 0.85; }

.dv-kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.dv-kpi {
  background: #fff;
  border-radius: 14px;
  padding: 18px 20px;
  border-left: 4px solid #2f6fed;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
}
.dv-kpi.c-blue { border-left-color: #2f6fed; }
.dv-kpi.c-amber { border-left-color: #d98a1f; }
.dv-kpi.c-red { border-left-color: #e02424; }
.dv-kpi.c-green { border-left-color: #0f9d6b; }
.dv-kpi-val { font-size: 32px; font-weight: 800; color: #303133; line-height: 1.1; }
.dv-kpi-label { font-size: 13px; color: #909399; margin-top: 4px; }
.dv-kpi-delta { font-size: 12px; margin-top: 6px; color: #909399; }
.dv-kpi-delta.dt-up { color: #0f9d6b; }
.dv-kpi-delta.dt-down { color: #e02424; }

.dv-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.dv-card.span-2 { grid-column: span 2; }
.dv-card-title { font-weight: 600; font-size: 14px; color: #303133; }

.dv-mod-row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 16px; }
.dv-mod { border-radius: 14px; }
.dv-mod-name { font-weight: 600; font-size: 14px; color: #303133; display: flex; align-items: center; gap: 8px; }
.dv-mod-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dv-mod-stats { display: flex; flex-wrap: wrap; gap: 12px 18px; margin-top: 14px; }
.dv-mod-stat { display: flex; flex-direction: column; }
.dv-mod-num { font-size: 20px; font-weight: 700; color: #303133; }
.dv-mod-key { font-size: 12px; color: #909399; }

.dv-list-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.dv-ul { list-style: none; margin: 0; padding: 0; }
.dv-ul li { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px dashed #f0f2f5; font-size: 13px; }
.dv-ul li:last-child { border-bottom: none; }
.dv-li-title { flex: 1; color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dv-li-sub { color: #b0b3b8; font-size: 12px; }
.dv-time { color: #2f6fed; font-weight: 600; }
.dv-empty { color: #b0b3b8; justify-content: center; }
.dv-tag { font-size: 11px; padding: 1px 6px; border-radius: 4px; background: #eef2fb; color: #2f6fed; }
.dv-tag.lv-紧急 { background: #fde2e2; color: #e02424; }
.dv-tag.lv-高优 { background: #fdf0e0; color: #d98a1f; }
.dv-tag.lv-中等 { background: #eef2fb; color: #2f6fed; }
.dv-tag.lv-低优 { background: #e8f7f0; color: #0f9d6b; }
.dv-badge { font-size: 11px; padding: 1px 6px; border-radius: 4px; }
.dv-badge.b-严重 { background: #fde2e2; color: #e02424; }
.dv-badge.b-警告 { background: #fdf0e0; color: #d98a1f; }
.dv-badge.b-提醒 { background: #eef2fb; color: #2f6fed; }
.dv-badge.b-正常 { background: #e8f7f0; color: #0f9d6b; }
.is-over .dv-li-title { color: #e02424; }

@media (max-width: 1200px) {
  .dv-kpi-row { grid-template-columns: repeat(2, 1fr); }
  .dv-grid { grid-template-columns: 1fr; }
  .dv-card.span-2 { grid-column: span 1; }
  .dv-mod-row { grid-template-columns: repeat(3, 1fr); }
  .dv-list-row { grid-template-columns: repeat(2, 1fr); }
}
</style>
