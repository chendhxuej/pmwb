<template>
  <div class="task-center">
    <div class="page-header">
      <div class="page-title">任务中心</div>
      <div class="page-actions">
        <el-button type="primary" @click="openNewTodo">
          <el-icon><Plus /></el-icon>
          <span>新建待办</span>
        </el-button>
        <el-button type="primary" :loading="loading" @click="refreshAll">刷新</el-button>
      </div>
    </div>

    <!-- 统计卡 -->
    <div class="stats-row">
      <el-card shadow="hover" class="stat-card">
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">全部待办</div>
      </el-card>
      <el-card shadow="hover" class="stat-card stat-danger">
        <div class="stat-value">{{ stats.overdue }}</div>
        <div class="stat-label">已超期</div>
      </el-card>
      <el-card shadow="hover" class="stat-card stat-warning">
        <div class="stat-value">{{ stats.due_soon }}</div>
        <div class="stat-label">3天内临期</div>
      </el-card>
      <el-card
        v-for="src in sourceList"
        :key="src.key"
        shadow="hover"
        class="stat-card stat-mini"
        :class="{ 'stat-active': activeTab === src.key }"
        @click="activeTab = src.key"
      >
        <div class="stat-value">{{ stats.by_source?.[src.key] ?? 0 }}</div>
        <div class="stat-label">{{ src.label }}</div>
      </el-card>
    </div>

    <el-tabs v-model="activeTab" class="task-tabs">
      <el-tab-pane label="全部任务" name="all" />
      <el-tab-pane
        v-for="src in sourceList"
        :key="src.key"
        :label="`${src.label} (${stats.by_source?.[src.key] ?? 0})`"
        :name="src.key"
      />
    </el-tabs>

    <!-- 需求催办 Tab：保留按 SA 分组批量催办交互 -->
    <template v-if="activeTab === 'requirement_urge'">
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
      <div v-if="activeTab === 'operation_issue' && issueTypeList.length" class="issue-type-bar">
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
        <el-table-column label="问题类型" width="110" v-if="activeTab === 'operation_issue'">
          <template #default="{ row }">
            {{ row.detail?.['问题类型'] || '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="owner" label="负责人" width="110" show-overflow-tooltip />
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
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Plus } from '@element-plus/icons-vue'
import { getTaskStats, getTasks, sendTaskEmail } from '@/api/taskCenter.js'
import { getPendingReminders, sendReminder } from '@/api/reminder.js'
import { todoApi } from '@/api/todo'
import StaffSelect from '@/components/Common/StaffSelect.vue'
import MailComposeDialog from '@/components/Common/MailComposeDialog.vue'
import StatusBadge from '@/components/Common/StatusBadge.vue'

const router = useRouter()

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

const sourceList = [
  { key: 'todo', label: '个人待办' },
  { key: 'operation_issue', label: '运营问题' },
  { key: 'research_issue', label: '一线调研' },
  { key: 'dev_ticket', label: '开发工单' },
  { key: 'meeting_action', label: '会议行动项' },
  { key: 'key_work', label: '重点工作' },
  { key: 'requirement_urge', label: '需求催办' },
]

const loading = ref(false)
const activeTab = ref('all')
const stats = ref({ total: 0, overdue: 0, due_soon: 0, by_source: {}, by_status: {}, by_issue_type: {} })
const tasks = ref([])
const selectedTasks = ref([])
const filters = reactive({ status: '', onlyOverdue: false, includeDone: false, keyword: '', issueType: '', owners: [] })
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
  if (activeTab.value === 'requirement_urge') return
  loading.value = true
  try {
    const params = {
      page: pager.page,
      page_size: pager.pageSize,
      include_done: filters.includeDone,
      only_overdue: filters.onlyOverdue,
    }
    if (activeTab.value !== 'all') params.source = activeTab.value
    if (filters.status) params.status = filters.status
    if (filters.issueType) params.issue_type = filters.issueType
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

function refreshAll() {
  loadStats()
  if (activeTab.value === 'requirement_urge') loadUrgeGroups()
  else loadTasks()
}

watch(activeTab, () => {
  pager.page = 1
  selectedTasks.value = []
  filters.issueType = ''
  if (activeTab.value === 'requirement_urge') loadUrgeGroups()
  else loadTasks()
})

watch(() => filters.issueType, () => {
  pager.page = 1
  selectedTasks.value = []
  loadTasks()
})

watch(() => filters.owners, () => {
  pager.page = 1
  selectedTasks.value = []
  loadTasks()
}, { deep: true })

function sourceTagType(source) {
  return {
    todo: 'primary',
    operation_issue: 'danger',
    dev_ticket: 'warning',
    meeting_action: 'success',
    key_work: 'info',
    requirement_urge: 'warning',
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
    operator: 'pmwb',
  })
}

function handleMailSuccess() {
  mailDialogVisible.value = false
  if (mailDialogMode.value === 'task') {
    selectedTasks.value = []
  } else {
    loadUrgeGroups()
    loadStats()
  }
}

// T-E：构建任务清单 HTML（{{{tasks}}} 透传，3210 模板引擎不支持循环，由调用方格式化）
function escapeHtmlText(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
}

function buildTaskListHtml(rows) {
  const items = (rows || [])
    .map((t) => {
      const title = escapeHtmlText(t.title || '（无标题）')
      const owner = escapeHtmlText(t.owner || '未分配')
      const due = escapeHtmlText(t.due_date || '')
      const status = escapeHtmlText(t.status_label || t.status || '')
      const dueText = due ? ` · 截止：${due}` : ''
      const statusText = status ? ` · 状态：${status}` : ''
      return `<li><b>${title}</b>（负责人：${owner}${dueText}${statusText}）</li>`
    })
    .join('')
  return `<ul style="padding-left:20px;margin:8px 0;line-height:1.8;">${items}</ul>`
}

async function openTaskEmail(rows, sendType) {
  if (!rows.length) return
  mailDialogMode.value = 'task'
  // T-E：task 模式切 task_center_notify/urge 场景，正文由 3210 模板渲染（tasks HTML 列表）
  mailDialogScene.value = sendType === 'urge' ? 'task_center_urge' : 'task_center_notify'
  mailDialogVariables.value = {
    tasks: buildTaskListHtml(rows),
    sendType: sendType === 'urge' ? 'urge' : 'notify',
  }
  mailDialogTitle.value = sendType === 'urge' ? '发送催办邮件' : '发送通知邮件'
  const first = rows[0]
  mailDialogSubject.value =
    (sendType === 'urge' ? '催办：' : '通知：') +
    (rows.length === 1 ? (first.title || '') : `${rows.length} 项待办任务`)
  mailDialogBody.value =
    sendType === 'urge'
      ? '各位：\n\n以下任务已到跟进节点，麻烦尽快处理并反馈进展，辛苦了！\n\n——产品经理工作台（PMWB）'
      : '各位：\n\n同步以下任务的当前情况，请知悉。\n\n——产品经理工作台（PMWB）'
  mailDialogContext.value = { tasks: rows.slice(), send_type: sendType }
  // 预填负责人姓名（StaffSelect 会按姓名解析邮箱）
  const names = [
    ...new Set(
      rows
        .map((t) => (t.owner || '').trim())
        .filter((n) => n && n !== '我' && n !== '未分配')
        .flatMap((n) => n.split(/[,;，；、\s]+/).filter(Boolean)),
    ),
  ]
  mailDialogTo.value = names
  mailDialogCc.value = []
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
  loadStats()
  loadTasks()
})
</script>

<style scoped>
.task-center {
  padding: 20px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
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
.task-tabs {
  margin-bottom: 4px;
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
