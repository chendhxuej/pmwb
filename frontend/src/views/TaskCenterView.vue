<template>
  <div class="task-center">
    <div class="page-header">
      <div class="page-title">任务中心</div>
      <div class="page-actions">
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
        按 SA 分组的待催办需求（团队评估中「工作量（人天）」未登记的行，按该行 SA 负责人归集）。「批量催办」向该 SA 群发汇总邮件，
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
      <div class="filter-bar">
        <el-select v-model="filters.status" placeholder="状态" clearable style="width: 130px">
          <el-option label="待处理" value="pending" />
          <el-option label="进行中" value="in_progress" />
          <el-option label="已完成" value="done" />
          <el-option label="阻塞/挂起" value="blocked" />
        </el-select>
        <el-checkbox v-model="filters.onlyOverdue" label="只看超期" />
        <el-checkbox v-model="filters.includeDone" label="含已完成/挂起" />
        <el-input
          v-model="filters.keyword"
          placeholder="搜索标题 / 负责人"
          clearable
          style="width: 220px"
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
        <el-table-column prop="title" label="任务标题" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" :underline="false" @click="openDetail(row)">{{ row.title || '(无标题)' }}</el-link>
            <el-tag v-if="row.synced_to_todo" size="small" type="success" style="margin-left: 6px">已转待办</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="owner" label="负责人" width="110" show-overflow-tooltip />
        <el-table-column label="状态" width="95">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTagType(row.status)">{{ row.status_label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="75">
          <template #default="{ row }">
            <el-tag v-if="row.priority" size="small" :type="row.priority === 'P0' ? 'danger' : row.priority === 'P1' ? 'warning' : 'info'">
              {{ row.priority }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="截止日期" width="120">
          <template #default="{ row }">
            <span :class="{ 'due-overdue': row.is_overdue, 'due-soon': row.is_due_soon }">
              {{ row.due_date || '—' }}
              <template v-if="row.is_overdue">（超期）</template>
              <template v-else-if="row.is_due_soon">（临期）</template>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
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
    <el-drawer v-model="drawerVisible" :title="detailTask?.title || '任务详情'" size="440px">
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
          <el-descriptions-item label="截止日期">
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

    <!-- 任务邮件对话框（通知/催办） -->
    <el-dialog v-model="emailDialogVisible" :title="emailForm.send_type === 'urge' ? '发送催办邮件' : '发送通知邮件'" width="620px">
      <el-form :model="emailForm" label-width="100px">
        <el-form-item label="关联任务">
          <div class="task-chips">
            <el-tag v-for="t in emailForm.tasks" :key="t.task_id" size="small" closable @close="removeEmailTask(t)">
              [{{ t.source_label }}] {{ t.title?.slice(0, 24) }}
            </el-tag>
          </div>
        </el-form-item>
        <el-form-item label="收件人">
          <StaffSelect v-model="emailTo" multiple value-key="email" placeholder="选择人员自动带出邮箱，支持手输" />
          <div class="form-hint">已按负责人姓名自动解析邮箱；无邮箱时回退显示姓名。</div>
        </el-form-item>
        <el-form-item label="抄送">
          <StaffSelect v-model="emailCc" multiple value-key="email" placeholder="抄送人员" />
        </el-form-item>
        <el-form-item label="主题">
          <el-input v-model="emailForm.subject" />
        </el-form-item>
        <el-form-item label="正文">
          <el-input v-model="emailForm.body" type="textarea" :rows="8" />
          <div class="form-hint">发送时系统会在正文末尾自动附上任务清单（标题/负责人/状态/截止时间）。</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="emailDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="emailSending" @click="handleTaskEmailSend">发送</el-button>
      </template>
    </el-dialog>

    <!-- 需求催办邮件对话框（沿用原催办中心交互） -->
    <el-dialog v-model="urgeDialogVisible" title="发送催办邮件" width="600px">
      <el-form :model="urgeForm" label-width="100px">
        <el-form-item label="需求编号">
          <el-input v-model="urgeForm.req_id" disabled />
        </el-form-item>
        <el-form-item label="收件人">
          <StaffSelect v-model="urgeTo" multiple value-key="email" placeholder="选择人员自动带出邮箱，支持手输" />
          <div class="form-hint">收件人邮箱按姓名自动从邮件中心通讯录解析；无邮箱时回退显示姓名。</div>
        </el-form-item>
        <el-form-item label="抄送">
          <StaffSelect v-model="urgeCc" multiple value-key="email" placeholder="抄送人员" />
        </el-form-item>
        <el-form-item label="主题">
          <el-input v-model="urgeForm.subject" />
        </el-form-item>
        <el-form-item label="正文">
          <el-input v-model="urgeForm.body" type="textarea" :rows="10" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="urgeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="urgeSending" @click="handleUrgeSend">发送</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User } from '@element-plus/icons-vue'
import { getTaskStats, getTasks, resolveTaskContacts, sendTaskEmail } from '@/api/taskCenter.js'
import { getPendingReminders, sendReminder, resolveContacts } from '@/api/reminder.js'
import StaffSelect from '@/components/Common/StaffSelect.vue'

const router = useRouter()

const sourceList = [
  { key: 'todo', label: '个人待办' },
  { key: 'operation_issue', label: '运营问题' },
  { key: 'dev_ticket', label: '开发工单' },
  { key: 'meeting_action', label: '会议行动项' },
  { key: 'key_work', label: '重点工作' },
  { key: 'requirement_urge', label: '需求催办' },
]

const loading = ref(false)
const activeTab = ref('all')
const stats = ref({ total: 0, overdue: 0, due_soon: 0, by_source: {}, by_status: {} })
const tasks = ref([])
const selectedTasks = ref([])
const filters = reactive({ status: '', onlyOverdue: false, includeDone: false, keyword: '' })
const pager = reactive({ page: 1, pageSize: 20, total: 0 })

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
    if (filters.keyword) params.keyword = filters.keyword
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
  if (activeTab.value === 'requirement_urge') loadUrgeGroups()
  else loadTasks()
})

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

// ------- 任务邮件（通知/催办） -------
const EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/
function invalidEmails(raw) {
  if (!raw) return []
  return raw
    .split(/[,;，；\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .filter((s) => !EMAIL_RE.test(s))
}

const emailDialogVisible = ref(false)
const emailSending = ref(false)
const emailForm = reactive({ tasks: [], to: '', cc: '', subject: '', body: '', send_type: 'urge' })
const emailTo = ref([])
const emailCc = ref([])
const urgeForm = reactive({ req_id: '', req_name: '', to: '', cc: '', recipient_name: '', subject: '', body: '' })
const urgeTo = ref([])
const urgeCc = ref([])

async function openTaskEmail(rows, sendType) {
  if (!rows.length) return
  emailForm.tasks = rows.slice()
  emailForm.send_type = sendType
  emailTo.value = []
  emailCc.value = []
  const first = rows[0]
  emailForm.subject =
    (sendType === 'urge' ? '催办：' : '通知：') +
    (rows.length === 1 ? first.title?.slice(0, 40) : `${rows.length} 项待办任务`)
  emailForm.body =
    sendType === 'urge'
      ? '各位：\n\n以下任务已到跟进节点，麻烦尽快处理并反馈进展，辛苦了！\n\n——产品经理工作台（PMWB）'
      : '各位：\n\n同步以下任务的当前情况，请知悉。\n\n——产品经理工作台（PMWB）'
  emailDialogVisible.value = true
  // 按负责人姓名自动解析邮箱（排除"我"/未分配）
  const names = [...new Set(
    rows.map((t) => (t.owner || '').trim()).filter((n) => n && n !== '我' && n !== '未分配')
  )].flatMap((n) => n.split(/[,;，；、\s]+/).filter(Boolean))
  if (!names.length) return
  try {
    const map = (await resolveTaskContacts([...new Set(names)])) || {}
    const resolved = []
    const missing = []
    for (const n of new Set(names)) {
      if (map[n]) resolved.push(map[n])
      else missing.push(n)
    }
    emailTo.value = resolved
    if (missing.length) {
      ElMessage.warning(`以下负责人未在通讯录找到邮箱，请手动填写：${missing.join('、')}`)
    }
  } catch (e) {
    console.error('解析收件人失败', e)
  }
}

function removeEmailTask(t) {
  emailForm.tasks = emailForm.tasks.filter((x) => x.task_id !== t.task_id)
}

async function handleTaskEmailSend() {
  if (!emailForm.tasks.length) {
    ElMessage.warning('请至少保留一个关联任务')
    return
  }
  emailForm.to = (emailTo.value || []).join(', ')
  emailForm.cc = (emailCc.value || []).join(', ')
  if (!emailForm.to || !emailForm.subject) {
    ElMessage.warning('请填写收件人和主题')
    return
  }
  const bad = [...invalidEmails(emailForm.to), ...invalidEmails(emailForm.cc)]
  if (bad.length) {
    ElMessage.warning(`收件人邮箱格式不正确：${bad.join('、')}`)
    return
  }
  emailSending.value = true
  try {
    const res = await sendTaskEmail({
      tasks: emailForm.tasks.map((t) => ({ source: t.source, source_id: t.source_id })),
      to: emailForm.to,
      cc: emailForm.cc || null,
      subject: emailForm.subject,
      body: emailForm.body,
      send_type: emailForm.send_type,
      operator: 'pmwb',
    })
    if (res && res.success) {
      ElMessage.success('邮件发送成功')
      emailDialogVisible.value = false
      selectedTasks.value = []
    } else {
      ElMessage.warning(res?.message || '邮件发送失败')
    }
  } catch (e) {
    console.error('任务邮件发送失败', e)
  } finally {
    emailSending.value = false
  }
}

// ------- 需求催办 Tab（沿用原催办中心逻辑） -------
const urgeLoading = ref(false)
const urgeGroups = ref([])
const urgeDialogVisible = ref(false)
const urgeSending = ref(false)

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

async function prefillUrgeRecipients(names) {
  urgeForm.recipient_name = (names || []).join(', ')
  urgeTo.value = []
  urgeCc.value = []
  const list = (names || []).filter(Boolean)
  if (!list.length) return
  try {
    const map = (await resolveContacts(list)) || {}
    const resolved = []
    const missing = []
    for (const n of list) {
      const email = map[n] || map[n.trim()]
      if (email) resolved.push(email)
      else missing.push(n)
    }
    urgeTo.value = resolved
    if (missing.length) {
      ElMessage.warning(`以下 SA 未在邮件中心通讯录找到邮箱，请手动填写：${missing.join('、')}`)
    }
  } catch (e) {
    console.error('解析收件人邮箱失败', e)
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

function openUrgeBatch(group) {
  if (group.sa_name === '未分配') {
    ElMessage.warning('该组需求未分配 SA，无法自动解析收件人，请到需求管理指定 SA 后催办。')
    return
  }
  urgeForm.req_id = group.items.map((i) => i.req_id).join('; ')
  urgeForm.req_name = ''
  urgeForm.subject = `催办：${group.sa_name} 负责的 ${group.count} 个需求评估`
  urgeForm.body = buildUrgeBatchBody(group.sa_name, group.items)
  prefillUrgeRecipients([group.sa_name])
  urgeDialogVisible.value = true
}

function openUrgeSingle(item) {
  urgeForm.req_id = item.req_id
  urgeForm.req_name = item.req_name
  urgeForm.subject = `催办：${item.req_name || item.req_id}`
  urgeForm.body = buildUrgeSingleBody(item)
  prefillUrgeRecipients(item.sa_name ? [item.sa_name] : [])
  urgeDialogVisible.value = true
}

async function handleUrgeSend() {
  urgeForm.to = (urgeTo.value || []).join(', ')
  urgeForm.cc = (urgeCc.value || []).join(', ')
  if (!urgeForm.to || !urgeForm.subject) {
    ElMessage.warning('请填写收件人和主题')
    return
  }
  const bad = [...invalidEmails(urgeForm.to), ...invalidEmails(urgeForm.cc)]
  if (bad.length) {
    ElMessage.warning(`收件人邮箱格式不正确：${bad.join('、')}（请填写真实邮箱）`)
    return
  }
  urgeSending.value = true
  try {
    const res = await sendReminder({
      req_id: urgeForm.req_id,
      req_name: urgeForm.req_name,
      to: urgeForm.to,
      cc: urgeForm.cc,
      recipient_name: urgeForm.recipient_name,
      subject: urgeForm.subject,
      body: urgeForm.body,
      operator: 'pmwb',
    })
    if (res && res.success) {
      ElMessage.success('催办邮件发送成功')
      urgeDialogVisible.value = false
      await loadUrgeGroups()
      loadStats()
    } else {
      ElMessage.warning(res?.message || '催办邮件发送失败')
    }
  } catch (e) {
    console.error('催办邮件发送失败', e)
  } finally {
    urgeSending.value = false
  }
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
.task-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
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
.form-hint {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
  margin-top: 4px;
}
</style>
