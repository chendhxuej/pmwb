<template>
  <div class="module-problem">
    <PageHeader title="主要投诉点 · 功能模块问题" :subtitle="subTitle">
      <template #actions>
        <el-select v-if="weekOptions.length" v-model="statWeek" style="width: 150px" @change="loadClasses">
          <el-option v-for="w in weekOptions" :key="w" :label="w + '（本周对比）'" :value="w" />
        </el-select>
        <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
        <el-button type="primary" :icon="Refresh" :loading="running" @click="confirmRerun">
          重新归并（落库）
        </el-button>
        <el-button text tag="a" :href="v42Href" target="_blank" :icon="Document">
          单工单 AI 简述明细
        </el-button>
      </template>
    </PageHeader>

    <!-- 汇总 KPI -->
    <section class="card summary-card">
      <div class="pm-stat-grid pm-stat-grid--6 summary-kpis">
        <div class="pm-stat">
          <div class="pm-stat__top"><span class="pm-stat__label">总工单</span></div>
          <div class="pm-stat__val">{{ summary.total }}<span class="pm-stat__unit">单</span></div>
        </div>
        <div class="pm-stat">
          <div class="pm-stat__top"><span class="pm-stat__label">缺陷已归集</span></div>
          <div class="pm-stat__val is-accent">{{ summary.defectClassified }}<span class="pm-stat__unit">单</span></div>
        </div>
        <div class="pm-stat">
          <div class="pm-stat__top"><span class="pm-stat__label">缺陷类数</span></div>
          <div class="pm-stat__val">{{ summary.defectClasses }}<span class="pm-stat__unit">个</span></div>
          <div class="pm-stat__sub">类单比 {{ summary.classRatio }}%</div>
        </div>
        <div class="pm-stat">
          <div class="pm-stat__top"><span class="pm-stat__label">最大单类</span></div>
          <div class="pm-stat__val">{{ summary.maxClass }}<span class="pm-stat__unit">单</span></div>
          <div class="pm-stat__sub">TOP10 覆盖 {{ summary.top10Rate }}%</div>
        </div>
        <div class="pm-stat">
          <div class="pm-stat__top"><span class="pm-stat__label">未归类</span></div>
          <div class="pm-stat__val" :class="summary.unclassified ? 'is-warning' : 'is-success'">
            {{ summary.unclassified }}<span class="pm-stat__unit">单</span>
          </div>
          <div class="pm-stat__sub">待管理 {{ summary.reviewQueue }} 单</div>
        </div>
        <div class="pm-stat">
          <div class="pm-stat__top"><span class="pm-stat__label">咨询类</span></div>
          <div class="pm-stat__val is-muted">{{ summary.consult }}<span class="pm-stat__unit">单</span></div>
          <div class="pm-stat__sub">非缺陷·隔离</div>
        </div>
      </div>
      <el-alert
        type="info" :closable="false" show-icon
        title="口径 vL2：归并键 = 业务功能模块 × 失效对象 × 失效性质；同一模块问题下『描述不同、本质同模块』的工单强制归并（跨表象汇聚）。主流投诉自动归集；少量无匹配/低置信进入人工管理台，系统不依赖人工修正即可完整运行。" />
    </section>

    <el-tabs v-model="activeTab" class="mp-tabs">
      <!-- 主要投诉点 -->
      <el-tab-pane label="主要投诉点" name="points">
        <section class="card">
          <div class="block-head">
            <span class="block-title">功能模块问题（按工单量降序）</span>
            <span class="block-sub">共 {{ classItems.length }} 个模块问题 · 展开看跨表象汇聚的多种说法</span>
            <el-checkbox v-model="includeConsult" class="block-chk" @change="applyDisplay">包含咨询类</el-checkbox>
          </div>
          <el-table :data="classItems" v-loading="loading" size="small" stripe row-key="module_problem_id" :row-class-name="rowClass">
            <el-table-column label="排名" width="60" align="center">
              <template #default="{ $index }"><span class="rank">{{ $index + 1 }}</span></template>
            </el-table-column>
            <el-table-column label="功能模块问题（一句话）" min-width="300">
              <template #default="{ row }">
                <div class="cls-name" :class="{ 'is-consult': !row.is_defect }">{{ row.name }}</div>
                <div class="cls-tags">
                  <el-tag size="small" effect="plain" type="info">{{ row.module }}</el-tag>
                  <el-tag size="small" effect="plain" type="info">{{ row.fail_object }}</el-tag>
                  <el-tag size="small" effect="plain" :type="row.is_defect ? 'warning' : 'success'">{{ row.fail_nature }}</el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="ticket_cnt" label="累计工单" width="96" align="center" sortable />
            <el-table-column :label="statWeek ? statWeek.replace('2026-', '') : '本周'" width="88" align="center" sortable prop="week_cnt">
              <template #default="{ row }">
                <span class="week-cnt">{{ row.week_cnt ?? 0 }}</span>
              </template>
            </el-table-column>
            <el-table-column label="环比" width="100" align="center" sortable prop="wow_pct">
              <template #default="{ row }">
                <span v-if="row.wow_pct === null || row.wow_pct === undefined" class="wow-new">新出现</span>
                <span v-else-if="row.wow_pct > 0" class="wow-up">+{{ row.wow_pct }}%</span>
                <span v-else-if="row.wow_pct < 0" class="wow-down">{{ row.wow_pct }}%</span>
                <span v-else class="wow-flat">持平</span>
              </template>
            </el-table-column>
            <el-table-column prop="surface_cnt" label="表象数" width="80" align="center" sortable>
              <template #default="{ row }">
                <el-tooltip :content="'跨表象汇聚：同一问题 ' + row.surface_cnt + ' 种不同说法归并为一类'" placement="top">
                  <span class="surface-cnt">{{ row.surface_cnt }}</span>
                </el-tooltip>
              </template>
            </el-table-column>
            <el-table-column prop="active_weeks" label="活跃周" width="80" align="center" sortable />
            <el-table-column label="近 8 周趋势" min-width="180">
              <template #default="{ row }">
                <div class="trend">
                  <span v-for="(w, i) in weeklyBars(row.weekly)" :key="i" class="trend-bar" :style="{ height: w.h + 'px' }" :title="w.week + ': ' + w.cnt" />
                </div>
              </template>
            </el-table-column>
            <el-table-column type="expand" label="跨表象" width="76">
              <template #default="{ row }">
                <div class="surfaces" v-if="row.surfaces && row.surfaces.length">
                  <div class="surfaces-title">该类下 {{ row.surface_cnt }} 种不同说法（本质同一模块问题）：</div>
                  <div class="surfaces-list">
                    <span v-for="(s, i) in row.surfaces" :key="i" class="surface-item">{{ s }}</span>
                  </div>
                </div>
                <div v-else class="surfaces-empty">暂无表象明细</div>
              </template>
            </el-table-column>
            <el-table-column label="下钻" width="158" align="center" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" plain @click="drillTickets(row)">工单 {{ row.ticket_cnt }}</el-button>
                <el-button size="small" plain @click="drillLedger(row)">问题台账</el-button>
              </template>
            </el-table-column>
          </el-table>
        </section>
      </el-tab-pane>

      <!-- 人工管理台 -->
      <el-tab-pane label="人工管理台" :name="reviewName">
        <section class="card">
          <div class="block-head">
            <span class="block-title">待处理 / 需复核（低置信 + 未归类 + 已改派）</span>
            <span class="block-sub">共 {{ reviewTotal }} 单 · 系统不依赖此操作即可完整运行，此处为可选安全网</span>
          </div>
          <el-table :data="reviewItems" v-loading="loading" size="small" stripe max-height="460">
            <el-table-column prop="ticket_no" label="工单号" width="150" />
            <el-table-column label="表象（L1 简述）" min-width="300">
              <template #default="{ row }"><span class="rv-surface">{{ row.surface || '（L1 简述为空）' }}</span></template>
            </el-table-column>
            <el-table-column label="当前归类" width="200">
              <template #default="{ row }">
                <span v-if="row.current_name" class="rv-cur">{{ row.current_name }}</span>
                <el-tag v-else size="small" type="info" effect="plain">未归类</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="110" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="reviewTagType(row.review_status)" effect="plain">{{ reviewTagText(row.review_status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="缺口/建议" min-width="220">
              <template #default="{ row }">
                <span v-if="row.gap" class="rv-gap">{{ row.gap }}</span>
                <span v-else-if="row.suggested_id" class="rv-sug">建议：{{ nameOf(row.suggested_id) }}</span>
                <span v-else class="rv-ok">—</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220" align="center" fixed="right">
              <template #default="{ row }">
                <el-button v-if="row.suggested_id" size="small" type="success" plain @click="accept(row)">采纳建议</el-button>
                <el-select v-model="row._target" size="small" placeholder="改派到" class="rv-select" @change="override(row)">
                  <el-option v-for="m in defectOptions" :key="m.module_problem_id" :label="m.name" :value="m.module_problem_id" />
                </el-select>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-if="reviewTotal > reviewPageSize" class="pg" layout="prev,pager,next"
            :total="reviewTotal" :page-size="reviewPageSize" v-model:current-page="reviewPage"
            @current-change="loadReview" />
        </section>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Refresh, Document } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/Common/PageHeader.vue'
import { complaintApi as api } from '@/api/complaint'

const router = useRouter()
const route = useRoute()
const focusId = ref('')

const loading = ref(false)
const running = ref(false)
const activeTab = ref('points')
const reviewName = computed(() => 'review')
const includeConsult = ref(false)
const v42Href = '#/complaint-center/problem-v42'

const allItems = ref([]) // 全量（含咨询类），用于 KPI 计数
const classItems = ref([]) // 展示列表（含咨询类开关控制）
// 对比周（承接原热点投诉页的环比能力；默认库内最新周）
const statWeek = ref('')
const weekOptions = ref([])
const unclassifiedTotal = ref(0)
const reviewItems = ref([])
const reviewTotal = ref(0)
const reviewPage = ref(1)
const reviewPageSize = 30

const subTitle = computed(() => '跨表象汇聚：找出主要投诉点，定位系统改造落点（vL2 闭集字典）')

// 缺陷类选项（供改派下拉），始终来自全量缺陷类
const defectOptions = computed(() => allItems.value.filter((c) => c.is_defect))

function nameOf(id) {
  const m = classItems.value.find((c) => c.module_problem_id === id)
  return m ? m.name : id
}

// 汇总从 classes(全量) + unclassified + review-queue 派生（不依赖会 500 的 summary 端点）
const summary = reactive({
  total: 0, defectClassified: 0, defectClasses: 0, classRatio: 0,
  maxClass: 0, top10Rate: 0, unclassified: 0, reviewQueue: 0, consult: 0,
})
function recomputeSummary() {
  const all = allItems.value
  const defect = all.filter((c) => c.is_defect)
  const consult = all.filter((c) => !c.is_defect)
  const defectClassified = defect.reduce((s, c) => s + (c.ticket_cnt || 0), 0)
  const consultCnt = consult.reduce((s, c) => s + (c.ticket_cnt || 0), 0)
  const maxClass = defect.reduce((m, c) => Math.max(m, c.ticket_cnt || 0), 0)
  const top10 = defect.slice(0, 10).reduce((s, c) => s + (c.ticket_cnt || 0), 0)
  const defectClasses = defect.length
  const unclassified = unclassifiedTotal.value
  const reviewQueue = reviewTotal.value
  const total = defectClassified + consultCnt + unclassified
  Object.assign(summary, {
    total, defectClassified, defectClasses, consult: consultCnt,
    classRatio: defectClassified ? +(defectClasses / defectClassified * 100).toFixed(1) : 0,
    maxClass, top10Rate: defectClassified ? +(top10 / defectClassified * 100).toFixed(1) : 0,
    unclassified, reviewQueue,
  })
}

function weeklyBars(weekly) {
  if (!weekly || !weekly.length) return []
  const max = Math.max(...weekly.map((w) => w.cnt || 0), 1)
  return weekly.slice(-8).map((w) => ({ week: w.week, cnt: w.cnt || 0, h: Math.max(4, Math.round((w.cnt || 0) / max * 32)) }))
}

function reviewTagType(s) {
  return { low: 'warning', unclassified: 'info', override: 'success', accepted: 'success' }[s] || 'info'
}
function reviewTagText(s) {
  return { low: '低置信(性质回退)', unclassified: '未归类', override: '已改派', accepted: '已采纳' }[s] || s
}

async function loadClasses() {
  const r = await api.moduleProblemClasses({
    include_consult: true,
    ...(statWeek.value ? { week: statWeek.value } : {}),
  })
  const d = r || {}
  allItems.value = d.items || []
  if (!statWeek.value && allItems.value.length) statWeek.value = allItems.value[0].stat_week || ''
  applyDisplay()
  recomputeSummary()
}
async function loadWeeks() {
  try {
    const r = await api.listWeeks(16)
    weekOptions.value = r?.weeks || []
  } catch (e) { weekOptions.value = [] }
}
function applyDisplay() {
  // 「包含咨询类」只看展示；KPI 计数始终基于 allItems（含咨询类），避免总数低估
  classItems.value = includeConsult.value
    ? allItems.value
    : allItems.value.filter((c) => c.is_defect)
}
async function loadUnclassified() {
  const r = await api.moduleProblemUnclassified({ page: 1, page_size: 1 })
  const d = r || {}
  unclassifiedTotal.value = d.total || 0
  recomputeSummary()
}
async function loadReview() {
  const r = await api.moduleProblemReviewQueue({ page: reviewPage.value, page_size: reviewPageSize })
  const d = r || {}
  reviewItems.value = (d.items || []).map((it) => ({ ...it, _target: '' }))
  reviewTotal.value = d.total || 0
  recomputeSummary()
}
async function loadAll() {
  loading.value = true
  try {
    await Promise.all([loadClasses(), loadUnclassified(), loadReview()])
  } finally {
    loading.value = false
  }
}

async function accept(row) {
  try {
    await api.moduleProblemAccept(row.ticket_no)
    ElMessage.success(`已采纳建议：${nameOf(row.suggested_id)}`)
    await loadReview()
  } catch (e) {
    ElMessage.error('采纳失败：' + (e?.response?.data?.message || e.message))
  }
}
async function override(row) {
  if (!row._target) return
  try {
    await api.moduleProblemOverride(row.ticket_no, row._target)
    ElMessage.success('已改派：' + nameOf(row._target))
    await Promise.all([loadReview(), loadClasses()])
  } catch (e) {
    ElMessage.error('改派失败：' + (e?.response?.data?.message || e.message))
  }
}
// 下钻：主要投诉点 → 工单明细（按 module_problem_id 过滤）/ 问题台账（按锚点过滤）
function drillTickets(row) {
  router.push({ path: '/complaint-center/tickets', query: { module_problem_id: row.module_problem_id } })
}
function drillLedger(row) {
  router.push({ path: '/complaint-center/problems', query: { module_problem_id: row.module_problem_id } })
}
function rowClass({ row }) {
  return row.module_problem_id === focusId.value ? 'row-focus' : ''
}

async function confirmRerun() {
  try {
    await ElMessageBox.confirm(
      '将按 vL2 闭集字典全量重跑功能模块问题归并并落库（确定性规则，零 LLM 费用）。确定执行？',
      '重新归并', { type: 'warning', confirmButtonText: '确定落库', cancelButtonText: '取消' })
  } catch { return }
  running.value = true
  try {
    const r = await api.moduleProblemRun({ dry_run: false, force: true })
    const d = r || {}
    ElMessage.success(`归并完成：已归集 ${d.classified ?? 0} 单 / ${d.unclassified ?? 0} 单未归类 / ${d.classes ?? 0} 个缺陷类`)
    await loadAll()
  } catch (e) {
    ElMessage.error('归并失败：' + (e?.response?.data?.message || e.message))
  } finally {
    running.value = false
  }
}

onMounted(async () => {
  if (route.query.focus) focusId.value = String(route.query.focus)
  await loadWeeks()
  await loadAll()
})
</script>

<style scoped>
.module-problem { padding: 4px 2px 24px; }
.row-focus { background: var(--brand-soft, #eef4ff) !important; }
.row-focus:hover > td { background: var(--brand-soft, #eef4ff) !important; }
.summary-card { margin-bottom: 16px; }
.summary-kpis { margin-bottom: 12px; }
.mp-tabs { margin-top: 4px; }
.block-head { display: flex; align-items: baseline; gap: 10px; margin: 4px 2px 12px; flex-wrap: wrap; }
.block-title { font-size: 14.5px; font-weight: 600; color: var(--text-primary, #1f2d3d); }
.block-sub { font-size: 12px; color: var(--text-muted, #94a3b8); }
.block-chk { margin-left: auto; }
.cls-name { font-weight: 600; line-height: 1.5; color: var(--text-primary, #1f2d3d); }
.cls-name.is-consult { color: var(--text-muted, #94a3b8); }
.cls-tags { margin-top: 4px; display: flex; gap: 4px; flex-wrap: wrap; }
.rank { font-weight: 700; color: var(--text-secondary, #64748b); }
.surface-cnt { font-weight: 700; color: var(--accent, #2563eb); cursor: help; }
/* 环比：投诉上升=恶化(红)，下降=好转(绿)；新出现单列以免与 0% 混淆 */
.wow-up { color: var(--pm-danger, #c0392b); font-weight: 600; }
.wow-down { color: var(--pm-success, #1e8e3e); font-weight: 600; }
.wow-flat { color: var(--pm-text-3, #909399); }
.wow-new { color: var(--pm-warning, #e6a23c); font-size: 12px; }
.week-cnt { font-weight: 600; }
.trend { display: flex; align-items: flex-end; gap: 3px; height: 34px; }
.trend-bar { width: 9px; background: var(--accent, #2563eb); border-radius: 2px 2px 0 0; opacity: 0.8; }
.surfaces { padding: 8px 4px; }
.surfaces-title { font-size: 12.5px; color: var(--text-secondary, #64748b); margin-bottom: 6px; }
.surfaces-list { display: flex; flex-direction: column; gap: 4px; }
.surface-item { font-size: 13px; color: var(--text-primary, #1f2d3d); padding: 3px 8px; background: var(--bg-soft, #f1f5f9); border-radius: 6px; }
.surfaces-empty { font-size: 12px; color: var(--text-muted, #94a3b8); padding: 6px; }
.rv-surface { color: var(--text-primary, #1f2d3d); }
.rv-cur { color: var(--text-secondary, #64748b); }
.rv-gap { font-size: 12.5px; color: var(--warning, #d97706); }
.rv-sug { font-size: 12.5px; color: var(--accent, #2563eb); }
.rv-ok { color: var(--text-muted, #94a3b8); }
.rv-select { width: 150px; margin-left: 6px; }
.pg { margin-top: 12px; justify-content: flex-end; }
</style>
