<template>
  <div class="home-view">
    <div class="bento-grid">

      <!-- ══ ROW 1: 问候区 + 实时动态 ══ -->
      <BentoCard class="greeting-tile" :span="8" flat :body-padding="'0'">
        <div class="greeting-inner">
          <div class="g-top">
            <div>
              <div class="g-hello">{{ helloText }}，<span>{{ greeting.name }}</span></div>
              <div class="g-sub">{{ greeting.sub }}</div>
            </div>
            <div class="g-eff">
              <div class="g-eff-key">运营闭环率</div>
              <div class="g-eff-val">{{ greeting.efficiency }}<span class="g-eff-unit">%</span></div>
            </div>
          </div>
          <div class="g-stats">
            <div class="g-stat" v-for="(s, i) in greeting.stats" :key="i">
              <span class="g-stat-val" :class="s.cls">{{ s.value }}</span>
              <span class="g-stat-key">{{ s.key }}</span>
            </div>
          </div>
          <div class="cmd-bar">
            <div class="cmd-bar-kbd"><span class="kbd">⌘</span><span class="kbd">K</span></div>
            <div class="cmd-bar-text">{{ cmdText }}</div><span class="cmd-cursor"></span>
          </div>
        </div>
      </BentoCard>

      <BentoCard title="实时动态" :span="4">
        <ul class="ls-list">
          <li class="ls-item" v-for="(item, i) in liveStatus" :key="i">
            <span class="ls-dot" :class="item.color"></span>
            <span class="ls-text">{{ item.text }}</span>
            <span class="ls-time">{{ item.time }}</span>
          </li>
        </ul>
      </BentoCard>

      <!-- ══ ROW 2: KPI 指标条 ══ -->
      <BentoCard
        v-for="(k, i) in kpis"
        :key="'kpi' + i"
        class="kpi-card"
        :span="3"
        flat
      >
        <div class="kpi-num" :class="k.color">{{ k.num }}</div>
        <div class="kpi-label">{{ k.label }}</div>
        <div class="kpi-delta" :class="k.deltaType">{{ k.delta }}</div>
      </BentoCard>

      <!-- 快捷操作 -->
      <div class="action-row" style="grid-column:1/-1">
        <button class="act-btn primary" @click="goTo('/requirement-delivery')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>新增需求·工单
        </button>
        <button class="act-btn success" @click="goTo('/meeting')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>新增会议
        </button>
        <button class="act-btn warn" @click="goTo('/operation')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>新增运营问题
        </button>
        <button class="act-btn ghost" @click="goTo('/knowledge')">知识库 →</button>
      </div>

      <!-- ══ 核心工作区：按菜单顺序突出（任务中心 → 需求工单 → 运营工单 → 会议日程）══ -->
      <div class="section-title" style="grid-column:1/-1">
        <span class="st-main">核心工作区</span>
        <span class="st-sub">重点关注 · 任务中心 / 需求工单 / 运营工单 / 会议日程</span>
      </div>

      <!-- 任务中心 -->
      <BentoCard class="card-highlight" :span="6" :body-padding="'16px 22px 18px'">
        <template #head>
          <span class="card-label">任务中心</span>
        </template>
        <template #action><a class="card-action" @click="goTo('/task-center')">更多</a></template>
        <div class="op-wrap">
          <div class="op-stats">
            <div class="op-stat"><b>{{ taskCenter.total }}</b><span>共待办</span></div>
            <div class="op-stat"><b>{{ taskCenter.processing }}</b><span>进行中</span></div>
            <div class="op-stat"><b>{{ taskCenter.pending }}</b><span>待处理</span></div>
            <div class="op-stat" :class="{ danger: taskCenter.overdue > 0 }"><b>{{ taskCenter.overdue }}</b><span>超期</span></div>
          </div>
          <div class="op-dist">
            <div class="op-dist-h">来源分布</div>
            <div class="op-bar" v-for="(s, i) in taskCenter.by_source" :key="i">
              <span class="op-bar-label">{{ s.name }}</span>
              <span class="op-bar-track"><i class="op-bar-fill" :style="{ width: pct(s.value, taskCenter.total) + '%' }"></i></span>
              <span class="op-bar-val">{{ s.value }}</span>
            </div>
            <div v-if="!taskCenter.by_source.length" class="tc-empty">暂无来源分布</div>
          </div>
        </div>
      </BentoCard>

      <!-- 需求工单 -->
      <BentoCard class="card-highlight" :span="6" :body-padding="'16px 22px 18px'">
        <template #head>
          <span class="card-label">需求工单</span>
        </template>
        <template #action><a class="card-action" @click="goTo('/requirement-delivery')">需求与交付 →</a></template>
        <div class="rq-wrap">
          <div class="rq-stats">
            <div class="rq-stat"><b>{{ reqs.total }}</b><span>需求总数</span></div>
            <div class="rq-stat"><b>{{ reqs.thisWeek }}</b><span>本周新增</span></div>
            <div class="rq-stat"><b>{{ reqs.inReview }}</b><span>跟踪中</span></div>
            <div class="rq-stat" :class="{ danger: reqs.overdueDev > 0 }"><b>{{ reqs.overdueDev }}</b><span>超期开发</span></div>
          </div>
          <div class="rq-dist">
            <div class="rq-dist-h">状态分布</div>
            <div class="rq-bar" v-for="(s, i) in reqStatusDist" :key="i">
              <span class="rq-bar-label">{{ s.name }}</span>
              <span class="rq-bar-track"><i class="rq-bar-fill" :class="rqStatusClass(s.name)" :style="{ width: pct(s.value, reqs.total) + '%' }"></i></span>
              <span class="rq-bar-val">{{ s.value }}</span>
            </div>
            <div v-if="!reqStatusDist.length" class="tc-empty">暂无需求状态分布</div>
          </div>
        </div>
      </BentoCard>

      <!-- 运营工单 -->
      <BentoCard class="card-highlight" :span="6" :body-padding="'16px 22px 18px'">
        <template #head>
          <span class="card-label">运营工单</span>
        </template>
        <template #action><a class="card-action" @click="goTo('/operation')">运营监控 →</a></template>
        <div class="op-wrap">
          <div class="op-stats">
            <div class="op-stat"><b>{{ issues.total }}</b><span>问题总数</span></div>
            <div class="op-stat"><b>{{ issues.processing }}</b><span>处理中</span></div>
            <div class="op-stat"><b>{{ issues.resolved }}</b><span>已解决</span></div>
            <div class="op-stat" :class="{ danger: issues.overdue > 0 }"><b>{{ issues.overdue }}</b><span>超期</span></div>
          </div>
          <div class="op-dist">
            <div class="op-dist-h">类型分布</div>
            <div class="op-bar" v-for="(s, i) in issueTypeDist" :key="i">
              <span class="op-bar-label">{{ s.name }}</span>
              <span class="op-bar-track"><i class="op-bar-fill" :style="{ width: pct(s.value, issues.total) + '%' }"></i></span>
              <span class="op-bar-val">{{ s.value }}</span>
            </div>
            <div v-if="!issueTypeDist.length" class="tc-empty">暂无类型分布</div>
          </div>
        </div>
      </BentoCard>

      <!-- 会议日程 -->
      <BentoCard class="card-highlight" :span="6" :body-padding="'16px 22px 18px'">
        <template #head>
          <span class="card-label">会议日程</span>
        </template>
        <template #action><a class="card-action" @click="goTo('/meeting')">日历</a></template>
        <div class="mt-wrap">
          <div class="mt-stats">
            <div class="mt-stat"><b>{{ meetingStats.totalThisWeek }}</b><span>本周会议</span></div>
            <div class="mt-stat"><b>{{ meetingStats.today }}</b><span>今日</span></div>
            <div class="mt-stat"><b>{{ meetingStats.upcoming }}</b><span>即将召开</span></div>
            <div class="mt-stat" :class="{ danger: meetingStats.pendingMinutes > 0 }"><b>{{ meetingStats.pendingMinutes }}</b><span>待写纪要</span></div>
          </div>
          <ul class="mt-list">
            <li class="mt-item" v-for="(s, i) in schedule" :key="i">
              <span class="mt-time">{{ s.time }}</span>
              <div class="mt-info">
                <div class="mt-title">{{ s.title }}</div>
                <div class="mt-loc">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>
                  {{ s.loc }}
                </div>
              </div>
            </li>
            <li v-if="!schedule.length" class="mt-empty">今日暂无会议安排</li>
          </ul>
        </div>
      </BentoCard>

      <!-- ══ 需求概览：趋势图 + 最近需求 整合为单卡 ══ -->
      <BentoCard title="需求概览" :span="12">
        <template #action><a class="card-action" @click="goTo('/requirement-delivery')">需求与交付 →</a></template>
        <div class="req-overview">
          <div class="ro-chart">
            <div class="chart-wrap">
              <svg class="chart-svg" viewBox="0 0 600 220" preserveAspectRatio="xMidYMid meet">
                <defs>
                  <linearGradient id="areaGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stop-color="#2f6fed" stop-opacity=".22" />
                    <stop offset="100%" stop-color="#2f6fed" stop-opacity=".02" />
                  </linearGradient>
                </defs>
                <g stroke="#eef1f6" stroke-width="1">
                  <line v-for="(g, i) in trendGrid" :key="'g' + i"
                        :x1="plotLeft" :y1="g.y" :x2="plotRight" :y2="g.y"
                        :stroke-dasharray="i < 3 ? '4,4' : 'none'" />
                </g>
                <path :d="trendGeom.areaPath" fill="url(#areaGrad)" />
                <polyline :points="trendGeom.polyPoints" fill="none" stroke="#2f6fed"
                          stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
                <g v-for="(p, i) in trendGeom.pts" :key="'d' + i" fill="#2f6fed">
                  <circle :cx="p.x" :cy="p.y" r="4.5" />
                </g>
                <g v-for="(p, i) in trendGeom.pts" :key="'dh' + i" fill="#ffffff" stroke="#2f6fed" stroke-width="2">
                  <circle :cx="p.x" :cy="p.y" r="2.5" />
                </g>
                <g fill="#0f172a" font-size="10.5" font-weight="600" text-anchor="middle">
                  <text v-for="(p, i) in trendGeom.pts" :key="'v' + i" :x="p.x" :y="p.y - 10">{{ p.value }}</text>
                </g>
                <g fill="#94a3b8" font-size="11" text-anchor="middle">
                  <text v-for="(p, i) in trendGeom.pts" :key="'x' + i" :x="p.x" :y="200">{{ p.label }}</text>
                </g>
                <g fill="#94a3b8" font-size="10.5" text-anchor="end">
                  <text v-for="(g, i) in trendGrid" :key="'y' + i" :x="34" :y="g.y + 3">{{ g.value }}</text>
                </g>
              </svg>
            </div>
            <div class="chart-legend ro-legend">
              <div class="legend-item"><span class="legend-dot" style="background:#2f6fed"></span>已处理需求量</div>
              <div class="legend-item"><span class="legend-dot" style="background:#e4e9f0"></span>网格参考线</div>
            </div>
          </div>
          <div class="ro-reqs">
            <div class="ro-reqs-h">最近需求</div>
            <div class="req-wrap ro-req-wrap">
              <table class="req-table">
                <thead>
                  <tr><th>需求名称</th><th>负责人</th><th>状态</th><th>更新日期</th></tr>
                </thead>
                <tbody>
                  <tr v-for="(r, i) in recentReqs" :key="i">
                    <td class="req-name" :title="r.name">{{ r.name }}</td>
                    <td class="req-owner">{{ r.owner }}</td>
                    <td><span class="status-tag" :class="r.statusClass">{{ r.status }}</span></td>
                    <td class="req-date">{{ r.date }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </BentoCard>

      <!-- ══ 我的待办 + 重点工作 ══ -->
      <BentoCard title="智能优先级 · 我的待办" :span="6">
        <template #action><a class="card-action" @click="goTo('/todo')">更多</a></template>
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
      </BentoCard>

      <BentoCard title="重点工作进度" :span="6">
        <template #action><a class="card-action" @click="goTo('/key-works')">更多</a></template>
        <ul class="kp-list">
          <li class="kp-item" v-for="(p, i) in keyProjects" :key="i">
            <div class="kp-head">
              <span class="kp-name">{{ p.name }}</span>
              <span class="kp-pct">{{ p.percent }}%</span>
            </div>
            <div class="kp-bar"><i class="kp-fill" :style="{ width: p.percent + '%' }"></i></div>
          </li>
          <li v-if="!keyProjects.length" class="kp-empty">暂无进行中的重点工作</li>
        </ul>
      </BentoCard>

      <!-- ══ 模块概览：按菜单顺序（人员中台 / 知识中心 / 邮件中心）══ -->
      <div class="section-title" style="grid-column:1/-1">
        <span class="st-main">模块概览</span>
        <span class="st-sub">人员中台 / 知识中心 / 邮件中心</span>
      </div>

      <BentoCard title="人员中台" :span="4">
        <div class="mod-grid">
          <div class="mod-stat">
            <span class="mod-num">{{ personnel.staff }}</span>
            <span class="mod-key">在职人员</span>
          </div>
          <div class="mod-sub">{{ personnel.org }} 个组织 · 启用 {{ personnel.enabled }}</div>
        </div>
      </BentoCard>

      <BentoCard title="知识中心" :span="4">
        <div class="mod-grid">
          <div class="mod-stat">
            <span class="mod-num">{{ knowledge.total }}</span>
            <span class="mod-key">知识条目</span>
          </div>
          <div class="mod-sub">本周新增 {{ knowledge.thisWeek }} 条</div>
        </div>
      </BentoCard>

      <BentoCard title="邮件中心" :span="4">
        <div class="mod-grid">
          <div class="mod-stat">
            <span class="mod-num">{{ emails.week }}</span>
            <span class="mod-key">本周发送</span>
          </div>
          <div class="mod-sub">今日 {{ emails.today }} · 成功率 {{ emails.sr }}%</div>
        </div>
      </BentoCard>

    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import BentoCard from '@/components/Common/BentoCard.vue'
import { dashboardApi } from '@/api/dashboard'

const router = useRouter()

/* ───────────────── 图表坐标常量 ───────────────── */
const plotLeft = 40
const plotRight = 560
const plotTop = 44
const plotBottom = 179
const yMin = 0

/* ───────────────── Demo 有机数据（默认渲染） ───────────────── */
const dayLabels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

/* 运营问题类型中文映射（后端 distribution_charts.issueTypeDist 含英文 key） */
const ISSUE_TYPE_CN = {
  bug: 'BUG管理',
  系统错误: '系统错误',
  数据异常: '数据异常',
  流程阻塞: '流程阻塞',
  需求变更: '需求变更',
  spot_event: '热点投诉',
  temp_task: '临时交办',
  其他: '其他',
}
function pct(v, t) {
  return t ? Math.round((v / t) * 100) : 0
}
function rqStatusClass(name) {
  if (name === '开发中') return 'st-dev'
  if (name === '已上线') return 'st-live'
  if (name === '评审中') return 'st-review'
  return 'st-backlog'
}

const greeting = reactive({
  name: '陈工',
  sub: '本周共处理 127 条事项，较上周提升 14.3%。运营预警已从 8 条降至 5 条，闭环率 86.7%。',
  efficiency: 86.7,
  stats: [
    { value: '+14.3%', key: '周环比 ↑', cls: 'up' },
    { value: '23', key: '已完成工单', cls: 'up' },
    { value: '5', key: '待关注项', cls: 'down' },
    { value: '3', key: '明日截止', cls: 'accent' },
  ],
})

const liveStatus = ref([
  { color: 'red', text: '超期工单：某园区5G弱覆盖', time: '12m 前' },
  { color: 'amber', text: '新需求评审：云MAS扩容', time: '34m 前' },
  { color: 'green', text: '知识库同步：极客FAQ 已更新', time: '1h 前' },
  { color: 'red', text: '热点投诉升级：南京某园区', time: '2h 前' },
  { color: 'green', text: '会议纪要已归档：周例会', time: '3h 前' },
])

const kpis = ref([
  { num: 14, color: 'blue', label: '我的待办', delta: '↑ 3 较昨日', deltaType: 'up' },
  { num: 38, color: 'amber', label: '本周新增需求', delta: '评审中 11', deltaType: 'neutral' },
  { num: 9, color: 'blue', label: '进行中工单', delta: '本周完成 23', deltaType: 'up' },
  { num: 5, color: 'red', label: '运营预警', delta: '超期 2 条', deltaType: 'down' },
])

const trendValues = ref([18, 24, 21, 33, 29, 38, 42])
const trendLabels = ref([...dayLabels])

// 趋势图 Y 轴自适应：避免真实小数值被固定 15–45 轴裁到图底
const yMax = computed(() => {
  const m = Math.max(0, ...trendValues.value)
  return m <= 5 ? 5 : m <= 10 ? 10 : Math.ceil(m * 1.25)
})

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

/* ───────────────── 补充模块卡片数据（知识/邮件/人员/重点工作/任务中心/四核心卡片）───────────────── */
const knowledge = ref({ total: 0, thisWeek: 0 })
const emails = ref({ today: 0, week: 0, sr: 0 })
const personnel = ref({ org: 0, staff: 0, enabled: 0, orgs: [] })
const keyProjects = ref([])
const taskCenter = ref({ total: 0, overdue: 0, due_soon: 0, processing: 0, pending: 0, by_source: [], by_priority: [], by_status: [] })
// 四张核心卡片的丰富维度数据
const reqs = ref({ total: 0, thisWeek: 0, inReview: 0, completed: 0, overdueDev: 0 })
const issues = ref({ total: 0, pending: 0, processing: 0, resolved: 0, overdue: 0 })
const meetingStats = ref({ totalThisWeek: 0, today: 0, upcoming: 0, pendingMinutes: 0 })
const reqStatusDist = ref([])
const issueTypeDist = ref([])

/* ───────────────── 命令栏打字机 ───────────────── */
const cmdPhrases = [
  '搜索需求 / 工单 / 知识库…',
  '快速创建运营问题记录',
  '查询「政企宽带」相关需求',
  '查看今日待办与截止时间',
  '打开产品圣经 · 极客业务',
]
const cmdText = ref('')
let _ti = 0, _ci = 0, _erasing = false, _timer = null
function _tick() {
  const ph = cmdPhrases[_ti]
  if (!_erasing) {
    cmdText.value = ph.substring(0, ++_ci)
    if (_ci >= ph.length) { _erasing = true; _timer = setTimeout(_tick, 2200); return }
  } else {
    cmdText.value = ph.substring(0, --_ci)
    if (_ci <= 0) { _erasing = false; _ti = (_ti + 1) % cmdPhrases.length; _timer = setTimeout(_tick, 400); return }
  }
  _timer = setTimeout(_tick, _erasing ? 35 : 80)
}

/* ───────────────── 派生：问候语 / 日期 ───────────────── */
const helloText = computed(() => {
  const h = new Date().getHours()
  if (h < 5) return '凌晨好'
  if (h < 11) return '早上好'
  if (h < 13) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

/* ───────────────── 派生：趋势图几何 ───────────────── */
const trendGrid = computed(() => {
  const max = yMax.value
  const steps = 4
  return Array.from({ length: steps + 1 }, (_, i) => {
    const v = Math.round((max / steps) * (steps - i))
    return { value: v, y: plotBottom - ((v - yMin) / (max - yMin || 1)) * (plotBottom - plotTop) }
  })
})

const trendGeom = computed(() => {
  const vals = trendValues.value
  const n = vals.length || 1
  const xs = vals.map((_, i) => (n === 1 ? plotLeft : plotLeft + (i * (plotRight - plotLeft)) / (n - 1)))
  const ys = vals.map((v) => {
    const clamped = Math.max(yMin, Math.min(yMax.value, v))
    return plotBottom - ((clamped - yMin) / (yMax.value - yMin || 1)) * (plotBottom - plotTop)
  })
  const pts = xs.map((x, i) => ({ x, y: ys[i], label: trendLabels.value[i] || dayLabels[i], value: vals[i] }))
  const polyPoints = pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
  const areaPath =
    `M${pts[0].x.toFixed(1)},${plotBottom} ` +
    pts.map((p) => `L${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ') +
    ` L${pts[n - 1].x.toFixed(1)},${plotBottom} Z`
  return { pts, polyPoints, areaPath }
})

/* ───────────────── 防御式 API 接入 ───────────────── */
const goTo = (path) => router.push(path)

function mergeDashboard(res) {
  if (!res || typeof res !== 'object') return

  if (res.user_name) greeting.name = res.user_name
  if (res.greeting_sub) greeting.sub = res.greeting_sub
  if (typeof res.efficiency === 'number') greeting.efficiency = res.efficiency
  if (Array.isArray(res.greet_stats) && res.greet_stats.length) {
    greeting.stats = res.greet_stats.map((s) => ({
      value: s.value ?? '',
      key: s.key ?? '',
      cls: s.cls || 'accent',
    }))
  }

  if (Array.isArray(res.live_status) && res.live_status.length) {
    liveStatus.value = res.live_status.map((x) => ({
      color: x.color || 'green',
      text: x.text || '',
      time: x.time || '',
    }))
  }

  if (Array.isArray(res.kpis) && res.kpis.length) {
    kpis.value = res.kpis.map((k) => ({
      num: k.value ?? k.num ?? 0,
      color: k.color || 'blue',
      label: k.label || '',
      delta: k.delta || '',
      deltaType: k.delta_type || k.trend || 'neutral',
    }))
  }

  const normTrend = (t) => {
    if (Array.isArray(t) && t.length) {
      const vals = t.map((x) => (typeof x === 'object' ? (x.value ?? 0) : x))
      const labs = t.map((x, i) => (typeof x === 'object' ? (x.label || dayLabels[i]) : dayLabels[i]))
      return { vals, labs }
    }
    return null
  }
  if (res.trend_labels && Array.isArray(res.trend_labels) && res.trend_labels.length) {
    trendLabels.value = res.trend_labels
  }
  const tr = normTrend(res.trend) || normTrend(res.trend_values)
  if (tr) {
    trendValues.value = tr.vals
    if (!res.trend_labels) trendLabels.value = tr.labs
  }

  if (Array.isArray(res.todos) && res.todos.length) {
    const pMap = { '紧急': 'tp-urgent', '高优': 'tp-high', '中等': 'tp-med', '低优': 'tp-low' }
    todos.value = res.todos.map((t) => {
      const p = t.priority || '中等'
      return {
        priority: p,
        priorityClass: pMap[p] || 'tp-med',
        title: t.title || '未命名待办',
        deadline: t.deadline || '',
        owner: t.owner || '',
        overdue: !!t.overdue,
      }
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
    schedule.value = res.schedule.map((s) => ({
      time: s.time || '',
      title: s.title || '',
      loc: s.loc || s.location || '',
    }))
  }

  /* 补充模块卡片（知识/邮件/人员/重点工作/任务中心/四核心卡片）—— 后端已就绪数据 */
  if (res.module_stats && typeof res.module_stats === 'object') {
    const ms = res.module_stats
    if (ms.knowledge) knowledge.value = { total: ms.knowledge.total || 0, thisWeek: ms.knowledge.thisWeek || 0 }
    if (ms.emails) emails.value = { today: ms.emails.todaySent || 0, week: ms.emails.weekSent || 0, sr: ms.emails.successRate || 0 }
    if (ms.requirements) reqs.value = {
      total: ms.requirements.total || 0,
      thisWeek: ms.requirements.thisWeek || 0,
      inReview: ms.requirements.inReview || 0,
      completed: ms.requirements.completed || 0,
      overdueDev: ms.requirements.overdueDev || 0,
    }
    if (ms.issues) issues.value = {
      total: ms.issues.total || 0,
      pending: ms.issues.pending || 0,
      processing: ms.issues.processing || 0,
      resolved: ms.issues.resolved || 0,
      overdue: ms.issues.overdue || 0,
    }
    if (ms.meetings) meetingStats.value = {
      totalThisWeek: ms.meetings.totalThisWeek || 0,
      today: ms.meetings.today || 0,
      upcoming: ms.meetings.upcoming || 0,
      pendingMinutes: ms.meetings.pendingMinutes || 0,
    }
  }
  if (res.distribution_charts && typeof res.distribution_charts === 'object') {
    const dc = res.distribution_charts
    if (Array.isArray(dc.requirementStatusDist)) reqStatusDist.value = dc.requirementStatusDist
    if (Array.isArray(dc.issueTypeDist)) {
      issueTypeDist.value = dc.issueTypeDist.map((x) => ({
        name: ISSUE_TYPE_CN[x.name] || x.name,
        value: x.value,
      }))
    }
  }
  if (res.personnel && typeof res.personnel === 'object') {
    personnel.value = {
      org: res.personnel.org_count || 0,
      staff: res.personnel.staff_count || 0,
      enabled: res.personnel.enabled_staff || 0,
      orgs: res.personnel.org_list || [],
    }
  }
  if (res.progress_items && Array.isArray(res.progress_items.keyProjects)) {
    keyProjects.value = res.progress_items.keyProjects
  }
  if (res.task_center_dist && typeof res.task_center_dist === 'object') {
    const tcd = res.task_center_dist
    const findStatus = (arr, names) => {
      const o = (arr || []).find((x) => names.some((n) => (x.name || '').includes(n)))
      return o ? (o.value || 0) : 0
    }
    taskCenter.value = {
      total: tcd.total || 0,
      overdue: tcd.overdue || 0,
      due_soon: tcd.due_soon || 0,
      processing: findStatus(tcd.by_status, ['进行中']),
      pending: findStatus(tcd.by_status, ['待处理', '待办']),
      by_source: tcd.by_source || [],
      by_priority: tcd.by_priority || [],
      by_status: tcd.by_status || [],
    }
  }
}

async function loadData() {
  try {
    const res = await dashboardApi.getDashboard()
    // 响应已解包为业务对象；接口结构未知，做防御式覆盖，缺失字段静默回退 demo
    mergeDashboard(res)
  } catch (err) {
    // 接口异常或为空：保持 demo 数据渲染，不白屏
    console.warn('[HomeView] 看板接口不可用，已回退至本地 demo 数据', err)
  }
}

onMounted(() => {
  loadData()
  _timer = setTimeout(_tick, 600)
})

onUnmounted(() => {
  if (_timer) clearTimeout(_timer)
})
</script>

<style scoped>
.home-view {
  padding: 28px 32px 40px;
  max-width: 1440px;
  width: 100%;
}

/* ── 问候区 ── */
.greeting-tile {
  background: linear-gradient(135deg, #1e293b 0%, #334155 100%) !important;
  border: none !important;
  color: #f8fafc;
  position: relative;
  overflow: hidden;
}
.greeting-tile::after {
  content: '';
  position: absolute;
  top: -40%;
  right: -10%;
  width: 320px;
  height: 320px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(47, 111, 237, .18) 0%, transparent 70%);
  pointer-events: none;
}
.greeting-inner {
  position: relative;
  z-index: 1;
  padding: 28px 30px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.g-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.g-hello {
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -.3px;
  line-height: 1.25;
}
.g-hello span { color: #93c5fd; }
.g-sub {
  font-size: 14px;
  color: #94a3b8;
  line-height: 1.5;
  max-width: 440px;
  margin-top: 8px;
}
.g-eff { text-align: right; flex-shrink: 0; }
.g-eff-key { font-size: 12px; color: #64748b; margin-bottom: 4px; }
.g-eff-val {
  font-size: 32px;
  font-weight: 800;
  font-family: var(--font-mono);
  color: #4ade80;
  letter-spacing: -1px;
}
.g-eff-unit { font-size: 16px; color: #64748b; }
.g-stats { display: flex; gap: 28px; flex-wrap: wrap; }
.g-stat { display: flex; flex-direction: column; }
.g-stat-val { font-size: 22px; font-weight: 700; font-family: var(--font-mono); line-height: 1.2; }
.g-stat-val.up { color: #4ade80; }
.g-stat-val.down { color: #f87171; }
.g-stat-val.accent { color: #93c5fd; }
.g-stat-key { font-size: 11.5px; color: #64748b; margin-top: 2px; letter-spacing: .03em; }

.cmd-bar {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(255, 255, 255, .07);
  border: 1px solid rgba(255, 255, 255, .09);
  border-radius: 12px;
  padding: 10px 16px;
  backdrop-filter: blur(8px);
}
.cmd-bar-kbd { display: flex; gap: 4px; }
.kbd {
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 600;
  background: rgba(255, 255, 255, .1);
  border: 1px solid rgba(255, 255, 255, .14);
  color: #94a3b8;
  padding: 2px 7px;
  border-radius: 5px;
}
.cmd-bar-text { flex: 1; font-size: 13px; color: #64748b; min-width: 0; white-space: nowrap; overflow: hidden; }
.cmd-cursor {
  display: inline-block;
  width: 2px;
  height: 15px;
  background: #60a5fa;
  vertical-align: text-bottom;
  animation: blink 1s step-end infinite;
}
@keyframes blink { 50% { opacity: 0; } }

/* ── 实时动态 ── */
.ls-list { list-style: none; padding: 0 22px 18px; }
.ls-item { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--border-subtle); }
.ls-item:last-child { border-bottom: none; }
.ls-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.ls-dot.red { background: var(--danger); box-shadow: 0 0 6px rgba(217, 84, 77, .4); }
.ls-dot.amber { background: var(--warning); box-shadow: 0 0 6px rgba(217, 138, 31, .35); }
.ls-dot.green { background: var(--success); }
.ls-text { font-size: 13px; color: var(--text-primary); flex: 1; min-width: 0; }
.ls-time { font-size: 11.5px; color: var(--text-muted); font-family: var(--font-mono); white-space: nowrap; }

/* ── KPI 增量 ── */
.kpi-delta {
  font-size: 11.5px;
  font-weight: 600;
  margin-top: 4px;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.kpi-delta.up { color: var(--success); }
.kpi-delta.down { color: var(--danger); }
.kpi-delta.neutral { color: var(--text-muted); }

/* ── 快捷操作 ── */
.action-row {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  margin: 18px 0 4px;
}
.act-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 9px 18px;
  border-radius: 9px;
  font-size: 13px;
  font-weight: 600;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
  text-decoration: none;
  line-height: 1.35;
  font-family: var(--font-display);
}
.act-btn svg { width: 16px; height: 16px; flex-shrink: 0; }
.act-btn.primary { background: var(--accent); color: #fff; border-color: var(--accent); }
.act-btn.primary:hover { background: var(--accent-hover); transform: translateY(-1px); box-shadow: 0 6px 20px -4px rgba(47, 111, 237, .35); }
.act-btn.success { background: var(--success); color: #fff; }
.act-btn.success:hover { background: #0c885c; transform: translateY(-1px); }
.act-btn.warn { background: var(--warning); color: #fff; }
.act-btn.warn:hover { background: #c37a16; transform: translateY(-1px); }
.act-btn.ghost { background: transparent; color: var(--text-secondary); border-color: var(--border); }
.act-btn.ghost:hover { background: var(--bg-app); color: var(--text-primary); border-color: var(--text-muted); }

/* ── 趋势图 ── */
.chart-wrap { padding: 8px 4px 4px; }
.chart-svg { width: 100%; height: 220px; display: block; }
.chart-legend {
  display: flex;
  gap: 20px;
  padding: 12px 22px 0;
  border-top: 1px solid var(--border-subtle);
  margin-top: 4px;
}
.legend-item { display: flex; align-items: center; gap: 7px; font-size: 12px; color: var(--text-secondary); }
.legend-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }

/* ── 甜甜圈 ── */
.donut-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 4px 0 16px;
}
.donut-svg { width: 180px; height: 180px; }
.donut-legend {
  margin-top: 12px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 20px;
  width: 100%;
  padding: 0 22px;
}
.dl-item { display: flex; align-items: center; gap: 7px; font-size: 12.5px; color: var(--text-secondary); }
.dl-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
.dl-val { font-family: var(--font-mono); font-weight: 600; color: var(--text-primary); margin-left: auto; }

/* ── 待办 ── */
.todo-list { list-style: none; padding: 0 22px 16px; }
.todo-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 11px 0;
  border-bottom: 1px solid var(--border-subtle);
  transition: background var(--transition-fast);
}
.todo-item:last-child { border-bottom: none; }
.todo-item:hover { background: rgba(47, 111, 237, .02); margin: 0 -22px; padding: 11px 22px; border-radius: 8px; border-color: transparent; }
.todo-priority {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 5px;
  flex-shrink: 0;
  line-height: 1.5;
  white-space: nowrap;
  margin-top: 1px;
}
.tp-urgent { background: var(--danger-soft); color: var(--danger); }
.tp-high { background: var(--warning-soft); color: var(--warning); }
.tp-med { background: var(--accent-soft); color: var(--accent); }
.tp-low { background: var(--border-subtle); color: var(--text-muted); }
.todo-body { flex: 1; min-width: 0; }
.todo-title { font-size: 13.5px; color: var(--text-primary); line-height: 1.4; word-break: break-word; }
.todo-meta { font-size: 11.5px; color: var(--text-muted); margin-top: 3px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.todo-deadline { color: var(--danger); font-weight: 500; }
.todo-overdue { color: var(--danger); background: var(--danger-soft); padding: 0 6px; border-radius: 4px; }

/* ── 预警 ── */
.alert-list { list-style: none; padding: 0 22px 16px; }
.alert-item { display: flex; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--border-subtle); }
.alert-item:last-child { border-bottom: none; }
.alert-sev {
  font-size: 10px;
  font-weight: 700;
  padding: 3px 9px;
  border-radius: 5px;
  flex-shrink: 0;
  white-space: nowrap;
}
.as-red { background: var(--danger-soft); color: var(--danger); }
.as-amber { background: var(--warning-soft); color: var(--warning); }
.as-green { background: var(--success-soft); color: var(--success); }
.alert-body { flex: 1; min-width: 0; }
.alert-msg { font-size: 13px; color: var(--text-primary); }
.alert-count { font-size: 12px; font-family: var(--font-mono); font-weight: 600; margin-top: 2px; color: var(--text-secondary); }

/* ── 快捷入口 ── */
.qa-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; padding: 14px 22px 18px; }
.qa-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 8px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--surface);
  cursor: pointer;
  transition: all var(--transition-fast);
  text-decoration: none;
}
.qa-btn:hover { border-color: var(--accent); background: var(--accent-soft); transform: translateY(-1px); }
.qa-icon { width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 17px; }
.qa-label { font-size: 11.5px; color: var(--text-secondary); font-weight: 500; text-align: center; }

/* ── 最近需求 ── */
.req-wrap { padding: 0 22px 16px; overflow-x: auto; }
.req-table { width: 100%; border-collapse: collapse; }
.req-table th {
  text-align: left;
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: .06em;
  padding: 10px 10px 10px 0;
  border-bottom: 1px solid var(--border);
}
.req-table td { font-size: 13px; padding: 12px 10px; border-bottom: 1px solid var(--border-subtle); color: var(--text-primary); vertical-align: middle; }
.req-table tr:last-child td { border-bottom: none; }
.req-name { font-weight: 500; max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.req-owner { color: var(--text-secondary); font-size: 12.5px; }
.status-tag { font-size: 11px; font-weight: 600; padding: 3px 9px; border-radius: 5px; display: inline-block; white-space: nowrap; }
.st-review { background: var(--accent-soft); color: var(--accent); }
.st-dev { background: var(--warning-soft); color: var(--warning); }
.st-backlog { background: var(--border-subtle); color: var(--text-muted); }
.st-live { background: var(--success-soft); color: var(--success); }
.req-date { font-size: 12px; color: var(--text-muted); font-family: var(--font-mono); white-space: nowrap; }

  /* ── 需求概览整合卡（趋势图 + 最近需求 同卡）── */
  .req-overview {
    display: grid;
    grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr);
    gap: 28px;
    align-items: start;
  }
  @media (max-width: 1080px) {
    .req-overview { grid-template-columns: 1fr; gap: 18px; }
  }
  .ro-legend { padding: 10px 0 0; }
  .ro-reqs-h {
    font-size: 11.5px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: .05em;
    margin-bottom: 10px;
  }
  .ro-req-wrap { padding: 0; overflow-x: auto; }
  .ro-reqs .req-table th { padding-top: 0; }

/* ── 今日日程 ── */
.sched-list { list-style: none; padding: 0 22px 16px; }
.sched-item { display: flex; gap: 14px; padding: 13px 0; border-bottom: 1px solid var(--border-subtle); align-items: flex-start; }
.sched-item:last-child { border-bottom: none; }
.sched-time { font-size: 13px; font-weight: 700; font-family: var(--font-mono); color: var(--accent); width: 52px; flex-shrink: 0; padding-top: 1px; }
.sched-info { flex: 1; min-width: 0; }
.sched-title { font-size: 13.5px; color: var(--text-primary); line-height: 1.35; }
  .sched-loc { font-size: 11.5px; color: var(--text-muted); margin-top: 3px; display: flex; align-items: center; gap: 5px; }

  /* ── 补充模块卡片（知识/邮件/人员）── */
  .mod-grid { display: flex; flex-direction: column; gap: 6px; padding: 6px 4px; }
  .mod-stat { display: flex; align-items: baseline; gap: 8px; }
  .mod-num { font-size: 30px; font-weight: 800; font-family: var(--font-mono); color: var(--text-primary); line-height: 1.1; }
  .mod-key { font-size: 12.5px; color: var(--text-muted); }
  .mod-sub { font-size: 12.5px; color: var(--text-secondary); }

  /* ── 任务中心 / 运营工单 共用空态 ── */
  .tc-empty { font-size: 12.5px; color: var(--text-muted); padding: 8px 0; }

  /* ── 重点工作进度 ── */
  .kp-list { list-style: none; padding: 4px 4px; display: flex; flex-direction: column; gap: 14px; }
  .kp-item { display: flex; flex-direction: column; gap: 6px; }
  .kp-head { display: flex; align-items: center; justify-content: space-between; }
  .kp-name { font-size: 13px; color: var(--text-primary); font-weight: 500; }
  .kp-pct { font-size: 12.5px; font-family: var(--font-mono); color: var(--accent); font-weight: 700; }
  .kp-bar { height: 6px; background: var(--border-subtle); border-radius: 4px; overflow: hidden; }
  .kp-fill { display: block; height: 100%; background: linear-gradient(90deg, var(--accent), #6aa0ff); border-radius: 4px; }
  .kp-empty { font-size: 12.5px; color: var(--text-muted); padding: 8px 0; }

  /* ── 分区标题 ── */
  .section-title {
    display: flex;
    align-items: baseline;
    gap: 12px;
    padding: 6px 4px 0;
  }
  .st-main { font-size: 16px; font-weight: 700; color: var(--text-primary); letter-spacing: -.2px; }
  .st-sub { font-size: 12px; color: var(--text-muted); }

  /* ── 核心卡片高亮（与全站 .card 视觉一致，仅以左侧强调条 + 徽标突出）── */
  .card-highlight {
    border-color: var(--border) !important;
    box-shadow: inset 3px 0 0 var(--accent), var(--shadow-card);
    background: var(--surface);
  }
  .card-highlight:hover {
    box-shadow: inset 3px 0 0 var(--accent-hover), var(--shadow-elevated);
    border-color: var(--border) !important;
    transform: translateY(-2px);
  }

  /* ── 需求工单（增强）── */
  .rq-stats, .op-stats, .mt-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 16px; }
  .rq-stat, .op-stat, .mt-stat { display: flex; flex-direction: column; gap: 2px; }
  .rq-stat b, .op-stat b, .mt-stat b { font-size: 22px; font-weight: 800; font-family: var(--font-mono); color: var(--text-primary); line-height: 1.1; }
  .rq-stat span, .op-stat span, .mt-stat span { font-size: 11px; color: var(--text-muted); }
  .rq-stat.danger b, .op-stat.danger b, .mt-stat.danger b { color: var(--danger); }
  .rq-dist-h, .op-dist-h { font-size: 11.5px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: .05em; margin-bottom: 8px; }
  .rq-bar, .op-bar { display: grid; grid-template-columns: 64px 1fr 30px; align-items: center; gap: 10px; font-size: 12.5px; margin-bottom: 7px; }
  .rq-bar-label, .op-bar-label { color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .rq-bar-track, .op-bar-track { height: 7px; background: var(--border-subtle); border-radius: 4px; overflow: hidden; }
  .rq-bar-fill, .op-bar-fill { display: block; height: 100%; background: var(--accent); border-radius: 4px; transition: width var(--transition-normal); }
  .rq-bar-fill.st-backlog { background: var(--text-muted); }
  .rq-bar-fill.st-dev { background: var(--warning); }
  .rq-bar-fill.st-review { background: var(--accent); }
  .rq-bar-fill.st-live { background: var(--success); }
  .rq-bar-val, .op-bar-val { text-align: right; font-family: var(--font-mono); color: var(--text-primary); font-weight: 600; }

  /* ── 会议日程（增强）── */
  .mt-list { list-style: none; margin-top: 14px; padding: 0; }
  .mt-item { display: flex; gap: 14px; padding: 11px 0; border-bottom: 1px solid var(--border-subtle); align-items: flex-start; }
  .mt-item:last-child { border-bottom: none; }
  .mt-time { font-size: 13px; font-weight: 700; font-family: var(--font-mono); color: var(--accent); width: 52px; flex-shrink: 0; padding-top: 1px; }
  .mt-info { flex: 1; min-width: 0; }
  .mt-title { font-size: 13.5px; color: var(--text-primary); line-height: 1.35; }
  .mt-loc { font-size: 11.5px; color: var(--text-muted); margin-top: 3px; display: flex; align-items: center; gap: 5px; }
  .mt-empty { font-size: 12.5px; color: var(--text-muted); padding: 12px 0; }
</style>
