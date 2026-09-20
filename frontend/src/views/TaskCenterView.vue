<template>
  <div class="task-center">
    <PageHeader
      :title="pageTitle"
      :subtitle="pageSubtitle"
    >
      <template #actions>
        <el-button type="primary" @click="openNewTodo">
          <el-icon><Plus /></el-icon>
          <span>新建待办</span>
        </el-button>
        <el-button type="primary" :loading="loading" @click="refreshAll">刷新</el-button>
      </template>
    </PageHeader>

    <!-- 统计卡（在办口径，与表格默认筛选一致） -->
    <div class="stats-row">
      <el-card shadow="hover" class="stat-card">
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">在办任务</div>
      </el-card>
      <el-card shadow="hover" class="stat-card stat-danger">
        <div class="stat-value">{{ stats.overdue }}</div>
        <div class="stat-label">已超期</div>
      </el-card>
      <el-card shadow="hover" class="stat-card stat-warning">
        <div class="stat-value">{{ stats.due_soon }}</div>
        <div class="stat-label">3天内临期</div>
      </el-card>
    </div>

    <!-- 来源切换（2026-09-20 精简后：来源不再独立子页，统一在全部任务页通过下拉检索） -->
    <div class="source-bar">
      <span class="source-bar-label">来源</span>
      <el-select v-model="filters.source" placeholder="全部来源" clearable style="width: 168px">
        <el-option label="全部来源" value="" />
        <el-option v-for="s in SOURCE_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
    </div>

    <!-- 需求催办 Tab：保留按 SA 分组批量催办交互 -->
    <template v-if="activeSource === 'requirement_urge'">
      <div class="table-hint">
        按 SA 分组的待催办需求（团队评估中「工作量（人天）」未登记且未复核的行，按该行 SA 负责人归集；已复核/不需要开发不催办）。「批量催办」向该 SA 群发汇总邮件，
        单行「催办」单独发送；收件人邮箱按姓名从统一邮件中心通讯录自动解析。
      </div>
      <el-empty v-if="!urgeLoading && !urgeGroups.length" description="暂无待催办需求" />
      <el-card v-for="group in urgeGroups" :key="group.sa_name" shadow="never" class="sa-card">
        <template #header>
          <div class="sa-header">
            <div class="sa-title">
              <el-icon><User /></el-icon>
              <span class="sa-name">{{ group.sa_name }}</span>
              <el-tag size="small" type="info">{{ group.count }} 个需求</el-tag>
            </div>
            <el-button
              type="warning"
              size="small"
              :disabled="group.sa_name === '未分配'"
              @click="openUrgeBatch(group)"
            >
              批量催办
            </el-button>
          </div>
        </template>
        <el-table :data="group.items" size="small" border stripe>
          <el-table-column prop="req_id" label="需求编号" width="200" show-overflow-tooltip />
          <el-table-column prop="req_name" label="需求名称" min-width="220" show-overflow-tooltip />
          <el-table-column prop="system_name" label="负责系统" width="140" show-overflow-tooltip />
          <el-table-column prop="proposer" label="提出人" width="90" />
          <el-table-column label="操作" width="80" align="center" fixed="right">
            <template #default="{ row }">
              <el-button link type="warning" size="small" @click="openUrgeSingle(row)">催办</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <!-- 其余 Tab：统一任务表格 -->
    <template v-else>
      <!-- 运营问题按问题类型汇聚 -->
      <div v-if="activeSource === 'operation_issue' && issueTypeList.length" class="issue-type-bar">
        <span class="issue-type-label">问题类型：</span>
        <el-check-tag
          v-for="it in issueTypeList"
          :key="it.name"
          :checked="filters.issueType === it.name"
          size="small"
          @change="filters.issueType = filters.issueType === it.name ? '' : it.name"
        >
          {{ it.name }} ({{ it.value }})
        </el-check-tag>
      </div>

      <div class="filter-bar">
        <el-select v-model="filters.status" placeholder="状态" clearable style="width: 130px">
          <el-option label="待处理" value="pending" />
          <el-option label="进行中" value="in_progress" />
          <el-option label="已完成" value="done" />
          <el-option label="阻塞/挂起" value="blocked" />
        </el-select>
        <StaffSelect
          v-model="filters.owners"
          :multiple="true"
          placeholder="选择负责人"
          collapse-tags
          style="width: 220px"
          class="staff-owner-select"
        />
        <el-checkbox v-model="filters.onlyOverdue" label="只看超期" />
        <el-checkbox v-model="filters.includeDone" label="含已完成/挂起" />
        <el-input
          v-model="filters.keyword"
          placeholder="搜索标题 / 关键字"
          clearable
          style="width: 200px"
          @keyup.enter="loadTasks"
        />
        <el-button type="primary" plain @click="loadTasks">查询</el-button>
        <div class="filter-spacer" />
        <el-button
          type="warning"
          :disabled="!selectedTasks.length"
          @click="openTaskEmail(selectedTasks, 'urge')"
        >
          批量催办 ({{ selectedTasks.length }})
        </el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="tasks"
        size="small"
        border
        stripe
        @selection-change="(rows) => (selectedTasks = rows)"
      >
        <el-table-column type="selection" width="42" />
        <el-table-column label="来源" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="sourceTagType(row.source)">{{ row.source_label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="任务标题" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" :underline="false" @click="openDetail(row)">{{ row.title || '(无标题)' }}</el-link>
            <el-tag v-if="row.synced_to_todo" size="small" type="success" style="margin-left: 6px">已转待办</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="问题类型" width="110" v-if="activeSource === 'operation_issue'">
          <template #default="{ row }">
            {{ row.detail?.['问题类型'] || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="负责人" width="130" show-overflow-tooltip>
          <template #default="{ row }">{{ (row.owner || '').replace(/,/g, '、') || '—' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="95">
          <template #default="{ row }">
            <StatusBadge module="task_center" :value="row.status" />
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="75">
          <template #default="{ row }">
            <el-tag v-if="row.priority" size="small" :type="row.priority === 'P0' ? 'danger' : row.priority === 'P1' ? 'warning' : 'info'">
              {{ row.priority }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="120">
          <template #default="{ row }">{{ row.created_at ? String(row.created_at).slice(0, 10) : '—' }}</template>
        </el-table-column>
        <el-table-column label="计划完成" width="120">
          <template #default="{ row }">
            <span :class="{ 'due-overdue': row.is_overdue, 'due-soon': row.is_due_soon }">
              {{ row.due_date || '—' }}
              <template v-if="row.is_overdue">（超期）</template>
              <template v-else-if="row.is_due_soon">（临期）</template>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
            <el-button link type="success" size="small" @click="gotoSource(row)">编辑</el-button>
            <el-button link type="warning" size="small" @click="openTaskEmail([row], 'urge')">催办</el-button>
            <el-button link type="info" size="small" @click="openTaskEmail([row], 'notify')">通知</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager-row">
        <el-pagination
          v-model:current-page="pager.page"
          v-model:page-size="pager.pageSize"
          :total="pager.total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="loadTasks"
          @size-change="loadTasks"
        />
      </div>
    </template>

    <!-- 任务详情抽屉 -->
    <el-drawer v-model="drawerVisible" :title="detailTask?.title || '任务详情'" size="70%">
      <template v-if="detailTask">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="来源">
            <el-tag size="small" :type="sourceTagType(detailTask.source)">{{ detailTask.source_label }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            {{ detailTask.status_label }}（原始：{{ detailTask.raw_status || '—' }}）
          </el-descriptions-item>
          <el-descriptions-item label="负责人">{{ detailTask.owner || '—' }}</el-descriptions-item>
          <el-descriptions-item label="优先级">{{ detailTask.priority || '—' }}</el-descriptions-item>
          <el-descriptions-item label="计划完成">
            <span :class="{ 'due-overdue': detailTask.is_overdue, 'due-soon': detailTask.is_due_soon }">
              {{ detailTask.due_date || '—' }}
              <template v-if="detailTask.is_overdue">（已超期）</template>
              <template v-else-if="detailTask.is_due_soon">（3天内临期）</template>
            </span>
          </el-descriptions-item>
          <el-descriptions-item
            v-for="(v, k) in detailFields"
            :key="k"
            :label="k"
          >
            {{ v }}
          </el-descriptions-item>
        </el-descriptions>
        <div class="drawer-actions">
        <!-- 邮件督办记录 -->
        <EmailSuperviseLog ref-type="task_center" :ref-id="detailTask ? detailTask.source + ':' + detailTask.source_id : ''" :key="mailLogKey" />

          <el-button type="primary" @click="gotoSource(detailTask)">前往源模块</el-button>
          <el-button type="warning" @click="openTaskEmail([detailTask], 'urge')">邮件催办</el-button>
          <el-button @click="openTaskEmail([detailTask], 'notify')">邮件通知</el-button>
        </div>
      </template>
    </el-drawer>

    <MailComposeDialog
      v-model="mailDialogVisible"
      :title="mailDialogTitle"
      :scene="mailDialogScene"
      :variables="mailDialogVariables"
      :default-to="mailDialogTo"
      :default-cc="mailDialogCc"
      :default-subject="mailDialogSubject"
      :default-body="mailDialogBody"
      value-key="email"
      :custom-send="mailDialogSendFn"
      :ref-type="mailDialogRefType"
      :ref-id="mailDialogRefId"
      @success="handleMailSuccess"
    />

    <!-- 新建待办（个人待办整合入口，复用待办核心字段） -->
    <el-dialog
      v-model="newTodoVisible"
      title="新建待办"
      width="560px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form :model="newTodoForm" label-width="92px" :rules="newTodoRules" ref="newTodoFormRef">
        <el-form-item label="标题" prop="title">
          <el-input v-model="newTodoForm.title" placeholder="待办标题" maxlength="120" show-word-limit />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="分类" prop="category">
              <el-select v-model="newTodoForm.category" placeholder="请选择" style="width: 100%">
                <el-option v-for="item in categoryOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级" prop="priority">
              <el-select v-model="newTodoForm.priority" placeholder="请选择" style="width: 100%">
                <el-option v-for="item in priorityOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-select v-model="newTodoForm.status" placeholder="请选择" style="width: 100%">
                <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划完成">
              <el-date-picker
                v-model="newTodoForm.due_date"
                type="date"
                placeholder="选择日期"
                style="width: 100%"
                value-format="YYYY-MM-DD"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="内容">
          <el-input v-model="newTodoForm.content" type="textarea" :rows="3" placeholder="补充说明（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="newTodoVisible = false">取消</el-button>
        <el-button type="primary" :loading="newTodoSubmitting" @click="handleNewTodoSubmit">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Plus } from '@element-plus/icons-vue'
import { getTaskStats, getTasks, sendTaskEmail, requestTaskCenterDraft } from '@/api/taskCenter.js'
import { getPendingReminders, sendReminder } from '@/api/reminder.js'
import { todoApi } from '@/api/todo'
import StaffSelect from '@/components/Common/StaffSelect.vue'
import MailComposeDialog from '@/components/Common/MailComposeDialog.vue'
import EmailSuperviseLog from '@/components/Common/EmailSuperviseLog.vue'
import StatusBadge from '@/components/Common/StatusBadge.vue'
import PageHeader from '@/components/Common/PageHeader.vue'

const route = useRoute()
const router = useRouter()

// 与后端 settings.SELF_NAME 对齐（同 MeetingView 约定）：个人待办归属本人，
// 不参与邮件收件人预填。后端 collect_todo 已统一用 SELF_NAME（历史上硬编码「我」）。
const SELF_NAME = '陈大海'

// ------- 新建待办（整合个人待办入口） -------
const newTodoVisible = ref(false)
const newTodoSubmitting = ref(false)
const newTodoFormRef = ref(null)

const categoryOptions = [
  { value: 'requirement', label: '需求' },
  { value: 'ticket', label: '工单' },
  { value: 'operation', label: '运营问题' },
  { value: 'meeting', label: '会议' },
  { value: 'study', label: '学习' },
  { value: 'other', label: '其他' },
]
const statusOptions = [
  { value: 'todo', label: '未开始' },
  { value: 'in_progress', label: '进行中' },
  { value: 'done', label: '已完成' },
  { value: 'cancelled', label: '已取消' },
]
const priorityOptions = [
  { value: 'P0', label: 'P0' },
  { value: 'P1', label: 'P1' },
  { value: 'P2', label: 'P2' },
  { value: 'P3', label: 'P3' },
]

const newTodoForm = reactive({
  title: '',
  content: '',
  category: 'other',
  priority: 'P2',
  status: 'todo',
  due_date: '',
  source: 'manual',
})

const newTodoRules = {
  title: [{ required: true, message: '请输入待办标题', trigger: 'blur' }],
  category: [{ required: true, message: '请选择分类', trigger: 'change' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
}

function openNewTodo() {
  Object.assign(newTodoForm, {
    title: '',
    content: '',
    category: 'other',
    priority: 'P2',
    status: 'todo',
    due_date: '',
    source: 'manual',
  })
  newTodoVisible.value = true
}

async function handleNewTodoSubmit() {
  if (!newTodoFormRef.value) return
  newTodoFormRef.value.validate(async (valid) => {
    if (!valid) return
    const payload = { ...newTodoForm }
    if (!payload.due_date) payload.due_date = null
    newTodoSubmitting.value = true
    try {
      await todoApi.createTodo(payload)
      ElMessage.success('待办创建成功')
      newTodoVisible.value = false
      refreshAll()
    } catch (e) {
      ElMessage.error(e?.response?.data?.message || e?.message || '创建失败')
    } finally {
      newTodoSubmitting.value = false
    }
  })
}

// 来源 key → 中文名（与后端 schemas.task_center.SOURCE_LABELS 对齐）
const SOURCE_LABELS = {
  todo: '个人待办',
  operation_issue: '运营问题',
  research_issue: '一线调研',
  dev_ticket: '开发工单',
  meeting_action: '会议行动项',
  key_work: '重点工作',
  requirement_urge: '需求催办',
  active_optimization: '主动优化',
}

// 当前来源：优先地址栏 ?source=（总览下钻自动设置检索条件），其次旧二级路由 meta.source（现已废弃恒空）；空 = 全部任务
const activeSource = computed(() => route.query.source || route.meta?.source || '')
// 来源下拉选项（全部来源 + 8 个聚合来源），供用户在全部任务页手动切换来源
const SOURCE_OPTIONS = Object.entries(SOURCE_LABELS).map(([value, label]) => ({ value, label }))
const pageTitle = computed(() =>
  activeSource.value
    ? `任务中心 · ${SOURCE_LABELS[activeSource.value] || activeSource.value}`
    : '任务中心'
)
const pageSubtitle = computed(() => {
  if (activeSource.value === 'requirement_urge') return '待催办需求（团队评估环节，按 SA 分组催办）'
  if (activeSource.value) return '该来源任务列表（在办口径，不含已完成/挂起）'
  return '需求催办 / 邮件中心 / 运营监控 —— 三端任务聚合（在办口径）'
})

const loading = ref(false)
const stats = ref({ total: 0, overdue: 0, due_soon: 0, by_source: {}, by_status: {}, by_issue_type: {} })
const tasks = ref([])
const selectedTasks = ref([])
const filters = reactive({ source: '', status: '', onlyOverdue: false, includeDone: false, keyword: '', issueType: '', owners: [] })
const pager = reactive({ page: 1, pageSize: 20, total: 0 })

// 运营问题类型汇聚列表
const issueTypeList = computed(() => {
  const map = stats.value.by_issue_type || {}
  return Object.entries(map)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
})

// ------- 统一任务列表 -------
async function loadStats() {
  try {
    stats.value = (await getTaskStats()) || stats.value
  } catch (e) {
    console.error('获取任务统计失败', e)
  }
}

async function loadTasks() {
  if (activeSource.value === 'requirement_urge') return
  loading.value = true
  try {
    const params = {
      page: pager.page,
      page_size: pager.pageSize,
      include_done: filters.includeDone,
      only_overdue: filters.onlyOverdue,
    }
    if (filters.source) params.source = filters.source
    if (filters.status) params.status = filters.status
    // 「问题类型」仅对运营问题来源有意义，切到其他来源后忽略残留值（避免筛出空列表）
    if (filters.issueType && activeSource.value === 'operation_issue') {
      params.issue_type = filters.issueType
    }
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.owners?.length) params.owners = filters.owners.join(',')
    const res = await getTasks(params)
    tasks.value = res?.items || []
    pager.total = res?.total || 0
  } catch (e) {
    ElMessage.error(e.message || '获取任务列表失败')
  } finally {
    loading.value = false
  }
}

// 按当前来源分流加载：需求催办走 SA 分组视图，其余走统一任务表格
function loadBySource() {
  if (activeSource.value === 'requirement_urge') loadUrgeGroups()
  else loadTasks()
}

function refreshAll() {
  loadStats()
  loadBySource()
}

// ---- 深链筛选：任务总览「责任人分布」矩阵 → /task-center/{来源}?owner=xx&status=yy ----
const VALID_STATUS_KEYS = ['pending', 'in_progress', 'done', 'blocked']

// 当前筛选是否与地址栏一致（用于识别 filters 变更是否由路由同步引起，避免重复拉取）
function filtersMatchQuery() {
  const q = route.query
  return (
    filters.source === (q.source ? String(q.source) : '') &&
    (filters.owners || []).join(',') === (q.owner ? String(q.owner) : '') &&
    filters.status === (q.status ? String(q.status) : '') &&
    filters.issueType === (q.issue_type ? String(q.issue_type) : '') &&
    filters.keyword === (q.keyword ? String(q.keyword) : '')
  )
}

// 路由 query → 筛选状态（返回是否发生变化，供调用方决定要不要重新拉数据）
function applyRouteFilters() {
  const q = route.query
  const nextSource = q.source ? String(q.source) : ''
  const nextOwners = q.owner
    ? String(q.owner).split(',').map((s) => s.trim()).filter(Boolean)
    : []
  const st = q.status && VALID_STATUS_KEYS.includes(String(q.status)) ? String(q.status) : ''
  const it = q.issue_type ? String(q.issue_type) : ''
  const kw = q.keyword ? String(q.keyword) : ''
  const changed =
    nextSource !== filters.source ||
    nextOwners.join(',') !== (filters.owners || []).join(',') ||
    st !== filters.status ||
    it !== filters.issueType ||
    kw !== filters.keyword
  filters.source = nextSource
  filters.owners = nextOwners
  filters.status = st
  filters.issueType = it
  filters.keyword = kw
  return changed
}

// 筛选状态 → 路由 query（刷新/分享不丢筛选条件）
function syncQuery() {
  const q = { ...route.query }
  const owners = filters.owners || []
  if (filters.source) q.source = filters.source
  else delete q.source
  if (owners.length) q.owner = owners.join(',')
  else delete q.owner
  if (filters.status) q.status = filters.status
  else delete q.status
  if (filters.issueType) q.issue_type = filters.issueType
  else delete q.issue_type
  if (filters.keyword) q.keyword = filters.keyword
  else delete q.keyword
  const same =
    (q.source || '') === (route.query.source || '') &&
    (q.owner || '') === (route.query.owner || '') &&
    (q.status || '') === (route.query.status || '') &&
    (q.issue_type || '') === (route.query.issue_type || '') &&
    (q.keyword || '') === (route.query.keyword || '')
  if (!same) router.replace({ query: q })
}

// 筛选变化 → 地址栏同步 + 重新拉取（与地址栏一致的变更说明来自路由，跳过避免重复请求）
watch(
  () => [filters.source, filters.status, filters.issueType, filters.keyword, filters.onlyOverdue, filters.includeDone],
  () => {
    if (filtersMatchQuery()) return
    pager.page = 1
    selectedTasks.value = []
    syncQuery()
    loadBySource()
  }
)

watch(
  () => filters.owners,
  () => {
    if (filtersMatchQuery()) return
    pager.page = 1
    selectedTasks.value = []
    syncQuery()
    loadBySource()
  },
  { deep: true }
)

// 地址栏 query 变化（总览矩阵下钻 / 来源磁贴下钻 / 手动改地址栏）→ 同步到筛选并重新加载
let filtersInitialized = false
watch(
  () => route.query,
  () => {
    const changed = applyRouteFilters()
    if (changed && filtersInitialized) {
      pager.page = 1
      selectedTasks.value = []
      loadBySource()
    }
  }
)

function sourceTagType(source) {
  return {
    todo: 'primary',
    operation_issue: 'danger',
    research_issue: 'primary',
    dev_ticket: 'warning',
    meeting_action: 'success',
    key_work: 'info',
    requirement_urge: 'warning',
    active_optimization: 'success',
  }[source] || 'info'
}

function statusTagType(status) {
  return { pending: 'info', in_progress: 'primary', done: 'success', blocked: 'danger' }[status] || 'info'
}

// ------- 详情抽屉 -------
const drawerVisible = ref(false)
const detailTask = ref(null)
const detailFields = computed(() => {
  const d = detailTask.value?.detail || {}
  const out = {}
  for (const [k, v] of Object.entries(d)) {
    if (v !== null && v !== undefined && v !== '') out[k] = v
  }
  return out
})

function openDetail(row) {
  detailTask.value = row
  drawerVisible.value = true
}

function gotoSource(task) {
  drawerVisible.value = false
  if (task?.source_url) router.push(task.source_url)
}

// ------- 统一邮件发送弹窗（任务邮件 / 需求催办） -------
const mailDialogVisible = ref(false)
const mailDialogTitle = ref('发送邮件')
const mailDialogTo = ref([])
const mailDialogCc = ref([])
const mailDialogSubject = ref('')
const mailDialogBody = ref('')
// 'task' | 'urge'，决定 customSend 调用哪个后端接口
const mailDialogMode = ref('task')
// T-E：scene 模式变量——task 切 task_center_notify/urge 模板，urge（需求催办）切 requirement_reminder 模板
const mailDialogScene = ref('')
const mailDialogVariables = ref({})
const mailDialogContext = ref({})
const mailDialogRefType = ref('')
const mailDialogRefId = ref('')
const mailLogKey = ref(0)

async function mailDialogSendFn(payload) {
  if (mailDialogMode.value === 'task') {
    const ctx = mailDialogContext.value
    return sendTaskEmail({
      tasks: (ctx.tasks || []).map((t) => ({ source: t.source, source_id: t.source_id })),
      to: (payload.to || []).join(', '),
      cc: (payload.cc || []).length ? (payload.cc || []).join(', ') : null,
      subject: payload.subject,
      body: payload.body,
      send_type: ctx.send_type,
      operator: 'pmwb',
      ref_type: mailDialogRefType.value,
      ref_id: mailDialogRefId.value,
      confirm_send: true,
      // T-E：scene 模式下把模板变量透传后端（tasks HTML 列表），保证发送与预览同模板渲染
      template_data: payload.variables || null,
    })
  }
  const ctx = mailDialogContext.value
  return sendReminder({
    req_id: ctx.req_id,
    req_name: ctx.req_name,
    to: (payload.to || []).join(', '),
    cc: (payload.cc || []).length ? (payload.cc || []).join(', ') : null,
    recipient_name: ctx.recipient_name,
    subject: payload.subject,
    body: payload.variables?.body || payload.body || '',
    template_data: payload.variables || null,
    ref_type: mailDialogRefType.value,
    ref_id: mailDialogRefId.value,
    operator: 'pmwb',
  })
}

function handleMailSuccess() {
  mailDialogVisible.value = false
  mailLogKey.value++
  if (mailDialogMode.value === 'task') {
    selectedTasks.value = []
  } else {
    loadUrgeGroups()
    loadStats()
  }
}

// T-E：构建结构化任务数组（2026-09-07 改造）：
// 取代旧的 buildTaskListHtml(HTML 列表)——每条任务都带详情（来源/负责人/截止/状态/优先级/工单内容/超期标记），
// 后端 utils.mail_content.render_task_center_section 据此渲染每条任务卡片（H3+字段表+工单内容）。
const TASK_DESC_KEYS = ['需求描述', '情况说明', '行动项', '内容', '说明', '备注', '风险说明']

function pickTaskDescription(detail) {
  if (!detail) return ''
  for (const k of TASK_DESC_KEYS) {
    if (detail[k]) return String(detail[k]).trim()
  }
  return ''
}

function buildStructuredTasks(rows) {
  return (rows || []).map((t, idx) => ({
    index: idx + 1,
    title: t.title || '（无标题）',
    source_label: t.source_label || t.source || '',
    source: t.source,
    source_id: t.source_id,
    owner: t.owner || '未分配',
    due_date: t.due_date || '',
    status_label: t.status_label || t.status || '',
    priority: t.priority || '',
    description: pickTaskDescription(t.detail || {}),
    is_overdue: !!t.is_overdue,
    is_due_soon: !!t.is_due_soon,
    source_url: t.source_url || '',
  }))
}

function aggregateOwners(rows) {
  const seen = new Set()
  const names = []
  for (const t of rows || []) {
    const owner = (t.owner || '').trim()
    // 本人（SELF_NAME）与历史遗留的「我」一并跳过：个人待办默认归属本人，不参与收件人预填
    if (!owner || owner === '我' || owner === SELF_NAME || owner === '未分配') continue
    for (const sub of owner.split(/[,;，；、\s]+/)) {
      const s = sub.trim()
      if (s && !seen.has(s)) {
        seen.add(s)
        names.push(s)
      }
    }
  }
  return names.join('、')
}

async function openTaskEmail(rows, sendType) {
  if (!rows.length) return
  mailDialogMode.value = 'task'
  // T-F：task 模式切 task_center_notify/urge 场景，正文由 PMWB 装配器
  // (utils.mail_content.render_task_center_section) 按结构化 tasks 渲染每条任务卡片。
  mailDialogScene.value = sendType === 'urge' ? 'task_center_urge' : 'task_center_notify'
  mailDialogVariables.value = {
    tasks: buildStructuredTasks(rows),     // 结构化数组（不再是 <ul> HTML）
    sendType: sendType === 'urge' ? 'urge' : 'notify',
    recipient_name: aggregateOwners(rows),  // 聚合负责人，后端 render_greeting 据此生成称呼
  }
  mailDialogTitle.value = sendType === 'urge' ? '发送催办邮件' : '发送通知邮件'
  // 主题交给后端 default_subject + 装配器格式化生成（单任务：催办：{title}；
  // 多任务：催办：{first_title} 等 {N} 项任务），前端不再硬编码。
  mailDialogSubject.value = ''
  // 正文完全由后端装配（品牌带+称呼+引导语+任务卡片+签名），前端留空。
  mailDialogBody.value = ''
  mailDialogContext.value = { tasks: rows.slice(), send_type: sendType }
  mailDialogRefType.value = 'task_center'
  mailDialogRefId.value = rows[0] ? rows[0].source + ':' + rows[0].source_id : ''
  // 预填负责人姓名（StaffSelect 会按姓名解析邮箱）
  const names = [
    ...new Set(
      rows
        .map((t) => (t.owner || '').trim())
        .filter((n) => n && n !== '我' && n !== SELF_NAME && n !== '未分配')
        .flatMap((n) => n.split(/[,;，；、\s]+/).filter(Boolean)),
    ),
  ]
  mailDialogTo.value = names
  mailDialogCc.value = []
  // T-G：拉取后端按场景拼装好的 Markdown 草稿，作为左侧 Markdown 编辑区默认值。
  // 让用户基于已装配的内容（引导语 + 每条任务 H3+字段表+工单内容）继续编辑调整。
  // 编辑后再点发送，body 走 TaskSendRequest.body 透传，最终由 build_mail_body 再次渲染。
  try {
    const res = await requestTaskCenterDraft(
      buildStructuredTasks(rows),
      sendType === 'urge' ? 'urge' : 'notify',
      '',
    )
    mailDialogBody.value = (res && res.body_md) || ''
  } catch (e) {
    // 拉取失败兜底为空（MailComposeDialog 内已有"按字段重置"按钮可重新生成）
    mailDialogBody.value = ''
    console.warn('[TaskCenter] requestTaskCenterDraft failed:', e && e.message)
  }
  mailDialogVisible.value = true
}

// ------- 需求催办 Tab（沿用原催办中心逻辑） -------
const urgeLoading = ref(false)
const urgeGroups = ref([])

async function loadUrgeGroups() {
  urgeLoading.value = true
  try {
    urgeGroups.value = (await getPendingReminders()) || []
  } catch (e) {
    ElMessage.error(e.message || '获取待催办列表失败')
  } finally {
    urgeLoading.value = false
  }
}

function buildUrgeBatchBody(saName, items) {
  const lines = [
    `${saName}（相关团队）：`,
    ``,
    `你们负责的以下 ${items.length} 个需求现在到前期评估环节了，麻烦尽快把每个需求的①前期评估（可行性、范围、依赖）②工作量初评（大概多少人天）和预计完成时间反馈给我：`,
    ``,
  ]
  items.forEach((it, i) => {
    lines.push(`${i + 1}. [${it.req_id}] ${it.req_name}`)
    lines.push(`   系统：${it.system_name || '未指定'} | 提出人：${it.proposer || '未知'}`)
    if (it.description) {
      lines.push(`   需求描述：${it.description}`)
    }
  })
  lines.push(``, `收到后尽快回我哈，辛苦了！`, ``, `——产品经理工作台（PMWB）`)
  return lines.join('\n')
}

function buildUrgeSingleBody(item) {
  return [
    `${item.sa_name || '相关团队'}（${item.system_name || '相关'}团队）：`,
    ``,
    `你负责的需求现在到前期评估环节了，麻烦尽快把下面两件事搞定，然后反馈给我：`,
    `1. 需求前期评估（可行性、范围、依赖这些）；`,
    `2. 工作量初评（大概要多少人天）和预计完成时间。`,
    ``,
    `需求信息：`,
    `需求编号：${item.req_id || ''}`,
    `需求名称：${item.req_name || ''}`,
    `提出人：${item.proposer || ''}`,
    ...(item.system_name ? [`负责系统：${item.system_name}`] : []),
    ...(item.description ? [`需求描述：${item.description}`] : []),
    ``,
    `收到后尽快回我评估结果哈，辛苦了！`,
    ``,
    `——产品经理工作台（PMWB）`,
  ].join('\n')
}

// T-C：批量催办诉求（xqemail_reminder 模板 items 变量）
function buildUrgeBatchItems(items) {
  const lines = [
    `以下 ${items.length} 个需求已到前期评估环节，请尽快完成每个需求的①前期评估（可行性、范围、依赖）②工作量初评（大概多少人天）和预计完成时间并反馈：`,
    ``,
  ]
  items.forEach((it, i) => {
    lines.push(`${i + 1}. [${it.req_id}] ${it.req_name}`)
    lines.push(`   系统：${it.system_name || '未指定'} | 提出人：${it.proposer || '未知'}`)
  })
  return lines.join('\n')
}

// T-C：单条催办诉求（xqemail_reminder 模板 items 变量）
function buildUrgeSingleItems(item) {
  const lines = [
    `该需求已到前期评估环节，请尽快完成以下事项并反馈：`,
    `1. 需求前期评估（可行性、范围、依赖这些）；`,
    `2. 工作量初评（大概要多少人天）和预计完成时间。`,
  ]
  if (item.system_name) lines.push(`负责系统：${item.system_name}`)
  if (item.description) lines.push(`需求描述：${item.description}`)
  return lines.join('\n')
}

function openUrgeBatch(group) {
  if (group.sa_name === '未分配') {
    ElMessage.warning('该组需求未分配 SA，无法自动解析收件人，请到需求管理指定 SA 后催办。')
    return
  }
  mailDialogMode.value = 'urge'
  mailDialogScene.value = 'requirement_reminder'
  mailDialogVariables.value = {
    reqId: group.items.map((i) => i.req_id).join('; '),
    reqName: `${group.sa_name} 负责的 ${group.count} 个需求评估`,
    saName: group.sa_name,
    proposeTime: '',
    items: buildUrgeBatchItems(group.items),
  }
  mailDialogTitle.value = '发送催办邮件'
  mailDialogSubject.value = `催办：${group.sa_name} 负责的 ${group.count} 个需求评估`
  mailDialogBody.value = buildUrgeBatchBody(group.sa_name, group.items)
  mailDialogContext.value = {
    req_id: group.items.map((i) => i.req_id).join('; '),
    req_name: '',
    recipient_name: group.sa_name,
  }
  mailDialogTo.value = [group.sa_name]
  mailDialogCc.value = []
  mailDialogVisible.value = true
}

function openUrgeSingle(item) {
  mailDialogMode.value = 'urge'
  mailDialogScene.value = 'requirement_reminder'
  mailDialogVariables.value = {
    reqId: item.req_id || '',
    reqName: item.req_name || '',
    saName: item.sa_name || '',
    proposeTime: item.propose_time || item.send_datetime || '',
    items: buildUrgeSingleItems(item),
  }
  mailDialogTitle.value = '发送催办邮件'
  mailDialogSubject.value = `催办：${item.req_name || item.req_id}`
  mailDialogBody.value = buildUrgeSingleBody(item)
  mailDialogContext.value = {
    req_id: item.req_id,
    req_name: item.req_name,
    recipient_name: item.sa_name || '',
  }
  mailDialogTo.value = item.sa_name ? [item.sa_name] : []
  mailDialogCc.value = []
  mailDialogVisible.value = true
}

onMounted(() => {
  // 首次进入时先应用地址栏深链（?source=&owner=&status=&keyword=），再做首次拉取
  applyRouteFilters()
  loadStats()
  loadBySource()
  filtersInitialized = true
})
</script>

<style scoped>
.task-center {
  padding: 20px;
}
.stats-row {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.stat-card {
  flex: 1;
  min-width: 110px;
  text-align: center;
  cursor: default;
}
.stat-mini {
  cursor: pointer;
}
.stat-active {
  border-color: #409eff;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #409eff;
}
.stat-label {
  font-size: 13px;
  color: #606266;
  margin-top: 6px;
}
.stat-danger .stat-value {
  color: #f56c6c;
}
.stat-warning .stat-value {
  color: #e6a23c;
}
.source-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 12px;
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 6px;
}
.source-bar-label {
  font-size: 13px;
  color: #606266;
  font-weight: 600;
}
.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 8px 0 12px;
  flex-wrap: wrap;
}
.filter-spacer {
  flex: 1;
}
.staff-owner-select {
  width: 220px;
}
.pager-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
.due-overdue {
  color: #f56c6c;
  font-weight: 600;
}
.due-soon {
  color: #e6a23c;
  font-weight: 600;
}
.drawer-actions {
  margin-top: 20px;
  display: flex;
  gap: 8px;
}
.table-hint {
  font-size: 13px;
  color: #909399;
  margin: 4px 2px 16px;
  line-height: 1.6;
}
.sa-card {
  margin-bottom: 16px;
}
.sa-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.sa-title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.sa-name {
  font-size: 16px;
  font-weight: 600;
}
.issue-type-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 6px;
}
.issue-type-label {
  font-size: 13px;
  color: #606266;
  font-weight: 600;
}
</style>
