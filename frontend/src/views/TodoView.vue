<template>
  <div class="todo-view">
    <h2 class="page-title">待办中心</h2>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-col">
        <el-card shadow="hover" class="stat-card stat-warning clickable" @click="goTo('/requirement')">
          <div class="stat-item">
            <div class="stat-value" v-countup="stats.dev_ticket_missing"></div>
            <div class="stat-label">开发单号未录入</div>
          </div>
        </el-card>
      </div>
      <div class="stat-col">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-value" v-countup="stats.total"></div>
            <div class="stat-label">待办总数</div>
          </div>
        </el-card>
      </div>
      <div class="stat-col">
        <el-card shadow="hover" class="status-todo">
          <div class="stat-item">
            <div class="stat-value" v-countup="stats.todo"></div>
            <div class="stat-label">未开始</div>
          </div>
        </el-card>
      </div>
      <div class="stat-col">
        <el-card shadow="hover" class="status-progress">
          <div class="stat-item">
            <div class="stat-value" v-countup="stats.in_progress"></div>
            <div class="stat-label">进行中</div>
          </div>
        </el-card>
      </div>
      <div class="stat-col">
        <el-card shadow="hover" class="status-done">
          <div class="stat-item">
            <div class="stat-value" v-countup="stats.done"></div>
            <div class="stat-label">已完成</div>
          </div>
        </el-card>
      </div>
      <div class="stat-col">
        <el-card shadow="hover" class="status-today">
          <div class="stat-item">
            <div class="stat-value" v-countup="stats.today"></div>
            <div class="stat-label">今日截止</div>
          </div>
        </el-card>
      </div>
      <div class="stat-col">
        <el-card shadow="hover" class="status-overdue">
          <div class="stat-item">
            <div class="stat-value" v-countup="stats.overdue"></div>
            <div class="stat-label">已超期</div>
          </div>
        </el-card>
      </div>
    </div>

    <!-- 搜索表单 -->
    <el-card class="search-card" shadow="never">
      <el-form :model="queryForm" inline>
        <el-form-item label="关键字">
          <EnlargeInput v-model="queryForm.keyword" placeholder="标题/内容" clearable />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="queryForm.category" placeholder="全部" clearable>
            <el-option
              v-for="item in categoryOptions"
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
        <el-form-item label="优先级">
          <el-select v-model="queryForm.priority" placeholder="全部" clearable>
            <el-option
              v-for="item in priorityOptions"
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

    <div class="toolbar">
      <el-button type="primary" @click="handleAdd">新增待办</el-button>
    </div>

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
        <el-table-column prop="title" label="待办标题" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span
              class="todo-title"
              :class="{ linked: row.related_id, 'done-text': row.status === 'done' }"
              :title="row.related_id ? '点击查看关联工单详情' : ''"
              @click="row.related_id && openLinked(row)"
            >{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="100">
          <template #default="{ row }">
            {{ categoryText(row.category) }}
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="90">
          <template #default="{ row }">
            <el-tag :type="priorityType(row.priority)" size="small">{{ row.priority }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-select
              v-model="row.status"
              size="small"
              class="w-xs"
              @change="(val) => handleStatusChange(row, val)"
            >
              <el-option
                v-for="item in statusOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column prop="due_date" label="计划完成" width="120">
          <template #default="{ row }">
            <span :class="{ overdue: row.is_overdue }">{{ row.due_date || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="related_type" label="关联" width="140">
          <template #default="{ row }">
            <el-tag v-if="row.related_type" size="small" type="info">{{ relatedTypeText(row.related_type) }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="100" />
        <el-table-column prop="created_at" label="创建时间" width="130">
          <template #default="{ row }">{{ row.created_at ? String(row.created_at).slice(0, 10) : '-' }}</template>
        </el-table-column>
      </template>
    </DataTable>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑待办' : '新增待办'"
      width="650px"
      destroy-on-close
    >
      <el-form :model="form" label-width="100px" :rules="rules" ref="formRef">
        <el-form-item label="待办标题" prop="title">
          <EnlargeInput v-model="form.title" placeholder="待办标题" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="分类" prop="category">
              <el-select v-model="form.category" placeholder="请选择" style="width: 100%">
                <el-option
                  v-for="item in categoryOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级" prop="priority">
              <el-select v-model="form.priority" placeholder="请选择" style="width: 100%">
                <el-option
                  v-for="item in priorityOptions"
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
            <el-form-item label="重复" prop="repeat_type">
              <el-select v-model="form.repeat_type" placeholder="请选择" style="width: 100%">
                <el-option label="不重复" value="none" />
                <el-option label="每天" value="daily" />
                <el-option label="每周" value="weekly" />
                <el-option label="每月" value="monthly" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="截止日期" prop="due_date">
              <el-date-picker
                v-model="form.due_date"
                type="date"
                placeholder="选择日期"
                style="width: 100%"
                value-format="YYYY-MM-DD"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="截止时间" prop="due_time">
              <el-time-picker
                v-model="form.due_time"
                placeholder="选择时间"
                style="width: 100%"
                value-format="HH:mm"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="关联类型" prop="related_type">
              <el-select v-model="form.related_type" placeholder="请选择" style="width: 100%" clearable>
                <el-option label="需求" value="requirement" />
                <el-option label="工单" value="ticket" />
                <el-option label="运营问题" value="operation" />
                <el-option label="会议" value="meeting" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联ID" prop="related_id">
              <EnlargeInput v-model="form.related_id" placeholder="关联对象编号" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="提醒时间" prop="remind_at">
          <el-date-picker
            v-model="form.remind_at"
            type="datetime"
            placeholder="选择提醒时间"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="待办内容" prop="content">
          <EnlargeInput v-model="form.content" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 关联工单详情抽屉（点击待办标题直接展开，不跳转） -->
    <el-drawer
      v-model="woDrawerVisible"
      :title="'工单详情 · ' + (woDetail?.issue_no || '')"
      size="56%"
      destroy-on-close
    >
      <div v-loading="woLoading" class="wo-drawer-body">
        <template v-if="woDetail">
          <el-descriptions :column="2" border size="small" class="wo-desc">
            <el-descriptions-item label="工单标题" :span="2">{{ woDetail.title || '-' }}</el-descriptions-item>
            <el-descriptions-item label="状态">{{ woDetail.status || '-' }}</el-descriptions-item>
            <el-descriptions-item label="优先级/影响">{{ woDetail.impact_level || '-' }}</el-descriptions-item>
            <el-descriptions-item label="责任人">{{ woDetail.handler || '-' }}</el-descriptions-item>
            <el-descriptions-item label="关联系统">{{ woDetail.related_system || '-' }}</el-descriptions-item>
            <el-descriptions-item label="发现时间">{{ fmtDate(woDetail.discovery_date) }}</el-descriptions-item>
            <el-descriptions-item label="解决时间">{{ fmtDate(woDetail.resolve_date) }}</el-descriptions-item>
            <el-descriptions-item label="计划完成">{{ fmtDate(woDetail.go_live_date) }}</el-descriptions-item>
            <el-descriptions-item label="逾期">
              <el-tag v-if="woDetail.is_overdue" type="danger" size="small">已逾期</el-tag>
              <span v-else>正常</span>
            </el-descriptions-item>
          </el-descriptions>

          <div class="wo-sec" v-if="woDetail.situation_desc">
            <div class="wo-sec-title">情况说明</div>
            <div class="wo-desc-text">{{ woDetail.situation_desc }}</div>
          </div>
          <div class="wo-sec" v-if="woDetail.result_feedback">
            <div class="wo-sec-title">处理结果反馈</div>
            <div class="wo-desc-text">{{ woDetail.result_feedback }}</div>
          </div>
          <div class="wo-sec" v-if="woDetail.root_cause || woDetail.solution || woDetail.lesson_learned">
            <div class="wo-sec-title">结构化分析</div>
            <el-descriptions :column="1" border size="small" class="wo-desc">
              <el-descriptions-item v-if="woDetail.root_cause_type" label="根因分类">{{ woDetail.root_cause_type }}</el-descriptions-item>
              <el-descriptions-item v-if="woDetail.root_cause" label="根因分析">{{ woDetail.root_cause }}</el-descriptions-item>
              <el-descriptions-item v-if="woDetail.solution_type" label="解决方案类型">{{ woDetail.solution_type }}</el-descriptions-item>
              <el-descriptions-item v-if="woDetail.solution" label="解决方案">{{ woDetail.solution }}</el-descriptions-item>
              <el-descriptions-item v-if="woDetail.lesson_learned" label="经验总结">{{ woDetail.lesson_learned }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </template>
        <el-empty v-else-if="!woLoading" description="未找到关联工单" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import DataTable from '@/components/Common/DataTable.vue'
import { todoApi } from '@/api/todo'
import { getRequirementStats } from '@/api/requirement.js'
import { operationApi } from '@/api/operation'

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
  category: '',
  status: '',
  priority: '',
})

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

const categoryText = (category) => {
  const item = categoryOptions.find((i) => i.value === category)
  return item ? item.label : category
}

const priorityType = (priority) => {
  const map = { P0: 'danger', P1: 'warning', P2: 'primary', P3: 'info' }
  return map[priority] || 'info'
}

const relatedTypeText = (type) => {
  const map = { requirement: '需求', ticket: '工单', operation: '运营问题', meeting: '会议' }
  return map[type] || type
}

const defaultForm = {
  title: '',
  content: '',
  category: 'other',
  priority: 'P2',
  status: 'todo',
  due_date: '',
  due_time: '',
  remind_at: '',
  repeat_type: 'none',
  related_type: '',
  related_id: '',
  source: 'manual',
}

const form = reactive({ ...defaultForm })

const rules = {
  title: [{ required: true, message: '请输入待办标题', trigger: 'blur' }],
  category: [{ required: true, message: '请选择分类', trigger: 'change' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
}

const stats = reactive({
  total: 0,
  todo: 0,
  in_progress: 0,
  done: 0,
  cancelled: 0,
  overdue: 0,
  today: 0,
  dev_ticket_missing: 0,
})

const loadData = async () => {
  loading.value = true
  try {
    const res = await todoApi.listTodos({
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
    const res = await todoApi.getStats()
    Object.assign(stats, res)
  } catch (error) {
    ElMessage.error('加载统计失败')
  }
}

const router = useRouter()
const route = useRoute()

/* 深链：?id= 定位并编辑待办 */
const deepLinkId = computed(() => route.query.id)

function applyDeepLink() {
  const id = deepLinkId.value
  if (!id) return
  const row = tableData.value.find((t) => String(t.id) === String(id))
  if (row) handleEdit(row)
}
const goTo = (path) => {
  router.push(path)
}

// 点击待办标题：关联工单直接在抽屉内展开详情（不跳转）
const woDrawerVisible = ref(false)
const woDetail = ref(null)
const woLoading = ref(false)

const openWoDetail = async (relatedId) => {
  woLoading.value = true
  woDrawerVisible.value = true
  woDetail.value = null
  try {
    const num = Number(relatedId)
    let res = null
    if (isFinite(num) && num > 0) {
      try { res = await operationApi.getIssue(num) } catch (e) { res = null }
    }
    if (!res) {
      const list = await operationApi.listIssues({ issue_no: String(relatedId), page: 1, page_size: 1 })
      res = (list.items || [])[0] || null
    }
    if (!res) {
      ElMessage.warning('未找到关联工单（编号：' + relatedId + '）')
      woDrawerVisible.value = false
      return
    }
    woDetail.value = res
  } catch (e) {
    ElMessage.error('加载工单详情失败')
    woDrawerVisible.value = false
  } finally {
    woLoading.value = false
  }
}

const fmtDate = (v) => (v ? String(v).slice(0, 10) : '—')

const openLinked = (row) => {
  if (!row.related_id) {
    ElMessage.info('该待办未关联工单')
    return
  }
  // 工单类（运营工单 / 开发工单）直接弹抽屉展示详情
  if (row.related_type === 'operation' || row.related_type === 'ticket') {
    openWoDetail(row.related_id)
    return
  }
  // 其它关联类型跳转到对应模块
  const modMap = { requirement: '/requirement', meeting: '/meeting' }
  router.push(modMap[row.related_type] || '/operation')
}

// 开发单号未录入需求数（来自需求统计，点击跳转需求管理跟进）
const loadDevTicketMissing = async () => {
  try {
    const res = await getRequirementStats()
    stats.dev_ticket_missing = res.dev_ticket_missing || 0
  } catch (error) {
    console.error('加载开发单号未录入统计失败', error)
  }
}

const handleSearch = () => {
  pagination.page = 1
  loadData()
}

const handleReset = () => {
  queryForm.keyword = ''
  queryForm.category = ''
  queryForm.status = ''
  queryForm.priority = ''
  pagination.page = 1
  loadData()
}

const handleAdd = () => {
  isEdit.value = false
  Object.assign(form, { ...defaultForm })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  Object.assign(form, JSON.parse(JSON.stringify(row)))
  dialogVisible.value = true
}

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定删除待办「${row.title}」吗？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    await todoApi.deleteTodo(row.id)
    ElMessage.success('删除成功')
    loadData()
    loadStats()
  })
}

const handleStatusChange = async (row, status) => {
  try {
    await todoApi.updateTodoStatus(row.id, status)
    ElMessage.success('状态更新成功')
    loadData()
    loadStats()
  } catch (error) {
    ElMessage.error('状态更新失败')
  }
}

const handleSubmit = async () => {
  formRef.value.validate(async (valid) => {
    if (!valid) return

    const payload = { ...form }
    for (const k of Object.keys(payload)) {
      if (payload[k] === '') payload[k] = null
    }
    if (payload.remind_at && typeof payload.remind_at === 'object') {
      payload.remind_at = payload.remind_at.toISOString()
    }

    try {
      if (isEdit.value) {
        await todoApi.updateTodo(form.id, payload)
        ElMessage.success('更新成功')
      } else {
        await todoApi.createTodo(payload)
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

onMounted(async () => {
  await loadData()
  loadStats()
  loadDevTicketMissing()
  applyDeepLink()
})
</script>

<style scoped>
.todo-view {
  padding: 20px;
}

.page-title {
  margin-bottom: 20px;
  font-size: 20px;
  font-weight: 600;
}

.stats-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.stat-col {
  flex: 1;
  min-width: 140px;
}

.clickable {
  cursor: pointer;
}

.clickable:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-elevated);
}

.stat-item {
  text-align: center;
  padding: 10px 0;
}

.status-todo .stat-value {
  color: var(--danger);
}

.status-progress .stat-value {
  color: var(--warning);
}

.status-done .stat-value {
  color: var(--success);
}

.status-today .stat-value {
  color: var(--accent);
}

.status-overdue .stat-value {
  color: var(--text-muted);
}

.search-card {
  margin-bottom: 16px;
}

.toolbar {
  margin-bottom: 16px;
}

.done-text {
  text-decoration: line-through;
  color: #909399;
}

.overdue {
  color: #f56c6c;
  font-weight: 600;
}

.todo-title.linked {
  color: var(--accent);
  cursor: pointer;
}
.todo-title.linked:hover {
  text-decoration: underline;
}

/* 关联工单详情抽屉 */
.wo-drawer-body {
  padding: 4px 2px;
}
.wo-sec {
  margin-top: 16px;
}
.wo-sec-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}
.wo-desc-text {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
  white-space: pre-wrap;
}
</style>
