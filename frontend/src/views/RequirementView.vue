<template>
  <div class="page-container">
    <div class="page-header">
      <div class="page-title">需求管理</div>
      <div class="page-actions">
        <el-button type="primary" @click="fetchData">刷新</el-button>
      </div>
    </div>

    <div class="stats-row">
      <el-card v-for="item in statsItems" :key="item.label" shadow="hover" class="stat-card">
        <div class="stat-value">{{ item.value }}</div>
        <div class="stat-label">{{ item.label }}</div>
      </el-card>
    </div>

    <div class="table-card">
      <SearchForm
        :fields="searchFields"
        @search="handleSearch"
        @reset="handleReset"
      />

      <div class="table-hint">
        点击「需求名称」查看详情；点击表格任意一行可展开 / 收起
        <b>团队评估</b> 与 <b>关联工单进度</b>（再次点击收起）。
      </div>

      <el-table
        ref="tableRef"
        v-loading="tableLoading"
        :data="tableData"
        stripe
        border
        class="req-table"
        style="width: 100%"
        row-key="req_id"
        @expand-change="handleExpandChange"
        @row-click="handleRowClick"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expand-content" v-loading="evalLoadingMap[row.req_id]">
              <div class="expand-title">
                <span>团队评估记录（{{ (evaluationsMap[row.req_id] || []).length || row.eval_count || 0 }} 个团队）</span>
                <el-button type="primary" size="small" @click="handleAddEval(row)">新增评估</el-button>
              </div>
              <el-table :data="evaluationsMap[row.req_id] || []" size="small" border>
                <el-table-column prop="sa_name" label="评估SA" width="90" show-overflow-tooltip />
                <el-table-column prop="system_name" label="负责系统" width="110" show-overflow-tooltip />
                <el-table-column prop="workload" label="工作量(人天)" width="110" align="center" />
                <el-table-column prop="review_workload" label="复核(人天)" width="100" align="center" />
                <el-table-column prop="dev_ticket_no" label="开发单号" width="130" show-overflow-tooltip />
                <el-table-column label="评估意见" min-width="200" show-overflow-tooltip>
                  <template #default="{ row: ev }">
                    <span class="opinion-text">{{ ev.opinion || '未登记' }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="200" align="center">
                  <template #default="{ row: ev }">
                    <el-button link type="primary" size="small" @click="handleViewEval(ev)">查看</el-button>
                    <el-button link type="success" size="small" @click="handleEditEval(ev)">编辑</el-button>
                    <el-button link type="warning" size="small" @click="handleReminderOpenEval(ev)">催办</el-button>
                    <el-button link type="danger" size="small" @click="handleDeleteEval(ev)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <div v-if="!(evaluationsMap[row.req_id] || []).length && !evalLoadingMap[row.req_id]" class="expand-empty">
                暂无团队评估数据
              </div>

              <div class="expand-title" style="margin-top: 20px">
                <span>关联开发工单进度（{{ (ticketMap[row.req_id] || []).length }} 个工单）</span>
                <span class="expand-hint">版本要求：{{ row.ext?.version_required_date || '未设置' }}</span>
              </div>
              <div class="ticket-scroll">
                <el-table
                  :data="ticketMap[row.req_id] || []"
                  size="small"
                  border
                  class="ticket-table"
                  :row-class-name="ticketRowClass"
                >
                  <el-table-column prop="ticket_no" label="工单号" width="160" />
                  <el-table-column prop="system_name" label="系统" width="130" />
                  <el-table-column label="状态" width="100" align="center">
                    <template #default="{ row: t }">
                      <el-tag size="small" :type="devStatusTag(t.status)">{{ devStatusLabel(t.status) }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="progress" label="进度%" width="80" align="center" />
                  <el-table-column prop="dev_completed_date" label="开发完成" width="120" />
                  <el-table-column prop="test_completed_date" label="测试完成" width="120" />
                  <el-table-column prop="go_live_date" label="上线日期" width="120" />
                  <el-table-column label="预警" width="90" align="center">
                    <template #default="{ row: t }">
                      <el-tag v-if="t.flag === 'overdue' || t.flag === 'late'" size="small" type="danger">超期</el-tag>
                      <el-tag v-else-if="t.flag === 'warning'" size="small" type="warning">临近</el-tag>
                      <el-tag v-else-if="t.flag === 'on_time'" size="small" type="success">按时</el-tag>
                      <span v-else class="muted">-</span>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
              <div v-if="!(ticketMap[row.req_id] || []).length && !evalLoadingMap[row.req_id]" class="expand-empty">
                该需求暂无关联开发工单
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="req_id" label="需求编号" width="180" show-overflow-tooltip />
        <el-table-column prop="req_name" label="需求名称" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="req-name-link" :title="row.req_name" @click="handleView(row)">{{ row.req_name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="proposer" label="提出人" width="90" />
        <el-table-column label="团队评估" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.eval_count || 0 }}个团队</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="优先级" width="80" align="center">
          <template #default="{ row }">
            <StatusBadge :value="row.ext?.priority || 'P2'" :options="priorityOptions" />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <StatusBadge :value="row.ext?.status || 'proposed'" :options="statusOptions" />
          </template>
        </el-table-column>
        <el-table-column label="版本要求" width="150" align="center">
          <template #default="{ row }">
            <el-popover placement="bottom" trigger="click" width="260" popper-class="version-popover">
              <template #reference>
                <span class="version-text" :class="versionTextClass(row)" @click.stop>
                  {{ row.ext?.version_required_date || '设置日期' }}
                </span>
              </template>
              <div class="version-pop">
                <el-date-picker
                  v-model="row.ext.version_required_date"
                  type="date"
                  value-format="YYYY-MM-DD"
                  format="YYYY-MM-DD"
                  size="small"
                  style="width: 100%"
                  @change="(val) => handleVersionDateChange(row, val)"
                />
                <div class="version-pop-actions">
                  <el-button size="small" text type="info" @click="handleVersionClear(row)">清除</el-button>
                </div>
              </div>
            </el-popover>
          </template>
        </el-table-column>
        <el-table-column label="跟踪状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="trackingTagType(row.tracking_status)">
              {{ trackingLabel(row.tracking_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleEdit(row)">跟踪</el-button>
            <el-button link type="primary" @click="handleView(row)">详情</el-button>
            <el-button link type="warning" @click="handleReminderOpen(row)">催办</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > 0"
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </div>

    <el-dialog v-model="dialogVisible" title="需求跟踪" width="600px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="需求编号">
          <el-input v-model="form.req_id" disabled />
        </el-form-item>
        <el-form-item label="需求名称">
          <el-input v-model="form.req_name" disabled />
        </el-form-item>
        <el-form-item label="个人状态">
          <el-select v-model="form.status">
            <el-option
              v-for="opt in statusSelectOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="个人优先级">
          <el-select v-model="form.priority">
            <el-option
              v-for="opt in prioritySelectOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="form.tags" placeholder="逗号分隔" />
        </el-form-item>
        <el-form-item label="个人备注">
          <el-input v-model="form.personal_note" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailVisible" :title="detail.is_eval ? '团队评估详情' : '需求详情'" width="700px">
      <div class="detail-actions" v-if="!detail.is_eval">
        <el-button type="warning" size="small" @click="handleReminderFromDetail">一键催办</el-button>
      </div>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="需求编号">{{ detail.req_id }}</el-descriptions-item>
        <el-descriptions-item label="需求名称">{{ detail.req_name }}</el-descriptions-item>
        <template v-if="detail.is_eval">
          <el-descriptions-item label="评估SA">{{ detail.sa_name }}</el-descriptions-item>
          <el-descriptions-item label="负责系统">{{ detail.system_name }}</el-descriptions-item>
          <el-descriptions-item label="工作量(人天)">{{ detail.workload ?? '未填写' }}</el-descriptions-item>
          <el-descriptions-item label="开发单号">{{ detail.dev_ticket_no || '未填写' }}</el-descriptions-item>
          <el-descriptions-item label="发送时间">{{ detail.send_datetime }}</el-descriptions-item>
          <el-descriptions-item label="评估意见">{{ detail.opinion || '未登记' }}</el-descriptions-item>
        </template>
        <template v-else>
          <el-descriptions-item label="提出人">{{ detail.proposer }}</el-descriptions-item>
          <el-descriptions-item label="提出时间">{{ detail.propose_time }}</el-descriptions-item>
          <el-descriptions-item label="团队数">{{ detail.eval_count || 0 }} 个</el-descriptions-item>
          <el-descriptions-item label="开发单号">{{ detail.dev_ticket_no }}</el-descriptions-item>
          <el-descriptions-item label="版本要求">{{ detail.ext?.version_required_date || '未设置' }}</el-descriptions-item>
        </template>
      </el-descriptions>
      <div v-if="detail.background" class="detail-section">
        <div class="detail-section-title">需求背景</div>
        <div class="detail-section-content">{{ detail.background }}</div>
      </div>
      <div v-if="detail.description && !detail.is_eval" class="detail-section">
        <div class="detail-section-title">需求描述</div>
        <div class="detail-section-content">{{ detail.description }}</div>
      </div>
      <div v-if="!detail.is_eval" class="detail-section">
        <div class="detail-section-title">催办记录</div>
        <el-timeline v-if="reminderRecords.length">
          <el-timeline-item
            v-for="record in reminderRecords"
            :key="record.id"
            :type="record.send_status === 'success' ? 'success' : 'danger'"
            :timestamp="record.created_at"
          >
            <div>{{ record.subject }}</div>
            <div class="record-meta">收件人：{{ record.recipient_name || record.recipient }} | 状态：{{ record.send_status }}</div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无催办记录" />
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="reminderVisible" title="发送催办邮件" width="600px">
      <el-form :model="reminderForm" label-width="100px">
        <el-form-item label="需求编号">
          <el-input v-model="reminderForm.req_id" disabled />
        </el-form-item>
        <el-form-item label="收件人">
          <el-input v-model="reminderForm.to" placeholder="多个收件人用逗号分隔" />
          <div class="form-hint">收件人邮箱按姓名自动从邮件中心通讯录解析；若未匹配到，请手动填写真实邮箱。</div>
        </el-form-item>
        <el-form-item label="抄送">
          <el-input v-model="reminderForm.cc" placeholder="多个抄送人用逗号分隔" />
        </el-form-item>
        <el-form-item label="主题">
          <el-input v-model="reminderForm.subject" />
        </el-form-item>
        <el-form-item label="正文">
          <el-input v-model="reminderForm.body" type="textarea" :rows="6" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reminderVisible = false">取消</el-button>
        <el-button type="primary" :loading="reminderLoading" @click="handleReminderSend">发送</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="evalFormVisible" :title="evalForm.id ? '编辑团队评估' : '新增团队评估'" width="560px">
      <el-form :model="evalForm" label-width="110px">
        <el-form-item label="需求编号">
          <el-input v-model="evalForm.req_id" disabled />
        </el-form-item>
        <el-form-item label="评估SA" required>
          <el-input v-model="evalForm.sa_name" placeholder="评估SA/团队负责人" />
        </el-form-item>
        <el-form-item label="负责系统">
          <el-input v-model="evalForm.system_name" placeholder="负责系统" />
        </el-form-item>
        <el-form-item label="工作量(人天)">
          <el-input-number v-model="evalForm.workload" :min="0" :precision="1" :step="0.5" controls-position="right" />
        </el-form-item>
        <el-form-item label="复核工作量(人天)">
          <el-input-number v-model="evalForm.review_workload" :min="0" :precision="1" :step="0.5" controls-position="right" />
        </el-form-item>
        <el-form-item label="开发单号">
          <el-input v-model="evalForm.dev_ticket_no" placeholder="开发单号" />
        </el-form-item>
        <el-form-item label="评估意见">
          <el-input v-model="evalForm.opinion" type="textarea" :rows="3" placeholder="评估意见登记" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="evalFormVisible = false">取消</el-button>
        <el-button type="primary" @click="handleEvalSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SearchForm from '@/components/Common/SearchForm.vue'
import StatusBadge from '@/components/Common/StatusBadge.vue'
import {
  getRequirements, getRequirement, updateRequirement,
  getRequirementStats, getEvaluations, updateEvaluation,
  createEvaluation, deleteEvaluation
} from '@/api/requirement.js'
import { sendReminder, getReminderRecords, resolveContacts } from '@/api/reminder.js'

const searchFields = [
  { name: 'keyword', label: '关键字', type: 'input', placeholder: '编号/名称/提出人' },
  { name: 'status', label: '状态', type: 'select', options: [
    { label: '全部', value: '' },
    { label: '已提出', value: 'proposed' },
    { label: '已受理', value: 'accepted' },
    { label: '开发中', value: 'dev' },
    { label: '已关闭', value: 'closed' },
    { label: '已暂停', value: 'paused' },
  ]},
  { name: 'priority', label: '优先级', type: 'select', options: [
    { label: '全部', value: '' },
    { label: 'P0', value: 'P0' },
    { label: 'P1', value: 'P1' },
    { label: 'P2', value: 'P2' },
    { label: 'P3', value: 'P3' },
    { label: '集团需求', value: '集团需求' },
    { label: '紧急需求', value: '紧急需求' },
  ]},
]

const columns = [] // 不再使用 DataTable，直接用 el-table

const statusOptions = {
  proposed: { label: '已提出', type: 'info' },
  accepted: { label: '已受理', type: 'primary' },
  dev: { label: '开发中', type: 'warning' },
  closed: { label: '已关闭', type: 'success' },
  paused: { label: '已暂停', type: 'danger' },
}

const priorityOptions = {
  P0: { label: 'P0', type: 'danger' },
  P1: { label: 'P1', type: 'warning' },
  P2: { label: 'P2', type: 'primary' },
  P3: { label: 'P3', type: 'info' },
  '集团需求': { label: '集团需求', type: 'success' },
  '紧急需求': { label: '紧急需求', type: 'danger' },
}

const statusSelectOptions = Object.entries(statusOptions).map(([value, item]) => ({ value, label: item.label }))
const prioritySelectOptions = Object.entries(priorityOptions).map(([value, item]) => ({ value, label: item.label }))

// 跟踪状态（版本要求 vs 关联开发工单进度）
const trackingMap = {
  none: { label: '无工单', type: 'info' },
  on_time: { label: '按时', type: 'success' },
  on_track: { label: '进行中', type: 'primary' },
  warning: { label: '预警', type: 'warning' },
  overdue: { label: '超期', type: 'danger' },
}
function trackingLabel(s) { return (trackingMap[s] || trackingMap.none).label }
function trackingTagType(s) { return (trackingMap[s] || trackingMap.none).type }

// 开发工单状态
const devStatusOptions = {
  created: { label: '已创建', type: 'info' },
  design_reviewed: { label: '已评审', type: 'primary' },
  dev_completed: { label: '开发完成', type: 'warning' },
  test_completed: { label: '测试完成', type: 'warning' },
  live: { label: '已上线', type: 'success' },
  archived: { label: '已归档', type: 'info' },
}
function devStatusLabel(s) { return (devStatusOptions[s] || {}).label || s }
function devStatusTag(s) { return (devStatusOptions[s] || {}).type || 'info' }

const tableRef = ref(null)
const tableData = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const tableLoading = ref(false)
const query = reactive({ keyword: '', status: '', priority: '' })
const stats = ref({ total: 0, proposed: 0, accepted: 0, dev: 0, closed: 0, paused: 0, involved: 0 })

// 团队评估展开行数据
const evaluationsMap = ref({})       // { [req_id]: [...] }
const evalLoadingMap = ref({})        // { [req_id]: true/false }
const ticketMap = ref({})             // { [req_id]: [关联开发工单] }

const statsItems = computed(() => [
  { label: '需求总数', value: stats.value.total },
  { label: '已受理', value: stats.value.accepted },
  { label: '开发中', value: stats.value.dev },
  { label: '已关闭', value: stats.value.closed },
  { label: '已暂停', value: stats.value.paused },
  { label: '涉及开发', value: stats.value.involved },
])

const dialogVisible = ref(false)
const detailVisible = ref(false)
const reminderVisible = ref(false)
const reminderLoading = ref(false)
const evalFormVisible = ref(false)
const evalForm = reactive({
  req_id: '', req_name: '', id: null,
  sa_name: '', system_name: '', workload: null,
  review_workload: null, opinion: '', dev_ticket_no: '',
})
const form = reactive({ req_id: '', req_name: '', status: '', priority: '', tags: '', personal_note: '' })
const detail = ref({})
const reminderRecords = ref([])
const reminderForm = reactive({ req_id: '', req_name: '', to: '', cc: '', recipient_name: '', subject: '', body: '' })

async function fetchData() {
  tableLoading.value = true
  try {
    const res = await getRequirements({
      ...query,
      page: page.value,
      page_size: pageSize.value,
    })
    tableData.value = (res.items || []).map((r) => ({ ...r, ext: r.ext || {} }))
    total.value = res.total || 0
  } catch (err) {
    ElMessage.error(err.message || '获取需求列表失败')
  } finally {
    tableLoading.value = false
  }
}

async function fetchStats() {
  try {
    const res = await getRequirementStats()
    stats.value = res || {}
  } catch (err) {
    console.error('获取需求统计失败', err)
  }
}

function handleSearch(values) {
  query.keyword = values.keyword || ''
  query.status = values.status || ''
  query.priority = values.priority || ''
  page.value = 1
  fetchData()
}

function handleReset() {
  query.keyword = ''
  query.status = ''
  query.priority = ''
  page.value = 1
  fetchData()
}

function handlePageChange(p) {
  page.value = p
  fetchData()
}

// 整行点击展开/收起评估与工单面板；对交互元素做防误触 guard
function handleRowClick(row, column, event) {
  // 展开箭头列、需求名称列（自带详情跳转）不触发展开
  if (column && column.type === 'expand') return
  if (column && column.property === 'req_name') return
  // 点击已展开内容区、输入框、按钮、文本域时不折叠
  const t = event && event.target
  if (t && t.closest) {
    if (t.closest('.expand-content')) return
    const tag = t.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'BUTTON') return
  }
  if (tableRef.value) tableRef.value.toggleRowExpansion(row)
}

// ===== 团队评估展开行逻辑 =====

async function handleExpandChange(row, expanded) {
  if (!expanded) return
  // 已加载过则不重复请求
  if (evaluationsMap.value[row.req_id] && ticketMap.value[row.req_id]) return
  evalLoadingMap.value[row.req_id] = true
  try {
    const [evals, detail] = await Promise.all([
      getEvaluations(row.req_id),
      getRequirement(row.req_id),
    ])
    const list = evals || []
    // 记录原始值，用于失焦时判断是否真的改动，避免重复保存
    list.forEach((ev) => {
      ev._orig = {
        workload: ev.workload, opinion: ev.opinion,
        dev_ticket_no: ev.dev_ticket_no, review_workload: ev.review_workload,
      }
    })
    evaluationsMap.value[row.req_id] = list
    ticketMap.value[row.req_id] = (detail && detail.linked_tickets) || []
  } catch (err) {
    console.error('获取团队评估/工单失败', err)
    ElMessage.error('获取需求详情失败')
    evaluationsMap.value[row.req_id] = evaluationsMap.value[row.req_id] || []
    ticketMap.value[row.req_id] = ticketMap.value[row.req_id] || []
  } finally {
    evalLoadingMap.value[row.req_id] = false
  }
}

async function handleEditEval(ev) {
  // 打开评估编辑弹窗（复用新增表单，带 id 即编辑模式）
  Object.assign(evalForm, {
    req_id: ev.req_id,
    req_name: ev.req_name,
    id: ev.id,
    sa_name: ev.sa_name || '',
    system_name: ev.system_name || '',
    workload: ev.workload ?? null,
    review_workload: ev.review_workload ?? null,
    opinion: ev.opinion || '',
    dev_ticket_no: ev.dev_ticket_no || '',
  })
  evalFormVisible.value = true
}

// 版本要求文本着色：按跟踪状态提示紧急度
function versionTextClass(row) {
  const t = row.tracking_status
  if (t === 'overdue' || t === 'late') return 'is-overdue'
  if (t === 'warning') return 'is-warning'
  return row.ext?.version_required_date ? '' : 'is-unset'
}

async function handleVersionClear(row) {
  try {
    await updateRequirement(row.req_id, { version_required_date: null })
    row.ext.version_required_date = null
    ElMessage.success('已清除版本要求')
    fetchData()
  } catch (err) {
    ElMessage.error(err.message || '操作失败')
  }
}

// 超期/晚于版本要求的工单整行高亮
function ticketRowClass({ row }) {
  if (row.flag === 'overdue' || row.flag === 'late') return 'ticket-row-overdue'
  if (row.flag === 'warning') return 'ticket-row-warning'
  return ''
}

async function handleVersionDateChange(row, val) {
  try {
    await updateRequirement(row.req_id, { version_required_date: val || null })
    ElMessage.success('已保存版本要求')
    fetchData()  // 刷新以更新跟踪状态
  } catch (err) {
    ElMessage.error(err.message || '保存失败')
  }
}

function handleViewEval(ev) {
  // 查看单条评估详情（可复用详情对话框）
  detail.value = { ...ev, is_eval: true }
  detailVisible.value = true
}

function handleAddEval(row) {
  // 打开新增团队评估弹窗
  Object.assign(evalForm, {
    req_id: row.req_id,
    req_name: row.req_name,
    id: null,
    sa_name: '',
    system_name: '',
    workload: null,
    review_workload: null,
    opinion: '',
    dev_ticket_no: '',
  })
  evalFormVisible.value = true
}

async function handleEvalSubmit() {
  if (!evalForm.sa_name || !evalForm.sa_name.trim()) {
    ElMessage.warning('请填写评估SA/团队负责人')
    return
  }
  try {
    const payload = {
      sa_name: evalForm.sa_name,
      system_name: evalForm.system_name || '',
      workload: evalForm.workload ?? null,
      review_workload: evalForm.review_workload ?? null,
      opinion: evalForm.opinion || '',
      dev_ticket_no: evalForm.dev_ticket_no || '',
    }
    if (evalForm.id) {
      // 编辑模式：更新已存在评估
      const updated = await updateEvaluation(evalForm.req_id, evalForm.id, payload)
      const list = evaluationsMap.value[evalForm.req_id] || []
      const idx = list.findIndex((x) => x.id === evalForm.id)
      if (idx !== -1) {
        const origKeys = { workload: updated.workload, opinion: updated.opinion, dev_ticket_no: updated.dev_ticket_no, review_workload: updated.review_workload }
        list.splice(idx, 1, { ...list[idx], ...updated, _orig: origKeys })
      }
      ElMessage.success('已更新评估')
    } else {
      // 新增模式
      const newEv = await createEvaluation(evalForm.req_id, payload)
      if (!evaluationsMap.value[evalForm.req_id]) {
        evaluationsMap.value[evalForm.req_id] = []
      }
      newEv._orig = {
        workload: newEv.workload, opinion: newEv.opinion,
        dev_ticket_no: newEv.dev_ticket_no, review_workload: newEv.review_workload,
      }
      evaluationsMap.value[evalForm.req_id].push(newEv)
      ElMessage.success('新增评估成功')
    }
    evalFormVisible.value = false
  } catch (err) {
    ElMessage.error(err.message || '保存失败')
  }
}

async function handleDeleteEval(ev) {
  try {
    await ElMessageBox.confirm(
      `确认删除「${ev.sa_name || '该团队'}」的评估记录？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch (e) {
    return // 用户取消
  }
  try {
    await deleteEvaluation(ev.req_id, ev.id)
    const list = evaluationsMap.value[ev.req_id] || []
    const idx = list.findIndex((x) => x.id === ev.id)
    if (idx !== -1) list.splice(idx, 1)
    ElMessage.success('已删除')
  } catch (err) {
    ElMessage.error(err.message || '删除失败')
  }
}

function handleEdit(row) {
  form.req_id = row.req_id
  form.req_name = row.req_name
  form.status = row.ext?.status || 'proposed'
  form.priority = row.ext?.priority || 'P2'
  form.tags = row.ext?.tags || ''
  form.personal_note = row.ext?.personal_note || ''
  dialogVisible.value = true
}

async function handleSave() {
  try {
    await updateRequirement(form.req_id, {
      status: form.status,
      priority: form.priority,
      tags: form.tags,
      personal_note: form.personal_note,
    })
    ElMessage.success('保存成功')
    dialogVisible.value = false
    fetchData()
    fetchStats()
  } catch (err) {
    ElMessage.error(err.message || '保存失败')
  }
}

async function handleView(row) {
  try {
    const res = await getRequirement(row.req_id)
    detail.value = res || {}
    await fetchReminderRecords(row.req_id)
    detailVisible.value = true
  } catch (err) {
    ElMessage.error(err.message || '获取详情失败')
  }
}

async function fetchReminderRecords(reqId) {
  try {
    const res = await getReminderRecords(reqId)
    reminderRecords.value = res || []
  } catch (err) {
    console.error('获取催办记录失败', err)
    reminderRecords.value = []
  }
}

// 严格邮箱正则（ASCII 本地名），与后端校验保持一致
const EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/

function validateEmailsField(raw) {
  if (!raw) return []
  return raw
    .split(/[,;，；\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .filter((s) => !EMAIL_RE.test(s))
}

// 按 SA 姓名从统一邮件中心通讯录解析真实邮箱并预填收件人
async function prefillRecipients(names) {
  reminderForm.recipient_name = (names || []).join(', ')
  reminderForm.to = ''
  const list = (names || []).filter(Boolean)
  if (!list.length) return
  try {
    const res = await resolveContacts(list)
    // 注意：request.js 拦截器在 code===0 时已返回 data.data（即邮箱映射对象本身），
    // res 已经是 {姓名: 邮箱} 映射，不要再取 res.data（会是 undefined）。
    const map = res || {}
    const resolved = []
    const missing = []
    for (const n of list) {
      const email = map[n] || map[n.trim()]
      if (email) resolved.push(email)
      else missing.push(n)
    }
    reminderForm.to = resolved.join(', ')
    if (missing.length) {
      ElMessage.warning(
        `以下 SA 未在邮件中心通讯录找到邮箱，请手动填写真实邮箱或先在邮件中心添加：${missing.join('、')}`
      )
    }
  } catch (e) {
    console.error('解析收件人邮箱失败', e)
  }
}

function buildDefaultReminderBody(req, systemName, saName) {
  const salutation = saName
    ? `${saName}（${systemName || '相关'}团队）：`
    : '各相关评估团队：'
  const target = saName ? '你' : '你们'
  const lines = [
    salutation,
    ``,
    `${target}负责的需求现在到前期评估环节了，麻烦尽快把下面两件事搞定，然后反馈给我：`,
    `1. 需求前期评估（可行性、范围、依赖这些）；`,
    `2. 工作量初评（大概要多少人天）和预计完成时间。`,
    ``,
    `需求信息：`,
    `需求编号：${req.req_id || ''}`,
    `需求名称：${req.req_name || ''}`,
    `提出人：${req.proposer || ''}`,
  ]
  if (systemName) {
    lines.push(`负责系统：${systemName}`)
  }
  lines.push(
    ``,
    `收到后尽快回我评估结果哈，辛苦了！`,
    ``,
    `——产品经理工作台（PMWB）`,
  )
  return lines.join('\n')
}

// 聚合需求下所有团队评估的 SA（按系统对应），去重后作为收件人
async function aggregateSaRecipients(reqId) {
  const saNames = []
  const seen = new Set()
  try {
    const evs = await getEvaluations(reqId)
    for (const ev of (evs || [])) {
      if (ev.sa_name && !seen.has(ev.sa_name)) {
        seen.add(ev.sa_name)
        saNames.push(ev.sa_name)
      }
    }
  } catch (e) {
    console.error('聚合团队SA失败', e)
  }
  return saNames
}

// 需求级催办：自动获取该需求下全部系统的对应 SA，群发给所有团队
async function handleReminderOpen(row) {
  reminderForm.req_id = row.req_id
  reminderForm.req_name = row.req_name
  const saNames = await aggregateSaRecipients(row.req_id)
  const names = saNames.length ? saNames : (row.sa_name ? [row.sa_name] : [])
  await prefillRecipients(names)
  reminderForm.cc = ''
  reminderForm.subject = `催办：${row.req_name || row.req_id}`
  reminderForm.body = buildDefaultReminderBody(row)
  reminderVisible.value = true
}

// 团队级催办：按当前系统的对应 SA 精确发送
async function handleReminderOpenEval(ev) {
  reminderForm.req_id = ev.req_id
  reminderForm.req_name = ev.req_name
  reminderForm.cc = ''
  reminderForm.subject = `催办：${ev.req_name || ev.req_id}（${ev.system_name || '系统'}）`
  reminderForm.body = buildDefaultReminderBody(ev, ev.system_name, ev.sa_name)
  await prefillRecipients([ev.sa_name])
  reminderVisible.value = true
}

function handleReminderFromDetail() {
  // 需求详情弹窗内一键催办：复用需求级聚合逻辑（按系统对应 SA 群发）
  handleReminderOpen(detail.value)
}

async function handleReminderSend() {
  if (!reminderForm.to || !reminderForm.subject) {
    ElMessage.warning('请填写收件人和主题')
    return
  }
  const bad = [
    ...validateEmailsField(reminderForm.to),
    ...validateEmailsField(reminderForm.cc),
  ]
  if (bad.length) {
    ElMessage.warning(
      `收件人邮箱格式不正确：${bad.join('、')}（请填写真实邮箱，可在邮件中心通讯录按姓名查询）`
    )
    return
  }
  reminderLoading.value = true
  try {
    const res = await sendReminder({
      req_id: reminderForm.req_id,
      req_name: reminderForm.req_name,
      to: reminderForm.to,
      cc: reminderForm.cc,
      recipient_name: reminderForm.recipient_name,
      subject: reminderForm.subject,
      body: reminderForm.body,
      operator: 'pmwb',
    })
    if (res && res.success) {
      ElMessage.success('催办邮件发送成功')
    } else {
      ElMessage.warning(res?.message || '催办邮件发送失败')
    }
    reminderVisible.value = false
    if (detailVisible.value) {
      await fetchReminderRecords(reminderForm.req_id)
    }
  } catch (err) {
    // 服务端已通过拦截器提示具体错误（如 400 校验失败），此处仅记录避免重复弹窗
    console.error('催办邮件发送失败', err)
  } finally {
    reminderLoading.value = false
  }
}

onMounted(() => {
  fetchData()
  fetchStats()
})
</script>

<style scoped>
.form-hint {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
  margin-top: 4px;
}
.stats-row {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.stat-card {
  flex: 1;
  min-width: 140px;
  text-align: center;
}
.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}
.stat-label {
  font-size: 14px;
  color: #606266;
  margin-top: 8px;
}
.detail-section {
  margin-top: 16px;
}
.detail-section-title {
  font-weight: bold;
  margin-bottom: 8px;
}
.detail-section-content {
  color: #606266;
  line-height: 1.6;
  white-space: pre-wrap;
}
.detail-actions {
  margin-bottom: 16px;
  text-align: right;
}
.record-meta {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.expand-content {
  padding: 16px 24px;
}
.expand-title {
  font-weight: bold;
  margin-bottom: 12px;
  color: #303133;
}
.expand-empty {
  text-align: center;
  color: #909399;
  padding: 16px;
}
.pagination {
  margin-top: 20px;
  justify-content: flex-end;
}
.table-hint {
  font-size: 13px;
  color: #909399;
  margin: 4px 2px 12px;
  line-height: 1.6;
}
.table-hint b {
  color: #606266;
}
.req-name-link {
  color: #409eff;
  cursor: pointer;
  font-weight: 500;
}
.req-name-link:hover {
  text-decoration: underline;
}
.req-table :deep(.el-table__row) {
  cursor: pointer;
}
.muted {
  color: #c0c4cc;
}
.version-text {
  display: inline-block;
  cursor: pointer;
  color: #409eff;
  font-size: 13px;
}
.version-text:hover {
  text-decoration: underline;
}
.version-text.is-overdue {
  color: #f56c6c;
  font-weight: 600;
}
.version-text.is-warning {
  color: #e6a23c;
  font-weight: 600;
}
.version-text.is-unset {
  color: #c0c4cc;
}
.version-pop {
  text-align: center;
}
.version-pop-actions {
  margin-top: 8px;
  text-align: right;
}
.opinion-text {
  color: #606266;
}
.ticket-scroll {
  overflow-x: auto;
  width: 100%;
}
.ticket-table {
  min-width: 940px;
}
.ticket-table :deep(.ticket-row-overdue) {
  background-color: #fef0f0;
}
.ticket-table :deep(.ticket-row-overdue:hover > td) {
  background-color: #fde2e2 !important;
}
.ticket-table :deep(.ticket-row-overdue td:first-child) {
  border-left: 3px solid #f56c6c;
}
.ticket-table :deep(.ticket-row-warning) {
  background-color: #fdf6ec;
}
.ticket-table :deep(.ticket-row-warning:hover > td) {
  background-color: #faecd8 !important;
}
.ticket-table :deep(.ticket-row-warning td:first-child) {
  border-left: 3px solid #e6a23c;
}
</style>
