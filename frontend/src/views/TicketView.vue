<template>
  <div class="page-container">
    <div class="page-header">
      <div class="page-title">开发工单</div>
      <div class="page-actions">
        <el-button type="primary" @click="handleCreate">新建工单</el-button>
        <el-button @click="fetchData">刷新</el-button>
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

      <DataTable
        :data="tableData"
        :columns="columns"
        :total="total"
        :page="page"
        :page-size="pageSize"
        @page-change="handlePageChange"
      >
        <template #status="{ row }">
          <StatusBadge :value="row.status" :options="statusOptions" />
        </template>
        <template #priority="{ row }">
          <StatusBadge :value="row.priority" :options="priorityOptions" />
        </template>
        <template #progress="{ row }">
          <el-progress :percentage="row.progress || 0" :status="row.progress === 100 ? 'success' : ''" />
        </template>
        <template #actions="{ row }">
          <el-button size="small" @click="handleDetail(row)">详情</el-button>
          <el-button size="small" @click="handleStatus(row)">状态</el-button>
          <el-button type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
          <el-button type="danger" size="small" @click="handleDelete(row)">删除</el-button>
        </template>
      </DataTable>
    </div>

    <el-dialog v-model="formDialogVisible" :title="isEdit ? '编辑工单' : '新建工单'" width="600px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="工单编号" required>
          <el-input v-model="form.ticket_no" placeholder="如 DTS-2026-xxxx" />
        </el-form-item>
        <el-form-item label="关联需求" required>
          <el-input v-model="form.req_id" placeholder="对应 sent_emails.req_id" />
        </el-form-item>
        <el-form-item label="涉及系统" required>
          <el-input v-model="form.system_name" />
        </el-form-item>
        <el-form-item label="开发团队">
          <el-input v-model="form.dev_team" />
        </el-form-item>
        <el-form-item label="开发负责人">
          <el-input v-model="form.developer" />
        </el-form-item>
        <el-form-item label="联系方式">
          <el-input v-model="form.dev_contact" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="form.priority">
            <el-option v-for="opt in prioritySelectOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="开发内容">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="风险/延期">
          <el-input v-model="form.risk_note" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailDialogVisible" title="工单详情" width="720px" destroy-on-close>
      <el-descriptions v-loading="detailLoading" :column="2" border>
        <el-descriptions-item label="工单编号">{{ detail.ticket_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="关联需求">{{ detail.req_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="涉及系统">{{ detail.system_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="开发团队">{{ detail.dev_team || '-' }}</el-descriptions-item>
        <el-descriptions-item label="开发负责人">{{ detail.developer || '-' }}</el-descriptions-item>
        <el-descriptions-item label="联系方式">{{ detail.dev_contact || '-' }}</el-descriptions-item>
        <el-descriptions-item label="优先级">
          <StatusBadge :value="detail.priority" :options="priorityOptions" />
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <StatusBadge :value="detail.status" :options="statusOptions" />
        </el-descriptions-item>
        <el-descriptions-item label="进度">
          <el-progress :percentage="detail.progress || 0" :status="detail.progress === 100 ? 'success' : ''" />
        </el-descriptions-item>
        <el-descriptions-item label="创建人">{{ detail.created_by || '-' }}</el-descriptions-item>
        <el-descriptions-item label="开发内容" :span="2">{{ detail.description || '-' }}</el-descriptions-item>
        <el-descriptions-item label="风险/延期" :span="2">{{ detail.risk_note || '-' }}</el-descriptions-item>
      </el-descriptions>

      <el-divider content-position="left">状态变更日志</el-divider>
      <el-timeline v-if="detailLogs.length">
        <el-timeline-item
          v-for="(log, idx) in detailLogs"
          :key="idx"
          :timestamp="formatLogTime(log.created_at)"
        >
          <span>{{ statusLabel(log.from_status) }} → {{ statusLabel(log.to_status) }}</span>
          <span v-if="log.operator" class="log-operator">（{{ log.operator }}）</span>
          <div v-if="log.note" class="log-note">{{ log.note }}</div>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无状态变更记录" />

      <el-divider content-position="left">交付物</el-divider>
      <el-table v-if="detailDeliverables.length" :data="detailDeliverables" border size="small">
        <el-table-column prop="deliverable_type" label="类型" width="100">
          <template #default="{ row }">
            {{ deliverableTypeLabel(row.deliverable_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="file_name" label="文件名" min-width="160" show-overflow-tooltip />
        <el-table-column prop="obsidian_path" label="Obsidian路径" min-width="160" show-overflow-tooltip />
        <el-table-column prop="local_path" label="本地路径" min-width="160" show-overflow-tooltip />
        <el-table-column prop="note" label="备注" min-width="120" show-overflow-tooltip />
      </el-table>
      <el-empty v-else description="暂无交付物" />

      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="openDetailEdit">编辑工单</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="statusDialogVisible" title="状态流转" width="500px">
      <el-form :model="statusForm" label-width="100px">
        <el-form-item label="当前状态">
          <StatusBadge :value="statusForm.currentStatus" :options="statusOptions" />
        </el-form-item>
        <el-form-item label="目标状态">
          <el-select v-model="statusForm.status">
            <el-option v-for="opt in statusSelectOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="statusForm.note" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="statusDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveStatus">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import DataTable from '@/components/Common/DataTable.vue'
import SearchForm from '@/components/Common/SearchForm.vue'
import StatusBadge from '@/components/Common/StatusBadge.vue'
import {
  getDevTickets,
  getDevTicket,
  getDevTicketLogs,
  getDevTicketDeliverables,
  createDevTicket,
  updateDevTicket,
  updateDevTicketStatus,
  deleteDevTicket,
  getDevTicketStats,
} from '@/api/dev_ticket.js'

const statusOptions = {
  created: { label: '已创建', type: 'info' },
  design_reviewed: { label: '设计已评审', type: 'primary' },
  dev_completed: { label: '开发完成', type: 'warning' },
  test_completed: { label: '测试完成', type: 'warning' },
  live: { label: '已上线', type: 'success' },
  archived: { label: '已归档', type: 'success' },
}

const priorityOptions = {
  P0: { label: 'P0', type: 'danger' },
  P1: { label: 'P1', type: 'warning' },
  P2: { label: 'P2', type: 'primary' },
  P3: { label: 'P3', type: 'info' },
}

const statusSelectOptions = Object.entries(statusOptions).map(([value, item]) => ({ value, label: item.label }))
const prioritySelectOptions = Object.entries(priorityOptions).map(([value, item]) => ({ value, label: item.label }))

const statusLabel = (s) => (statusOptions[s] || { label: s || '-' }).label

const deliverableTypeMap = {
  operation_manual: '操作手册',
  interface_doc: '接口文档',
  test_case: '测试用例',
  release_note: '发布说明',
  other: '其他',
}
const deliverableTypeLabel = (t) => deliverableTypeMap[t] || t || '-'

const searchFields = [
  { name: 'keyword', label: '关键字', type: 'input', placeholder: '编号/系统/负责人' },
  { name: 'status', label: '状态', type: 'select', options: [{ label: '全部', value: '' }, ...statusSelectOptions] },
  { name: 'priority', label: '优先级', type: 'select', options: [{ label: '全部', value: '' }, ...prioritySelectOptions] },
]

const columns = [
  { prop: 'ticket_no', label: '工单编号', width: 160 },
  { prop: 'req_id', label: '关联需求', width: 140 },
  { prop: 'system_name', label: '系统', width: 120 },
  { prop: 'developer', label: '负责人', width: 100 },
  { slot: 'priority', label: '优先级', width: 90 },
  { slot: 'status', label: '状态', width: 110 },
  { slot: 'progress', label: '进度', width: 120 },
  { slot: 'actions', label: '操作', width: 280, fixed: 'right' },
]

const tableData = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = reactive({ keyword: '', status: '', priority: '' })
const stats = ref({ total: 0, created: 0, design_reviewed: 0, dev_completed: 0, test_completed: 0, live: 0, archived: 0, overdue: 0 })

const statsItems = computed(() => [
  { label: '工单总数', value: stats.value.total },
  { label: '已创建', value: stats.value.created },
  { label: '设计已评审', value: stats.value.design_reviewed },
  { label: '开发完成', value: stats.value.dev_completed },
  { label: '测试完成', value: stats.value.test_completed },
  { label: '已上线', value: stats.value.live },
])

const formDialogVisible = ref(false)
const statusDialogVisible = ref(false)
const detailDialogVisible = ref(false)
const detailLoading = ref(false)
const detail = ref({})
const detailLogs = ref([])
const detailDeliverables = ref([])
const isEdit = ref(false)
const form = reactive({ id: null, ticket_no: '', req_id: '', system_name: '', dev_team: '', developer: '', dev_contact: '', priority: 'P2', description: '', risk_note: '' })
const statusForm = reactive({ id: null, currentStatus: '', status: '', note: '', operator: '当前用户' })

async function fetchData() {
  try {
    const res = await getDevTickets({ ...query, page: page.value, page_size: pageSize.value })
    tableData.value = res.items || []
    total.value = res.total || 0
  } catch (err) {
    ElMessage.error(err.message || '获取工单列表失败')
  }
}

async function fetchStats() {
  try {
    const res = await getDevTicketStats()
    stats.value = res || {}
  } catch (err) {
    console.error('获取工单统计失败', err)
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

function handleCreate() {
  isEdit.value = false
  Object.assign(form, { id: null, ticket_no: '', req_id: '', system_name: '', dev_team: '', developer: '', dev_contact: '', priority: 'P2', description: '', risk_note: '' })
  formDialogVisible.value = true
}

function handleEdit(row) {
  isEdit.value = true
  Object.assign(form, { ...row })
  formDialogVisible.value = true
}

async function handleSave() {
  try {
    if (isEdit.value) {
      const updatePayload = {
        dev_team: form.dev_team,
        developer: form.developer,
        dev_contact: form.dev_contact,
        priority: form.priority,
        description: form.description,
        risk_note: form.risk_note,
      }
      await updateDevTicket(form.id, updatePayload)
    } else {
      const createPayload = {
        ticket_no: form.ticket_no,
        req_id: form.req_id,
        system_name: form.system_name,
        dev_team: form.dev_team,
        developer: form.developer,
        dev_contact: form.dev_contact,
        priority: form.priority,
        description: form.description,
        risk_note: form.risk_note,
      }
      await createDevTicket(createPayload)
    }
    ElMessage.success('保存成功')
    formDialogVisible.value = false
    fetchData()
    fetchStats()
  } catch (err) {
    ElMessage.error(err.message || '保存失败')
  }
}

function handleStatus(row) {
  statusForm.id = row.id
  statusForm.currentStatus = row.status
  statusForm.status = row.status
  statusForm.note = ''
  statusDialogVisible.value = true
}

async function handleSaveStatus() {
  try {
    await updateDevTicketStatus(statusForm.id, { status: statusForm.status, note: statusForm.note, operator: statusForm.operator })
    ElMessage.success('状态更新成功')
    statusDialogVisible.value = false
    fetchData()
    fetchStats()
  } catch (err) {
    ElMessage.error(err.message || '状态更新失败')
  }
}

async function handleDetail(row) {
  detailDialogVisible.value = true
  detailLoading.value = true
  detailLogs.value = []
  detailDeliverables.value = []
  try {
    const [d, logs, deliverables] = await Promise.all([
      getDevTicket(row.id),
      getDevTicketLogs(row.id),
      getDevTicketDeliverables(row.id),
    ])
    detail.value = d || {}
    detailLogs.value = logs || []
    detailDeliverables.value = deliverables || []
  } catch (err) {
    ElMessage.error(err.message || '获取工单详情失败')
  } finally {
    detailLoading.value = false
  }
}

function formatLogTime(t) {
  if (!t) return ''
  return String(t).replace('T', ' ').slice(0, 19)
}

function openDetailEdit() {
  if (!detail.value || !detail.value.id) return
  detailDialogVisible.value = false
  handleEdit(detail.value)
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确认删除该工单？', '提示', { type: 'warning' })
    await deleteDevTicket(row.id)
    ElMessage.success('删除成功')
    fetchData()
    fetchStats()
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error(err.message || '删除失败')
    }
  }
}

onMounted(() => {
  fetchData()
  fetchStats()
})
</script>

<style scoped>
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
</style>
