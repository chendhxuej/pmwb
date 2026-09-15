<template>
  <div class="home-view">
    <div class="bento-grid">

      <!-- ══ L1 问候层（高度压缩：内容两端对齐，与右侧动态卡高度对齐）══ -->
      <BentoCard class="greeting-tile" :span="8" flat :body-padding="'0'">
        <div class="greeting-inner">
          <div class="g-top">
            <div>
              <div class="g-hello">{{ helloText }}，<span>{{ greeting.name }}</span></div>
              <div class="g-sub">{{ greeting.sub }}</div>
            </div>
            <div class="g-eff">
              <div class="g-eff-key">运营闭环率（含调研）</div>
              <div class="g-eff-val">{{ greeting.efficiency }}<span class="g-eff-unit">%</span></div>
            </div>
          </div>
          <div class="g-bottom">
            <div class="g-stats">
              <div class="g-stat" v-for="(s, i) in greeting.stats" :key="i">
                <span class="g-stat-val" :class="s.cls">{{ s.value }}</span>
                <span class="g-stat-key">{{ s.key }}</span>
              </div>
            </div>
            <div class="g-cmd" @click="cmdOpen = true">
              <span class="kbd">Ctrl</span><span class="kbd">K</span>&nbsp;{{ cmdText }}<span class="cmd-cursor"></span>
            </div>
          </div>
        </div>
      </BentoCard>

      <BentoCard title="实时动态 · 多源" :span="4" :body-padding="'12px 22px 14px'">
        <template #action><a class="card-action" @click="goTo('/task-center')">更多 →</a></template>
        <ul class="ls-list">
          <li class="ls-item" v-for="(item, i) in liveStatus" :key="i">
            <span class="pm-dot" :class="item.color" style="margin-top:4px"></span>
            <div class="ls-body">
              <div class="ls-text"><span class="ls-src" :class="srcClass(item.source)">{{ item.source }}</span>{{ item.text }}</div>
              <div class="ls-foot"><span class="ls-time">{{ item.time }}</span></div>
            </div>
          </li>
          <li v-if="!liveStatus.length" class="tc-empty">暂无动态</li>
        </ul>
      </BentoCard>

      <!-- ══ L2 指标层（KPI 全真实值）══ -->
      <BentoCard
        v-for="(k, i) in kpis"
        :key="'kpi' + i"
        class="kpi-card"
        :span="3"
        flat
      >
        <div class="kpi-num" :class="k.color">{{ k.num }}</div>
        <div class="kpi-label">{{ k.label }}</div>
        <div class="kpi-trend" :class="k.deltaType">{{ k.delta }}</div>
      </BentoCard>

      <!-- ══ L3 模块概览（紧贴指标行 · 6 卡补满两行）══ -->
      <div class="row-label" style="grid-column:1/-1">
        <span class="rl-t">模块概览</span>
        <span class="rl-s">13 个一级模块全部覆盖 · AI 中心与业务资料库为本轮新增</span>
        <span class="rl-line"></span>
      </div>

      <BentoCard :span="4" :body-padding="'14px 22px 16px'" class="mod-tile">
        <div class="mod-grid">
          <div class="mod-stat"><span class="mod-num">{{ personnel.staff }}</span><span class="mod-key">在职人员 · 人员中台</span></div>
          <div class="mod-sub"><b>{{ personnel.org }}</b> 个组织 · 订单中心 / 电子协议 / CRM / BOSS 等条线全覆盖</div>
        </div>
      </BentoCard>

      <BentoCard :span="4" :body-padding="'14px 22px 16px'" class="mod-tile">
        <div class="mod-grid">
          <div class="mod-stat"><span class="mod-num">{{ knowledge.total }}</span><span class="mod-key">知识条目 · 知识中心</span></div>
          <div class="mod-sub"><b>{{ knowledge.domainCount }}</b> 个业务领域 · 本周沉淀 <b>{{ knowledge.thisWeek }}</b> 条 · 需求/运营自动归档汇入</div>
        </div>
      </BentoCard>

      <BentoCard :span="4" :body-padding="'14px 22px 16px'" class="mod-tile">
        <div class="mod-grid">
          <div class="mod-stat"><span class="mod-num">{{ emails.sr }}<span class="mod-unit">%</span></span><span class="mod-key">邮件中心</span></div>
          <div class="mod-sub">本周发送 <b>{{ emails.week }}</b> · 今日 {{ emails.today }} · 12 类场景模板</div>
        </div>
      </BentoCard>

      <BentoCard :span="4" :body-padding="'14px 22px 16px'" class="mod-tile mod-clickable" @click.native="goTo('/ai-center')">
        <div class="mod-grid">
          <div class="mod-stat"><span class="mod-num">{{ aiCenter.total }}</span><span class="mod-key">AI 总结 · AI 中心<span class="new-badge">NEW</span></span></div>
          <div class="mod-sub">本周新增 <b>{{ aiCenter.thisWeek }}</b> 篇 · 可用模型 <b>{{ aiCenter.modelCount }}</b> 个 · 自动归档 Obsidian</div>
        </div>
      </BentoCard>

      <BentoCard :span="4" :body-padding="'14px 22px 16px'" class="mod-tile mod-clickable" @click.native="goTo('/material-library')">
        <div class="mod-grid">
          <div class="mod-stat"><span class="mod-num">{{ materials.total }}</span><span class="mod-key">资料总数 · 业务资料库<span class="new-badge">NEW</span></span></div>
          <div class="mod-sub"><b>{{ materials.categoryCount }}</b> 个分类 · 本周新增 <b>{{ materials.thisWeek }}</b> 份 · 接口规范/操作手册自动归档</div>
        </div>
      </BentoCard>

      <BentoCard :span="4" :body-padding="'14px 22px 16px'" class="mod-tile">
        <div class="mod-grid">
          <div class="mod-stat"><span class="mod-num">{{ researchStats.total }}</span><span class="mod-key">调研工单 · 一线调研</span></div>
          <div class="mod-sub">待处理 <b>{{ researchStats.pending }}</b> · 超期 <span class="hot">{{ researchStats.overdue }}</span> · 已并入任务中心来源分布</div>
        </div>
      </BentoCard>

      <!-- 快捷操作（紧凑行）-->
      <div class="action-row" style="grid-column:1/-1">
        <button class="pm-btn primary" @click="goTo('/requirement-delivery')">＋ 新增需求·工单</button>
        <button class="pm-btn primary" @click="goTo('/meeting')">＋ 新增会议</button>
        <button class="pm-btn primary" @click="goTo('/operation')">＋ 新增运营问题</button>
        <button class="pm-btn" @click="goTo('/ai-center/qa')">✦ AI 问答</button>
        <button class="pm-btn" @click="goTo('/knowledge-center')">知识中心 →</button>
      </div>

      <!-- ══ L4 核心工作区 ══ -->
      <div class="row-label" style="grid-column:1/-1">
        <span class="rl-t">核心工作区</span>
        <span class="rl-s">任务中心 / 需求工单 / 运营工单 / 会议日程</span>
        <span class="rl-line"></span>
      </div>

      <!-- 任务中心 -->
      <BentoCard :span="6" :body-padding="'14px 20px 16px'">
        <template #head><span class="card-label">任务中心</span></template>
        <template #action><a class="card-action" @click="goTo('/task-center')">全部任务 →</a></template>
        <div class="stat4">
          <div class="stat"><b>{{ taskCenter.total }}</b><span>共待办</span></div>
          <div class="stat"><b>{{ taskCenter.processing }}</b><span>进行中</span></div>
          <div class="stat"><b>{{ taskCenter.pending }}</b><span>待处理</span></div>
          <div class="stat"><b :class="{ danger: taskCenter.overdue > 0 }">{{ taskCenter.overdue }}</b><span>超期</span></div>
        </div>
        <div class="dist-h">来源分布</div>
        <div class="bar" v-for="(s, i) in taskCenter.by_source" :key="i">
          <span class="bar-k">{{ s.name }}</span>
          <span class="bar-track"><i class="bar-fill" :style="{ width: pct(s.value, taskCenter.total) + '%' }"></i></span>
          <span class="bar-v">{{ s.value }}</span>
        </div>
        <div v-if="!taskCenter.by_source.length" class="tc-empty">暂无来源分布</div>
        <div class="detail-box" v-if="overdueTop3.length">
          <div class="detail-h">超期 TOP 3 <span class="cnt">共 {{ taskCenter.overdue }} 条</span></div>
          <div class="d-item" v-for="(o, i) in overdueTop3" :key="'od' + i">
            <span class="d-pri" :class="priClass(o.priority)">{{ o.priority }}</span>
            <span class="d-t" :title="o.title">{{ o.title }}</span>
            <span class="d-date">{{ o.date }}</span>
          </div>
        </div>
      </BentoCard>

      <!-- 需求工单 -->
      <BentoCard :span="6" :body-padding="'14px 20px 16px'">
        <template #head><span class="card-label">需求工单</span></template>
        <template #action><a class="card-action" @click="goTo('/requirement-delivery')">需求与交付 →</a></template>
        <div class="stat4">
          <div class="stat"><b>{{ reqs.total }}</b><span>需求总数</span></div>
          <div class="stat"><b>{{ reqs.thisWeek }}</b><span>本周新增</span></div>
          <div class="stat"><b>{{ reqs.inReview }}</b><span>跟踪中</span></div>
          <div class="stat"><b :class="{ danger: reqs.overdueDev > 0 }">{{ reqs.overdueDev }}</b><span>超期开发</span></div>
        </div>
        <div class="dist-h">状态分布</div>
        <div class="bar" v-for="(s, i) in reqStatusDist" :key="'rq' + i">
          <span class="bar-k">{{ s.name }}</span>
          <span class="bar-track"><i class="bar-fill" :class="rqStatusClass(s.name)" :style="{ width: pct(s.value, reqs.total) + '%' }"></i></span>
          <span class="bar-v">{{ s.value }}</span>
        </div>
        <div v-if="!reqStatusDist.length" class="tc-empty">暂无需求状态分布</div>
        <div class="detail-box">
          <div class="detail-h ok">主动优化</div>
          <div class="stat4" style="margin-bottom:0">
            <div class="stat"><b>{{ activeOpts.total }}</b><span>总数</span></div>
            <div class="stat"><b>{{ activeOpts.pending }}</b><span>待评估</span></div>
            <div class="stat"><b class="ok">{{ activeOpts.adopted }}</b><span>已采纳</span></div>
            <div class="stat"><b>{{ activeOpts.rejected }}</b><span>不采纳</span></div>
          </div>
        </div>
      </BentoCard>

      <!-- 运营工单 -->
      <BentoCard :span="6" :body-padding="'14px 20px 16px'">
        <template #head>
          <span class="head-extra">
            <span class="card-label">运营工单</span>
            <span class="caliber" v-if="issues.researchTotal">含一线调研 {{ issues.total - issues.researchTotal }} + {{ issues.researchTotal }}</span>
          </span>
        </template>
        <template #action><a class="card-action" @click="goTo('/operation')">运营监控 →</a></template>
        <div class="stat4">
          <div class="stat"><b>{{ issues.total }}</b><span>问题总数</span></div>
          <div class="stat"><b>{{ issues.processing }}</b><span>处理中</span></div>
          <div class="stat"><b class="ok">{{ issues.resolved }}</b><span>已解决</span></div>
          <div class="stat"><b :class="{ danger: issues.overdue > 0 }">{{ issues.overdue }}</b><span>超期</span></div>
        </div>
        <div class="dist-h">类型分布</div>
        <div class="bar" v-for="(s, i) in issueTypeDist" :key="'it' + i">
          <span class="bar-k">{{ s.name }}</span>
          <span class="bar-track"><i class="bar-fill" :style="{ width: pct(s.value, issues.total) + '%' }"></i></span>
          <span class="bar-v">{{ s.value }}</span>
        </div>
        <div v-if="!issueTypeDist.length" class="tc-empty">暂无类型分布</div>
      </BentoCard>

      <!-- 会议日程 -->
      <BentoCard :span="6" :body-padding="'14px 20px 16px'">
        <template #head>
          <span class="head-extra">
            <span class="card-label">会议日程</span>
            <span class="caliber">今日 {{ meetingStats.today }} 场</span>
          </span>
        </template>
        <template #action><a class="card-action" @click="goTo('/meeting')">日历 →</a></template>
        <div class="stat4" style="margin-bottom:10px">
          <div class="stat"><b>{{ meetingStats.totalThisWeek }}</b><span>本周会议</span></div>
          <div class="stat"><b>{{ meetingStats.today }}</b><span>今日</span></div>
          <div class="stat"><b>{{ meetingStats.upcoming }}</b><span>即将召开</span></div>
          <div class="stat"><b :class="{ danger: meetingStats.pendingMinutes > 0 }">{{ meetingStats.pendingMinutes }}</b><span>待写纪要</span></div>
        </div>
        <template v-if="schedule.length">
          <div class="mt-item" v-for="(s, i) in schedule" :key="'sch' + i">
            <span class="mt-time">{{ s.time }}</span>
            <div class="mt-info">
              <div class="mt-title">{{ s.title }}</div>
              <div class="mt-loc">{{ s.loc }}</div>
            </div>
          </div>
        </template>
        <div class="mt-item" v-else-if="upcomingMeeting">
          <span class="mt-time">{{ upcomingMeeting.date }}</span>
          <div class="mt-info">
            <div class="mt-title">{{ upcomingMeeting.title }}</div>
            <div class="mt-loc">即将召开</div>
          </div>
        </div>
        <div class="mt-item" v-else>
          <div class="mt-info"><div class="mt-title tc-empty">今日暂无会议安排</div></div>
        </div>
        <template v-if="pendingMinutes.length">
          <div class="mt-sep">待写纪要（{{ meetingStats.pendingMinutes }}）</div>
          <div class="mt-item" v-for="(m, i) in pendingMinutes" :key="'pm' + i">
            <span class="mt-time">{{ m.date }}</span>
            <div class="mt-info"><div class="mt-title">{{ m.title }}</div></div>
            <span class="pm-tag amber" style="cursor:pointer" @click="goTo('/meeting')">去补录</span>
          </div>
        </template>
      </BentoCard>

      <!-- ══ L5 分析层 ══ -->
      <!-- 需求概览：趋势图 + 最近需求 整合为单卡 -->
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
            <div class="chart-note">近 7 日需求新增趋势（真实数据）</div>
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
                    <td><StatusBadge :label="r.status" :type="rqStatusTone(r.status)" size="small" /></td>
                    <td class="req-date">{{ r.date }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </BentoCard>

      <!-- 今日聚焦（7 栏）-->
      <BentoCard title="今日聚焦" :span="7">
        <template #action>
          <span class="head-extra">
            <span class="caliber">个人待办 + 任务中心合并排序</span>
            <a class="card-action" @click="goTo('/task-center')">任务中心 →</a>
          </span>
        </template>
        <div class="fz-item" v-for="(f, i) in focusItems" :key="'fz' + i">
          <span class="d-pri" :class="priClass(f.priority)">{{ f.priority }} {{ focusTag(f) }}</span>
          <span class="d-t" :title="f.title">{{ f.title }}</span>
          <span class="d-date" :class="{ ok: !f.overdue }">{{ f.date_text }}</span>
        </div>
        <div v-if="!focusItems.length" class="tc-empty">今日暂无聚焦事项，去任务中心看看 →</div>
      </BentoCard>

      <!-- 重点工作（5 栏）-->
      <BentoCard title="重点工作进度" :span="5">
        <template #action><a class="card-action" @click="goTo('/key-works')">更多 →</a></template>
        <ul class="kp-list">
          <li class="kp-item" v-for="(p, i) in keyProjects" :key="i">
            <div class="kp-head">
              <span class="kp-name">{{ p.name }}</span>
              <span class="kp-pct">{{ p.percent }}%</span>
            </div>
            <div class="kp-bar"><i class="kp-fill" :style="{ width: p.percent + '%' }"></i></div>
          </li>
          <li v-if="!keyProjects.length" class="tc-empty">暂无进行中的重点工作</li>
        </ul>
      </BentoCard>

    </div>
    <CommandPalette v-model="cmdOpen" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import BentoCard from '@/components/Common/BentoCard.vue'
import CommandPalette from '@/components/Common/CommandPalette.vue'
import StatusBadge from '@/components/Common/StatusBadge.vue'
import { dashboardApi } from '@/api/dashboard'
import { researchApi } from '@/api/research'

const router = useRouter()

/* ───────────────── 全局命令面板（⌘K / Ctrl+K）──────────────── */
const cmdOpen = ref(false)
function onCmdKey(e) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    cmdOpen.value = true
  }
}

/* ───────────────── 图表坐标常量 ───────────────── */
const plotLeft = 40
const plotRight = 560
const plotTop = 44
const plotBottom = 179
const yMin = 0

/* ───────────────── Demo 有机数据（默认渲染，接口成功后被真实数据覆盖） ───────────────── */
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
  topic_analysis: '专题分析',
  其他: '其他',
}
function pct(v, t) {
  return t ? Math.round((v / t) * 100) : 0
}
/* 需求状态分布条语义色（design.css bar-fill：ok 绿 / warn 琥珀 / mute 灰 / 默认蓝） */
function rqStatusClass(name) {
  if (name === '已上线') return 'ok'
  if (name === '开发中') return 'warn'
  if (name === '待排期' || name === '已暂停') return 'mute'
  return ''
}
function rqStatusTone(name) {
  if (name === '开发中') return 'warning'
  if (name === '已上线') return 'success'
  if (name === '评审中') return 'primary'
  return 'info'
}
/* 优先级徽章色（d-pri：P0 红 / P1 琥珀 / P2 蓝 / P3 灰，兼容中文） */
const PRI_CLASS = { P0: '', P1: 'p1', P2: 'p2', P3: 'p3', 紧急: '', 高优: 'p1', 中等: 'p2', 低优: 'p3' }
function priClass(p) {
  return PRI_CLASS[p] ?? 'p3'
}
/* 动态来源徽章色（ls-src：调研/运营 红 / 会议 蓝 / 需求 绿 / 知识 琥珀） */
const SRC_CLASS = { 调研: 'op', 运营: 'op', 会议: 'mt', 需求: 'rq', 知识: 'kn' }
function srcClass(s) {
  return SRC_CLASS[s] || 'op'
}
function focusTag(f) {
  if (f.overdue) return '超期'
  return f.date_text === '今日' ? '今日' : '本周'
}

const greeting = reactive({
  name: '老大',
  sub: '本周共 2 场会议，运营问题 101 条（含一线调研 6，待处理 2），我的待办 105 条、42 条超期。',
  efficiency: 55.4,
  stats: [
    { value: '2', key: '本周会议', cls: 'accent' },
    { value: '42', key: '超期任务', cls: 'down' },
    { value: '19', key: '3日内到期', cls: 'up' },
    { value: '5', key: '待写纪要', cls: 'down' },
  ],
})

const liveStatus = ref([
  { color: 'red', text: 'RES-20260901-506 领导调研反馈已超期', time: '09-01', source: '调研' },
  { color: 'amber', text: 'TASK-2026091416284450109 能运交互相关接口详情梳理', time: '18 小时前', source: '运营' },
  { color: 'amber', text: '「商客业务全省培训」已召开，纪要待补', time: '09-10', source: '会议' },
  { color: 'green', text: '商客重点产品三个月信控销户需求 已上线', time: '09-14', source: '需求' },
])

const kpis = ref([
  { num: 105, color: 'blue', label: '我的待办（任务中心）', delta: '超期 42 · 今日到期 1', deltaType: 'down' },
  { num: 2, color: 'amber', label: '本周会议', delta: '待写纪要 5', deltaType: 'neutral' },
  { num: 5, color: 'amber', label: '跟踪中需求', delta: '开发中 17 · 超期开发 11', deltaType: 'neutral' },
  { num: '96.7%', color: 'green', label: '邮件 7 日成功率', delta: '本周发送 3', deltaType: 'neutral' },
])

const trendValues = ref([18, 24, 21, 33, 29, 38, 42])
const trendLabels = ref([...dayLabels])

// 趋势图 Y 轴自适应：避免真实小数值被固定 15–45 轴裁到图底
const yMax = computed(() => {
  const m = Math.max(0, ...trendValues.value)
  return m <= 5 ? 5 : m <= 10 ? 10 : Math.ceil(m * 1.25)
})

const recentReqs = ref([
  { name: '关于新增特殊签名和高风险客户合规数据维护的需求', owner: '张振', status: '已上线', date: '09-14' },
  { name: '关于新增集团下发的风险库数据支持在行短实名制菜单查询的需求', owner: '张振', status: '已上线', date: '09-14' },
  { name: '关于商客重点产品三个月信控销户的需求', owner: '童振彦', status: '已上线', date: '09-14' },
  { name: '关于电子协议统一条款格式的需求（第一批）', owner: '方舟', status: '评审中', date: '09-12' },
  { name: '关于淮安订单中心集客增值业务结算系统功能扩展的需求', owner: '李能禾', status: '评审中', date: '09-11' },
])

const schedule = ref([])
const upcomingMeeting = ref(null)
const pendingMinutes = ref([])

const focusItems = ref([
  { priority: 'P0', title: '[COMP-20260914-250] 【投诉风险】后台执行批量销户，误操作手机用户被动销户的问题', date_text: '超期 1 天', overdue: true },
  { priority: 'P0', title: '[BUG-20260824-520] HDICT业务办理后自动到期失效导致套餐费无法收取的问题', date_text: '超期 5 天', overdue: true },
  { priority: 'P1', title: '需求方案评审 — 补录会议纪要', date_text: '今日', overdue: false },
  { priority: 'P2', title: '[里程碑] 电子协议系统补推机制开发完成', date_text: '超期 3 天', overdue: true },
  { priority: 'P3', title: '完成一键保障上报业务上下文字段确认及关联改造方案', date_text: '09-18', overdue: false },
  { priority: 'P3', title: '评估电子协议系统 UI 改造教学指引能力建设方案', date_text: '09-19', overdue: false },
])

/* ───────────────── 模块概览 / 核心工作区数据 ───────────────── */
const knowledge = ref({ total: 0, thisWeek: 0, domainCount: 0 })
const emails = ref({ today: 0, week: 0, sr: 0 })
const aiCenter = ref({ total: 0, thisWeek: 0, modelCount: 0 })
const materials = ref({ total: 0, thisWeek: 0, categoryCount: 0 })
const personnel = ref({ org: 0, staff: 0, enabled: 0, orgs: [] })
const keyProjects = ref([])
const taskCenter = ref({ total: 0, overdue: 0, due_soon: 0, processing: 0, pending: 0, by_source: [], overdue_items: [] })
const reqs = ref({ total: 0, thisWeek: 0, inReview: 0, completed: 0, overdueDev: 0 })
const issues = ref({ total: 0, pending: 0, processing: 0, resolved: 0, overdue: 0, researchTotal: 0 })
const meetingStats = ref({ totalThisWeek: 0, today: 0, upcoming: 0, pendingMinutes: 0 })
const activeOpts = ref({ total: 0, pending: 0, adopted: 0, rejected: 0, thisWeek: 0 })
const reqStatusDist = ref([])
const issueTypeDist = ref([])

/* 超期 TOP 3（deadline "2026-09-14" → "09-14"） */
const overdueTop3 = computed(() =>
  (taskCenter.value.overdue_items || []).slice(0, 3).map((o) => ({
    priority: o.priority || 'P3',
    title: o.title || '',
    date: (o.deadline || '').slice(5, 10),
  }))
)

/* ───────────────── 命令栏打字机 ───────────────── */
const cmdPhrases = [
  '搜索需求 / 工单 / 知识库…',
  '快速创建运营问题记录',
  '查询「商客专区」相关需求',
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

/* ───────────────── 派生：问候语 ───────────────── */
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
      source: x.source || '',
    }))
  }

  if (Array.isArray(res.kpis) && res.kpis.length) {
    kpis.value = res.kpis.map((k) => ({
      num: k.value_text || (k.value ?? k.num ?? 0),
      color: k.color || 'blue',
      label: k.label || '',
      delta: k.delta || '',
      deltaType: k.delta_type || k.trend || 'neutral',
    }))
  }

  if (Array.isArray(res.focus_items)) {
    focusItems.value = res.focus_items.map((f) => ({
      priority: f.priority || 'P3',
      title: f.title || '',
      date_text: f.date_text || '',
      overdue: !!f.overdue,
      source_url: f.source_url || '',
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

  if (Array.isArray(res.recent_requirements) && res.recent_requirements.length) {
    recentReqs.value = res.recent_requirements.map((r) => ({
      name: r.name || r.title || '',
      owner: r.owner || '',
      status: r.status || '',
      date: (r.date || r.updated_at || '').slice(5, 10) || r.date || '',
    }))
  }

  if (Array.isArray(res.schedule) && res.schedule.length) {
    schedule.value = res.schedule.map((s) => ({
      time: s.time || '',
      title: s.title || '',
      loc: s.loc || s.location || '',
    }))
  }

  /* 即将召开（今日无日程时降级展示）：取 planned 最近一场 */
  if (Array.isArray(res.recent_meetings) && res.recent_meetings.length) {
    const next = res.recent_meetings[0]
    upcomingMeeting.value = {
      date: (next.start_time || '').slice(5, 10) || '',
      title: next.title || '',
    }
  }

  /* 待写纪要明细（date "2026-09-14" → "09-14"） */
  if (Array.isArray(res.pending_minutes_meetings) && res.pending_minutes_meetings.length) {
    pendingMinutes.value = res.pending_minutes_meetings.map((m) => ({
      title: m.title || '',
      date: (m.start_time || '').slice(5, 10) || '',
    }))
  }

  /* 模块统计（含 aiCenter / materials / knowledge.domainCount / issues.researchTotal） */
  if (res.module_stats && typeof res.module_stats === 'object') {
    const ms = res.module_stats
    if (ms.knowledge) knowledge.value = {
      total: ms.knowledge.total || 0,
      thisWeek: ms.knowledge.thisWeek || 0,
      domainCount: ms.knowledge.domainCount || 0,
    }
    if (ms.emails) emails.value = { today: ms.emails.todaySent || 0, week: ms.emails.weekSent || 0, sr: ms.emails.successRate || 0 }
    if (ms.aiCenter) aiCenter.value = {
      total: ms.aiCenter.total || 0,
      thisWeek: ms.aiCenter.thisWeek || 0,
      modelCount: ms.aiCenter.modelCount || 0,
    }
    if (ms.materials) materials.value = {
      total: ms.materials.total || 0,
      thisWeek: ms.materials.thisWeek || 0,
      categoryCount: ms.materials.categoryCount || 0,
    }
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
      researchTotal: ms.issues.researchTotal || 0,
    }
    if (ms.meetings) meetingStats.value = {
      totalThisWeek: ms.meetings.totalThisWeek || 0,
      today: ms.meetings.today || 0,
      upcoming: ms.meetings.upcoming || 0,
      pendingMinutes: ms.meetings.pendingMinutes || 0,
    }
    if (ms.activeOptimization) activeOpts.value = {
      total: ms.activeOptimization.total || 0,
      pending: ms.activeOptimization.pending || 0,
      adopted: ms.activeOptimization.adopted || 0,
      rejected: ms.activeOptimization.rejected || 0,
      thisWeek: ms.activeOptimization.thisWeek || 0,
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
      overdue_items: tcd.overdue_items || [],
    }
  }
}

/* 一线调研统计：模板「一线调研」卡片引用；接口不可用时保持 0 值渲染，不白屏 */
const researchStats = reactive({ total: 0, pending: 0, overdue: 0 })

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

async function loadResearchStats() {
  try {
    const res = await researchApi.getStats()
    if (res) {
      researchStats.total = res.total ?? 0
      researchStats.pending = res.pending ?? 0
      researchStats.overdue = res.overdue ?? 0
    }
  } catch (err) {
    // 接口不可用：保持 0 值渲染，绝不因单点接口故障白屏
    console.warn('[HomeView] 一线调研统计接口不可用，保持 0 值', err)
  }
}

onMounted(() => {
  loadData()
  loadResearchStats()
  _timer = setTimeout(_tick, 600)
  window.addEventListener('keydown', onCmdKey)
})

onUnmounted(() => {
  if (_timer) clearTimeout(_timer)
  window.removeEventListener('keydown', onCmdKey)
})
</script>

<style scoped>
.home-view {
  padding: 24px 28px 40px;
  max-width: 1480px;
  width: 100%;
}

/* ── 轻量分区标题（design.css 风格 24px 细行）── */
.row-label {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 2px 2px 0;
  min-height: 24px;
}
.rl-t { font-size: 12.5px; font-weight: 600; color: var(--text-secondary); letter-spacing: .06em; }
.rl-s { font-size: 11.5px; color: var(--text-muted); }
.rl-line { flex: 1; height: 1px; background: var(--border); }

/* 卡头多元素组合（label + caliber / caliber + action 相邻排列）*/
.head-extra { display: inline-flex; align-items: center; gap: 10px; min-width: 0; }

/* ── 问候卡（压缩版：上下两端对齐，无集中留白）── */
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
  top: -45%;
  right: -6%;
  width: 300px;
  height: 300px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(47, 111, 237, .16) 0%, transparent 70%);
  pointer-events: none;
}
.greeting-inner {
  position: relative;
  z-index: 1;
  padding: 16px 24px 14px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 10px;
  flex: 1;
  min-height: 148px;
}
.g-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.g-hello {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -.3px;
  line-height: 1.25;
}
.g-hello span { color: #93c5fd; }
.g-sub {
  font-size: 12.5px;
  color: #94a3b8;
  line-height: 1.55;
  max-width: 520px;
  margin-top: 4px;
}
.g-eff { text-align: right; flex-shrink: 0; }
.g-eff-key { font-size: 11.5px; color: #cbd5e1; }
.g-eff-val {
  font-size: 28px;
  font-weight: 800;
  font-family: var(--font-mono);
  color: #6ee7b7;
  letter-spacing: -1px;
  line-height: 1.15;
}
.g-eff-unit { font-size: 13px; color: #cbd5e1; }
.g-bottom {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
}
.g-stats { display: flex; gap: 22px; flex-wrap: wrap; }
.g-stat { display: flex; flex-direction: column; }
.g-stat-val { font-size: 19px; font-weight: 700; font-family: var(--font-mono); line-height: 1.15; }
.g-stat-val.up { color: #4ade80; }
.g-stat-val.down { color: #f87171; }
.g-stat-val.accent { color: #93c5fd; }
.g-stat-val.neutral { color: #e2e8f0; }
.g-stat-key { font-size: 11px; color: #64748b; margin-top: 1px; }
.g-cmd {
  display: flex;
  align-items: center;
  gap: 9px;
  background: rgba(255, 255, 255, .07);
  border: 1px solid rgba(255, 255, 255, .09);
  border-radius: 10px;
  padding: 6px 13px;
  cursor: pointer;
  font-size: 12.5px;
  color: #94a3b8;
  white-space: nowrap;
}
.kbd {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  background: rgba(255, 255, 255, .1);
  border: 1px solid rgba(255, 255, 255, .14);
  color: #cbd5e1;
  padding: 1px 6px;
  border-radius: 5px;
}
.cmd-cursor {
  display: inline-block;
  width: 2px;
  height: 13px;
  background: #60a5fa;
  vertical-align: text-bottom;
  animation: blink 1s step-end infinite;
}
@keyframes blink { 50% { opacity: 0; } }

/* ── 实时动态（紧凑多源）── */
.ls-list { list-style: none; padding: 0; }
.ls-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid var(--border-subtle);
}
.ls-item:last-child { border-bottom: none; padding-bottom: 0; }
.ls-item:first-child { padding-top: 0; }
.ls-body { flex: 1; min-width: 0; }
.ls-text { font-size: 12px; color: var(--text-primary); line-height: 1.4; }
.ls-src {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 999px;
  margin-right: 6px;
  vertical-align: 1px;
}
.ls-src.op { background: var(--danger-soft); color: var(--danger); }
.ls-src.mt { background: var(--accent-soft); color: var(--accent); }
.ls-src.rq { background: var(--success-soft); color: var(--success); }
.ls-src.kn { background: var(--warning-soft); color: var(--warning); }
.ls-foot { display: flex; justify-content: space-between; margin-top: 2px; }
.ls-time { font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); }

/* ── KPI（数值/标签走 design.css 全局 34px；此处仅补 neutral 色）── */
.kpi-trend.neutral { color: var(--text-muted); }

/* ── 主数字带（卡内四段式第 2 段）── */
.stat4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 14px; }
.stat { display: flex; flex-direction: column; gap: 2px; }
.stat b {
  font-size: 22px;
  font-weight: 800;
  font-family: var(--font-mono);
  line-height: 1.1;
  letter-spacing: -.5px;
  color: var(--text-primary);
}
.stat b.danger { color: var(--danger); }
.stat b.ok { color: var(--success); }
.stat span { font-size: 11px; color: var(--text-muted); }

/* ── 分布条（卡内四段式第 3 段）── */
.dist-h {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: .08em;
  margin: 0 0 8px;
}
.bar { display: grid; grid-template-columns: 76px 1fr 36px; gap: 10px; align-items: center; font-size: 12.5px; margin-bottom: 8px; }
.bar:last-child { margin-bottom: 0; }
.bar-k { color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.bar-track { height: 8px; background: var(--border-subtle); border-radius: 5px; overflow: hidden; }
.bar-fill { display: block; height: 100%; background: var(--accent); border-radius: 5px; transition: width var(--transition-normal); }
.bar-fill.ok { background: var(--success); }
.bar-fill.warn { background: var(--warning); }
.bar-fill.mute { background: #cbd5e1; }
.bar-v { text-align: right; font-family: var(--font-mono); font-weight: 600; font-size: 12px; color: var(--text-primary); }

/* ── 明细区（卡内四段式第 4 段）── */
.detail-box { margin-top: 12px; padding-top: 12px; border-top: 1px dashed var(--border); }
.detail-h { display: flex; align-items: center; gap: 8px; font-size: 11.5px; font-weight: 600; color: var(--danger); margin-bottom: 8px; }
.detail-h.ok { color: var(--text-secondary); }
.detail-h .cnt { background: var(--danger-soft); color: var(--danger); padding: 0 8px; border-radius: 999px; font-family: var(--font-mono); font-size: 10.5px; }
.d-item { display: flex; gap: 8px; align-items: flex-start; padding: 5px 0; font-size: 12.5px; }
.d-pri {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 7px;
  border-radius: 5px;
  flex-shrink: 0;
  margin-top: 1px;
  background: var(--danger-soft);
  color: var(--danger);
  white-space: nowrap;
}
.d-pri.p1 { background: var(--warning-soft); color: var(--warning); }
.d-pri.p2 { background: var(--accent-soft); color: var(--accent); }
.d-pri.p3 { background: var(--border-subtle); color: var(--text-muted); }
.d-t {
  flex: 1;
  min-width: 0;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.d-date { color: var(--danger); font-family: var(--font-mono); font-size: 11px; flex-shrink: 0; margin-top: 1px; }
.d-date.ok { color: var(--text-muted); }

/* ── 口径徽标 ── */
.caliber {
  font-size: 10.5px;
  font-weight: 600;
  color: var(--text-muted);
  background: var(--border-subtle);
  padding: 1px 9px;
  border-radius: 999px;
  white-space: nowrap;
}

/* ── 会议列表 ── */
.mt-item { display: flex; gap: 12px; padding: 7px 0; border-bottom: 1px solid var(--border-subtle); align-items: flex-start; }
.mt-item:last-child { border-bottom: none; }
.mt-time { font-size: 12px; font-weight: 700; font-family: var(--font-mono); color: var(--accent); width: 46px; flex-shrink: 0; padding-top: 1px; }
.mt-info { flex: 1; min-width: 0; }
.mt-title { font-size: 12.5px; line-height: 1.4; color: var(--text-primary); }
.mt-loc { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
.mt-sep {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: .08em;
  margin: 10px 0 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.mt-sep::after { content: ''; flex: 1; height: 1px; background: var(--border-subtle); }

/* ── 需求概览整合卡（趋势图 + 最近需求 同卡）── */
.req-overview {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(0, 1fr);
  gap: 26px;
  align-items: start;
}
@media (max-width: 1080px) {
  .req-overview { grid-template-columns: 1fr; gap: 18px; }
}
.chart-wrap { padding: 4px 0 0; }
.chart-svg { width: 100%; height: 200px; display: block; }
.chart-note { font-size: 11px; color: var(--text-muted); padding: 2px 0 6px; }
.ro-reqs-h {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: .08em;
  margin-bottom: 8px;
}
.req-wrap { overflow-x: auto; }
.req-table { width: 100%; border-collapse: collapse; }
.req-table th {
  text-align: left;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: .04em;
  padding: 6px 10px 6px 0;
  border-bottom: 1px solid var(--border);
}
.req-table td { font-size: 12.5px; padding: 10px 10px; border-bottom: 1px solid var(--border-subtle); color: var(--text-primary); vertical-align: middle; }
.req-table tr:last-child td { border-bottom: none; }
.req-name { font-weight: 500; max-width: 230px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.req-owner { color: var(--text-secondary); font-size: 12px; }
.req-date { font-size: 11.5px; color: var(--text-muted); font-family: var(--font-mono); white-space: nowrap; }

/* ── 今日聚焦条目 ── */
.fz-item {
  display: flex;
  gap: 9px;
  align-items: flex-start;
  padding: 7px 0;
  border-bottom: 1px solid var(--border-subtle);
}
.fz-item:last-child { border-bottom: none; padding-bottom: 0; }
.fz-item:first-child { padding-top: 0; }

/* ── 重点工作进度 ── */
.kp-list { list-style: none; padding: 0; display: flex; flex-direction: column; gap: 11px; }
.kp-item { display: flex; flex-direction: column; gap: 4px; }
.kp-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
.kp-name { font-size: 12.5px; color: var(--text-primary); font-weight: 500; }
.kp-pct { font-size: 12px; font-family: var(--font-mono); color: var(--accent); font-weight: 700; }
.kp-bar { height: 6px; background: var(--border-subtle); border-radius: 4px; overflow: hidden; }
.kp-fill { display: block; height: 100%; background: var(--accent); border-radius: 4px; }

/* ── 模块概览小卡 ── */
/* 模块概览居中指标卡：数字→标签→描述三层中线对齐，水平+垂直双向居中 */
.mod-tile :deep(.card-body) { display: flex; flex-direction: column; }
.mod-grid { display: flex; flex-direction: column; gap: 8px; padding: 2px 0; align-items: center; justify-content: center; text-align: center; flex: 1; }
.mod-stat { display: flex; flex-direction: column; align-items: center; gap: 2px; }
.mod-num { font-size: 26px; font-weight: 800; font-family: var(--font-mono); color: var(--text-primary); line-height: 1.1; letter-spacing: -.5px; }
.mod-unit { font-size: 14px; }
.mod-key { font-size: 12px; color: var(--text-muted); }
.mod-sub { font-size: 12px; color: var(--text-secondary); line-height: 1.55; max-width: 94%; }
.mod-sub b { color: var(--text-primary); font-weight: 600; }
.mod-sub .hot { color: var(--danger); font-weight: 600; }
.new-badge {
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: .06em;
  color: #fff;
  background: var(--accent);
  padding: 1px 8px;
  border-radius: 999px;
  vertical-align: 2px;
  margin-left: 6px;
}
.mod-clickable { cursor: pointer; }

/* ── 快捷操作 ── */
.action-row {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

/* ── 任务中心 / 运营工单 共用空态 ── */
.tc-empty { font-size: 12.5px; color: var(--text-muted); padding: 8px 0; }
</style>
