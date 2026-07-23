<template>
  <div class="operation-overview">
    <div class="bento-grid">
      <!-- 总览：甜甜圈 + 4 项指标 -->
      <div class="card ops-summary">
        <div class="ops-donut">
          <svg width="104" height="104" viewBox="0 0 104 104">
            <circle cx="52" cy="52" r="42" fill="none" stroke="#eef2f7" stroke-width="11" />
            <circle
              cx="52" cy="52" r="42" fill="none" stroke="#2f6fed" stroke-width="11"
              stroke-linecap="round" stroke-dasharray="263.9"
              :stroke-dashoffset="donutOffset"
              transform="rotate(-90 52 52)"
            />
          </svg>
          <div class="ops-donut-center">
            <div class="ops-donut-val">{{ overall.closed_loop_rate || 0 }}%</div>
            <div class="ops-donut-label">整体闭环率</div>
          </div>
        </div>
        <div class="ops-summary-divider"></div>
        <div class="ops-summary-meta">
          <div class="ops-meta-item">
            <div class="ops-meta-num">{{ overall.total }}</div>
            <div class="ops-meta-lab">工单总量</div>
          </div>
          <div class="ops-meta-item">
            <div class="ops-meta-num">{{ overall.processing }}</div>
            <div class="ops-meta-lab">进行中</div>
          </div>
          <div class="ops-meta-item">
            <div class="ops-meta-num" :class="{ warn: overall.overdue > 0 }">{{ overall.overdue }}</div>
            <div class="ops-meta-lab">已逾期</div>
          </div>
          <div class="ops-meta-item">
            <div class="ops-meta-num">{{ closedCount }}</div>
            <div class="ops-meta-lab">已闭环</div>
          </div>
        </div>
      </div>

      <!-- 5 大类统计磁贴（点击筛选下方列表） -->
      <div class="cat-tiles">
        <div
          v-for="t in tiles"
          :key="t.key"
          class="card cat-tile"
          :class="{ active: selectedCategory === t.key }"
          @click="selectCategory(t.key)"
        >
          <div class="cat-tile-top">
            <span class="cat-name">{{ t.label }}</span>
            <span class="cat-ico" :style="{ background: t.bg, color: t.fg }">
              <el-icon><component :is="t.icon" /></el-icon>
            </span>
          </div>
          <div class="cat-count">{{ t.count }}</div>
          <div class="cat-count-sub">{{ t.sub }}</div>
          <div class="cat-rate">
            <span>闭环率</span>
            <span class="cat-rate-val">{{ t.rate }}%</span>
          </div>
          <div class="cat-bar">
            <div class="cat-bar-fill" :style="{ width: t.rate + '%', background: t.fg }"></div>
          </div>
        </div>
      </div>

      <!-- 工单列表 -->
      <div class="card ops-list-col">
        <div class="card-header" style="padding:18px 20px 0">
          <div>
            <div class="card-title-styled">工单列表</div>
            <div class="card-sub-styled">{{ currentLabel }} · {{ filteredList.length }} 条</div>
          </div>
          <el-button type="primary" size="small" @click="openEntry">
            <el-icon><Plus /></el-icon><span>录入工单</span>
          </el-button>
        </div>
        <div class="ops-tabs">
          <div
            v-for="t in tiles"
            :key="t.key"
            class="ops-tab"
            :class="{ active: selectedCategory === t.key }"
            @click="selectCategory(t.key)"
          >{{ t.label }}<span class="cnt">{{ t.count }}</span></div>
        </div>
        <div class="list-toolbar">
          <el-input
            v-model="keyword"
            placeholder="搜索工单号 / 标题 / 责任人"
            clearable
            size="small"
            style="width:260px"
          />
        </div>
        <el-table :data="pagedList" v-loading="loading" class="ops-table" @row-click="onRowClick">
          <el-table-column prop="issue_no" label="工单号" width="160" />
          <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="iss-title">{{ row.title }}</span>
            </template>
          </el-table-column>
          <el-table-column label="子类" width="120">
            <template #default="{ row }">{{ issueTypeLabel(row.category, row.issue_type) }}</template>
          </el-table-column>
          <el-table-column label="责任人" width="160">
            <template #default="{ row }">
              <template v-if="row.handler">
                <el-tag v-for="h in row.handler.split(',').filter(Boolean)" :key="h" size="small" class="handler-tag">{{ h }}</el-tag>
              </template>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <StatusBadge :value="row.status" :options="statusBadgeOptions" />
            </template>
          </el-table-column>
          <el-table-column label="逾期" width="80">
            <template #default="{ row }">
              <el-tag v-if="row.is_overdue" type="danger" size="small">逾期</el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="创建" width="120">
            <template #default="{ row }">{{ formatDate(row.created_at, 'MM-DD') }}</template>
          </el-table-column>
          <el-table-column label="操作" width="190" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click.stop="openDetail(row)">详情</el-button>
              <el-dropdown size="small" trigger="click" @command="(cmd) => changeStatus(row, cmd)">
                <el-button link type="primary" :loading="statusLoadingMap[row.id]">
                  改状态<el-icon class="el-icon--right"><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item
                      v-for="s in STATUS_OPTIONS"
                      :key="s.key"
                      :command="s.key"
                      :disabled="row.status === s.key"
                    >
                      <span :class="['status-dot', 'dot-' + s.key]"></span>{{ s.label }}
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <el-button link type="warning" @click.stop="openEmailFromRow(row)">督办</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="list-foot" v-if="filteredList.length > pageSize">
          <el-pagination
            v-model:current-page="page"
            :page-size="pageSize"
            :total="filteredList.length"
            layout="prev, pager, next"
            small
            background
          />
        </div>
      </div>

      <!-- 侧栏：知识沉淀 + 超期预警 -->
      <div class="ops-side-col">
        <div class="card">
          <div class="card-header" style="padding:18px 18px 0">
            <div>
              <div class="card-title-styled">知识沉淀</div>
              <div class="card-sub-styled">联动 Obsidian · 业务运营库</div>
            </div>
          </div>
          <div class="know-list">
            <div
              v-for="n in sideNotes"
              :key="n.path"
              class="know-item"
              @click="goNotes"
            >
              <div class="know-ico"><el-icon><Document /></el-icon></div>
              <div>
                <div class="know-name">{{ n.title }}</div>
                <div class="know-meta">{{ n.folder }}</div>
              </div>
            </div>
            <el-empty v-if="!sideNotes.length" description="暂无知识条目" :image-size="48" />
            <div class="know-more" @click="goNotes">查看全部知识沉淀 →</div>
          </div>
        </div>
        <div class="card">
          <div class="card-header" style="padding:18px 18px 0">
            <div>
              <div class="card-title-styled">超期预警</div>
              <div class="card-sub-styled">需优先介入</div>
            </div>
          </div>
          <div class="urgent-list">
            <div v-for="i in overdueList" :key="i.id" class="urgent-item" @click="openDetail(i)">
              <span class="urgent-dot"></span>
              <div class="urgent-text"><b>{{ i.issue_no }}</b> {{ i.title }}</div>
            </div>
            <el-empty v-if="!overdueList.length" description="当前无逾期工单" :image-size="48" />
          </div>
        </div>
      </div>
    </div>

    <!-- 录入工单弹层（总览入口，真实调用 createIssue） -->
    <el-dialog v-model="entryVisible" title="录入工单" width="640px" destroy-on-close>
      <el-form :model="entryForm" label-width="96px" :rules="entryRules" ref="entryRef">
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="工单类别" prop="category">
              <el-select v-model="entryForm.category" style="width:100%" @change="onEntryCatChange">
                <el-option v-for="c in CATEGORIES" :key="c.key" :label="c.label" :value="c.key" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="子类" prop="issue_type">
              <el-select v-model="entryForm.issue_type" style="width:100%">
                <el-option v-for="o in entryTypeOptions" :key="o.value" :label="o.label" :value="o.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="工单标题" prop="title">
          <el-input v-model="entryForm.title" placeholder="简要描述问题或任务" />
        </el-form-item>
        <el-form-item label="责任人" prop="handler">
          <el-select
            v-model="entryForm.handler"
            multiple
            filterable
            placeholder="可多选，逗号存储"
            style="width:100%"
          >
            <el-option-group v-for="g in HANDLER_GROUPS" :key="g.label" :label="g.label">
              <el-option v-for="o in g.options" :key="o.value" :label="o.label" :value="o.value" />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="优先级">
              <el-select v-model="entryForm.impact_level" style="width:100%">
                <el-option v-for="p in PRIORITY_OPTIONS" :key="p.value" :label="p.label" :value="p.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="期望完成">
              <el-date-picker v-model="entryForm.due" type="date" placeholder="选填" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="情况说明" prop="situation_desc">
          <el-input v-model="entryForm.situation_desc" type="textarea" :rows="3" placeholder="现象、影响范围、初步定位…" />
        </el-form-item>
        <el-form-item label="关联知识库">
          <el-select v-model="entryForm.obsidian_path" filterable placeholder="不关联" clearable style="width:100%">
            <el-option v-for="n in noteOptions" :key="n.path" :label="n.title" :value="n.path" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="entryVisible = false">取消</el-button>
        <el-button type="primary" :loading="entryLoading" @click="submitEntry">提交工单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Document, Warning, DataLine, Cpu, List, ChatDotRound, ArrowDown } from '@element-plus/icons-vue'
import StatusBadge from '@/components/Common/StatusBadge.vue'
import { operationApi } from '@/api/operation'
import { obsidianApi } from '@/api/obsidian'
import { HANDLER_GROUPS } from '@/constants/staff'
import { formatDate } from '@/utils/format'

const router = useRouter()

const CATEGORIES = [
  { key: 'bug', label: 'BUG 管理', icon: Warning, bg: '#fef2f2', fg: '#d9544d' },
  { key: 'data', label: '数据异常管理', icon: DataLine, bg: '#eff6ff', fg: '#3b82f6' },
  { key: 'prod', label: '生产问题分析', icon: Cpu, bg: '#fef7ed', fg: '#d98a1f' },
  { key: 'task', label: '临时交办任务', icon: List, bg: '#f3e8ff', fg: '#7c3aed' },
  { key: 'complaint', label: '热点投诉', icon: ChatDotRound, bg: '#ecfdf3', fg: '#0f9d6b' },
]

const TYPE_BY_CAT = {
  bug: [{ value: 'bug', label: '系统缺陷' }, { value: 'other', label: '其他' }],
  data: [{ value: 'data_abnormal', label: '数据异常' }, { value: 'other', label: '其他' }],
  prod: [{ value: 'topic_analysis', label: '专题分析' }, { value: 'spot_event', label: '投点事件' }, { value: 'other', label: '其他' }],
  task: [{ value: 'temp_task', label: '临时任务' }, { value: 'other', label: '其他' }],
  complaint: [{ value: 'spot_event', label: '投点事件' }, { value: 'other', label: '其他' }],
}

const PRIORITY_OPTIONS = [
  { value: 'P0', label: '严重' },
  { value: 'P1', label: '高' },
  { value: 'P2', label: '中' },
  { value: 'P3', label: '低' },
]

const statusBadgeOptions = {
  pending: { label: '待处理', type: 'danger' },
  processing: { label: '处理中', type: 'warning' },
  verify: { label: '验证中', type: 'primary' },
  resolved: { label: '已解决', type: 'success' },
  closed: { label: '已关闭', type: 'info' },
  suspended: { label: '已挂起', type: 'info' },
}

const STATUS_OPTIONS = [
  { key: 'pending', label: '待处理' },
  { key: 'processing', label: '处理中' },
  { key: 'verify', label: '验证中' },
  { key: 'resolved', label: '已解决' },
  { key: 'closed', label: '已关闭' },
  { key: 'suspended', label: '已挂起' },
]

const overall = reactive({
  total: 0, processing: 0, resolved: 0, closed: 0, overdue: 0, closed_loop_rate: 0,
})
const closedCount = computed(() => (overall.resolved || 0) + (overall.closed || 0))

const donutOffset = computed(() => {
  const C = 263.9
  const rate = Number(overall.closed_loop_rate) || 0
  return C * (1 - rate / 100)
})

const allIssues = ref([])
const loading = ref(false)
const keyword = ref('')
const selectedCategory = ref('all')
const page = ref(1)
const pageSize = 20

const issueTypeLabel = (category, type) => {
  const opt = (TYPE_BY_CAT[category] || []).find((o) => o.value === type)
  return opt ? opt.label : type
}

const catStats = computed(() => {
  const map = {}
  for (const c of CATEGORIES) {
    const items = allIssues.value.filter((i) => i.category === c.key)
    const total = items.length
    const closed = items.filter((i) => i.status === 'resolved' || i.status === 'closed').length
    map[c.key] = { total, rate: total ? +(closed * 100 / total).toFixed(1) : 0 }
  }
  return map
})

const tiles = computed(() => {
  const all = [
    {
      key: 'all', label: '全部', icon: Document, bg: '#eef2f7', fg: '#64748b',
      count: allIssues.value.length,
      sub: '全部工单',
      rate: overall.closed_loop_rate || 0,
    },
  ]
  for (const c of CATEGORIES) {
    const s = catStats.value[c.key] || { total: 0, rate: 0 }
    all.push({ ...c, count: s.total, sub: `进行中 ${allIssues.value.filter((i) => i.category === c.key && i.status === 'processing').length}`, rate: s.rate })
  }
  return all
})

const currentLabel = computed(() => tiles.value.find((t) => t.key === selectedCategory.value)?.label || '全部')

const filteredList = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return allIssues.value.filter((i) => {
    if (selectedCategory.value !== 'all' && i.category !== selectedCategory.value) return false
    if (kw && !(`${i.issue_no} ${i.title} ${i.handler || ''}`.toLowerCase().includes(kw))) return false
    return true
  })
})

const pagedList = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredList.value.slice(start, start + pageSize)
})

const sideNotes = ref([])
const overdueList = computed(() => allIssues.value.filter((i) => i.is_overdue).slice(0, 5))

const loadStats = async () => {
  try {
    const res = await operationApi.getStats()
    Object.assign(overall, {
      total: res.total || 0,
      processing: res.processing || 0,
      resolved: res.resolved || 0,
      closed: res.closed || 0,
      overdue: res.overdue || 0,
      closed_loop_rate: res.closed_loop_rate || 0,
    })
  } catch (e) {
    ElMessage.error('加载总统计失败')
  }
}

const loadIssues = async () => {
  loading.value = true
  try {
    const res = await operationApi.listIssues({ page: 1, page_size: 300 })
    allIssues.value = res.items || []
  } catch (e) {
    ElMessage.error('加载工单失败')
  } finally {
    loading.value = false
  }
}

const loadNotes = async () => {
  try {
    const res = await obsidianApi.listNotes()
    sideNotes.value = (res || []).slice(0, 3)
  } catch (e) {
    sideNotes.value = []
  }
}

const selectCategory = (key) => {
  selectedCategory.value = key
  page.value = 1
}

const statusLoadingMap = ref({})
const changeStatus = async (row, status) => {
  if (!row || row.status === status) return
  statusLoadingMap.value[row.id] = true
  try {
    await operationApi.updateIssue(row.id, { status })
    ElMessage.success('状态已更新')
    loadStats()
    loadIssues()
  } catch (e) {
    ElMessage.error('状态更新失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  } finally {
    delete statusLoadingMap.value[row.id]
  }
}

const onRowClick = (row) => openDetail(row)

const openDetail = (row) => {
  router.push({ path: routeCategoryPath(row.category), query: { issue: row.id } })
}
const routeCategoryPath = (cat) => `/operation/${cat || 'prod'}`

const openEmailFromRow = (row) => {
  router.push({ path: routeCategoryPath(row.category), query: { email: row.id } })
}

const goNotes = () => router.push('/operation/notes')

// ---- 录入工单（总览入口） ----
const entryVisible = ref(false)
const entryLoading = ref(false)
const entryRef = ref(null)
const noteOptions = ref([])
const entryForm = reactive({
  category: 'bug', issue_type: 'bug', title: '', handler: [], impact_level: 'P2', due: '', situation_desc: '', obsidian_path: '',
})
const entryTypeOptions = computed(() => TYPE_BY_CAT[entryForm.category] || [])
const entryRules = {
  category: [{ required: true, message: '请选择类别', trigger: 'change' }],
  issue_type: [{ required: true, message: '请选择子类', trigger: 'change' }],
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  handler: [{ required: true, type: 'array', min: 1, message: '请至少选择一名责任人', trigger: 'change' }],
  situation_desc: [{ required: true, message: '请输入情况说明', trigger: 'blur' }],
}

const onEntryCatChange = () => {
  const opts = TYPE_BY_CAT[entryForm.category] || []
  entryForm.issue_type = opts.length ? opts[0].value : 'other'
}

const openEntry = async () => {
  Object.assign(entryForm, {
    category: 'bug', issue_type: 'bug', title: '', handler: [], impact_level: 'P2', due: '', situation_desc: '', obsidian_path: '',
  })
  entryVisible.value = true
  if (!noteOptions.value.length) {
    try {
      const res = await obsidianApi.listNotes()
      noteOptions.value = res || []
    } catch (e) {
      noteOptions.value = []
    }
  }
}

const generateIssueNo = (cat) => {
  const prefixMap = { bug: 'BUG', data: 'DATA', prod: 'PROD', task: 'TASK', complaint: 'COMP' }
  const prefix = prefixMap[cat] || 'WO'
  const d = new Date()
  const ds = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`
  const rnd = Math.floor(Math.random() * 900 + 100)
  return `${prefix}-${ds}-${rnd}`
}

const submitEntry = () => {
  entryRef.value.validate(async (valid) => {
    if (!valid) return
    entryLoading.value = true
    const payload = {
      issue_no: generateIssueNo(entryForm.category),
      title: entryForm.title.trim(),
      category: entryForm.category,
      issue_type: entryForm.issue_type,
      status: 'pending',
      handler: entryForm.handler.join(','),
      impact_level: entryForm.impact_level,
      situation_desc: entryForm.situation_desc.trim(),
      obsidian_path: entryForm.obsidian_path || null,
      discovery_date: new Date().toISOString(),
    }
    try {
      await operationApi.createIssue(payload)
      ElMessage.success('工单已录入')
      entryVisible.value = false
      loadStats()
      loadIssues()
    } catch (e) {
      ElMessage.error('录入失败：' + (e?.response?.data?.message || e.message || '未知错误'))
    } finally {
      entryLoading.value = false
    }
  })
}

onMounted(() => {
  loadStats()
  loadIssues()
  loadNotes()
})
</script>

<style scoped>
.operation-overview {
  padding: 20px;
}
.ops-summary {
  grid-column: span 12;
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 22px 26px;
}
.ops-donut {
  position: relative;
  width: 104px;
  height: 104px;
  flex-shrink: 0;
}
.ops-donut-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.ops-donut-val {
  font-size: 22px;
  font-weight: 800;
  color: var(--text-primary);
  line-height: 1;
}
.ops-donut-label {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}
.ops-summary-divider {
  width: 1px;
  height: 56px;
  background: var(--border);
}
.ops-summary-meta {
  display: flex;
  gap: 36px;
  flex-wrap: wrap;
}
.ops-meta-num {
  font-size: 26px;
  font-weight: 800;
  font-family: var(--font-mono);
  color: var(--text-primary);
}
.ops-meta-num.warn {
  color: var(--danger);
}
.ops-meta-lab {
  font-size: 12.5px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.cat-tiles {
  grid-column: span 12;
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
}
.cat-tile {
  padding: 18px;
  cursor: pointer;
  transition: all var(--transition-fast);
  position: relative;
  overflow: hidden;
}
.cat-tile:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-elevated);
}
.cat-tile.active {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.cat-tile-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.cat-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}
.cat-ico {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.cat-count {
  font-size: 30px;
  font-weight: 800;
  font-family: var(--font-mono);
  color: var(--text-primary);
  line-height: 1;
}
.cat-count-sub {
  font-size: 11.5px;
  color: var(--text-muted);
  margin-top: 3px;
}
.cat-rate {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 14px;
  font-size: 11.5px;
  color: var(--text-secondary);
}
.cat-rate-val {
  font-weight: 700;
  font-family: var(--font-mono);
}
.cat-bar {
  height: 6px;
  border-radius: 6px;
  background: #eef2f7;
  margin-top: 6px;
  overflow: hidden;
}
.cat-bar-fill {
  height: 100%;
  border-radius: 6px;
}

.ops-list-col {
  grid-column: span 8;
}
.card-title-styled {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}
.card-sub-styled {
  font-size: 12.5px;
  color: var(--text-muted);
  margin-top: 3px;
}
.ops-tabs {
  display: flex;
  gap: 6px;
  padding: 14px 16px 0;
  flex-wrap: wrap;
}
.ops-tab {
  padding: 7px 14px;
  border-radius: 9px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
  border: 1px solid transparent;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.ops-tab:hover {
  background: var(--border-subtle);
}
.ops-tab.active {
  background: var(--accent-soft);
  color: var(--accent);
  border-color: var(--accent);
}
.ops-tab .cnt {
  font-family: var(--font-mono);
  font-size: 11px;
  opacity: 0.7;
}
.list-toolbar {
  padding: 12px 16px 0;
}
.ops-table {
  padding: 8px 8px 4px;
}
.iss-title {
  font-weight: 600;
  color: var(--text-primary);
  cursor: pointer;
}
.iss-title:hover {
  color: var(--accent);
}
.handler-tag {
  margin: 0 4px 4px 0;
}
.list-foot {
  display: flex;
  justify-content: flex-end;
  padding: 10px 16px 14px;
}

.ops-side-col {
  grid-column: span 4;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.know-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 18px;
}
.know-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 11px 12px;
  border: 1px solid var(--border-subtle);
  border-radius: 9px;
  cursor: pointer;
  transition: all var(--transition-fast);
}
.know-item:hover {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.know-ico {
  width: 28px;
  height: 28px;
  border-radius: 7px;
  background: var(--warning-soft);
  color: var(--warning);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.know-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
}
.know-meta {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}
.know-more {
  font-size: 12px;
  color: var(--accent);
  cursor: pointer;
  padding: 4px 12px;
  font-weight: 500;
}
.urgent-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 18px;
}
.urgent-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: var(--danger-soft);
  border-radius: 9px;
  cursor: pointer;
}
.urgent-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--danger);
  flex-shrink: 0;
}
.urgent-text {
  font-size: 12.5px;
  color: var(--text-primary);
  line-height: 1.4;
}
.urgent-text b {
  color: var(--danger);
}

@media (max-width: 1280px) {
  .ops-list-col,
  .ops-side-col {
    grid-column: span 12;
  }
  .cat-tiles {
    grid-template-columns: repeat(3, 1fr);
  }
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 8px;
}
.dot-pending { background: #f56c6c; }
.dot-processing { background: #e6a23c; }
.dot-verify { background: #409eff; }
.dot-resolved { background: #67c23a; }
.dot-closed { background: #909399; }
.dot-suspended { background: #909399; }

</style>
