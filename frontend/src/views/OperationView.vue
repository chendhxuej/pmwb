<template>
  <div class="operation-view">
    <h2 class="page-title">业务运营监控</h2>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="4">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-value">{{ stats.total }}</div>
            <div class="stat-label">问题总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="status-pending">
          <div class="stat-item">
            <div class="stat-value">{{ stats.pending }}</div>
            <div class="stat-label">待处理</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="status-processing">
          <div class="stat-item">
            <div class="stat-value">{{ stats.processing }}</div>
            <div class="stat-label">处理中</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="status-verify">
          <div class="stat-item">
            <div class="stat-value">{{ stats.verify }}</div>
            <div class="stat-label">待验证</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="status-resolved">
          <div class="stat-item">
            <div class="stat-value">{{ stats.resolved }}</div>
            <div class="stat-label">已解决</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="status-overdue">
          <div class="stat-item">
            <div class="stat-value">{{ stats.overdue }}</div>
            <div class="stat-label">超期</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 搜索表单 -->
    <el-card class="search-card" shadow="never">
      <el-form :model="queryForm" inline>
        <el-form-item label="关键字">
          <el-input v-model="queryForm.keyword" placeholder="编号/标题/处理人" clearable />
        </el-form-item>
        <el-form-item label="问题类型">
          <el-select v-model="queryForm.issue_type" placeholder="全部" clearable>
            <el-option
              v-for="item in issueTypeOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryForm.status" placeholder="全部" clearable>
            <el-option
              v-for="item in statusOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="影响等级">
          <el-select v-model="queryForm.impact_level" placeholder="全部" clearable>
            <el-option
              v-for="item in impactLevelOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 操作栏 -->
    <div class="toolbar">
      <el-button type="primary" @click="handleAdd">新增问题</el-button>
      <el-button @click="loadStats">刷新统计</el-button>
    </div>

    <!-- 数据表格 -->
    <DataTable
      :data="tableData"
      :total="pagination.total"
      :loading="loading"
      v-model:page="pagination.page"
      v-model:pageSize="pagination.page_size"
      @change="loadData"
      @edit="handleEdit"
      @delete="handleDelete"
    >
      <template #columns>
        <el-table-column prop="issue_no" label="问题编号" width="140" />
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="issue_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="issueTypeTagType(row.issue_type)" size="small">
              {{ issueTypeText(row.issue_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <StatusBadge :value="row.status" :options="statusBadgeOptions" />
          </template>
        </el-table-column>
        <el-table-column prop="impact_level" label="影响等级" width="90" />
        <el-table-column prop="handler" label="处理人" width="120" />
        <el-table-column prop="related_system" label="关联系统" width="140" show-overflow-tooltip />
        <el-table-column prop="discovery_date" label="发现时间" width="160">
          <template #default="{ row }">
            {{ formatDateTime(row.discovery_date) }}
          </template>
        </el-table-column>
        <el-table-column prop="is_overdue" label="超期" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.is_overdue" type="danger" size="small">是</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </template>
    </DataTable>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑问题' : '新增问题'"
      width="700px"
      destroy-on-close
    >
      <el-form :model="form" label-width="100px" :rules="rules" ref="formRef">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="问题编号" prop="issue_no">
              <el-input v-model="form.issue_no" placeholder="如 ISSUE-20260713-001" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="问题标题" prop="title">
              <el-input v-model="form.title" placeholder="简短描述问题" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="问题类型" prop="issue_type">
              <el-select v-model="form.issue_type" placeholder="请选择" style="width: 100%">
                <el-option
                  v-for="item in issueTypeOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="影响等级" prop="impact_level">
              <el-select v-model="form.impact_level" placeholder="请选择" style="width: 100%">
                <el-option
                  v-for="item in impactLevelOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-select v-model="form.status" placeholder="请选择" style="width: 100%">
                <el-option
                  v-for="item in statusOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="处理人" prop="handler">
              <el-input v-model="form.handler" placeholder="处理人姓名" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="发现时间" prop="discovery_date">
              <el-date-picker
                v-model="form.discovery_date"
                type="datetime"
                placeholder="选择时间"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="解决时间" prop="resolve_date">
              <el-date-picker
                v-model="form.resolve_date"
                type="datetime"
                placeholder="选择时间"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="关联系统" prop="related_system">
          <el-input v-model="form.related_system" placeholder="如 CRM / BOSS / 订单中心" />
        </el-form-item>
        <el-form-item label="关联需求" prop="related_req_id">
          <el-input v-model="form.related_req_id" placeholder="关联需求编号" />
        </el-form-item>
        <el-form-item label="关联工单" prop="related_ticket_no">
          <el-input v-model="form.related_ticket_no" placeholder="关联开发工单编号" />
        </el-form-item>
        <el-form-item label="影响范围" prop="impact_scope">
          <el-input v-model="form.impact_scope" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="根因分析" prop="root_cause">
          <el-input v-model="form.root_cause" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="解决方案" prop="solution">
          <el-input v-model="form.solution" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="知识沉淀" prop="obsidian_path">
          <el-input v-model="form.obsidian_path" placeholder="Obsidian 知识条目路径" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import DataTable from '@/components/Common/DataTable.vue'
import StatusBadge from '@/components/Common/StatusBadge.vue'
import { operationApi } from '@/api/operation'
import { formatDateTime } from '@/utils/format'

const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const tableData = ref([])

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0,
})

const queryForm = reactive({
  keyword: '',
  issue_type: '',
  status: '',
  impact_level: '',
})

const issueTypeOptions = [
  { value: 'data_error', label: '数据异常' },
  { value: 'system_failure', label: '系统故障' },
  { value: 'complaint', label: '客户投诉' },
  { value: 'process_block', label: '流程阻塞' },
  { value: 'performance', label: '性能问题' },
  { value: 'other', label: '其他' },
]

const statusOptions = [
  { value: 'pending', label: '待处理' },
  { value: 'processing', label: '处理中' },
  { value: 'verify', label: '待验证' },
  { value: 'resolved', label: '已解决' },
  { value: 'closed', label: '已关闭' },
  { value: 'suspended', label: '已挂起' },
]

const impactLevelOptions = [
  { value: 'P0', label: 'P0-严重' },
  { value: 'P1', label: 'P1-高' },
  { value: 'P2', label: 'P2-中' },
  { value: 'P3', label: 'P3-低' },
]

const statusBadgeOptions = {
  pending: { label: '待处理', type: 'danger' },
  processing: { label: '处理中', type: 'warning' },
  verify: { label: '待验证', type: 'primary' },
  resolved: { label: '已解决', type: 'success' },
  closed: { label: '已关闭', type: 'info' },
  suspended: { label: '已挂起', type: 'info' },
}

const issueTypeTagType = (type) => {
  const map = {
    data_error: 'danger',
    system_failure: 'danger',
    complaint: 'warning',
    process_block: 'warning',
    performance: 'info',
    other: 'info',
  }
  return map[type] || 'info'
}

const issueTypeText = (type) => {
  const item = issueTypeOptions.find((i) => i.value === type)
  return item ? item.label : type
}

const defaultForm = {
  issue_no: '',
  title: '',
  issue_type: 'other',
  status: 'pending',
  source: 'manual',
  discovery_date: '',
  resolve_date: '',
  handler: '',
  impact_scope: '',
  impact_level: 'P2',
  root_cause: '',
  solution: '',
  related_req_id: '',
  related_ticket_no: '',
  related_system: '',
  obsidian_path: '',
  is_overdue: 0,
}

const form = reactive({ ...defaultForm })

const rules = {
  issue_no: [{ required: true, message: '请输入问题编号', trigger: 'blur' }],
  title: [{ required: true, message: '请输入问题标题', trigger: 'blur' }],
  issue_type: [{ required: true, message: '请选择问题类型', trigger: 'change' }],
  impact_level: [{ required: true, message: '请选择影响等级', trigger: 'change' }],
}

const stats = reactive({
  total: 0,
  pending: 0,
  processing: 0,
  verify: 0,
  resolved: 0,
  closed: 0,
  suspended: 0,
  overdue: 0,
  by_type: [],
})

const loadData = async () => {
  loading.value = true
  try {
    const res = await operationApi.listIssues({
      ...queryForm,
      page: pagination.page,
      page_size: pagination.page_size,
    })
    tableData.value = res.items || []
    pagination.total = res.total || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const res = await operationApi.getStats()
    Object.assign(stats, res)
  } catch (error) {
    ElMessage.error('加载统计失败')
  }
}

const handleSearch = () => {
  pagination.page = 1
  loadData()
}

const handleReset = () => {
  queryForm.keyword = ''
  queryForm.issue_type = ''
  queryForm.status = ''
  queryForm.impact_level = ''
  pagination.page = 1
  loadData()
}

const handleAdd = () => {
  isEdit.value = false
  Object.assign(form, { ...defaultForm, issue_no: generateIssueNo() })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  Object.assign(form, JSON.parse(JSON.stringify(row)))
  dialogVisible.value = true
}

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定删除问题「${row.title}」吗？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    await operationApi.deleteIssue(row.id)
    ElMessage.success('删除成功')
    loadData()
    loadStats()
  })
}

const handleSubmit = async () => {
  formRef.value.validate(async (valid) => {
    if (!valid) return

    const payload = { ...form }
    for (const k of Object.keys(payload)) {
      if (payload[k] === '') payload[k] = null
    }
    if (payload.discovery_date && typeof payload.discovery_date === 'object') {
      payload.discovery_date = payload.discovery_date.toISOString()
    }
    if (payload.resolve_date && typeof payload.resolve_date === 'object') {
      payload.resolve_date = payload.resolve_date.toISOString()
    }

    try {
      if (isEdit.value) {
        await operationApi.updateIssue(form.id, payload)
        ElMessage.success('更新成功')
      } else {
        await operationApi.createIssue(payload)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      loadData()
      loadStats()
    } catch (error) {
      ElMessage.error(error.response?.data?.message || '操作失败')
    }
  })
}

const generateIssueNo = () => {
  const date = new Date().toISOString().slice(0, 10).replace(/-/g, '')
  const random = Math.floor(Math.random() * 1000).toString().padStart(3, '0')
  return `ISSUE-${date}-${random}`
}

onMounted(() => {
  loadData()
  loadStats()
})
</script>

<style scoped>
.operation-view {
  padding: 20px;
}

.page-title {
  margin-bottom: 20px;
  font-size: 20px;
  font-weight: 600;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-item {
  text-align: center;
  padding: 10px 0;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #606266;
  margin-top: 6px;
}

.search-card {
  margin-bottom: 16px;
}

.toolbar {
  margin-bottom: 16px;
  display: flex;
  gap: 12px;
}

.status-pending .stat-value {
  color: #f56c6c;
}

.status-processing .stat-value {
  color: #e6a23c;
}

.status-verify .stat-value {
  color: #409eff;
}

.status-resolved .stat-value {
  color: #67c23a;
}

.status-overdue .stat-value {
  color: #909399;
}
</style>
