<template>
  <div class="problem-ledger">
    <PageHeader title="共性问题台账" :subtitle="subTitle">
      <template #actions>
        <el-button :icon="MagicStick" :loading="scanning" @click="doScan(false)">扫描候选（预览）</el-button>
        <el-button :icon="Promotion" :disabled="!urgeCnt" @click="doProblemsUrge">
          问题督办（{{ urgeCnt }}）
        </el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">手工立问题</el-button>
      </template>
    </PageHeader>

    <!-- KPI 区 -->
    <div class="pm-stat-grid pm-stat-grid--5">
      <div class="card kpi-card">
        <div class="kpi-num" :class="kpi.candidate ? 'amber' : 'green'">{{ kpi.candidate }}</div>
        <div class="kpi-label">待确认候选</div>
      </div>
      <div class="card kpi-card">
        <div class="kpi-num" :class="kpi.inflight ? 'blue' : 'green'">{{ kpi.inflight }}</div>
        <div class="kpi-label">在办问题</div>
      </div>
      <div class="card kpi-card">
        <div class="kpi-num" :class="suggestions.length ? 'green' : ''">{{ suggestions.length }}</div>
        <div class="kpi-label">待闭环建议</div>
      </div>
      <div class="card kpi-card">
        <div class="kpi-num" :class="kpi.longRunning ? 'red' : 'green'">{{ kpi.longRunning }}</div>
        <div class="kpi-label">长期未闭环（≥12周）</div>
      </div>
      <div class="card kpi-card">
        <div class="kpi-num" :class="kpi.reopen ? 'red' : 'green'">{{ kpi.reopen }}</div>
        <div class="kpi-label">闭环后复发（待重开）</div>
      </div>
    </div>

    <!-- 闭环建议 -->
    <el-alert v-if="suggestions.length" type="success" :closable="false" class="sug-alert">
      <template #title>
        {{ suggestions.length }} 个问题满足闭环条件（关联措施全部验证有效且连续零复发），请人工确认闭环
      </template>
      <div v-for="s in suggestions" :key="s.problem_no" class="sug-line">
        <b>{{ s.problem_no }}</b> {{ s.title }}（{{ s.reason }}）
        <el-button size="small" type="success" text @click="doClose(s)">确认闭环</el-button>
      </div>
    </el-alert>

    <!-- 候选确认区 -->
    <section class="card">
      <div class="card-header">
        <h3>候选问题（每周分析自动识别，须人工确认后方可关联措施）</h3>
      </div>
      <div class="card-body">
        <el-table ref="pmTbl1" v-if="candidates.length" :data="candidates" size="default" border>
          <el-table-column prop="problem_no" label="编号" width="150">
            <template #default="{ row }"><b>{{ row.problem_no }}</b></template>
          </el-table-column>
          <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
          <el-table-column prop="category_l2" label="场景" min-width="130" show-overflow-tooltip />
          <el-table-column label="命中规则" width="180">
            <template #default="{ row }">
              <el-tag v-for="h in ruleHits(row.rule_hits)" :key="h" size="small" class="rule-tag" type="warning">{{ h }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="证据摘要" min-width="200">
            <template #default="{ row }">{{ evidenceBrief(row.evidence) }}</template>
          </el-table-column>
          <el-table-column prop="week_cnt" label="当周单量" width="90" align="center" />
          <el-table-column label="操作" width="196" fixed="right" align="center">
            <template #default="{ row }">
              <el-button size="small" type="primary" text @click="doConfirmOpen(row)">入账</el-button>
              <el-button size="small" text @click="openMerge(row)">合并</el-button>
              <el-button size="small" text type="danger" @click="doIgnore(row)">忽略</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无待确认候选（每周导入分析后自动生成）" :image-size="60" />
      </div>
    </section>

    <!-- 台账表格 -->
    <section class="card">
      <div class="card-header">
        <h3>问题台账</h3>
        <el-select v-model="statusFilter" clearable size="small" style="width: 160px" placeholder="全部状态">
          <el-option v-for="s in statusDefs" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
      </div>
      <div class="card-body">
        <el-table ref="pmTbl2" v-loading="loading" :data="filteredRows" size="default" border stripe>
          <el-table-column prop="problem_no" label="问题编号" width="150">
            <template #default="{ row }"><b>{{ row.problem_no }}</b></template>
          </el-table-column>
          <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
          <el-table-column prop="category_l2" label="场景" min-width="130" show-overflow-tooltip />
          <el-table-column label="来源" width="96" align="center">
            <template #default="{ row }">
              <el-tag size="small" type="info">{{ sourceLabel(row.source_type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="106" align="center">
            <template #default="{ row }">
              <el-tag :type="statusTone(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="first_week" label="首见周" width="96" />
          <el-table-column prop="active_weeks" label="在办周" width="80" align="center">
            <template #default="{ row }">
              <span :class="{ 'long-run': row.active_weeks >= 12 && isOpen(row) }">{{ row.active_weeks }}</span>
            </template>
          </el-table-column>
          <el-table-column label="当周/累计" width="96" align="center">
            <template #default="{ row }">{{ row.week_cnt }} / {{ row.total_cnt }}</template>
          </el-table-column>
          <el-table-column prop="recur_cnt" label="累计复发" width="86" align="center">
            <template #default="{ row }">
              <span :class="{ recur: row.recur_cnt > 0 }">{{ row.recur_cnt }}</span>
            </template>
          </el-table-column>
          <el-table-column label="关联措施" width="120" align="center">
            <template #default="{ row }">{{ row.effective_cnt ?? 0 }} / {{ row.action_cnt }}</template>
          </el-table-column>
          <el-table-column prop="owner" label="责任人" width="100" show-overflow-tooltip />
          <el-table-column label="操作" width="200" fixed="right" align="center">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="openDetail(row)">详情</el-button>
              <el-button
                v-for="t in nextTargets(row.status)"
                :key="t.value"
                size="small"
                :type="t.value === 'closed' ? 'success' : (t.value === 'ignored' ? 'danger' : 'default')"
                text
                @click="doTransition(row, t)"
              >{{ t.label }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" :title="detail?.problem_no || '问题详情'" size="62%">
      <div v-if="detail" class="detail-body">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="标题" :span="2">{{ detail.title }}</el-descriptions-item>
          <el-descriptions-item label="场景">{{ detail.category_l2 }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTone(detail.status)" size="small">{{ statusLabel(detail.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="责任人">{{ detail.owner || '—' }}</el-descriptions-item>
          <el-descriptions-item label="首见/末见周">{{ detail.first_week }} / {{ detail.last_week || '—' }}</el-descriptions-item>
          <el-descriptions-item label="当周/累计单量">{{ detail.week_cnt }} / {{ detail.total_cnt }}</el-descriptions-item>
          <el-descriptions-item label="复发">{{ detail.recur_cnt }} 单（连续 {{ detail.recur_weeks }} 周）</el-descriptions-item>
          <el-descriptions-item label="连续零复发">{{ detail.quiet_weeks }} 周</el-descriptions-item>
          <el-descriptions-item label="闭环结论">{{ detail.conclusion || '—' }}</el-descriptions-item>
        </el-descriptions>

        <h4 class="sec-title">命中规则与证据</h4>
        <div class="ev-line">
          <el-tag v-for="h in ruleHits(detail.rule_hits)" :key="h" size="small" type="warning" class="rule-tag">{{ h }}</el-tag>
          <span class="ev-text">{{ evidenceBrief(detail.evidence) }}</span>
        </div>

        <h4 class="sec-title">周度轨迹（锚点场景单量）</h4>
        <ChartLine v-if="trajectory.length" :x-data="trajectory.map(t => t.week)" height="200px"
          :series="[{ name: '周单量', type: 'line', data: trajectory.map(t => t.cnt) }]" />
        <el-empty v-else description="暂无轨迹数据" :image-size="48" />

        <h4 class="sec-title">关联措施（{{ detail.actions.length }}）</h4>
        <el-table ref="pmTbl3" :data="detail.actions" size="small" border>
          <el-table-column prop="action_no" label="措施编号" width="140">
            <template #default="{ row }">
              <b>{{ row.action_no }}</b>
              <el-tag v-if="row.is_primary" size="small" type="primary" class="rule-tag">主</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="title" label="标题" min-width="140" show-overflow-tooltip />
          <el-table-column prop="owner" label="责任人" width="90" />
          <el-table-column label="状态" width="96" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="actionTone(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="关联工单" width="130">
            <template #default="{ row }">{{ row.issue_no || '—' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="90" align="center">
            <template #default="{ row }">
              <el-button size="small" text type="danger" @click="doUnlink(row)">解除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="link-row">
          <el-select v-model="linkActionNo" filterable clearable size="small" placeholder="选择措施关联到该问题" style="width: 320px">
            <el-option v-for="a in linkableActions" :key="a.action_no"
              :label="`${a.action_no} ${a.title}`" :value="a.action_no" />
          </el-select>
          <el-button size="small" type="primary" :disabled="!linkActionNo" @click="doLink">关联</el-button>
        </div>
      </div>
    </el-drawer>

    <!-- 入账对话框 -->
    <el-dialog v-model="openVisible" title="候选入账（置为待处置）" width="440px">
      <el-form label-width="88px" size="default">
        <el-form-item label="问题">{{ openRow?.problem_no }}</el-form-item>
        <el-form-item label="责任人" required>
          <el-input v-model="openOwner" placeholder="多负责人用逗号分隔" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="openVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveOpen">确认入账</el-button>
      </template>
    </el-dialog>

    <!-- 合并对话框 -->
    <el-dialog v-model="mergeVisible" title="合并候选到在办问题" width="480px">
      <el-form label-width="88px" size="default">
        <el-form-item label="候选">{{ mergeRow?.problem_no }}（{{ mergeRow?.title }}）</el-form-item>
        <el-form-item label="合并目标" required>
          <el-select v-model="mergeTarget" filterable placeholder="选择目标问题" style="width: 100%">
            <el-option v-for="p in mergeTargets" :key="p.problem_no"
              :label="`${p.problem_no} ${p.title}（${statusLabel(p.status)}）`" :value="p.problem_no" />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="gl-tip">合并后候选工单归因与计数并入目标，候选置为「已合并」。</div>
      <template #footer>
        <el-button @click="mergeVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveMerge">确认合并</el-button>
      </template>
    </el-dialog>

    <!-- 手工立问题 -->
    <el-dialog v-model="createVisible" title="手工立问题" width="480px">
      <el-form label-width="88px" size="default">
        <el-form-item label="场景" required>
          <el-select v-model="createForm.category_l2" filterable placeholder="二级问题场景" style="width: 100%">
            <el-option v-for="c in l2Options" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题" required>
          <el-input v-model="createForm.title" />
        </el-form-item>
        <el-form-item label="责任人">
          <el-input v-model="createForm.owner" placeholder="留空则先入候选，多负责人逗号分隔" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 问题督办 -->
    <el-dialog v-model="urgeVisible" title="客诉共性问题督办" width="520px">
      <el-alert type="info" :closable="false" show-icon class="gl-tip">
        对在办问题下的超期措施按责任人聚合发送督办（复用客诉措施督办场景）。先预览，确认后真发。
      </el-alert>
      <div v-for="r in urgeResults" :key="r.owner" class="urge-line">
        <b>{{ r.owner }}</b>：
        <template v-if="r.skipped"><span class="warn">{{ r.skipped }}</span></template>
        <template v-else>
          {{ r.task_cnt }} 项 → {{ r.to }}
          <el-tag :type="r.dry_run ? 'info' : 'success'" size="small">
            {{ r.dry_run ? 'dry_run 已落库' : '已发送' }}
          </el-tag>
        </template>
      </div>
      <template #footer>
        <el-button @click="urgeVisible = false">关闭</el-button>
        <el-button v-if="!urgeDone" :loading="urging" @click="doProblemsUrge(false)">预览（dry_run）</el-button>
        <el-button v-if="urgeDone" type="danger" :loading="urging" @click="doProblemsUrge(true)">确认真发</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick, Plus, Promotion } from '@element-plus/icons-vue'
import PageHeader from '@/components/Common/PageHeader.vue'
import ChartLine from '@/components/Charts/ChartLine.vue'
import { complaintApi } from '@/api/complaint'
import { domainStatuses, allowedNext } from '@/constants/statusConfig'

const DOMAIN = 'complaint_problem'
const RULE_NAMES = { batch_cluster: 'R1批量簇', surge: 'R3环比激增', top_scene: 'R2场景TOP', recur: 'R4复发', manual: '人工' }
const SOURCE_NAMES = { batch_cluster: '批量簇', surge: '环比激增', top_scene: '场景TOP', recur: '复发', manual: '手工' }

const loading = ref(false)
const saving = ref(false)
const scanning = ref(false)
const rows = ref([])
const suggestions = ref([])
const allActions = ref([])
const statusFilter = ref('')

const detailVisible = ref(false)
const detail = ref(null)
const trajectory = ref([])
const linkActionNo = ref('')

const openVisible = ref(false)
const openRow = ref(null)
const openOwner = ref('')
const mergeVisible = ref(false)
const mergeRow = ref(null)
const mergeTarget = ref('')
const createVisible = ref(false)
const createForm = ref({ category_l2: '', title: '', owner: '' })
const urgeVisible = ref(false)
const urgeResults = ref([])
const urgeDone = ref(false)
const urging = ref(false)

const statusDefs = computed(() => domainStatuses(DOMAIN))
const statusMap = computed(() => {
  const m = {}
  for (const s of statusDefs.value) m[s.value] = s
  return m
})

const subTitle = computed(() => {
  const inflight = rows.value.filter(r => ['open', 'resolving'].includes(r.status)).length
  return `共 ${rows.value.length} 个问题（在办 ${inflight}）｜闭环流程：周分析 → 台账确认 → 措施跟踪 → 周验证 → 闭环确认`
})

const candidates = computed(() => rows.value.filter(r => r.status === 'candidate'))
const filteredRows = computed(() =>
  statusFilter.value ? rows.value.filter(r => r.status === statusFilter.value) : rows.value
)

const kpi = computed(() => ({
  candidate: candidates.value.length,
  inflight: rows.value.filter(r => ['open', 'resolving'].includes(r.status)).length,
  longRunning: rows.value.filter(r => r.active_weeks >= 12 && ['open', 'resolving'].includes(r.status)).length,
  reopen: rows.value.filter(r => r.reopen_flag).length,
}))

const urgeCnt = computed(() => kpi.value.reopen + kpi.value.longRunning)

const mergeTargets = computed(() =>
  rows.value.filter(r => ['open', 'resolving'].includes(r.status) && r.problem_no !== mergeRow.value?.problem_no)
)

const l2Options = computed(() =>
  [...new Set(rows.value.map(r => r.category_l2).filter(Boolean))]
)

const linkableActions = computed(() =>
  allActions.value.filter(a => !['cancelled'].includes(a.status))
)

function isOpen(row) { return ['open', 'resolving'].includes(row.status) }
function statusLabel(v) { return statusMap.value[v]?.label || v }
function statusTone(v) {
  const t = statusMap.value[v]?.tone || 'info'
  return { danger: 'danger', warning: 'warning', primary: 'primary', success: 'success', info: 'info', neutral: 'info' }[t] || 'info'
}
function actionTone(v) {
  return { effective: 'success', ineffective: 'danger', verifying: 'primary', in_progress: 'warning', planned: 'info', cancelled: 'info' }[v] || 'info'
}
function nextTargets(current) {
  return allowedNext(DOMAIN, current).map(v => ({ value: v, label: statusLabel(v) }))
}
function ruleHits(v) {
  return (v || '').split(',').filter(Boolean).map(h => RULE_NAMES[h] || h)
}
function sourceLabel(v) { return SOURCE_NAMES[v] || v }
function evidenceBrief(v) {
  if (!v) return '—'
  try {
    const ev = typeof v === 'string' ? JSON.parse(v) : v
    if (ev.weeks) {
      const last = ev.weeks[ev.weeks.length - 1] || {}
      return evidenceBrief(JSON.stringify(last))
    }
    const parts = []
    if (ev.max_day_cnt) parts.push(`单日峰值 ${ev.max_day_cnt} 单`)
    if (ev.wow != null) parts.push(`环比 +${ev.wow}%`)
    if (ev.rank) parts.push(`场景第 ${ev.rank} 位`)
    if (ev.recur_cnt) parts.push(`复发 ${ev.recur_cnt} 单`)
    if (ev.cnt) parts.push(`周单量 ${ev.cnt}`)
    return parts.join('；') || '—'
  } catch (e) { return '—' }
}

async function load() {
  loading.value = true
  try {
    const data = await complaintApi.listProblems({ page_size: 200 })
    rows.value = data?.items || []
    try {
      const sug = await complaintApi.closureSuggestions()
      suggestions.value = sug?.items || []
    } catch (e) { suggestions.value = [] }
  } catch (e) {
    rows.value = []
  } finally {
    loading.value = false
  }
}

async function doScan(dryRun) {
  scanning.value = true
  try {
    const r = await complaintApi.scanProblems(null, dryRun)
    const txt = `候选新建 ${r.created.length}，归并更新 ${r.updated.length}，待重开 ${r.reopen.length}`
    if (dryRun || !r.created.length) {
      ElMessage.info(`扫描完成：${txt}${dryRun ? '（预览未落库）' : ''}`)
    } else {
      ElMessage.success(`扫描完成：${txt}`)
    }
    load()
  } catch (e) { /* request 已提示 */ } finally {
    scanning.value = false
  }
}

function doConfirmOpen(row) {
  openRow.value = row
  openOwner.value = row.owner || ''
  openVisible.value = true
}

async function saveOpen() {
  if (!openOwner.value.trim()) {
    ElMessage.warning('入账必须指定责任人')
    return
  }
  saving.value = true
  try {
    await complaintApi.confirmProblem(openRow.value.problem_no, {
      decision: 'open', owner: openOwner.value.trim(),
    })
    ElMessage.success(`${openRow.value.problem_no} 已入账`)
    openVisible.value = false
    load()
  } catch (e) { /* request 已提示 */ } finally {
    saving.value = false
  }
}

function openMerge(row) {
  mergeRow.value = row
  mergeTarget.value = ''
  mergeVisible.value = true
}

async function saveMerge() {
  if (!mergeTarget.value) {
    ElMessage.warning('请选择合并目标')
    return
  }
  saving.value = true
  try {
    await complaintApi.confirmProblem(mergeRow.value.problem_no, {
      decision: 'merge', merged_into: mergeTarget.value,
    })
    ElMessage.success(`已合并至 ${mergeTarget.value}`)
    mergeVisible.value = false
    load()
  } catch (e) { /* request 已提示 */ } finally {
    saving.value = false
  }
}

async function doIgnore(row) {
  try {
    await ElMessageBox.confirm(`确认忽略 ${row.problem_no}？忽略后可反悔（重新入账）。`, '忽略候选', { type: 'warning' })
  } catch (e) { return }
  try {
    await complaintApi.confirmProblem(row.problem_no, { decision: 'ignore' })
    ElMessage.success('已忽略')
    load()
  } catch (e) { /* request 已提示 */ }
}

async function doTransition(row, t) {
  const payload = {}
  if (t.value === 'open' && !row.owner) {
    ElMessage.warning('进入待处置须先指定责任人（入账时填写）')
    return
  }
  if (t.value === 'closed') {
    let conclusion
    try {
      ({ value: conclusion } = await ElMessageBox.prompt(
        `确认闭环 ${row.problem_no}？请填写闭环结论（必填）`, '闭环确认',
        { type: 'success', inputPlaceholder: '如：措施生效后连续 3 周零复发，问题闭环' }
      ))
    } catch (e) { return }
    if (!conclusion || !conclusion.trim()) {
      ElMessage.warning('闭环结论必填')
      return
    }
    payload.conclusion = conclusion.trim()
  }
  try {
    await ElMessageBox.confirm(`确认将 ${row.problem_no} 置为「${t.label}」？`, '状态流转', { type: 'warning' })
  } catch (e) { return }
  try {
    await complaintApi.changeProblemStatus(row.problem_no, { status: t.value, ...payload })
    ElMessage.success(`已置为「${t.label}」`)
    load()
  } catch (e) { /* request 已提示 */ }
}

async function doClose(s) {
  let conclusion = ''
  try {
    ({ value: conclusion } = await ElMessageBox.prompt(
      `确认闭环 ${s.problem_no}？请填写闭环结论（必填）`, '闭环确认',
      { type: 'success', inputPlaceholder: s.reason }
    ))
  } catch (e) { return }
  if (!conclusion || !conclusion.trim()) {
    ElMessage.warning('闭环结论必填')
    return
  }
  try {
    await complaintApi.changeProblemStatus(s.problem_no, { status: 'closed', conclusion: conclusion.trim() })
    ElMessage.success(`${s.problem_no} 已闭环`)
    load()
  } catch (e) { /* request 已提示 */ }
}

async function openDetail(row) {
  try {
    detail.value = await complaintApi.getProblem(row.problem_no)
    trajectory.value = detail.value.trajectory || []
    if (!allActions.value.length) {
      allActions.value = await complaintApi.listActions()
    }
    linkActionNo.value = ''
    detailVisible.value = true
  } catch (e) { /* request 已提示 */ }
}

async function doLink() {
  if (!linkActionNo.value || !detail.value) return
  try {
    const r = await complaintApi.linkProblemAction(detail.value.problem_no, {
      action_no: linkActionNo.value,
    })
    if (r.warning) ElMessage.warning(r.warning)
    else ElMessage.success('已关联')
    detail.value = await complaintApi.getProblem(detail.value.problem_no)
    detail.value.trajectory = trajectory.value
    load()
  } catch (e) { /* request 已提示 */ }
}

async function doUnlink(linkRow) {
  try {
    await ElMessageBox.confirm(`解除 ${linkRow.action_no} 与该问题的关联？`, '解除关联', { type: 'warning' })
  } catch (e) { return }
  try {
    await complaintApi.unlinkProblemAction(detail.value.problem_no, linkRow.action_no)
    ElMessage.success('已解除')
    detail.value = await complaintApi.getProblem(detail.value.problem_no)
    detail.value.trajectory = trajectory.value
    load()
  } catch (e) { /* request 已提示 */ }
}

function openCreate() {
  createForm.value = { category_l2: '', title: '', owner: '' }
  createVisible.value = true
}

async function saveCreate() {
  if (!createForm.value.category_l2 || !createForm.value.title.trim()) {
    ElMessage.warning('场景与标题必填')
    return
  }
  saving.value = true
  try {
    await complaintApi.createProblem({ ...createForm.value, title: createForm.value.title.trim() })
    ElMessage.success('问题已创建')
    createVisible.value = false
    load()
  } catch (e) { /* request 已提示 */ } finally {
    saving.value = false
  }
}

function doProblemsUrge(confirmSend) {
  if (!confirmSend) {
    urgeResults.value = []
    urgeDone.value = false
    urgeVisible.value = true
  }
  urging.value = true
  complaintApi.problemsUrge({ confirm_send: !!confirmSend })
    .then(data => {
      if (data.skipped && !confirmSend) {
        ElMessage.info(data.skipped)
        urgeVisible.value = false
        return
      }
      urgeResults.value = data.sent || []
      if (confirmSend) {
        ElMessage.success('问题督办邮件已发送')
        urgeVisible.value = false
      } else {
        urgeDone.value = true
      }
    })
    .catch(() => { /* request 已提示 */ })
    .finally(() => { urging.value = false })
}

onMounted(load)
</script>

<style scoped>
.problem-ledger {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.sug-alert {
  margin-bottom: 0;
}
.sug-line {
  font-size: 12.5px;
  padding: 4px 0;
}
.rule-tag {
  margin-right: 4px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.long-run {
  color: var(--danger);
  font-weight: 600;
}
.recur {
  color: var(--danger);
  font-weight: 600;
}
.detail-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.sec-title {
  font-size: 13.5px;
  margin: 8px 0 2px;
  color: var(--text-secondary);
}
.ev-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 12.5px;
}
.ev-text {
  color: var(--text-secondary);
}
.link-row {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.gl-tip {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.7;
}
.urge-line {
  font-size: 12.5px;
  padding: 6px 0;
  border-bottom: 1px dashed var(--border);
}
.urge-line .warn {
  color: var(--warning);
}
</style>
