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

      <DataTable
        :data="tableData"
        :columns="columns"
        :total="total"
        :page="page"
        :page-size="pageSize"
        @page-change="handlePageChange"
      >
        <template #status="{ row }">
          <StatusBadge :value="row.ext?.status || 'proposed'" :options="statusOptions" />
        </template>
        <template #priority="{ row }">
          <StatusBadge :value="row.ext?.priority || 'P2'" :options="priorityOptions" />
        </template>
        <template #actions="{ row }">
          <el-button type="primary" size="small" @click="handleEdit(row)">跟踪</el-button>
          <el-button size="small" @click="handleView(row)">详情</el-button>
        </template>
      </DataTable>
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

    <el-dialog v-model="detailVisible" title="需求详情" width="700px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="需求编号">{{ detail.req_id }}</el-descriptions-item>
        <el-descriptions-item label="需求名称">{{ detail.req_name }}</el-descriptions-item>
        <el-descriptions-item label="提出人">{{ detail.proposer }}</el-descriptions-item>
        <el-descriptions-item label="提出时间">{{ detail.propose_time }}</el-descriptions-item>
        <el-descriptions-item label="系统">{{ detail.system_name }}</el-descriptions-item>
        <el-descriptions-item label="SA">{{ detail.sa_name }}</el-descriptions-item>
        <el-descriptions-item label="开发单号">{{ detail.dev_ticket_no }}</el-descriptions-item>
        <el-descriptions-item label="工作量">{{ detail.workload }}</el-descriptions-item>
      </el-descriptions>
      <div class="detail-section">
        <div class="detail-section-title">需求背景</div>
        <div class="detail-section-content">{{ detail.background }}</div>
      </div>
      <div class="detail-section">
        <div class="detail-section-title">需求描述</div>
        <div class="detail-section-content">{{ detail.description }}</div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import DataTable from '@/components/Common/DataTable.vue'
import SearchForm from '@/components/Common/SearchForm.vue'
import StatusBadge from '@/components/Common/StatusBadge.vue'
import { getRequirements, getRequirement, updateRequirement, getRequirementStats } from '@/api/requirement.js'

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

const columns = [
  { prop: 'req_id', label: '需求编号', width: 160 },
  { prop: 'req_name', label: '需求名称', minWidth: 200 },
  { prop: 'proposer', label: '提出人', width: 100 },
  { prop: 'system_name', label: '系统', width: 120 },
  { slot: 'priority', label: '优先级', width: 90 },
  { slot: 'status', label: '状态', width: 100 },
  { slot: 'actions', label: '操作', width: 150, fixed: 'right' },
]

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
const query = reactive({ keyword: '', status: '', priority: '' })
const stats = ref({ total: 0, proposed: 0, accepted: 0, dev: 0, closed: 0, paused: 0, involved: 0 })

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
const form = reactive({ req_id: '', req_name: '', status: '', priority: '', tags: '', personal_note: '' })
const detail = ref({})

async function fetchData() {
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
    detailVisible.value = true
  } catch (err) {
    ElMessage.error(err.message || '获取详情失败')
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
</style>
