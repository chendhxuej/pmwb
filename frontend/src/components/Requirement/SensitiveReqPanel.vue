<template>
  <div class="srp">
    <!-- ════════ 统计条 ════════ -->
    <div class="pm-stat-grid pm-span-full srp-stats">
      <div class="pm-stat">
        <div class="pm-stat__top">
          <span class="pm-stat__label">在跟需求</span>
        </div>
        <div class="pm-stat__val">{{ stats.total || 0 }}<span class="pm-stat__unit">个</span></div>
        <div class="pm-stat__sub">P0/P1 及等同级别</div>
      </div>
      <div class="pm-stat">
        <div class="pm-stat__top">
          <span class="pm-stat__label">里程碑超期</span>
        </div>
        <div class="pm-stat__val is-danger">{{ stats.overdue || 0 }}<span class="pm-stat__unit">个</span></div>
        <div class="pm-stat__sub">有阶段超期未完成</div>
      </div>
      <div class="pm-stat">
        <div class="pm-stat__top">
          <span class="pm-stat__label">临期(3天内)</span>
        </div>
        <div class="pm-stat__val is-warning">{{ stats.due_soon || 0 }}<span class="pm-stat__unit">个</span></div>
        <div class="pm-stat__sub">临近阶段计划完成</div>
      </div>
      <div class="pm-stat">
        <div class="pm-stat__top">
          <span class="pm-stat__label">督办升级</span>
        </div>
        <div class="pm-stat__val">{{ stats.escalated || 0 }}<span class="pm-stat__unit">个</span></div>
        <div class="pm-stat__sub">已邮件督办/人工提级</div>
      </div>
      <div class="pm-stat">
        <div class="pm-stat__top">
          <span class="pm-stat__label">逾期未上线</span>
        </div>
        <div class="pm-stat__val is-danger">{{ stats.deadline_missed || 0 }}<span class="pm-stat__unit">个</span></div>
        <div class="pm-stat__sub">上线要求日已过</div>
      </div>
    </div>

    <!-- ════════ 工具条 ════════ -->
    <div class="srp-toolbar">
      <div class="srp-filters">
        <el-select v-model="filters.track_status" placeholder="跟踪态" clearable size="small" style="width: 120px">
          <el-option v-for="(meta, val) in TRACK_LABELS" :key="val" :label="meta" :value="val" />
        </el-select>
        <el-select v-model="filters.team" placeholder="团队" clearable filterable size="small" style="width: 150px">
          <el-option v-for="t in teamOptions" :key="t" :label="t" :value="t" />
        </el-select>
        <el-input
          v-model="filters.keyword"
          placeholder="需求名 / 编号"
          size="small"
          clearable
          style="width: 180px"
          @keyup.enter="loadList"
        />
        <el-checkbox v-model="filters.only_overdue" size="small">只看超期</el-checkbox>
        <el-checkbox v-model="filters.include_closed" size="small">含已闭环/移除</el-checkbox>
      </div>
      <div class="srp-actions">
        <el-button
          size="small"
          type="danger"
          plain
          :disabled="!selection.length"
          :loading="composeLoading"
          @click="openSupervise"
        >督办（{{ selection.length }}）</el-button>
        <el-button size="small" :loading="syncing" @click="onSync">同步入池</el-button>
      </div>
    </div>

    <!-- ════════ 列表 ════════ -->
    <el-table
      ref="tableRef"
      v-loading="loading"
      :data="items"
      size="small"
      class="pm-table"
      row-key="req_id"
      @selection-change="onSelChange"
    >
      <el-table-column type="selection" width="42" reserve-selection />
      <el-table-column label="需求" min-width="240">
        <template #default="{ row }">
          <div class="srp-req" @click="openDetail(row.req_id)">
            <span class="srp-req-id font-mono">{{ row.req_id }}</span>
            <span class="srp-req-name">{{ row.req_name }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="级别" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="priorityType(row.priority)">{{ row.priority_label || row.priority || '—' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="上线要求" width="110">
        <template #default="{ row }">
          <span :class="{ 'srp-deadline-missed': row.deadline_missed }">
            {{ row.version_required_date || '未填' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="里程碑进度" width="120">
        <template #default="{ row }">
          <span :class="{ 'srp-overdue-text': row.overdue_count > 0 }">
            {{ row.milestone_done }}/{{ row.milestone_total }}
          </span>
          <el-tag v-if="row.overdue_count > 0" size="small" type="danger" class="srp-ml4">超{{ row.overdue_count }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="当前卡点" min-width="170" show-overflow-tooltip>
        <template #default="{ row }">
          <template v-if="row.focus_milestone">
            <span class="srp-focus-team">{{ row.focus_milestone.team_system_name }}</span>
            <span class="srp-focus-stage">{{ row.focus_milestone.stage_label }}</span>
            <span class="srp-focus-date font-mono">{{ row.focus_milestone.planned_end || '' }}</span>
          </template>
          <span v-else class="text-muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="跟踪态" width="96">
        <template #default="{ row }">
          <StatusBadge module="sensitive_req_track" :value="row.track_status" size="small" />
        </template>
      </el-table-column>
      <el-table-column label="督办" width="60">
        <template #default="{ row }">
          <span :class="{ 'srp-overdue-text': (row.urge_count || 0) > 0 }">{{ row.urge_count || 0 }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openDetail(row.req_id)">详情</el-button>
          <el-button link type="danger" size="small" @click="openSuperviseOne(row)">督办</el-button>
          <el-button link type="warning" size="small" @click="dismissTrack(row)">移出</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="table-footer">
      <span class="text-muted">共 {{ total }} 条</span>
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        small
        background
        @size-change="loadList"
        @current-change="loadList"
      />
    </div>

    <!-- ════════ 详情抽屉：需求 × 团队泳道倒排 ════════ -->
    <el-drawer v-model="detailVisible" size="68%" :title="null" destroy-on-close>
      <template #header>
        <div class="srp-drawer-head">
          <div>
            <div class="srp-req-id font-mono">{{ detail.req_id }}</div>
            <div class="srp-drawer-name">{{ detail.req_name || '（未命名需求）' }}</div>
          </div>
          <div class="flex gap-8">
            <el-tag size="small" :type="priorityType(detail.priority)">{{ detail.priority_label || '—' }}</el-tag>
            <StatusBadge v-if="detail.track_status" module="sensitive_req_track" :value="detail.track_status" />
          </div>
        </div>
      </template>

      <div v-loading="detailLoading" class="srp-detail">
        <!-- 关键信息条 -->
        <div class="srp-meta">
          <div class="srp-meta-item">
            <span class="srp-meta-label">上线要求</span>
            <span class="srp-meta-val font-mono" :class="{ 'srp-deadline-missed': detail.deadline_missed }">
              {{ detail.version_required_date || '未填' }}
            </span>
          </div>
          <div class="srp-meta-item">
            <span class="srp-meta-label">倒计时</span>
            <span class="srp-meta-val font-mono">
              {{ daysText }}
            </span>
          </div>
          <div class="srp-meta-item">
            <span class="srp-meta-label">需求状态</span>
            <span class="srp-meta-val">{{ detail.req_status_label || detail.req_status || '—' }}</span>
          </div>
          <div class="srp-meta-item">
            <span class="srp-meta-label">实际上线</span>
            <span class="srp-meta-val font-mono">{{ detail.delivered_date || '—' }}</span>
          </div>
          <div class="srp-meta-item srp-meta-actions">
            <el-button size="small" type="primary" plain :disabled="!detail.version_required_date" @click="openEditor">
              {{ detail.milestone_total ? '调整倒排' : '生成倒排建议' }}
            </el-button>
          </div>
        </div>
        <div v-if="!detail.version_required_date" class="pm-notice srp-notice-warn">
          该需求未填写「版本要求上线时间」，请先到需求列表补填后再倒排。
        </div>

        <!-- 团队泳道 -->
        <div v-for="(rows, team) in detail.lanes || {}" :key="team" class="srp-lane">
          <div class="srp-lane-head">
            <span class="srp-lane-team">{{ team }}</span>
            <span class="srp-lane-progress text-muted">{{ laneProgress(rows) }}</span>
          </div>
          <el-table :data="rows" size="small" class="pm-table">
            <el-table-column label="阶段" width="90">
              <template #default="{ row }">
                <span class="srp-stage-label">{{ row.stage_label }}</span>
              </template>
            </el-table-column>
            <el-table-column label="责任人" min-width="110">
              <template #default="{ row }">
                <span v-if="row.owner">{{ row.owner }}</span>
                <span v-else class="text-muted">未填</span>
              </template>
            </el-table-column>
            <el-table-column label="计划开始" width="100">
              <template #default="{ row }">{{ row.planned_start || '—' }}</template>
            </el-table-column>
            <el-table-column label="计划完成" width="110">
              <template #default="{ row }">
                <span :class="{ 'srp-overdue-text': row.is_overdue, 'srp-due-soon': row.is_due_soon }">
                  {{ row.planned_end || '—' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="实际完成" width="110">
              <template #default="{ row }">
                <span>{{ row.actual_end || '—' }}</span>
                <div v-if="!row.actual_end && row.actual_hint" class="srp-hint">可回填 {{ row.actual_hint }}</div>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <StatusBadge module="sensitive_milestone" :value="row.status" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="130" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="row.status !== 'done'"
                  link type="success" size="small"
                  @click="completeMilestone(row)"
                >完成</el-button>
                <el-button link type="primary" size="small" @click="openMsEdit(row)">修正</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <el-empty
          v-if="detailLoading === false && !Object.keys(detail.lanes || {}).length"
          description="尚未制定倒排计划，点击「生成倒排建议」按模板排期"
          :image-size="72"
        />

        <!-- 督办历史 -->
        <div v-if="detail.req_id" class="srp-log">
          <div class="srp-lane-head">
            <span class="srp-lane-team">督办记录</span>
          </div>
          <EmailSuperviseLog ref-type="sensitive_req" :ref-id="detail.req_id" :refresh-key="mailLogKey" />
        </div>
      </div>
    </el-drawer>

    <!-- ════════ 倒排编辑弹窗（全量保存） ════════ -->
    <el-dialog v-model="editorVisible" title="倒排计划编辑" width="920px" top="4vh" append-to-body>
      <div class="srp-editor-tip">
        倒排终点 = 上线要求日 <b class="font-mono">{{ detail.version_required_date || '—' }}</b>；
        各阶段计划完成日不得晚于该日。保存为全量覆盖（删除未列出的行）。
      </div>
      <el-button size="small" class="srp-mb8" :loading="suggestionLoading" @click="applySuggestion">
        按模板重新生成（覆盖当前编辑）
      </el-button>
      <el-table :data="editorItems" size="small" max-height="440" class="pm-table">
        <el-table-column label="团队" width="150">
          <template #default="{ row }">
            <el-input v-model="row.team_system_name" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="阶段" width="90">
          <template #default="{ row }">{{ row.stage_label }}</template>
        </el-table-column>
        <el-table-column label="责任人" width="130">
          <template #default="{ row }">
            <el-input v-model="row.owner" size="small" placeholder="多人逗号分隔" />
          </template>
        </el-table-column>
        <el-table-column label="计划开始" width="150">
          <template #default="{ row }">
            <el-date-picker v-model="row.planned_start" type="date" size="small" value-format="YYYY-MM-DD" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column label="计划完成" width="150">
          <template #default="{ row }">
            <el-date-picker v-model="row.planned_end" type="date" size="small" value-format="YYYY-MM-DD" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-select v-model="row.status" size="small">
              <el-option label="未开始" value="pending" />
              <el-option label="进行中" value="doing" />
              <el-option label="已完成" value="done" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="风险/备注" min-width="140">
          <template #default="{ row }">
            <el-input v-model="row.risk_note" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="" width="52">
          <template #default="{ $index }">
            <el-button link type="danger" size="small" @click="editorItems.splice($index, 1)">删</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveMilestones">保存倒排</el-button>
      </template>
    </el-dialog>

    <!-- ════════ 单里程碑修正弹窗 ════════ -->
    <el-dialog v-model="msEditVisible" title="修正里程碑" width="440px" append-to-body>
      <div v-if="msEditRow" class="srp-ms-edit">
        <div class="srp-ms-line">
          <span class="srp-meta-label">{{ msEditRow.team_system_name }} · {{ msEditRow.stage_label }}</span>
        </div>
        <div class="srp-ms-field">
          <span class="srp-meta-label">责任人</span>
          <el-input v-model="msEditRow.owner" size="small" placeholder="多人逗号分隔" />
        </div>
        <div class="srp-ms-field">
          <span class="srp-meta-label">实际完成日</span>
          <el-date-picker v-model="msEditRow.actual_end" type="date" size="small" value-format="YYYY-MM-DD" clearable />
          <div v-if="msEditRow.actual_hint" class="srp-hint">系统事实时间：{{ msEditRow.actual_hint }}（只读引用，可回填确认）</div>
        </div>
        <div class="srp-ms-field">
          <span class="srp-meta-label">状态</span>
          <el-select v-model="msEditRow.status" size="small">
            <el-option label="未开始" value="pending" />
            <el-option label="进行中" value="doing" />
            <el-option label="已完成" value="done" />
          </el-select>
        </div>
        <div class="srp-ms-field">
          <span class="srp-meta-label">计划完成</span>
          <el-date-picker v-model="msEditRow.planned_end" type="date" size="small" value-format="YYYY-MM-DD" clearable />
        </div>
        <div class="srp-ms-field">
          <span class="srp-meta-label">风险/备注</span>
          <el-input v-model="msEditRow.risk_note" size="small" type="textarea" :rows="2" />
        </div>
      </div>
      <template #footer>
        <el-button @click="msEditVisible = false">取消</el-button>
        <el-button type="primary" :loading="msSaving" @click="saveMsEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- ════════ 督办邮件（真发仅页面显式点击 confirm_send=true） ════════ -->
    <MailComposeDialog
      v-model="composeVisible"
      title="敏感需求督办"
      scene="sensitive_req_urge"
      :default-to="composeTo"
      :default-subject="composeSubject"
      :default-body="composeBody"
      value-key="email"
      :variables="composeVariables"
      :custom-send="sendFn"
      @success="onSent"
    />
  </div>
</template>

<script setup>
/**
 * 敏感需求跟踪面板（需求与交付第 5 个 tab，2026-10-25）。
 *
 * 数据口径：
 *  - 列表/统计单一源 = /sensitive-reqs 接口，前端禁止自算；
 *  - 上线要求（倒排终点）权威源 = ext.version_required_date，只读展示；
 *  - 督办走 /sensitive-reqs/send（scene=sensitive_req_urge），
 *    draft 拿结构化清单透传 variables，保证预览=实发。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import StatusBadge from '@/components/Common/StatusBadge.vue'
import EmailSuperviseLog from '@/components/Common/EmailSuperviseLog.vue'
import MailComposeDialog from '@/components/Common/MailComposeDialog.vue'
import {
  getSensitiveReqs,
  getSensitiveReqStats,
  getSensitiveReqDetail,
  getSensitiveReqSuggestion,
  saveSensitiveReqMilestones,
  updateSensitiveReqMilestone,
  requestSensitiveReqDraft,
  sendSensitiveReqEmail,
  syncSensitiveReqs,
  updateSensitiveReqTrack,
} from '@/api/sensitiveReq.js'

const STAGE_LABELS = {
  evaluate: '需求评估',
  plan: '方案制定',
  dev: '开发',
  test: '测试',
  deploy: '上线交付',
}
const TRACK_LABELS = {
  active: '跟踪中',
  delayed: '已逾期',
  escalated: '督办升级',
  resolved: '已上线闭环',
  dropped: '已移除',
}

const loading = ref(false)
const syncing = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const stats = ref({})
const filters = reactive({
  track_status: '',
  team: '',
  keyword: '',
  only_overdue: false,
  include_closed: false,
})
const selection = ref([])
const tableRef = ref(null)
const mailLogKey = ref(0)

const teamOptions = computed(() => Object.keys(stats.value.by_team || {}))

function priorityType(p) {
  return { P0: 'danger', P1: 'warning', P2: '', P3: 'info' }[p] || ''
}

async function loadStats() {
  try {
    stats.value = (await getSensitiveReqStats()) || {}
  } catch (e) {
    console.warn('[SensitiveReqPanel] stats failed:', e && e.message)
  }
}

async function loadList() {
  loading.value = true
  try {
    const res = await getSensitiveReqs({
      track_status: filters.track_status || undefined,
      team: filters.team || undefined,
      keyword: filters.keyword || undefined,
      only_overdue: filters.only_overdue || undefined,
      include_closed: filters.include_closed || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    items.value = (res && res.items) || []
    total.value = (res && res.total) || 0
    if (res && res.summary) {
      // 列表返回的 summary 与统计接口口径一致，兜底刷新统计条
      stats.value = { ...stats.value, ...res.summary }
    }
  } catch (e) {
    ElMessage.error('拉取敏感需求列表失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

function onSelChange(rows) {
  selection.value = rows
}

async function onSync() {
  syncing.value = true
  try {
    const res = await syncSensitiveReqs()
    ElMessage.success(
      `同步完成：敏感 ${res.sensitive} 个（新增 ${res.added}，闭环 ${res.resolved}，超期 ${res.delayed}）`
    )
    await Promise.all([loadList(), loadStats()])
  } catch (e) {
    ElMessage.error('同步失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  } finally {
    syncing.value = false
  }
}

/* ── 详情抽屉 ─────────────────────────────────────────── */
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref({})

const daysText = computed(() => {
  const d = detail.value.days_to_deadline
  if (d === null || d === undefined) return '—'
  if (detail.value.deadline_missed) return `已过期 ${Math.abs(d)} 天`
  return `剩 ${d} 天`
})

function laneProgress(rows) {
  const done = rows.filter((r) => r.status === 'done').length
  return `${done}/${rows.length} 完成`
}

async function openDetail(reqId) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = {}
  try {
    detail.value = (await getSensitiveReqDetail(reqId)) || {}
  } catch (e) {
    ElMessage.error('拉取详情失败：' + (e?.response?.data?.message || e.message || '未知错误'))
    detailVisible.value = false
  } finally {
    detailLoading.value = false
  }
}

/* ── 里程碑操作 ───────────────────────────────────────── */
async function completeMilestone(row) {
  try {
    await updateSensitiveReqMilestone(row.id, {
      status: 'done',
      actual_end: row.actual_end || new Date().toISOString().slice(0, 10),
    })
    ElMessage.success(`${row.team_system_name} · ${row.stage_label} 已完成`)
    await openDetail(detail.value.req_id)
  } catch (e) {
    ElMessage.error('操作失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  }
}

const msEditVisible = ref(false)
const msEditRow = ref(null)
const msSaving = ref(false)

function openMsEdit(row) {
  msEditRow.value = { ...row }
  msEditVisible.value = true
}

async function saveMsEdit() {
  if (!msEditRow.value) return
  msSaving.value = true
  try {
    await updateSensitiveReqMilestone(msEditRow.value.id, {
      owner: msEditRow.value.owner ?? '',
      actual_end: msEditRow.value.actual_end || null,
      status: msEditRow.value.status,
      planned_end: msEditRow.value.planned_end || null,
      risk_note: msEditRow.value.risk_note ?? '',
    })
    msEditVisible.value = false
    ElMessage.success('里程碑已修正')
    await openDetail(detail.value.req_id)
    await loadList()
  } catch (e) {
    ElMessage.error('保存失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  } finally {
    msSaving.value = false
  }
}

/* ── 倒排编辑（全量保存） ─────────────────────────────── */
const editorVisible = ref(false)
const editorItems = ref([])
const suggestionLoading = ref(false)
const saving = ref(false)

async function applySuggestion() {
  suggestionLoading.value = true
  try {
    const sug = await getSensitiveReqSuggestion(detail.value.req_id)
    editorItems.value = (sug.items || []).map((it) => ({ ...it }))
  } catch (e) {
    ElMessage.error('生成建议失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  } finally {
    suggestionLoading.value = false
  }
}

async function openEditor() {
  editorItems.value = (detail.value.milestones || []).map((m) => ({
    team_system_name: m.team_system_name,
    stage: m.stage,
    stage_label: m.stage_label,
    owner: m.owner || '',
    planned_start: m.planned_start,
    planned_end: m.planned_end,
    status: m.status,
    risk_note: m.risk_note || '',
    source: 'manual',
  }))
  editorVisible.value = true
  if (!editorItems.value.length) await applySuggestion()
}

async function saveMilestones() {
  saving.value = true
  try {
    const res = await saveSensitiveReqMilestones(
      detail.value.req_id,
      editorItems.value.map((it) => ({
        team_system_name: (it.team_system_name || '').trim(),
        stage: it.stage,
        owner: it.owner || '',
        planned_start: it.planned_start || null,
        planned_end: it.planned_end || null,
        status: it.status || 'pending',
        risk_note: it.risk_note || '',
        source: it.source || 'manual',
      }))
    )
    editorVisible.value = false
    ElMessage.success(`倒排已保存（${res.saved} 条）`)
    await openDetail(detail.value.req_id)
    await Promise.all([loadList(), loadStats()])
  } catch (e) {
    ElMessage.error('保存失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

/* ── 督办邮件 ─────────────────────────────────────────── */
const composeVisible = ref(false)
const composeLoading = ref(false)
const composeVariables = ref({})
const composeBody = ref('')
const composeSubject = ref('')
const composeTo = ref([])
let pendingRefs = []

const DESC_KEYS = ['需求描述', '情况说明', '行动项', '内容', '说明', '备注', '风险说明']
function pickDescription(detailObj) {
  if (!detailObj) return ''
  for (const k of DESC_KEYS) {
    if (detailObj[k]) return String(detailObj[k]).trim()
  }
  return ''
}

function structuralize(rows) {
  return rows.map((t, i) => ({
    index: i + 1,
    title: t.title || t.req_name || '（未命名需求）',
    source_label: '敏感需求',
    source: 'sensitive_req',
    source_id: t.req_id,
    owner: t.focus_milestone?.owner || (t.milestones || []).map((m) => m.owner).filter(Boolean).join('、') || '未分配',
    created_at: t.first_seen_at ? String(t.first_seen_at).slice(0, 10) : '',
    due_date:
      t.focus_milestone?.planned_end || t.version_required_date || '',
    status_label: `${t.track_label || t.track_status}${t.focus_milestone ? '｜' + t.focus_milestone.stage_label : ''}`,
    priority: t.priority_label || t.priority || '',
    description: pickDescription(t.detail) ||
      `上线要求 ${t.version_required_date || '未填'}；里程碑 ${t.milestone_done}/${t.milestone_total} 完成` +
      (t.overdue_count ? `；超期 ${t.overdue_count} 项` : ''),
    is_overdue: (t.overdue_count || 0) > 0 || !!t.deadline_missed,
    is_due_soon: (t.due_soon_count || 0) > 0,
    source_url: t.source_url || '',
  }))
}

async function openSupervise() {
  if (!selection.value.length) return
  await doCompose(selection.value)
}

async function openSuperviseOne(row) {
  await doCompose([row])
}

async function doCompose(rows) {
  composeLoading.value = true
  pendingRefs = rows.map((r) => ({ source: 'sensitive_req', source_id: r.req_id }))
  const structured = structuralize(rows)
  // 兜底：draft 接口失败时仍按任务 owner 带出收件人
  composeTo.value = [
    ...new Set(
      structured.flatMap((t) =>
        String(t.owner || '').split(/[,，;；、]+/).map((s) => s.trim()).filter((s) => s && s !== '未分配')
      )
    ),
  ]
  composeVariables.value = {
    tasks: structured,
    sendType: 'urge',
    recipient_name: composeTo.value.join('、'),
  }
  try {
    const res = await requestSensitiveReqDraft(pendingRefs, 'urge', '', '')
    // 收件人 = 后端按 urge 口径（还未完成开发的团队）全部环节涉及人去重
    if (res && Array.isArray(res.recipients) && res.recipients.length) {
      composeTo.value = res.recipients
    }
    composeVariables.value = {
      tasks: structured,
      sendType: 'urge',
      recipient_name: (res && res.recipient_name) || composeTo.value.join('、'),
    }
    composeBody.value = (res && res.body_md) || ''
    composeSubject.value = (res && res.subject) || ''
  } catch (e) {
    composeBody.value = ''
    composeSubject.value = ''
    console.warn('[SensitiveReqPanel] draft failed:', e && e.message)
  } finally {
    composeLoading.value = false
  }
  composeVisible.value = true
}

async function sendFn(payload) {
  return sendSensitiveReqEmail({
    tasks: pendingRefs,
    to: (payload.to || []).join(', '),
    cc: (payload.cc || []).length ? (payload.cc || []).join(', ') : null,
    subject: payload.subject,
    body: payload.body,
    send_type: 'urge',
    operator: 'pmwb',
    confirm_send: true, // 真发唯一入口：页面显式点击
    template_data: payload.variables || null,
  })
}

async function onSent() {
  composeVisible.value = false
  mailLogKey.value++
  ElMessage.success(`已发送敏感需求督办邮件（${pendingRefs.length} 条）`)
  if (detailVisible.value && detail.value.req_id) {
    await openDetail(detail.value.req_id)
  }
  await loadList()
}

/* ── 跟踪态人工操作 ───────────────────────────────────── */
// 手工移出跟踪池（2026-10-27）：manual_override='dismiss' 永不复活——
// 之后即使级别再命中或重打超期风险标，sync 也不会自动纳入（仅可人工重新纳入）。
async function dismissTrack(row) {
  try {
    await ElMessageBox.confirm(
      `确认将需求「${row.req_name || row.req_id}」移出敏感跟踪池？移出后自动规则不再将其纳入（即使重新满足条件也不会自动恢复）。`,
      '移出敏感跟踪',
      { type: 'warning', confirmButtonText: '移出', cancelButtonText: '取消' }
    )
  } catch { return }
  await updateSensitiveReqTrack(row.req_id, { manual_override: 'dismiss', operator: 'pmwb' })
  ElMessage.success(`需求「${row.req_id}」已移出敏感跟踪池`)
  selection.value = []
  await Promise.all([loadList(), loadStats()])
}

defineExpose({
  openDetail,
  refresh: () => Promise.all([loadList(), loadStats()]),
})

onMounted(async () => {
  await Promise.all([loadStats(), loadList()])
})
</script>

<style scoped>
.srp { display: flex; flex-direction: column; gap: 12px; padding: 12px 20px 20px; }
.srp-stats { --cols: 5; }
.srp-toolbar { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.srp-filters { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.srp-actions { display: flex; gap: 8px; }
.srp-req { display: flex; flex-direction: column; cursor: pointer; line-height: 1.4; }
.srp-req:hover .srp-req-name { color: var(--accent, #165dff); }
.srp-req-id { font-size: 11.5px; color: var(--text-muted); }
.srp-req-name { font-size: 13px; color: var(--text-primary); font-weight: 500; }
.srp-deadline-missed { color: var(--danger, #f53f3f); font-weight: 600; }
.srp-overdue-text { color: var(--danger, #f53f3f); font-weight: 600; }
.srp-due-soon { color: var(--warning, #ff7d00); font-weight: 600; }
.srp-ml4 { margin-left: 4px; }
.srp-focus-team { font-weight: 600; margin-right: 6px; }
.srp-focus-stage { color: var(--text-secondary); margin-right: 6px; }
.srp-focus-date { color: var(--text-muted); font-size: 12px; }
.table-footer { display: flex; align-items: center; justify-content: space-between; margin-top: 8px; }

/* 详情抽屉 */
.srp-drawer-head { display: flex; align-items: center; justify-content: space-between; width: 100%; }
.srp-drawer-name { font-size: 15px; font-weight: 600; color: var(--text-primary); margin-top: 2px; }
.srp-detail { display: flex; flex-direction: column; gap: 14px; }
.srp-meta { display: flex; gap: 22px; flex-wrap: wrap; align-items: center; background: var(--bg-muted, #f7f8fa); border-radius: 8px; padding: 10px 14px; }
.srp-meta-item { display: flex; align-items: baseline; gap: 6px; }
.srp-meta-actions { margin-left: auto; }
.srp-meta-label { font-size: 12px; color: var(--text-muted); }
.srp-meta-val { font-size: 13px; color: var(--text-primary); font-weight: 500; }
.srp-notice-warn { font-size: 12.5px; }
.srp-lane { display: flex; flex-direction: column; gap: 6px; }
.srp-lane-head { display: flex; align-items: baseline; gap: 10px; }
.srp-lane-team { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.srp-lane-progress { font-size: 12px; }
.srp-stage-label { font-weight: 500; }
.srp-hint { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
.srp-log { margin-top: 6px; }

/* 编辑弹窗 */
.srp-editor-tip { font-size: 12.5px; color: var(--text-secondary); margin-bottom: 8px; line-height: 1.6; }
.srp-editor-tip b { color: var(--text-primary); }
.srp-mb8 { margin-bottom: 8px; }
.srp-ms-edit { display: flex; flex-direction: column; gap: 10px; }
.srp-ms-field { display: flex; flex-direction: column; gap: 4px; }
</style>
