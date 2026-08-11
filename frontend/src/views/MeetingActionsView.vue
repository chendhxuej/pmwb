<template>
  <div class="meeting-actions-view">
    <div class="page-head">
      <div>
        <h2 class="page-title">会议行动项</h2>
        <div class="page-crumb">工作台 / 会议日程 / 行动项</div>
      </div>
      <div class="page-actions">
        <el-button @click="handleRefresh" :icon="Refresh" :loading="loading">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never" class="search-card">
      <el-form :model="queryForm" inline>
        <el-form-item label="关键字">
          <EnlargeInput v-model="queryForm.keyword" placeholder="内容 / 会议主题" clearable />
        </el-form-item>
        <el-form-item label="负责人">
          <EnlargeInput v-model="queryForm.owner" placeholder="负责人姓名" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryForm.status" placeholder="全部" clearable style="width: 120px">
            <el-option
              v-for="item in statusOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker
            v-model="dueDateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            value-format="YYYY-MM-DD"
            style="width: 240px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card" v-loading="loading">
      <el-table :data="tableData" stripe>
        <el-table-column prop="meeting_title" label="会议主题" min-width="180" show-overflow-tooltip />
        <el-table-column prop="content" label="行动项内容" min-width="260" show-overflow-tooltip />
        <el-table-column prop="owner" label="负责人" width="120" />
        <el-table-column prop="created_at" label="创建时间" width="130">
          <template #default="{ row }">{{ row.created_at ? String(row.created_at).slice(0, 10) : '-' }}</template>
        </el-table-column>
        <el-table-column prop="due_date" label="计划完成" width="120">
          <template #default="{ row }">{{ row.due_date || '-' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status !== 'done'"
              link
              type="primary"
              size="small"
              @click="handleMarkDone(row)"
            >完成</el-button>
            <el-button
              v-if="row.status === 'done'"
              link
              type="warning"
              size="small"
              @click="handleReopen(row)"
            >重开</el-button>
            <el-button link type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button link type="primary" size="small" @click="handleSupervise(row)">督办</el-button>
            <el-button link type="info" size="small" @click="gotoMeeting(row)">会议</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-bar">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next"
          :page-sizes="[10, 20, 50]"
          @change="loadData"
        />
      </div>
    </el-card>

    <el-dialog v-model="superviseVisible" title="行动项督办" width="480px">
      <el-form :model="superviseForm" label-width="80px">
        <el-form-item label="行动项">
          <div class="dialog-content">{{ superviseForm.content }}</div>
        </el-form-item>
        <el-form-item label="负责人">
          <div class="dialog-content">{{ superviseForm.owner || '-' }}</div>
        </el-form-item>
        <el-form-item label="督办类型">
          <el-radio-group v-model="superviseForm.scene">
            <el-radio label="sync">同步通知</el-radio>
            <el-radio label="urge">催办</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="收件人">
          <EnlargeInput
            v-model="superviseForm.recipientsText"
            placeholder="多个收件人姓名用逗号分隔，为空则取负责人"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="superviseVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmSupervise" :loading="superviseLoading">发送督办</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑行动项" width="560px">
      <el-form :model="editForm" label-width="90px" :rules="editRules" ref="editFormRef">
        <el-form-item label="行动项内容" prop="content">
          <EnlargeInput
            v-model="editForm.content"
            type="textarea"
            :rows="3"
            placeholder="行动项具体内容"
          />
        </el-form-item>
        <el-form-item label="负责人">
          <EnlargeInput v-model="editForm.owner" placeholder="负责人姓名" />
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker
            v-model="editForm.due_date"
            type="date"
            placeholder="选择截止日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status" placeholder="选择状态" style="width: 100%">
            <el-option
              v-for="item in statusOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmEdit" :loading="editLoading">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { meetingApi } from '@/api/meeting'

const router = useRouter()

const loading = ref(false)
const tableData = ref([])
const queryForm = reactive({
  keyword: '',
  owner: '',
  status: '',
})
const dueDateRange = ref([])
const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0,
})

const statusOptions = [
  { label: '待处理', value: 'pending' },
  { label: '进行中', value: 'in_progress' },
  { label: '已完成', value: 'done' },
  { label: '未参加', value: 'not_attended' },
]

const statusMap = Object.fromEntries(statusOptions.map(i => [i.value, i]))

function statusLabel(status) {
  return statusMap[status]?.label || status
}

function statusType(status) {
  const map = {
    pending: 'info',
    in_progress: 'warning',
    done: 'success',
    not_attended: 'danger',
  }
  return map[status] || 'info'
}

function buildParams() {
  const params = {
    keyword: queryForm.keyword || undefined,
    owner: queryForm.owner || undefined,
    status: queryForm.status || undefined,
    page: pagination.page,
    page_size: pagination.page_size,
  }
  if (dueDateRange.value && dueDateRange.value.length === 2) {
    params.due_start = dueDateRange.value[0]
    params.due_end = dueDateRange.value[1]
  }
  return params
}

async function loadData() {
  loading.value = true
  try {
    const res = await meetingApi.listActions(buildParams())
    tableData.value = res.items || []
    pagination.total = res.total || 0
    pagination.page = res.page || 1
    pagination.page_size = res.page_size || 20
  } catch (err) {
    ElMessage.error(err.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.page = 1
  loadData()
}

function handleReset() {
  queryForm.keyword = ''
  queryForm.owner = ''
  queryForm.status = ''
  dueDateRange.value = []
  pagination.page = 1
  loadData()
}

function handleRefresh() {
  loadData()
}

async function updateStatus(row, status) {
  try {
    await meetingApi.updateActionStatus(row.meeting_id, row.id, { status })
    ElMessage.success('状态已更新')
    loadData()
  } catch (err) {
    ElMessage.error(err.message || '更新失败')
  }
}

function handleMarkDone(row) {
  ElMessageBox.confirm('确认将该行动项标记为已完成？', '提示', { type: 'warning' })
    .then(() => updateStatus(row, 'done'))
    .catch(() => {})
}

function handleReopen(row) {
  ElMessageBox.confirm('确认重开该行动项？', '提示', { type: 'warning' })
    .then(() => updateStatus(row, 'pending'))
    .catch(() => {})
}

function gotoMeeting(row) {
  router.push(`/meeting?id=${row.meeting_id}`)
}

const superviseVisible = ref(false)
const superviseLoading = ref(false)
const superviseForm = reactive({
  meeting_id: null,
  id: null,
  content: '',
  owner: '',
  scene: 'urge',
  recipientsText: '',
})

function handleSupervise(row) {
  superviseForm.meeting_id = row.meeting_id
  superviseForm.id = row.id
  superviseForm.content = row.content
  superviseForm.owner = row.owner || ''
  superviseForm.scene = 'urge'
  superviseForm.recipientsText = row.owner || ''
  superviseVisible.value = true
}

async function confirmSupervise() {
  const recipients = superviseForm.recipientsText
    .split(/[,，;；]/)
    .map(s => s.trim())
    .filter(Boolean)
  superviseLoading.value = true
  try {
    await meetingApi.superviseAction(superviseForm.meeting_id, superviseForm.id, {
      scene: superviseForm.scene,
      recipients: recipients.length ? recipients : undefined,
    })
    ElMessage.success('督办邮件已发送')
    superviseVisible.value = false
  } catch (err) {
    ElMessage.error(err.message || '督办失败')
  } finally {
    superviseLoading.value = false
  }
}

const editVisible = ref(false)
const editLoading = ref(false)
const editFormRef = ref(null)
const editForm = reactive({
  meeting_id: null,
  id: null,
  content: '',
  owner: '',
  due_date: '',
  status: '',
})

const editRules = {
  content: [{ required: true, message: '请输入行动项内容', trigger: 'blur' }],
}

function handleEdit(row) {
  editForm.meeting_id = row.meeting_id
  editForm.id = row.id
  editForm.content = row.content || ''
  editForm.owner = row.owner || ''
  editForm.due_date = row.due_date || ''
  editForm.status = row.status || 'pending'
  editVisible.value = true
}

async function confirmEdit() {
  if (!editFormRef.value) return
  try {
    await editFormRef.value.validate()
  } catch {
    return
  }

  editLoading.value = true
  try {
    await meetingApi.updateAction(editForm.meeting_id, editForm.id, {
      content: editForm.content,
      owner: editForm.owner || undefined,
      due_date: editForm.due_date || undefined,
      status: editForm.status,
    })
    ElMessage.success('保存成功')
    editVisible.value = false
    loadData()
  } catch (err) {
    ElMessage.error(err.message || '保存失败')
  } finally {
    editLoading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.meeting-actions-view {
  padding: 20px;
}
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 18px;
}
.page-title {
  margin: 0 0 6px 0;
  font-size: 22px;
  font-weight: 600;
}
.page-crumb {
  color: #909399;
  font-size: 13px;
}
.page-actions {
  display: flex;
  gap: 10px;
}
.search-card {
  margin-bottom: 16px;
}
.table-card {
  min-height: 400px;
}
.pagination-bar {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
.dialog-content {
  color: #606266;
  line-height: 1.5;
  word-break: break-all;
}
</style>
