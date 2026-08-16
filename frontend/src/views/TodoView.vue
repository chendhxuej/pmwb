<template>
  <div class="todo-view">
    <h2 class="page-title">待办中心</h2>

    <!-- 统计磁贴：仿运营 cat-tile 风格，7 项差异化配色 -->
    <div class="stats-grid">
      <div
        v-for="t in statTiles"
        :key="t.key"
        class="stat-tile"
        :class="['tone-' + t.tone, { clickable: t.clickable, active: t.active }]"
        @click="t.clickable && onStatClick(t.key)"
      >
        <div class="stat-tile-top">
          <span class="stat-name">{{ t.label }}</span>
          <span class="stat-ico" :style="{ background: t.bg, color: t.fg }">
            <el-icon><component :is="t.icon" /></el-icon>
          </span>
        </div>
        <div class="stat-count">{{ t.count }}</div>
        <div class="stat-count-sub">{{ t.sub }}</div>
        <div class="stat-rate" v-if="t.rate !== undefined">
          <span>{{ t.rateLabel || '完成率' }}</span>
          <span class="stat-rate-val">{{ t.rate }}%</span>
        </div>
        <div class="stat-bar" v-if="t.rate !== undefined">
          <div class="stat-bar-fill" :style="{ width: t.rate + '%', background: t.fg }"></div>
        </div>
      </div>
    </div>

    <!-- 紧凑检索栏 -->
    <div class="search-bar">
      <div class="search-bar-fields">
        <div class="search-field">
          <el-icon class="search-prefix"><Search /></el-icon>
          <EnlargeInput
            v-model="queryForm.keyword"
            placeholder="标题 / 内容 / 工单号"
            clearable
            size="default"
          />
        </div>
        <el-select v-model="queryForm.category" placeholder="全部分类" clearable size="default" class="search-select">
          <el-option v-for="i in categoryOptions" :key="i.value" :label="i.label" :value="i.value" />
        </el-select>
        <el-select v-model="queryForm.status" placeholder="全部状态" clearable size="default" class="search-select">
          <el-option v-for="i in statusOptions" :key="i.value" :label="i.label" :value="i.value" />
        </el-select>
        <el-select v-model="queryForm.priority" placeholder="全部优先级" clearable size="default" class="search-select">
          <el-option v-for="i in priorityOptions" :key="i.value" :label="i.label" :value="i.value" />
        </el-select>
      </div>
      <div class="search-bar-actions">
        <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
        <el-button :icon="RefreshLeft" @click="handleReset">重置</el-button>
        <el-button type="primary" plain :icon="Plus" @click="handleAdd">新增待办</el-button>
      </div>
    </div>

    <!-- 待办列表 -->
    <DataTable
      :data="displayedData"
      :total="tableTotal"
      :loading="loading"
      v-model:page="pagination.page"
      v-model:pageSize="pagination.page_size"
      row-key="id"
      :row-class-name="rowClassName"
      @change="loadData"
      @edit="handleEdit"
      @delete="handleDelete"
    >
      <template #columns>
        <el-table-column prop="title" label="待办标题" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="title-cell">
              <span
                class="todo-title"
                :class="{ linked: row.related_id, 'done-text': row.status === 'done' }"
                :title="row.related_id ? '点击查看关联工单详情' : ''"
                @click="row.related_id && openLinked(row)"
              >{{ row.title }}</span>
              <el-tag
                v-if="row.related_id"
                size="small"
                type="info"
                effect="plain"
                class="related-chip"
              >
                <el-icon><Link /></el-icon><span>{{ relatedTypeText(row.related_type) }}</span>
              </el-tag>
              <span v-if="row.repeat_type && row.repeat_type !== 'none'" class="repeat-chip">重复</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="90">
          <template #default="{ row }">
            <span class="dim-text">{{ categoryText(row.category) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="80">
          <template #default="{ row }">
            <span :class="['priority-chip', 'pri-' + (row.priority || 'P3')]">{{ row.priority || 'P3' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="140">
          <template #default="{ row }">
            <el-popover
              placement="bottom"
              :width="220"
              trigger="click"
              v-model:visible="statusPopoverVisible[row.id]"
            >
              <template #reference>
                <span class="status-cell">
                  <StatusBadge
                    module="todo"
                    :value="row.status"
                    :sensitive="row.is_overdue"
                  />
                  <el-icon class="status-edit-tip"><ArrowDown /></el-icon>
                </span>
              </template>
              <div class="status-switch">
                <div class="status-switch-title">切换状态</div>
                <div class="status-switch-grid">
                  <button
                    v-for="s in statusOptions"
                    :key="s.value"
                    class="status-switch-btn"
                    :class="{ active: row.status === s.value }"
                    :disabled="statusLoadingMap[row.id]"
                    @click="changeStatus(row, s.value)"
                  >
                    <StatusBadge module="todo" :value="s.value" />
                    <span class="status-switch-check" v-if="row.status === s.value">
                      <el-icon><Check /></el-icon>
                    </span>
                  </button>
                </div>
              </div>
            </el-popover>
          </template>
        </el-table-column>
        <el-table-column prop="due_date" label="计划完成" width="130">
          <template #default="{ row }">
            <span :class="['due-cell', 'due-' + dueTone(row)]">
              {{ row.due_date ? String(row.due_date).slice(0, 10) : '—' }}
              <span class="due-flag" v-if="dueFlagText(row)">{{ dueFlagText(row) }}</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="related_id" label="关联" width="100">
          <template #default="{ row }">
            <span v-if="row.related_id" class="link-id" :title="row.related_id">{{ row.related_id }}</span>
            <span v-else class="dim-text">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="80">
          <template #default="{ row }">
            <span class="source-tag" :class="'src-' + (row.source || 'manual')">
              {{ row.source || 'manual' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="110">
          <template #default="{ row }">
            <span class="dim-text">{{ row.created_at ? String(row.created_at).slice(0, 10) : '—' }}</span>
          </template>
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
            <el-descriptions-item label="工单标题" :span="2">{{ woDetail.title || '—' }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <StatusBadge module="operation" :value="woDetail.status" :sensitive="woDetail.is_overdue" />
            </el-descriptions-item>
            <el-descriptions-item label="优先级/影响">{{ woDetail.impact_level || '—' }}</el-descriptions-item>
            <el-descriptions-item label="责任人">{{ woDetail.handler || '—' }}</el-descriptions-item>
            <el-descriptions-item label="关联系统">{{ woDetail.related_system || '—' }}</el-descriptions-item>
            <el-descriptions-item label="发现时间">{{ fmtDate(woDetail.discovery_date) }}</el-descriptions-item>
            <el-descriptions-item label="解决时间">{{ fmtDate(woDetail.resolve_date) }}</el-descriptions-item>
            <el-descriptions-item label="计划完成">{{ fmtDate(woDetail.go_live_date) }}</el-descriptions-item>
            <el-descriptions-item label="逾期">
              <StatusBadge v-if="woDetail.is_overdue" module="operation" value="overdue" :sensitive="true" />
              <span v-else class="dim-text">正常</span>
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
import {
  Search,
  Plus,
  RefreshLeft,
  ArrowDown,
  Check,
  Link,
  Warning,
  Calendar,
  List,
  PieChart,
  Tickets,
  Document,
} from '@element-plus/icons-vue'
import DataTable from '@/components/Common/DataTable.vue'
import StatusBadge from '@/components/Common/StatusBadge.vue'
import EnlargeInput from '@/components/Common/EnlargeInput.vue'
import { todoApi } from '@/api/todo'
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

// 点击 stat tile 是否筛选/跳转
const filterKey = ref('')

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
})

// ────────────────────────────────────────────────
// 6 张统计磁贴（仿运营 cat-tile 风格，差异化色彩+图标）
// ────────────────────────────────────────────────
const statTiles = computed(() => {
  const t = stats
  const total = t.total || 0
  const doneRate = total ? +((t.done * 100) / total).toFixed(1) : 0
  return [
    {
      key: 'overdue',
      label: '已超期',
      count: t.overdue,
      sub: '需立即处理',
      tone: 'danger',
      bg: '#fff1f0',
      fg: '#f5222d',
      icon: Warning,
      clickable: true,
      active: filterKey.value === 'overdue',
    },
    {
      key: 'today',
      label: '今日截止',
      count: t.today,
      sub: '当日交付',
      tone: 'warning',
      bg: '#fef7ed',
      fg: '#d98a1f',
      icon: Calendar,
      clickable: true,
      active: filterKey.value === 'today',
    },
    {
      key: 'total',
      label: '待办总数',
      count: t.total,
      sub: `完成率 ${doneRate}%`,
      tone: 'neutral',
      bg: '#eef2f7',
      fg: '#64748b',
      icon: PieChart,
      rate: doneRate,
      rateLabel: '完成率',
      clickable: false,
    },
    {
      key: 'todo',
      label: '未开始',
      count: t.todo,
      sub: '等待启动',
      tone: 'info',
      bg: '#eff6ff',
      fg: '#3b82f6',
      icon: Document,
      clickable: true,
      active: filterKey.value === 'todo',
    },
    {
      key: 'in_progress',
      label: '进行中',
      count: t.in_progress,
      sub: '推进中',
      tone: 'primary',
      bg: '#ecf5ff',
      fg: '#409eff',
      icon: Tickets,
      clickable: true,
      active: filterKey.value === 'in_progress',
    },
    {
      key: 'done',
      label: '已完成',
      count: t.done,
      sub: '已交付',
      tone: 'success',
      bg: '#ecfdf3',
      fg: '#0f9d6b',
      icon: Check,
      clickable: true,
      active: filterKey.value === 'done',
    },
  ]
})

// ────────────────────────────────────────────────
// 计划完成日期差异化（4 档语义色）
// ────────────────────────────────────────────────
function todayStr() {
  const d = new Date()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

function dueTone(row) {
  if (row.status === 'done' || row.status === 'cancelled') return 'none'
  if (!row.due_date) return 'none'
  const today = todayStr()
  if (row.due_date < today) return 'overdue'
  if (row.due_date === today) return 'today'
  // 3 天内
  const due = new Date(row.due_date + 'T00:00:00')
  const now = new Date(today + 'T00:00:00')
  const diff = Math.round((due - now) / (1000 * 60 * 60 * 24))
  if (diff <= 3) return 'soon'
  return 'normal'
}

function dueFlagText(row) {
  const t = dueTone(row)
  if (t === 'overdue') return '已超期'
  if (t === 'today') return '今日'
  if (t === 'soon') return '临近'
  return ''
}

// ────────────────────────────────────────────────
// 行的 className：逾期 / 已完成 整行差异化
// ────────────────────────────────────────────────
function rowClassName({ row }) {
  const t = dueTone(row)
  const flags = []
  if (row.is_overdue || t === 'overdue') flags.push('row-overdue')
  if (row.status === 'done') flags.push('row-done')
  return flags.join(' ')
}

// ────────────────────────────────────────────────
// 客户端 filter（overdue/today 视图层过滤，不依赖后端参数）
// ────────────────────────────────────────────────
const displayedData = computed(() => {
  if (filterKey.value === 'overdue') {
    return tableData.value.filter((r) => r.is_overdue || (r.due_date && r.due_date < todayStr() && r.status !== 'done' && r.status !== 'cancelled'))
  }
  if (filterKey.value === 'today') {
    return tableData.value.filter((r) => r.due_date === todayStr() && r.status !== 'done' && r.status !== 'cancelled')
  }
  return tableData.value
})

// 客户端过滤（overdue/today）时，分页总数应与可见行一致，避免“显示 N 条却 N 页”的错位
const tableTotal = computed(() => {
  if (filterKey.value === 'overdue' || filterKey.value === 'today') {
    return displayedData.value.length
  }
  return pagination.total
})

// ────────────────────────────────────────────────
// 数据加载
// ────────────────────────────────────────────────
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

// 点击 stat tile：与列表筛选联动
// total 仅展示；overdue/today 在前端用 is_overdue / due_date 客户端过滤（避免依赖后端参数）；
// 其它状态按 status 筛选。
function onStatClick(key) {
  if (key === 'total') return
  filterKey.value = filterKey.value === key ? '' : key
  if (filterKey.value === 'overdue' || filterKey.value === 'today') {
    queryForm.status = ''
  } else {
    queryForm.status = filterKey.value
  }
  pagination.page = 1
  loadData()
}

// ────────────────────────────────────────────────
// 状态切换（通过 popover 按钮组触发，避免行内 el-select 视觉扁平）
// ────────────────────────────────────────────────
const statusPopoverVisible = ref({})
const statusLoadingMap = ref({})
async function changeStatus(row, newStatus) {
  if (!row || row.status === newStatus) {
    statusPopoverVisible.value[row.id] = false
    return
  }
  statusLoadingMap.value[row.id] = true
  try {
    await todoApi.updateTodoStatus(row.id, newStatus)
    ElMessage.success('状态已更新')
    statusPopoverVisible.value[row.id] = false
    await loadData()
    await loadStats()
  } catch (error) {
    ElMessage.error('状态更新失败')
  } finally {
    delete statusLoadingMap.value[row.id]
  }
}

// 点击待办标题：关联工单直接在抽屉内展开详情（不跳转）
const woDrawerVisible = ref(false)
const woDetail = ref(null)
const woLoading = ref(false)

const fmtDate = (v) => (v ? String(v).slice(0, 10) : '—')

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

const openLinked = (row) => {
  if (!row.related_id) {
    ElMessage.info('该待办未关联工单')
    return
  }
  if (row.related_type === 'operation' || row.related_type === 'ticket') {
    openWoDetail(row.related_id)
    return
  }
  const modMap = { requirement: '/requirement', meeting: '/meeting' }
  router.push(modMap[row.related_type] || '/operation')
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
  filterKey.value = ''
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
  applyDeepLink()
})
</script>

<style scoped>
.todo-view {
  padding: 20px;
}

.page-title {
  margin: 0 0 18px;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

/* ───── 统计磁贴（仿运营 cat-tile：图标 chip + 大数字 + 副文字） ───── */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}
.stat-tile {
  background: var(--surface);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 16px 18px;
  cursor: default;
  transition: transform var(--transition-fast), box-shadow var(--transition-fast), border-color var(--transition-fast);
  position: relative;
  overflow: hidden;
  min-width: 0;
}
.stat-tile.clickable { cursor: pointer; }
.stat-tile.clickable:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-elevated);
  border-color: var(--accent);
}
.stat-tile.clickable:active {
  transform: translateY(0);
}
.stat-tile.active {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.stat-tile-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.stat-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}
.stat-ico {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}
.stat-count {
  font-size: 28px;
  font-weight: 800;
  font-family: var(--font-mono);
  color: var(--text-primary);
  line-height: 1;
}
.stat-count-sub {
  font-size: 11.5px;
  color: var(--text-muted);
  margin-top: 4px;
}
.stat-rate {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
  font-size: 11.5px;
  color: var(--text-secondary);
}
.stat-rate-val {
  font-weight: 700;
  font-family: var(--font-mono);
}
.stat-bar {
  height: 5px;
  border-radius: 5px;
  background: #eef2f7;
  margin-top: 5px;
  overflow: hidden;
}
.stat-bar-fill {
  height: 100%;
  border-radius: 5px;
  transition: width var(--transition-fast);
}

/* ───── 紧凑检索栏 ───── */
.search-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  margin-bottom: 16px;
  background: var(--surface);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  flex-wrap: wrap;
}
.search-bar-fields {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
  flex-wrap: wrap;
}
.search-field {
  position: relative;
  flex: 1;
  min-width: 200px;
  max-width: 320px;
  display: flex;
  align-items: center;
}
.search-prefix {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  z-index: 2;
  pointer-events: none;
  font-size: 14px;
}
.search-field :deep(.el-input__wrapper) {
  padding-left: 34px;
}
.search-select {
  width: 140px;
}
.search-bar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

/* ───── 表格列样式 ───── */
.title-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.todo-title {
  color: var(--text-primary);
  font-weight: 600;
  font-size: 13.5px;
  cursor: default;
  transition: color var(--transition-fast);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 0 1 auto;
  min-width: 0;
}
.todo-title.linked {
  cursor: pointer;
}
.todo-title.linked:hover {
  color: var(--accent);
  text-decoration: underline;
}
.todo-title.done-text {
  text-decoration: line-through;
  color: #a8abb2;
}
.related-chip {
  flex-shrink: 0;
}
.related-chip :deep(.el-icon) {
  margin-right: 3px;
  vertical-align: -1px;
}
.repeat-chip {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  font-size: 10px;
  font-weight: 500;
  border-radius: 4px;
  background: var(--warning-soft);
  color: var(--warning);
  flex-shrink: 0;
}

/* 优先级小色块 */
.priority-chip {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  font-family: var(--font-mono);
  letter-spacing: 0.5px;
}
.priority-chip.pri-P0 { background: #fff1f0; color: #f5222d; }
.priority-chip.pri-P1 { background: #fdf6ec; color: #d98a1f; }
.priority-chip.pri-P2 { background: #ecf5ff; color: #409eff; }
.priority-chip.pri-P3 { background: #f4f4f5; color: #909399; }

/* 状态列（点击徽标 → popover 切换） */
.status-cell {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 8px;
  transition: background var(--transition-fast);
}
.status-cell:hover {
  background: var(--border-subtle);
}
.status-edit-tip {
  color: var(--text-muted);
  font-size: 10px;
}
.status-switch {
  padding: 4px;
}
.status-switch-title {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 6px;
  padding: 0 4px;
}
.status-switch-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
}
.status-switch-btn {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
  padding: 6px 8px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}
.status-switch-btn:hover {
  background: var(--accent-soft);
  border-color: var(--accent);
}
.status-switch-btn.active {
  background: var(--accent-soft);
  border-color: var(--accent);
  color: var(--accent);
  font-weight: 600;
}
.status-switch-check {
  color: var(--accent);
  display: inline-flex;
  align-items: center;
}

/* 计划完成日期：4 档语义色 */
.due-cell {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-family: var(--font-mono);
  font-size: 12.5px;
}
.due-cell.due-overdue {
  color: #f5222d;
  font-weight: 700;
}
.due-cell.due-today {
  color: var(--warning);
  font-weight: 700;
}
.due-cell.due-soon {
  color: var(--warning);
}
.due-cell.due-normal {
  color: var(--text-primary);
}
.due-flag {
  display: inline-flex;
  align-items: center;
  padding: 1px 5px;
  font-size: 10px;
  font-weight: 600;
  border-radius: 4px;
  background: currentColor;
  color: #fff !important;
  font-family: var(--font-mono);
}
.due-flag::before { content: ''; }

/* 来源标签 */
.source-tag {
  display: inline-block;
  padding: 1px 8px;
  font-size: 11px;
  font-weight: 500;
  border-radius: 6px;
  background: var(--border-subtle);
  color: var(--text-secondary);
  font-family: var(--font-mono);
}
.source-tag.src-meeting {
  background: var(--accent-soft);
  color: var(--accent);
}
.source-tag.src-manual {
  background: var(--border-subtle);
  color: var(--text-secondary);
}

/* 辅助文本 */
.dim-text {
  color: var(--text-secondary);
  font-size: 12.5px;
}
.link-id {
  font-family: var(--font-mono);
  font-size: 12.5px;
  color: var(--accent);
}

/* 行差异化（逾期 / 已完成） */
:deep(.row-overdue) {
  background: #fff1f0 !important;
}
:deep(.row-overdue:hover) > td {
  background: #ffecea !important;
}
:deep(.row-done) {
  opacity: 0.85;
}

/* 关联工单详情抽屉 */
.wo-drawer-body { padding: 4px 2px; }
.wo-sec { margin-top: 16px; }
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

/* 响应式 */
@media (max-width: 1400px) {
  .stats-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
}
@media (max-width: 960px) {
  .stats-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
