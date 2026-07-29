<template>
  <div class="dv2" v-loading="loading">
    <!-- ═══ Hero 区：整体总结汇总 ═══ -->
    <section class="dv2-hero">
      <div class="dv2-h-left">
        <div class="dv2-breadcrumb">
          <span class="bc">个人工作台</span>
          <span class="bc-sep">›</span>
          <span class="bc bc-active">数据总览</span>
        </div>
        <h1 class="dv2-title">下午好，{{ data.user_name || '陈工' }}</h1>
        <p class="dv2-subtitle">{{ overallSummary }}</p>
      </div>
      <div class="dv2-h-right">
        <div class="dv2-eff">
          <div class="eff-num">{{ (data.efficiency || 0).toFixed(0) }}<span>%</span></div>
          <div class="eff-label">运营问题处置效率</div>
        </div>
        <el-button type="primary" @click="refreshData">
          <el-icon><Refresh /></el-icon> 刷新数据
        </el-button>
      </div>
    </section>

    <!-- ═══ KPI 总览条（真实数据、信息充实） ═══ -->
    <section class="dv2-kpi-row">
      <div class="dv2-kpi" v-for="(k, i) in kpiItems" :key="i">
        <div class="k-label">{{ k.label }}</div>
        <div class="k-val">{{ k.value }}</div>
        <div class="k-delta" :class="'dt-' + k.dir">{{ k.delta }}</div>
      </div>
    </section>

    <!-- ═══ 模块磁贴网格 ═══ -->
    <section class="dv2-bento">
      <!-- 任务中心（大块，2x2） -->
      <div class="tile tile-task">
        <div class="tile-head">
          <div class="tile-title"><span class="tdot" style="background:#2f6fed"></span>任务中心</div>
          <span class="pill" :class="taskOverdue > 0 ? 'pill-warn' : 'pill-ok'">
            {{ taskOverdue > 0 ? '需关注' : '正常' }}
          </span>
        </div>
        <div class="task-body">
          <div class="task-donut">
            <ChartPie v-if="taskDonut.length" :data="taskDonut" height="170px"
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
            <span class="fdot f-red"></span>重点关注：{{ taskOverdue }} 项超期待办
          </div>
          <div class="tile-focus" v-else>
            <span class="fdot f-green"></span>运行平稳，无超期事项
          </div>
          <router-link to="/task-center" class="tile-enter">进入模块 →</router-link>
        </div>
      </div>

      <!-- 需求与交付（2 列宽） -->
      <div class="tile tile-req">
        <div class="tile-head">
          <div class="tile-title"><span class="tdot" style="background:#2f6fed"></span>需求与交付</div>
          <router-link to="/requirement-delivery" class="tile-enter">进入管理 →</router-link>
        </div>
        <div class="req-stats">
          <div class="rs"><b>{{ ms?.requirements.total ?? 0 }}</b><span>总数</span></div>
          <div class="rs"><b>{{ ms?.requirements.thisWeek ?? 0 }}</b><span>本周新增</span></div>
          <div class="rs"><b>{{ ms?.requirements.inReview ?? 0 }}</b><span>跟踪中</span></div>
          <div class="rs"><b>{{ ms?.requirements.completed ?? 0 }}</b><span>已上线</span></div>
        </div>
        <div class="req-mid">
          <div class="req-pie">
            <ChartPie v-if="reqStatusDist.length" :data="reqStatusDist" height="150px" />
          </div>
          <div class="req-recent">
            <div class="rr-head">近期变更</div>
            <div class="rr-row" v-for="(r, i) in (data.recent_requirements || []).slice(0, 3)" :key="i">
              <span class="rr-dot" :class="statusCls(r.status)"></span>
              <span class="rr-name" :title="r.name">{{ r.name }}</span>
              <span class="rr-status">{{ r.status }}</span>
            </div>
            <div class="rr-overdue" v-if="(ms?.requirements.overdueDev ?? 0) > 0">
              ⚠ {{ ms.requirements.overdueDev }} 个需求开发中超 20 天
            </div>
          </div>
        </div>
      </div>

      <!-- 运营问题（2 列宽，拉长丰富） -->
      <div class="tile tile-issue">
        <div class="tile-head">
          <div class="tile-title"><span class="tdot" style="background:#e02424"></span>运营问题</div>
          <router-link to="/operation/data" class="tile-enter">进入 →</router-link>
        </div>
        <div class="issue-top">
          <div class="is"><b>{{ ms?.issues.total ?? 0 }}</b><span>总数</span></div>
          <div class="is"><b>{{ ms?.issues.pending ?? 0 }}</b><span>待处理</span></div>
          <div class="is"><b>{{ ms?.issues.processing ?? 0 }}</b><span>处理中</span></div>
          <div class="is warn"><b>{{ ms?.issues.overdue ?? 0 }}</b><span>逾期</span></div>
        </div>
        <div class="issue-mid">
          <div class="issue-pie">
            <ChartPie v-if="issueTypeDist.length" :data="issueTypeDist" height="140px" />
          </div>
          <div class="issue-trend">
            <ChartLine v-if="issueTrend.length" :xData="issueTrendX" :series="issueTrendS"
              height="140px" :smooth="true" />
          </div>
        </div>
        <div class="issue-types">
          <div class="it-row" v-for="(d, i) in issueTypeDist" :key="i">
            <span class="it-name">{{ d.name }}</span>
            <span class="it-bar"><i :style="{ width: pct(d.value, issueTotal) + '%', background: d.color }"></i></span>
            <span class="it-val">{{ d.value }}</span>
          </div>
        </div>
        <div class="tile-foot">
          <div class="tile-focus" v-if="(ms?.issues.overdue ?? 0) > 0">
            <span class="fdot f-red"></span>{{ ms.issues.overdue }} 项逾期需关注
          </div>
          <div class="tile-focus" v-else><span class="fdot f-green"></span>处置率良好</div>
          <router-link to="/operation/data" class="tile-enter">查看全部 →</router-link>
        </div>
      </div>

      <!-- 会议日程（1 列） -->
      <div class="tile tile-meet">
        <div class="tile-head">
          <div class="tile-title"><span class="tdot" style="background:#d98a1f"></span>会议日程</div>
          <router-link to="/meeting" class="tile-enter">进入 →</router-link>
        </div>
        <div class="meet-stats">
          <div class="ms"><b>{{ ms?.meetings.totalThisWeek ?? 0 }}</b><span>本周</span></div>
          <div class="ms"><b>{{ ms?.meetings.today ?? 0 }}</b><span>今日</span></div>
          <div class="ms"><b>{{ ms?.meetings.upcoming ?? 0 }}</b><span>待开</span></div>
        </div>
        <div class="meet-pending" v-if="(ms?.meetings.pendingMinutes ?? 0) > 0">
          <div class="mp-head">⚠ 待处理会议纪要 {{ ms.meetings.pendingMinutes }} 条</div>
          <div class="mp-row" v-for="(p, i) in pendingMeetings.slice(0, 3)" :key="i">
            {{ p.start_time }} · {{ p.title }}
          </div>
        </div>
        <div class="meet-next" v-if="(data.schedule || []).length">
          下次：{{ data.schedule[0].time }} {{ data.schedule[0].title }}
        </div>
      </div>

      <!-- 知识中心（1 列） -->
      <div class="tile tile-know">
        <div class="tile-head">
          <div class="tile-title"><span class="tdot" style="background:#2fc9a0"></span>知识中心</div>
          <router-link to="/knowledge-center" class="tile-enter">进入 →</router-link>
        </div>
        <div class="mini-big">{{ ms?.knowledge.total ?? 0 }}<span>篇</span></div>
        <div class="mini-sub">本月新增 {{ ms?.knowledge.thisWeek ?? 0 }} 篇</div>
        <div class="mini-line">持续沉淀中</div>
      </div>

      <!-- 重要工作（1 列，新增） -->
      <div class="tile tile-key">
        <div class="tile-head">
          <div class="tile-title"><span class="tdot" style="background:#946ce6"></span>重要工作</div>
          <router-link to="/key-works" class="tile-enter">进入 →</router-link>
        </div>
        <div class="key-list">
          <div class="kl-row" v-for="(p, i) in keyProjects.slice(0, 4)" :key="i">
            <div class="kl-top">
              <span class="kl-name" :title="p.name">{{ p.name }}</span>
              <span class="kl-pct">{{ p.percent }}%</span>
            </div>
            <div class="kl-bar"><i :style="{ width: p.percent + '%' }"></i></div>
          </div>
          <div class="kl-empty" v-if="!keyProjects.length">暂无进行中的重要工作</div>
        </div>
      </div>

      <!-- 邮件中心（1 列） -->
      <div class="tile tile-mail">
        <div class="tile-head">
          <div class="tile-title"><span class="tdot" style="background:#6b8afd"></span>邮件中心</div>
          <router-link to="/mail-center/logs" class="tile-enter">进入 →</router-link>
        </div>
        <div class="mini-big">{{ ms?.emails.weekSent ?? 0 }}<span>封/周</span></div>
        <div class="mini-sub">今日 {{ ms?.emails.todaySent ?? 0 }} · 成功率 {{ (ms?.emails.successRate || 0).toFixed(1) }}%</div>
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

const PALETTE = ['#2f6fed', '#e02424', '#0f9d6b', '#d98a1f', '#946ce6', '#2fc9a0', '#6b8afd']

const loading = ref(false)
const data = ref({
  user_name: '陈工',
  efficiency: 0,
  todos: [],
  recent_requirements: [],
  schedule: [],
  recent_issues: [],
  module_stats: null,
  trend_charts: null,
  distribution_charts: null,
  progress_items: null,
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

// ─── 整体总结汇总 ───
const overallSummary = computed(() => {
  const m = ms.value
  if (!m) return '数据加载中…'
  const parts = []
  parts.push(`待办 ${data.value.todos.length || 0} 项`)
  parts.push(`需求 ${m.requirements.total} 个（跟踪中 ${m.requirements.inReview}）`)
  if (m.requirements.overdueDev > 0) parts.push(`${m.requirements.overdueDev} 个需求开发中超期`)
  parts.push(`运营问题 ${m.issues.total} 条（逾期 ${m.issues.overdue}）`)
  if (m.meetings.pendingMinutes > 0) parts.push(`待补纪要 ${m.meetings.pendingMinutes} 场`)
  return '当前工作台概览：' + parts.join('，') + `；运营处置效率 ${(data.value.efficiency || 0).toFixed(0)}%。`
})

// ─── KPI 总览条（真实数据） ───
const kpiItems = computed(() => {
  const m = ms.value
  const d = data.value
  const overdueTodos = (d.todos || []).filter(t => t.overdue).length
  return [
    { label: '我的待办', value: d.todos.length || 0, dir: overdueTodos > 0 ? 'down' : 'neutral', delta: overdueTodos > 0 ? `${overdueTodos} 项超期` : '无超期' },
    { label: '需求总数', value: m?.requirements.total ?? 0, dir: 'up', delta: `本周 +${m?.requirements.thisWeek ?? 0}` },
    { label: '开发中需求', value: m?.requirements.inReview ?? 0, dir: (m?.requirements.overdueDev ?? 0) > 0 ? 'down' : 'neutral', delta: (m?.requirements.overdueDev ?? 0) > 0 ? `${m.requirements.overdueDev} 超期` : '正常推进' },
    { label: '开发工单', value: m?.tickets.total ?? 0, dir: (m?.tickets.pending ?? 0) > 0 ? 'down' : 'neutral', delta: `${m?.tickets.pending ?? 0} 待评审` },
    { label: '运营问题', value: m?.issues.total ?? 0, dir: (m?.issues.overdue ?? 0) > 0 ? 'down' : 'neutral', delta: `${m?.issues.overdue ?? 0} 逾期` },
    { label: '本周会议', value: m?.meetings.totalThisWeek ?? 0, dir: 'neutral', delta: `待补纪要 ${m?.meetings.pendingMinutes ?? 0}` },
    { label: '知识文档', value: m?.knowledge.total ?? 0, dir: 'up', delta: `本月 +${m?.knowledge.thisWeek ?? 0}` },
    { label: '处置效率', value: (d.efficiency || 0).toFixed(0) + '%', dir: d.efficiency >= 80 ? 'up' : 'down', delta: d.efficiency >= 80 ? '达标' : '待提升' },
  ]
})

// ─── 任务中心 ───
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

// ─── 需求卡片 ───
const reqStatusDist = computed(() =>
  (data.value.distribution_charts?.requirementStatusDist || []).map((d, i) => ({ ...d, color: PALETTE[i % PALETTE.length] }))
)
const statusCls = (s) => {
  if (['已上线'].includes(s)) return 'st-green'
  if (['已暂停'].includes(s)) return 'st-gray'
  return 'st-blue'
}

// ─── 运营卡片 ───
const issueTypeDist = computed(() =>
  (data.value.distribution_charts?.issueTypeDist || []).map((d, i) => ({ ...d, color: PALETTE[i % PALETTE.length] }))
)
const issueTotal = computed(() => issueTypeDist.value.reduce((s, d) => s + d.value, 0))
const pct = (v, total) => (total > 0 ? Math.round((v / total) * 100) : 0)
const issueTrend = computed(() => data.value.trend_charts?.issuesTrend || [])
const issueTrendX = computed(() => issueTrend.value.map(t => t.label))
const issueTrendS = computed(() => [{ name: '问题', data: issueTrend.value.map(t => t.value) }])

// ─── 会议卡片 ───
const pendingMeetings = computed(() => data.value.pending_minutes_meetings || [])

// ─── 重要工作卡片 ───
const keyProjects = computed(() => data.value.progress_items?.keyProjects || [])
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
.bc { color: #606266; }
.bc-active { color: #2f6fed; font-weight: 600; }
.bc-sep { color: #c0c4cc; }
.dv2-title { margin: 0 0 6px; font-size: 22px; font-weight: 700; color: #1a1a2e; }
.dv2-subtitle { margin: 0; font-size: 13px; color: #4a5568; line-height: 1.6; max-width: 760px; }
.dv2-h-right { display: flex; align-items: center; gap: 18px; }
.dv2-eff { text-align: center; }
.eff-num { font-size: 30px; font-weight: 800; color: #2f6fed; line-height: 1; }
.eff-num span { font-size: 14px; }
.eff-label { font-size: 11px; color: #606266; margin-top: 4px; }

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
  padding: 14px 12px;
  text-align: center;
  border-right: 1px solid #eef1f6;
  min-width: 0;
}
.dv2-kpi:last-child { border-right: none; }
.k-label { font-size: 12px; color: #909399; margin-bottom: 4px; }
.k-val { font-size: 24px; font-weight: 800; color: #1a1a2e; line-height: 1.1; }
.k-delta { font-size: 11px; margin-top: 3px; color: #909399; }
.dt-up { color: #0f9d6b; }
.dt-down { color: #e02424; }
.dt-neutral { color: #c0c4cc; }

/* Bento 网格 */
.dv2-bento {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  grid-auto-rows: minmax(210px, auto);
  gap: 16px;
  grid-template-areas:
    "task task req req"
    "task task issue issue"
    "meet know key mail";
}
.tile-task { grid-area: task; }
.tile-req { grid-area: req; }
.tile-issue { grid-area: issue; }
.tile-meet { grid-area: meet; }
.tile-know { grid-area: know; }
.tile-key { grid-area: key; }
.tile-mail { grid-area: mail; }

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
.tile-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.tile-title { font-size: 15px; font-weight: 700; color: #1a1a2e; display: flex; align-items: center; gap: 7px; }
.tdot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.tile-enter { font-size: 12px; color: #2f6fed; text-decoration: none; white-space: nowrap; }
.tile-enter:hover { text-decoration: underline; }
.pill { font-size: 11px; padding: 2px 9px; border-radius: 10px; }
.pill-ok { background: #e8f7f0; color: #0f9d6b; }
.pill-warn { background: #fde2e2; color: #e02424; }

.tile-foot { margin-top: auto; padding-top: 10px; border-top: 1px solid #f0f2f5; display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
.tile-focus { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #606266; }
.fdot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.f-red { background: #e02424; }
.f-green { background: #0f9d6b; }

/* 任务中心大块 */
.task-body { display: flex; gap: 16px; align-items: center; flex: 1; min-height: 0; }
.task-donut { width: 170px; flex-shrink: 0; }
.task-side { flex: 1; display: flex; flex-direction: column; gap: 12px; }
.task-big { font-size: 32px; font-weight: 800; color: #1a1a2e; }
.task-big span { font-size: 13px; font-weight: 400; color: #909399; margin-left: 4px; }
.task-legend { display: flex; flex-direction: column; gap: 6px; }
.tl-row { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.tl-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.tl-name { color: #606266; flex: 1; }
.tl-val { font-weight: 600; color: #303133; }

/* 需求卡片 */
.req-stats, .issue-top, .meet-stats { display: flex; gap: 10px; margin-bottom: 12px; }
.rs, .is, .ms { flex: 1; display: flex; flex-direction: column; align-items: center; background: #f7f9fc; border-radius: 8px; padding: 8px 4px; }
.rs b, .is b, .ms b { font-size: 19px; font-weight: 700; color: #1a1a2e; }
.rs span, .is span, .ms span { font-size: 11px; color: #909399; margin-top: 2px; }
.is.warn b { color: #e02424; }
.req-mid { display: flex; gap: 14px; flex: 1; min-height: 0; }
.req-pie { width: 150px; flex-shrink: 0; }
.req-recent { flex: 1; display: flex; flex-direction: column; gap: 5px; }
.rr-head { font-size: 12px; font-weight: 600; color: #606266; margin-bottom: 2px; }
.rr-row { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #303133; }
.rr-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.st-blue { background: #2f6fed; }
.st-green { background: #0f9d6b; }
.st-gray { background: #c0c4cc; }
.rr-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rr-status { color: #909399; font-size: 11px; }
.rr-overdue { margin-top: 4px; font-size: 11px; color: #e02424; background: #fdeaea; padding: 4px 8px; border-radius: 6px; }

/* 运营卡片 */
.issue-mid { display: flex; gap: 14px; margin-bottom: 10px; }
.issue-pie { width: 150px; flex-shrink: 0; }
.issue-trend { flex: 1; min-width: 0; }
.issue-types { display: flex; flex-direction: column; gap: 5px; }
.it-row { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.it-name { width: 64px; color: #606266; flex-shrink: 0; }
.it-bar { flex: 1; height: 7px; background: #eef1f6; border-radius: 4px; overflow: hidden; }
.it-bar i { display: block; height: 100%; border-radius: 4px; }
.it-val { width: 28px; text-align: right; font-weight: 600; color: #303133; }

/* 会议 / 通用小块 */
.mini-big { font-size: 30px; font-weight: 800; color: #1a1a2e; line-height: 1.1; }
.mini-big span { font-size: 12px; font-weight: 400; color: #909399; margin-left: 4px; }
.mini-sub { font-size: 12px; color: #909399; margin-top: 4px; }
.mini-line { font-size: 12px; color: #606266; margin-top: 2px; }
.meet-pending { margin-top: 10px; background: #fff7e6; border-radius: 8px; padding: 8px 10px; }
.mp-head { font-size: 12px; font-weight: 600; color: #d98a1f; margin-bottom: 4px; }
.mp-row { font-size: 12px; color: #606266; padding: 2px 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.meet-next { margin-top: 8px; font-size: 12px; color: #2f6fed; }

/* 重要工作 */
.key-list { display: flex; flex-direction: column; gap: 10px; flex: 1; justify-content: center; }
.kl-row { display: flex; flex-direction: column; gap: 4px; }
.kl-top { display: flex; justify-content: space-between; font-size: 12px; }
.kl-name { color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 70%; }
.kl-pct { font-weight: 700; color: #946ce6; }
.kl-bar { height: 6px; background: #efeaf8; border-radius: 4px; overflow: hidden; }
.kl-bar i { display: block; height: 100%; background: #946ce6; border-radius: 4px; }
.kl-empty { font-size: 12px; color: #c0c4cc; text-align: center; padding: 16px 0; }

/* 响应式 */
@media (max-width: 1200px) {
  .dv2-bento {
    grid-template-columns: repeat(2, 1fr);
    grid-template-areas:
      "task task"
      "req req"
      "issue issue"
      "meet know"
      "key mail";
  }
}
@media (max-width: 760px) {
  .dv2-kpi-row { flex-wrap: wrap; }
  .dv2-kpi { min-width: 33%; border-right: none; }
  .dv2-bento {
    grid-template-columns: 1fr;
    grid-template-areas: "task" "req" "issue" "meet" "know" "key" "mail";
  }
}
</style>
