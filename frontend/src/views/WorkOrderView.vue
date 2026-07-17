<template>
  <div class="work-order-view">
    <div class="page-head">
      <h2 class="page-title">{{ title }}</h2>
      <el-tag :type="categoryColor" effect="dark" size="large" round>{{ title }}</el-tag>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="12" class="stats-row">
      <el-col :span="3">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-value">{{ stats.total }}</div>
            <div class="stat-label">工单总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-pending">
          <div class="stat-item">
            <div class="stat-value">{{ stats.pending }}</div>
            <div class="stat-label">待处理</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-processing">
          <div class="stat-item">
            <div class="stat-value">{{ stats.processing }}</div>
            <div class="stat-label">处理中</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-verify">
          <div class="stat-item">
            <div class="stat-value">{{ stats.verify }}</div>
            <div class="stat-label">待验证</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-resolved">
          <div class="stat-item">
            <div class="stat-value">{{ stats.resolved }}</div>
            <div class="stat-label">已解决</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-closed">
          <div class="stat-item">
            <div class="stat-value">{{ stats.closed }}</div>
            <div class="stat-label">已关闭</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-overdue">
          <div class="stat-item">
            <div class="stat-value">{{ stats.overdue }}</div>
            <div class="stat-label">超期</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-loop">
          <div class="stat-item">
            <div class="stat-value">{{ stats.closed_loop_rate }}%</div>
            <div class="stat-label">闭环率</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 搜索表单 -->
    <el-card class="search-card" shadow="never">
      <el-form :model="queryForm" inline>
        <el-form-item label="关键字">
          <el-input v-model="queryForm.keyword" placeholder="编号/标题/责任人" clearable />
        </el-form-item>
        <el-form-item label="子类">
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
        <el-form-item label="责任人">
          <el-input v-model="queryForm.handler" placeholder="责任人姓名" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 操作栏 -->
    <div class="toolbar">
      <el-button type="primary" @click="handleAdd">新增工单</el-button>
      <el-button @click="loadStats">刷新统计</el-button>
      <span class="hint">每类工单责任到人、跟踪闭环（待处理→处理中→待验证→已解决/已关闭）</span>
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
        <el-table-column prop="issue_no" label="工单编号" width="150" />
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="issue_type" label="子类" width="110">
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
        <el-table-column prop="handler" label="责任人" width="160">
          <template #default="{ row }">
            <template v-if="row.handler">
              <el-tag
                v-for="h in row.handler.split(',')"
                :key="h"
                size="small"
                class="handler-tag"
              >{{ h }}</el-tag>
            </template>
            <span v-else>-</span>
          </template>
        </el-table-column>
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
      <template #actions="{ row }">
        <el-button link type="primary" @click="openDetail(row)">详情</el-button>
        <el-button link type="primary" @click="handleEdit(row)">编辑</el-button>
        <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
      </template>
    </DataTable>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑工单' : '新增工单'"
      width="720px"
      destroy-on-close
    >
      <el-form :model="form" label-width="100px" :rules="rules" ref="formRef">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="工单编号" prop="issue_no">
              <el-input v-model="form.issue_no" placeholder="如 BUG-20260716-001" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工单标题" prop="title">
              <el-input v-model="form.title" placeholder="简短描述问题" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="子类" prop="issue_type">
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
            <el-form-item label="责任人" prop="handler">
              <el-select
                v-model="form.handler"
                multiple
                filterable
                placeholder="选择责任人(可多选)"
                style="width: 100%"
              >
                <el-option-group
                  v-for="g in HANDLER_GROUPS"
                  :key="g.label"
                  :label="g.label"
                >
                  <el-option
                    v-for="o in g.options"
                    :key="o.value"
                    :label="o.label"
                    :value="o.value"
                  />
                </el-option-group>
              </el-select>
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
        <el-form-item label="情况说明" prop="situation_desc">
          <el-input v-model="form.situation_desc" type="textarea" :rows="2" placeholder="影响范围/具体情况说明" />
        </el-form-item>
        <el-form-item label="根因分析" prop="root_cause">
          <el-input v-model="form.root_cause" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="解决方案" prop="solution">
          <el-input v-model="form.solution" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="知识笔记" prop="obsidian_path">
          <div class="note-picker">
            <el-input
              v-model="form.obsidian_path"
              placeholder="选择关联的 Obsidian 知识笔记"
              readonly
              style="flex: 1"
            />
            <el-button @click="openNotePicker">选择笔记</el-button>
            <el-button
              v-if="form.obsidian_path"
              link
              type="danger"
              @click="form.obsidian_path = ''"
            >清除</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 关联笔记选择弹窗 -->
    <el-dialog
      v-model="notePickerVisible"
      title="选择关联知识笔记"
      width="640px"
      append-to-body
    >
      <el-input
        v-model="noteSearch"
        placeholder="搜索笔记标题"
        clearable
        style="margin-bottom: 12px"
      />
      <el-table
        :data="filteredNotes"
        height="360"
        v-loading="notesLoading"
        highlight-current-row
        @row-click="(row) => (pickedNote = row)"
        style="width: 100%"
      >
        <el-table-column prop="folder" label="目录" width="220" show-overflow-tooltip />
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
      </el-table>
      <template #footer>
        <el-button @click="notePickerVisible = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="!pickedNote"
          @click="confirmPickNote"
        >确定</el-button>
      </template>
    </el-dialog>

    <!-- 工单详情抽屉：DB 字段 + 关联知识笔记同屏联动 -->
    <el-drawer
      v-model="detailVisible"
      :title="'工单详情 · ' + (detailRow?.issue_no || '')"
      size="76%"
      destroy-on-close
    >
      <el-row :gutter="20">
        <el-col :span="10">
          <el-descriptions :column="1" border size="small" class="detail-desc">
            <el-descriptions-item label="编号">{{ detailRow?.issue_no }}</el-descriptions-item>
            <el-descriptions-item label="标题">{{ detailRow?.title }}</el-descriptions-item>
            <el-descriptions-item label="大类">
              {{ categoryMeta[detailRow?.category]?.label || detailRow?.category }}
            </el-descriptions-item>
            <el-descriptions-item label="子类">
              <el-tag :type="issueTypeTagType(detailRow?.issue_type)" size="small">
                {{ issueTypeText(detailRow?.issue_type) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <StatusBadge :value="detailRow?.status" :options="statusBadgeOptions" />
            </el-descriptions-item>
            <el-descriptions-item label="影响等级">{{ detailRow?.impact_level }}</el-descriptions-item>
            <el-descriptions-item label="责任人">
              <template v-if="detailRow?.handler">
                <el-tag
                  v-for="h in detailRow.handler.split(',')"
                  :key="h"
                  size="small"
                  class="handler-tag"
                >{{ h }}</el-tag>
              </template>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="关联系统">{{ detailRow?.related_system || '-' }}</el-descriptions-item>
            <el-descriptions-item label="发现时间">{{ formatDateTime(detailRow?.discovery_date) }}</el-descriptions-item>
            <el-descriptions-item label="解决时间">{{ formatDateTime(detailRow?.resolve_date) }}</el-descriptions-item>
            <el-descriptions-item label="情况说明">{{ detailRow?.situation_desc || '-' }}</el-descriptions-item>
            <el-descriptions-item label="根因分析">{{ detailRow?.root_cause || '-' }}</el-descriptions-item>
            <el-descriptions-item label="解决方案">{{ detailRow?.solution || '-' }}</el-descriptions-item>
            <el-descriptions-item label="关联需求">{{ detailRow?.related_req_id || '-' }}</el-descriptions-item>
            <el-descriptions-item label="关联工单">{{ detailRow?.related_ticket_no || '-' }}</el-descriptions-item>
            <el-descriptions-item label="知识笔记">
              {{ detailRow?.obsidian_path || '未关联' }}
            </el-descriptions-item>
          </el-descriptions>
        </el-col>
        <el-col :span="14">
          <div class="note-head">
            <span class="note-title">关联知识笔记</span>
            <div class="note-actions">
              <template v-if="!noteEditing && detailRow?.obsidian_path">
                <el-button size="small" @click="startNoteEdit">
                  <el-icon><Edit /></el-icon><span>编辑笔记</span>
                </el-button>
              </template>
              <template v-else-if="noteEditing">
                <el-button size="small" type="primary" :loading="noteSaving" @click="saveNoteEdit">保存</el-button>
                <el-button size="small" :disabled="noteSaving" @click="cancelNoteEdit">取消</el-button>
              </template>
            </div>
          </div>
          <div v-loading="noteLoading" class="note-body">
            <template v-if="!noteEditing">
              <MarkdownRender v-if="noteContent" :content="noteContent" />
              <el-empty v-else-if="detailRow?.obsidian_path" description="笔记读取失败或为空" />
              <el-empty v-else description="未关联知识笔记，可在编辑中关联" />
            </template>
            <el-input
              v-else
              v-model="noteEditContent"
              type="textarea"
              class="note-edit"
              resize="none"
            />
          </div>
        </el-col>
      </el-row>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import DataTable from '@/components/Common/DataTable.vue'
import StatusBadge from '@/components/Common/StatusBadge.vue'
import MarkdownRender from '@/components/Common/MarkdownRender.vue'
import { operationApi } from '@/api/operation'
import { obsidianApi } from '@/api/obsidian'
import { HANDLER_GROUPS } from '@/constants/staff'
import { formatDateTime } from '@/utils/format'

const route = useRoute()
const category = computed(() => route.meta.category || 'prod')
const title = computed(() => route.meta.title || '工单管理')

const categoryMeta = {
  bug: { prefix: 'BUG', color: 'danger', label: 'BUG管理' },
  data: { prefix: 'DATA', color: 'warning', label: '数据异常管理' },
  prod: { prefix: 'PROD', color: 'primary', label: '生产问题分析' },
  task: { prefix: 'TASK', color: 'success', label: '临时交办任务' },
  complaint: { prefix: 'COMP', color: 'danger', label: '热点投诉' },
}
const categoryColor = computed(() => categoryMeta[category.value]?.color || 'info')

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
  handler: '',
})

const issueTypeOptions = [
  { value: 'bug', label: 'BUG' },
  { value: 'data_abnormal', label: '数据异常' },
  { value: 'topic_analysis', label: '专题分析' },
  { value: 'spot_event', label: '投点事件' },
  { value: 'temp_task', label: '临时任务' },
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
    bug: 'danger',
    data_abnormal: 'warning',
    topic_analysis: 'primary',
    spot_event: 'info',
    temp_task: 'success',
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
  category: 'prod',
  issue_type: 'other',
  status: 'pending',
  source: 'manual',
  discovery_date: '',
  resolve_date: '',
  handler: [],
  situation_desc: '',
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
  issue_no: [{ required: true, message: '请输入工单编号', trigger: 'blur' }],
  title: [{ required: true, message: '请输入工单标题', trigger: 'blur' }],
  issue_type: [{ required: true, message: '请选择子类', trigger: 'change' }],
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
  closed_loop_rate: 0,
  by_type: [],
})

const loadData = async () => {
  loading.value = true
  try {
    const res = await operationApi.listIssues({
      ...queryForm,
      category: category.value,
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
    const res = await operationApi.getStats(category.value)
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
  queryForm.handler = ''
  pagination.page = 1
  loadData()
}

const handleAdd = () => {
  isEdit.value = false
  Object.assign(form, { ...defaultForm, category: category.value, issue_no: generateIssueNo() })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  Object.assign(form, JSON.parse(JSON.stringify(row)))
  form.handler = (row.handler || '').split(',').filter(Boolean)
  dialogVisible.value = true
}

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定删除工单「${row.title}」吗？`, '提示', {
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

    const payload = { ...form, category: category.value }
    payload.handler = Array.isArray(payload.handler) ? payload.handler.join(',') : payload.handler
    delete payload.id
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
  const prefix = categoryMeta[category.value]?.prefix || 'WO'
  const date = new Date().toISOString().slice(0, 10).replace(/-/g, '')
  const random = Math.floor(Math.random() * 1000).toString().padStart(3, '0')
  return `${prefix}-${date}-${random}`
}

// ---- 关联笔记选择 ----
const notePickerVisible = ref(false)
const notesList = ref([])
const notesLoading = ref(false)
const noteSearch = ref('')
const pickedNote = ref(null)

const filteredNotes = computed(() => {
  const kw = noteSearch.value.trim().toLowerCase()
  if (!kw) return notesList.value
  return notesList.value.filter((n) => (n.title || '').toLowerCase().includes(kw))
})

const openNotePicker = async () => {
  pickedNote.value = null
  notePickerVisible.value = true
  notesLoading.value = true
  try {
    const res = await obsidianApi.listNotes()
    notesList.value = res || []
  } catch (e) {
    ElMessage.error('加载笔记列表失败')
    notesList.value = []
  } finally {
    notesLoading.value = false
  }
}

const confirmPickNote = () => {
  if (!pickedNote.value) return
  form.obsidian_path = pickedNote.value.path
  notePickerVisible.value = false
}

// ---- 工单详情抽屉 + 笔记联动 ----
const detailVisible = ref(false)
const detailRow = ref(null)
const noteContent = ref('')
const noteLoading = ref(false)
const noteEditing = ref(false)
const noteEditContent = ref('')
const noteSaving = ref(false)

const openDetail = (row) => {
  detailRow.value = row
  noteContent.value = ''
  noteEditing.value = false
  detailVisible.value = true
  if (row.obsidian_path) {
    loadNote(row.obsidian_path)
  }
}

const loadNote = async (path) => {
  noteLoading.value = true
  try {
    const res = await obsidianApi.getNoteContent(path)
    noteContent.value = res.content || ''
  } catch (e) {
    noteContent.value = ''
    ElMessage.error('笔记读取失败')
  } finally {
    noteLoading.value = false
  }
}

const startNoteEdit = () => {
  noteEditContent.value = noteContent.value
  noteEditing.value = true
}

const cancelNoteEdit = () => {
  noteEditing.value = false
  noteEditContent.value = ''
}

const saveNoteEdit = async () => {
  if (!detailRow.value?.obsidian_path) return
  try {
    await ElMessageBox.confirm(
      '保存后将直接覆盖 Obsidian 中的源文件，且不可撤销。确认保存？',
      '保存确认',
      { type: 'warning', confirmButtonText: '确认保存', cancelButtonText: '再想想' }
    )
  } catch {
    return
  }
  noteSaving.value = true
  try {
    await obsidianApi.updateNoteContent(detailRow.value.obsidian_path, noteEditContent.value)
    noteContent.value = noteEditContent.value
    noteEditing.value = false
    ElMessage.success('已保存，Obsidian 文件已更新')
  } catch (e) {
    ElMessage.error('保存失败：' + (e?.message || '未知错误'))
  } finally {
    noteSaving.value = false
  }
}

// 切换分类（同一组件复用不同路由）时重置数据
watch(
  () => route.meta.category,
  () => {
    pagination.page = 1
    handleReset()
    loadStats()
  }
)

onMounted(() => {
  loadData()
  loadStats()
})
</script>

<style scoped>
.work-order-view {
  padding: 20px;
}

.page-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-item {
  text-align: center;
  padding: 10px 0;
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: #303133;
}

.stat-label {
  font-size: 13px;
  color: #606266;
  margin-top: 6px;
}

.search-card {
  margin-bottom: 16px;
}

.toolbar {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.hint {
  font-size: 12px;
  color: #909399;
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

.status-closed .stat-value {
  color: #909399;
}

.status-overdue .stat-value {
  color: #f56c6c;
}

.status-loop .stat-value {
  color: #409eff;
}

.handler-tag {
  margin: 0 4px 4px 0;
}

.note-picker {
  display: flex;
  align-items: center;
  gap: 8px;
}

.detail-desc {
  margin-bottom: 12px;
}

.note-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.note-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.note-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.note-body {
  min-height: 200px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 20px 24px;
}

.note-edit {
  width: 100%;
  height: 60vh;
}

.note-edit :deep(textarea) {
  height: 100%;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #303133;
  white-space: pre;
  overflow: auto;
}
</style>
