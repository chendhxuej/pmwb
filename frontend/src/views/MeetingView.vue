<template>
  <div class="meeting-view">
    <h2 class="page-title">会议管理</h2>

    <!-- 搜索表单 -->
    <el-card class="search-card" shadow="never">
      <el-form :model="queryForm" inline>
        <el-form-item label="关键字">
          <el-input v-model="queryForm.keyword" placeholder="编号/主题/主持人" clearable />
        </el-form-item>
        <el-form-item label="会议类型">
          <el-select v-model="queryForm.meeting_type" placeholder="全部" clearable>
            <el-option
              v-for="item in meetingTypeOptions"
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
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <div class="toolbar">
      <el-button type="primary" @click="handleAdd">新增会议</el-button>
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
        <el-table-column prop="meeting_id" label="会议编号" width="160" />
        <el-table-column prop="title" label="会议主题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="meeting_type" label="类型" width="120">
          <template #default="{ row }">
            {{ meetingTypeText(row.meeting_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <StatusBadge :value="row.status" :options="statusBadgeOptions" />
          </template>
        </el-table-column>
        <el-table-column prop="host" label="主持人" width="120" />
        <el-table-column prop="start_time" label="开始时间" width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.start_time) }}
          </template>
        </el-table-column>
        <el-table-column prop="location" label="地点/链接" min-width="150" show-overflow-tooltip />
        <el-table-column prop="attendees" label="参会人数" width="90">
          <template #default="{ row }">
            {{ row.attendees ? row.attendees.length : 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="actions" label="行动项" width="90">
          <template #default="{ row }">
            {{ row.actions ? row.actions.length : 0 }}
          </template>
        </el-table-column>
      </template>
    </DataTable>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑会议' : '新增会议'"
      width="800px"
      destroy-on-close
    >
      <el-form :model="form" label-width="100px" :rules="rules" ref="formRef">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="会议编号" prop="meeting_id">
              <el-input v-model="form.meeting_id" placeholder="如 MEET-20260713-001" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="会议主题" prop="title">
              <el-input v-model="form.title" placeholder="会议主题" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="会议类型" prop="meeting_type">
              <el-select v-model="form.meeting_type" placeholder="请选择" style="width: 100%">
                <el-option
                  v-for="item in meetingTypeOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
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
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="开始时间" prop="start_time">
              <el-date-picker
                v-model="form.start_time"
                type="datetime"
                placeholder="选择时间"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束时间" prop="end_time">
              <el-date-picker
                v-model="form.end_time"
                type="datetime"
                placeholder="选择时间"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="主持人" prop="host">
              <el-input v-model="form.host" placeholder="主持人" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="地点/链接" prop="location">
              <el-input v-model="form.location" placeholder="会议室/腾讯会议链接" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="纪要摘要" prop="summary">
          <el-input v-model="form.summary" type="textarea" :rows="3" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="关联需求" prop="related_req_id">
              <el-input v-model="form.related_req_id" placeholder="关联需求编号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联工单" prop="related_ticket_no">
              <el-input v-model="form.related_ticket_no" placeholder="关联开发工单编号" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="Obsidian" prop="obsidian_path">
          <el-input v-model="form.obsidian_path" placeholder="Obsidian 纪要路径" />
        </el-form-item>

        <!-- 参会人 -->
        <el-divider content-position="left">参会人</el-divider>
        <div class="sub-form-section">
          <el-row
            v-for="(attendee, index) in form.attendees"
            :key="index"
            :gutter="12"
            class="sub-row"
          >
            <el-col :span="7">
              <el-input v-model="attendee.name" placeholder="姓名" />
            </el-col>
            <el-col :span="7">
              <el-input v-model="attendee.email" placeholder="邮箱" />
            </el-col>
            <el-col :span="6">
              <el-input v-model="attendee.dept" placeholder="部门" />
            </el-col>
            <el-col :span="2">
              <el-checkbox v-model="attendee.is_required" :true-label="1" :false-label="0">必</el-checkbox>
            </el-col>
            <el-col :span="2">
              <el-button link type="danger" @click="removeAttendee(index)">删除</el-button>
            </el-col>
          </el-row>
          <el-button type="primary" link @click="addAttendee">+ 添加参会人</el-button>
        </div>

        <!-- 行动项 -->
        <el-divider content-position="left">行动项</el-divider>
        <div class="sub-form-section">
          <el-row
            v-for="(action, index) in form.actions"
            :key="index"
            :gutter="12"
            class="sub-row"
          >
            <el-col :span="10">
              <el-input v-model="action.content" placeholder="行动项内容" />
            </el-col>
            <el-col :span="5">
              <el-input v-model="action.owner" placeholder="负责人" />
            </el-col>
            <el-col :span="5">
              <el-date-picker
                v-model="action.due_date"
                type="date"
                placeholder="截止日期"
                style="width: 100%"
                value-format="YYYY-MM-DD"
              />
            </el-col>
            <el-col :span="4">
              <el-button link type="danger" @click="removeAction(index)">删除</el-button>
            </el-col>
          </el-row>
          <el-button type="primary" link @click="addAction">+ 添加行动项</el-button>
        </div>
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
import { meetingApi } from '@/api/meeting'
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
  meeting_type: '',
  status: '',
})

const meetingTypeOptions = [
  { value: 'requirement_review', label: '需求评审' },
  { value: 'project_weekly', label: '项目周报' },
  { value: 'troubleshooting', label: '问题排查' },
  { value: 'training', label: '培训' },
  { value: 'other', label: '其他' },
]

const statusOptions = [
  { value: 'planned', label: '计划中' },
  { value: 'held', label: '已召开' },
  { value: 'cancelled', label: '已取消' },
]

const statusBadgeOptions = {
  planned: { label: '计划中', type: 'primary' },
  held: { label: '已召开', type: 'success' },
  cancelled: { label: '已取消', type: 'info' },
}

const meetingTypeText = (type) => {
  const item = meetingTypeOptions.find((i) => i.value === type)
  return item ? item.label : type
}

const defaultForm = {
  meeting_id: '',
  title: '',
  meeting_type: 'other',
  status: 'planned',
  start_time: '',
  end_time: '',
  location: '',
  host: '',
  summary: '',
  obsidian_path: '',
  related_req_id: '',
  related_ticket_no: '',
  attendees: [],
  actions: [],
}

const form = reactive({ ...defaultForm })

const rules = {
  meeting_id: [{ required: true, message: '请输入会议编号', trigger: 'blur' }],
  title: [{ required: true, message: '请输入会议主题', trigger: 'blur' }],
  meeting_type: [{ required: true, message: '请选择会议类型', trigger: 'change' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await meetingApi.listMeetings({
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

const handleSearch = () => {
  pagination.page = 1
  loadData()
}

const handleReset = () => {
  queryForm.keyword = ''
  queryForm.meeting_type = ''
  queryForm.status = ''
  pagination.page = 1
  loadData()
}

const handleAdd = () => {
  isEdit.value = false
  Object.assign(form, { ...defaultForm, meeting_id: generateMeetingId() })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  Object.assign(form, JSON.parse(JSON.stringify(row)))
  dialogVisible.value = true
}

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定删除会议「${row.title}」吗？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    await meetingApi.deleteMeeting(row.id)
    ElMessage.success('删除成功')
    loadData()
  })
}

const addAttendee = () => {
  form.attendees.push({ name: '', email: '', dept: '', is_required: 1 })
}

const removeAttendee = (index) => {
  form.attendees.splice(index, 1)
}

const addAction = () => {
  form.actions.push({ content: '', owner: '', due_date: '', status: 'pending' })
}

const removeAction = (index) => {
  form.actions.splice(index, 1)
}

const handleSubmit = async () => {
  formRef.value.validate(async (valid) => {
    if (!valid) return

    const payload = { ...form }
    // 规范化：空字符串 -> null（避免后端 Optional[datetime] 等字段 422）；
    // Date 对象 -> ISO 字符串
    for (const key of Object.keys(payload)) {
      const v = payload[key]
      if (v instanceof Date) {
        payload[key] = v.toISOString()
      } else if (v === '') {
        payload[key] = null
      }
    }
    payload.attendees = payload.attendees
      .filter((a) => a.name.trim())
      .map((a) => ({
        name: a.name.trim(),
        email: a.email ? a.email.trim() : null,
        dept: a.dept ? a.dept.trim() : null,
        is_required: a.is_required ? 1 : 0,
      }))
    payload.actions = payload.actions
      .filter((a) => a.content.trim())
      .map((a) => ({
        content: a.content.trim(),
        owner: a.owner ? a.owner.trim() : null,
        due_date: a.due_date ? a.due_date : null,
        status: a.status || 'pending',
      }))

    try {
      if (isEdit.value) {
        await meetingApi.updateMeeting(form.id, payload)
        ElMessage.success('更新成功')
      } else {
        await meetingApi.createMeeting(payload)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      loadData()
    } catch (error) {
      ElMessage.error(error.response?.data?.message || '操作失败')
    }
  })
}

const generateMeetingId = () => {
  const date = new Date().toISOString().slice(0, 10).replace(/-/g, '')
  const random = Math.floor(Math.random() * 1000).toString().padStart(3, '0')
  return `MEET-${date}-${random}`
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.meeting-view {
  padding: 20px;
}

.page-title {
  margin-bottom: 20px;
  font-size: 20px;
  font-weight: 600;
}

.search-card {
  margin-bottom: 16px;
}

.toolbar {
  margin-bottom: 16px;
}

.sub-form-section {
  margin-bottom: 16px;
}

.sub-row {
  margin-bottom: 12px;
  align-items: center;
}
</style>
