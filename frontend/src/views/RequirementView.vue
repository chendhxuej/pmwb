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

      <el-table
        v-loading="tableLoading"
        :data="tableData"
        stripe
        border
        style="width: 100%"
        row-key="req_id"
        @expand-change="handleExpandChange"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expand-content" v-loading="evalLoadingMap[row.req_id]">
              <div class="expand-title">团队评估记录（{{ row.eval_count || 0 }} 个团队）</div>
              <el-table :data="evaluationsMap[row.req_id] || []" size="small" border>
                <el-table-column prop="sa_name" label="评估SA" width="90" />
                <el-table-column prop="system_name" label="负责系统" width="120" />
                <el-table-column prop="workload" label="工作量(人天)" width="140">
                  <template #default="{ row: ev }">
                    <el-input-number
                      v-model="ev.workload"
                      :min="0"
                      :precision="1"
                      :step="0.5"
                      size="small"
                      controls-position="right"
                      style="width: 120px"
                      @change="(val) => handleEvalUpdate(ev, 'workload', val)"
                    />
                  </template>
                </el-table-column>
                <el-table-column label="评估意见登记" min-width="240">
                  <template #default="{ row: ev }">
                    <el-input
                      v-model="ev.opinion"
                      type="textarea"
                      :autosize="{ minRows: 1, maxRows: 4 }"
                      size="small"
                      placeholder="填写评估意见后失焦自动保存"
                      @blur="handleEvalUpdate(ev, 'opinion', ev.opinion)"
                    />
                  </template>
                </el-table-column>
                <el-table-column prop="dev_ticket_no" label="开发单号" width="150">
                  <template #default="{ row: ev }">
                    <el-input
                      v-model="ev.dev_ticket_no"
                      size="small"
                      placeholder="开发单号"
                      @blur="handleEvalUpdate(ev, 'dev_ticket_no', ev.dev_ticket_no)"
                    />
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="80" align="center">
                  <template #default="{ row: ev }">
                    <el-button link type="primary" size="small" @click="handleViewEval(ev)">查看</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <div v-if="!(evaluationsMap[row.req_id] || []).length && !evalLoadingMap[row.req_id]" class="expand-empty">
                暂无团队评估数据
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="req_id" label="需求编号" width="180" show-overflow-tooltip />
        <el-table-column prop="req_name" label="需求名称" min-width="220" show-overflow-tooltip />
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
            <div class="record-meta">收件人：{{ record.recipient }} | 状态：{{ record.send_status }}</div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无催办记录" />
      </div>
    </el-dialog>
    <el-dialog v-model="reminderVisible" title="发送催办邮件" width="600px">
      <el-form :model="reminderForm" label-width="100px">
        <el-form-item label="需求编号">
          <el-input v-model="reminderForm.req_id" disabled />
        </el-form-item>
        <el-form-item label="收件人">
          <el-input v-model="reminderForm.to" placeholder="多个收件人用逗号分隔" />
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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import SearchForm from '@/components/Common/SearchForm.vue'
import StatusBadge from '@/components/Common/StatusBadge.vue'
import {
  getRequirements, getRequirement, updateRequirement,
  getRequirementStats, getEvaluations, updateEvaluation
} from '@/api/requirement.js'
import { sendReminder, getReminderRecords } from '@/api/reminder.js'

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
}

const statusSelectOptions = Object.entries(statusOptions).map(([value, item]) => ({ value, label: item.label }))
const prioritySelectOptions = Object.entries(priorityOptions).map(([value, item]) => ({ value, label: item.label }))

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
const form = reactive({ req_id: '', req_name: '', status: '', priority: '', tags: '', personal_note: '' })
const detail = ref({})
const reminderRecords = ref([])
const reminderForm = reactive({ req_id: '', req_name: '', to: '', cc: '', subject: '', body: '' })

async function fetchData() {
  tableLoading.value = true
  try {
    const res = await getRequirements({
      ...query,
      page: page.value,
      page_size: pageSize.value,
    })
    tableData.value = res.items || []
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

// ===== 团队评估展开行逻辑 =====

async function handleExpandChange(row, expanded) {
  if (!expanded) return
  // 已加载过则不重复请求
  if (evaluationsMap.value[row.req_id]) return
  evalLoadingMap.value[row.req_id] = true
  try {
    const res = await getEvaluations(row.req_id)
    const list = res || []
    // 记录原始值，用于失焦时判断是否真的改动，避免重复保存
    list.forEach((ev) => {
      ev._orig = { workload: ev.workload, opinion: ev.opinion, dev_ticket_no: ev.dev_ticket_no }
    })
    evaluationsMap.value[row.req_id] = list
  } catch (err) {
    console.error('获取团队评估失败', err)
    ElMessage.error('获取团队评估记录失败')
    evaluationsMap.value[row.req_id] = []
  } finally {
    evalLoadingMap.value[row.req_id] = false
  }
}

async function handleEvalUpdate(ev, field, value) {
  // 值未变化则跳过（尤其是 textarea/input 的 blur 事件）
  if (ev._orig && ev._orig[field] === value) return
  try {
    await updateEvaluation(ev.req_id, ev.id, { [field]: value })
    if (ev._orig) ev._orig[field] = value
    ElMessage.success('已保存')
  } catch (err) {
    ElMessage.error(err.message || '保存失败')
  }
}

function handleViewEval(ev) {
  // 查看单条评估详情（可复用详情对话框）
  detail.value = { ...ev, is_eval: true }
  detailVisible.value = true
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

function buildDefaultReminderBody(req) {
  const lines = [
    `您好，以下需求目前需要跟进，请协助处理：`,
    ``,
    `需求编号：${req.req_id || ''}`,
    `需求名称：${req.req_name || ''}`,
    `提出人：${req.proposer || ''}`,
    `系统：${req.system_name || ''}`,
    ``,
    `请及时反馈当前进展与预计完成时间，谢谢。`,
  ]
  return lines.join('\n')
}

function initReminderForm(rowOrDetail) {
  reminderForm.req_id = rowOrDetail.req_id
  reminderForm.req_name = rowOrDetail.req_name
  reminderForm.to = rowOrDetail.sa_name ? `${rowOrDetail.sa_name}@chinamobile.com` : ''
  reminderForm.cc = ''
  reminderForm.subject = `催办：${rowOrDetail.req_name || rowOrDetail.req_id}`
  reminderForm.body = buildDefaultReminderBody(rowOrDetail)
}

function handleReminderOpen(row) {
  initReminderForm(row)
  reminderVisible.value = true
}

function handleReminderFromDetail() {
  initReminderForm(detail.value)
  reminderVisible.value = true
}

async function handleReminderSend() {
  if (!reminderForm.to || !reminderForm.subject) {
    ElMessage.warning('请填写收件人和主题')
    return
  }
  reminderLoading.value = true
  try {
    const res = await sendReminder({
      req_id: reminderForm.req_id,
      req_name: reminderForm.req_name,
      to: reminderForm.to,
      cc: reminderForm.cc,
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
    ElMessage.error(err.message || '发送失败')
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
</style>
