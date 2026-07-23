<template>
  <div class="work-order-view">
    <div class="page-head">
      <h2 class="page-title">{{ title }}</h2>
      <el-tag :type="categoryColor" effect="dark" size="large" round>{{ title }}</el-tag>
      <el-button type="primary" @click="openEntry" style="margin-left:auto">
        <el-icon><Plus /></el-icon><span>录入工单</span>
      </el-button>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="12" class="stats-row">
      <el-col :span="3">
        <el-card shadow="hover"><div class="stat-item"><div class="stat-value">{{ stats.total }}</div><div class="stat-label">工单总数</div></div></el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-pending"><div class="stat-item"><div class="stat-value">{{ stats.pending }}</div><div class="stat-label">待处理</div></div></el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-processing"><div class="stat-item"><div class="stat-value">{{ stats.processing }}</div><div class="stat-label">处理中</div></div></el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-verify"><div class="stat-item"><div class="stat-value">{{ stats.verify }}</div><div class="stat-label">待验证</div></div></el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-resolved"><div class="stat-item"><div class="stat-value">{{ stats.resolved }}</div><div class="stat-label">已解决</div></div></el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-closed"><div class="stat-item"><div class="stat-value">{{ stats.closed }}</div><div class="stat-label">已关闭</div></div></el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-overdue"><div class="stat-item"><div class="stat-value">{{ stats.overdue }}</div><div class="stat-label">超期</div></div></el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="status-loop"><div class="stat-item"><div class="stat-value">{{ stats.closed_loop_rate }}%</div><div class="stat-label">闭环率</div></div></el-card>
      </el-col>
    </el-row>

    <!-- 5 大类子页签 + 全部 -->
    <div class="sub-tabs">
      <div
        v-for="t in subTabs"
        :key="t.key"
        class="sub-tab"
        :class="{ active: activeTab === t.key }"
        @click="activeTab = t.key"
      >{{ t.label }}<span class="cnt">{{ t.count }}</span></div>
    </div>

    <!-- 状态流转标签 + 搜索 -->
    <div class="filter-bar">
      <div class="status-tags">
        <span
          v-for="s in statusFilterOptions"
          :key="s.key"
          class="st-tag"
          :class="['st-' + s.key, { active: statusFilter === s.key }]"
          @click="statusFilter = s.key"
        >{{ s.label }}</span>
      </div>
      <el-input
        v-model="keyword"
        placeholder="搜索工单号 / 标题 / 责任人"
        clearable
        size="small"
        style="width:240px"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      />
      <el-button size="small" @click="handleSearch">查询</el-button>
      <el-button size="small" @click="loadStats">刷新统计</el-button>
    </div>

    <!-- 工单列表 -->
    <el-table
      :data="tableData"
      v-loading="loading"
      stripe
      border
      class="wo-table"
    >
      <el-table-column prop="issue_no" label="工单编号" width="160" />
      <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="iss-title" @click="openDetail(row)">{{ row.title }}</span>
        </template>
      </el-table-column>
      <el-table-column label="子类" width="110">
        <template #default="{ row }">
          <el-tag :type="issueTypeTag(row.category, row.issue_type)" size="small">
            {{ issueTypeLabel(row.category, row.issue_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="责任人" width="170">
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
      <el-table-column label="创建时间" width="130">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="190" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
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
          <el-button link type="warning" @click="openEmail(row)">督办</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="wo-pager">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.page_size"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @size-change="loadData"
        @current-change="loadData"
      />
    </div>

    <!-- 工单详情 / 管理抽屉 -->
    <el-drawer
      v-model="detailVisible"
      :title="'工单详情 · ' + (detailRow?.issue_no || '')"
      size="680px"
      destroy-on-close
    >
      <div v-loading="detailLoading" class="drawer-body-inner">
        <!-- 5 段状态 stepper -->
        <div class="pm-steps detail-stepper">
          <template v-for="(s, idx) in STATUS_FLOW" :key="s.key">
            <div class="pm-step" :class="stepClass(idx)">
              <div class="pm-step-dot">{{ idx < currentIdx ? '✓' : idx + 1 }}</div>
              <div class="pm-step-label">{{ s.label }}</div>
            </div>
            <div v-if="idx < STATUS_FLOW.length - 1" class="pm-step-line" :class="{ done: idx < currentIdx }"></div>
          </template>
        </div>

        <!-- 基本信息 -->
        <div class="dt-sec">
          <div class="dt-sec-title">基本信息</div>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="责任人">
              <template v-if="detailRow?.handler">
                <el-tag v-for="h in detailRow.handler.split(',').filter(Boolean)" :key="h" size="small" class="handler-tag">{{ h }}</el-tag>
              </template>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="优先级/影响">{{ detailRow?.impact_level || '-' }}</el-descriptions-item>
            <el-descriptions-item label="发现时间">{{ formatDateTime(detailRow?.discovery_date) }}</el-descriptions-item>
            <el-descriptions-item label="解决时间">{{ formatDateTime(detailRow?.resolve_date) }}</el-descriptions-item>
            <el-descriptions-item label="关联需求">{{ detailRow?.related_req_id || '-' }}</el-descriptions-item>
            <el-descriptions-item label="关联工单">{{ detailRow?.related_ticket_no || '-' }}</el-descriptions-item>
            <el-descriptions-item label="关联系统">{{ detailRow?.related_system || '-' }}</el-descriptions-item>
            <el-descriptions-item label="逾期">
              <el-tag v-if="detailRow?.is_overdue" type="danger" size="small">已逾期</el-tag>
              <span v-else>正常</span>
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <!-- 情况说明 -->
        <div class="dt-sec">
          <div class="dt-sec-title">情况说明</div>
          <div class="dt-desc">{{ detailRow?.situation_desc || '—' }}</div>
        </div>

        <!-- 关联知识库 -->
        <div class="dt-sec">
          <div class="dt-sec-title">关联知识库（Obsidian）</div>
          <div v-if="detailRow?.obsidian_path" class="dt-link-row">
            <div class="lk-ico"><el-icon><Document /></el-icon></div>
            <div>
              <div class="dt-link-name">{{ noteTitle(detailRow.obsidian_path) }}</div>
              <div class="dt-link-meta">{{ detailRow.obsidian_path }}</div>
            </div>
          </div>
          <div v-else class="dt-link-meta">尚未关联知识条目</div>
          <el-button size="small" link type="primary" @click="openLinkPicker('detail')">+ 关联知识条目</el-button>
        </div>

        <!-- 督办记录 -->
        <div class="dt-sec">
          <div class="dt-sec-title">邮件督办记录</div>
          <div class="email-log">
            <div v-for="(e, i) in supervisionList" :key="i" class="email-log-item">
              <div class="el-ico"><el-icon><Promotion /></el-icon></div>
              <div>
                <div class="email-log-to">收件：{{ e.to }}</div>
                <div class="email-log-time">{{ e.time }}</div>
                <div class="email-log-result">{{ e.result }}</div>
              </div>
            </div>
            <div v-if="!supervisionList.length" class="dt-link-meta">暂无督办邮件</div>
          </div>
          <div class="dt-link-meta" style="margin-top:6px;font-size:11px;color:var(--text-muted)">
            收件人通过「统一邮件中心」按姓名解析，不拼接邮箱地址
          </div>
        </div>
      </div>
      <template #footer>
        <div class="drawer-foot">
          <el-select v-model="nextStatus" size="small" style="width:130px" placeholder="选择状态">
            <el-option v-for="s in STATUS_OPTIONS" :key="s.key" :label="s.label" :value="s.key" />
          </el-select>
          <el-button :loading="advanceLoading" :disabled="!nextStatus || nextStatus === detailRow?.status" @click="changeStatusFromDetail">
            <el-icon><RefreshRight /></el-icon><span>确认变更</span>
          </el-button>
          <el-button @click="openEditFromDetail"><el-icon><Edit /></el-icon><span>编辑</span></el-button>
          <el-button @click="openLinkPicker('detail')"><el-icon><Connection /></el-icon><span>关联知识</span></el-button>
          <el-button type="primary" @click="openEmail(detailRow)"><el-icon><Promotion /></el-icon><span>邮件督办</span></el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 录入 / 编辑工单弹层 -->
    <el-dialog
      v-model="entryVisible"
      :title="isEdit ? '编辑工单' : '录入工单'"
      width="640px"
      destroy-on-close
    >
      <el-form :model="form" label-width="96px" :rules="entryRules" ref="formRef">
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="工单类别" prop="category">
              <el-select v-model="form.category" style="width:100%" @change="onCatChange">
                <el-option v-for="c in CATEGORIES" :key="c.key" :label="c.label" :value="c.key" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="子类" prop="issue_type">
              <el-select v-model="form.issue_type" style="width:100%">
                <el-option v-for="o in entryTypeOptions" :key="o.value" :label="o.label" :value="o.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="工单标题" prop="title">
          <el-input v-model="form.title" placeholder="简短描述问题或任务" />
        </el-form-item>
        <el-form-item label="责任人" prop="handler">
          <el-select v-model="form.handler" multiple filterable placeholder="可多选，逗号存储" style="width:100%">
            <el-option-group v-for="g in HANDLER_GROUPS" :key="g.label" :label="g.label">
              <el-option v-for="o in g.options" :key="o.value" :label="o.label" :value="o.value" />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="优先级">
              <el-select v-model="form.impact_level" style="width:100%">
                <el-option v-for="p in PRIORITY_OPTIONS" :key="p.value" :label="p.label" :value="p.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="期望完成">
              <el-date-picker v-model="form.due" type="date" placeholder="选填" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="情况说明" prop="situation_desc">
          <el-input v-model="form.situation_desc" type="textarea" :rows="3" placeholder="影响范围/具体情况说明" />
        </el-form-item>
        <el-form-item label="关联知识库">
          <div class="note-picker">
            <el-input v-model="form.obsidian_path" placeholder="选择关联的 Obsidian 知识笔记" readonly style="flex:1" />
            <el-button @click="openLinkPicker('entry')">选择笔记</el-button>
            <el-button v-if="form.obsidian_path" link type="danger" @click="form.obsidian_path = ''">清除</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="entryVisible = false">取消</el-button>
        <el-button type="primary" :loading="entryLoading" @click="submitEntry">确定</el-button>
      </template>
    </el-dialog>

    <!-- 邮件督办弹层 -->
    <el-dialog v-model="emailVisible" title="邮件督办" width="600px" destroy-on-close>
      <div v-if="currentEmailIssue" class="email-body">
        <div class="form-label">收件人（统一邮件中心按姓名解析）</div>
        <div class="recp-list">
          <span v-for="h in emailRecipients" :key="h" class="recp-chip"><span class="dot"></span>{{ h }}</span>
        </div>
        <div class="form-label" style="margin-top:16px">督办模板</div>
        <div class="tpl-pick">
          <button class="tpl-btn" :class="{active: emailTpl==='urgent'}" @click="useTpl('urgent')">催办（逾期）</button>
          <button class="tpl-btn" :class="{active: emailTpl==='progress'}" @click="useTpl('progress')">进度确认</button>
          <button class="tpl-btn" :class="{active: emailTpl==='close'}" @click="useTpl('close')">闭环确认</button>
        </div>
        <div class="form-label" style="margin-top:16px">正文（bodyFormat: text，口语化、禁敬语）</div>
        <el-input v-model="emailBody" type="textarea" :rows="6" style="margin-top:6px" />
      </div>
      <template #footer>
        <el-button @click="emailVisible = false">取消</el-button>
        <el-button type="primary" :loading="sendingEmail" @click="sendEmail">发送督办邮件</el-button>
      </template>
    </el-dialog>

    <!-- 关联笔记选择弹窗 -->
    <el-dialog v-model="notePickerVisible" title="选择关联知识笔记" width="640px" append-to-body>
      <el-input v-model="noteSearch" placeholder="搜索笔记标题" clearable style="margin-bottom:12px" />
      <el-table
        :data="filteredNotes"
        height="340"
        v-loading="notesLoading"
        highlight-current-row
        @row-click="(row) => (pickedNote = row)"
        style="width:100%"
      >
        <el-table-column prop="folder" label="目录" width="240" show-overflow-tooltip />
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
      </el-table>
      <template #footer>
        <el-button @click="notePickerVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!pickedNote" @click="confirmPickNote">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Edit, Promotion, RefreshRight, Connection, Document, ArrowDown } from '@element-plus/icons-vue'
import StatusBadge from '@/components/Common/StatusBadge.vue'
import { operationApi } from '@/api/operation'
import { obsidianApi } from '@/api/obsidian'
import { HANDLER_GROUPS } from '@/constants/staff'
import { formatDateTime } from '@/utils/format'
import request from '@/api/request'

const route = useRoute()
const category = computed(() => route.meta.category || 'prod')
const title = computed(() => route.meta.title || '工单管理')

const CATEGORIES = [
  { key: 'bug', label: 'BUG 管理', color: 'danger' },
  { key: 'data', label: '数据异常管理', color: 'warning' },
  { key: 'prod', label: '生产问题分析', color: 'primary' },
  { key: 'task', label: '临时交办任务', color: 'success' },
  { key: 'complaint', label: '热点投诉', color: 'danger' },
]
const categoryMeta = Object.fromEntries(CATEGORIES.map((c) => [c.key, c]))
const categoryColor = computed(() => categoryMeta[category.value]?.color || 'info')

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

const STATUS_FLOW = [
  { key: 'pending', label: '待处理' },
  { key: 'processing', label: '处理中' },
  { key: 'verify', label: '验证中' },
  { key: 'resolved', label: '已解决' },
  { key: 'closed', label: '已关闭' },
]
const STATUS_OPTIONS = [
  ...STATUS_FLOW,
  { key: 'suspended', label: '已挂起' },
]
const statusBadgeOptions = {
  pending: { label: '待处理', type: 'danger' },
  processing: { label: '处理中', type: 'warning' },
  verify: { label: '验证中', type: 'primary' },
  resolved: { label: '已解决', type: 'success' },
  closed: { label: '已关闭', type: 'info' },
  suspended: { label: '已挂起', type: 'info' },
}

const issueTypeLabel = (cat, type) => (TYPE_BY_CAT[cat] || []).find((o) => o.value === type)?.label || type
const issueTypeTag = (cat, type) => {
  if (type === 'bug') return 'danger'
  if (type === 'data_abnormal') return 'warning'
  if (type === 'topic_analysis') return 'primary'
  if (type === 'spot_event') return 'info'
  if (type === 'temp_task') return 'success'
  return 'info'
}

// ---- 列表 / 统计 ----
const loading = ref(false)
const tableData = ref([])
const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const keyword = ref('')
const activeTab = ref(category.value)
const statusFilter = ref('all')

const subTabs = computed(() => [{ key: 'all', label: '全部', count: overallTotal.value }, ...CATEGORIES.map((c) => ({ ...c, count: catCount(c.key) }))])
const overallTotal = ref(0)
const allByCategory = ref([])
const catCount = (key) => allByCategory.value.find((x) => x.name === key)?.value || 0

const loadAllCounts = async () => {
  try {
    const res = await operationApi.getStats()
    overallTotal.value = res.total || 0
    allByCategory.value = res.by_category || []
  } catch (e) { /* 非关键 */ }
}

const statusFilterOptions = [{ key: 'all', label: '全部' }, ...STATUS_FLOW, { key: 'suspended', label: '已挂起' }]

const stats = reactive({
  total: 0, pending: 0, processing: 0, verify: 0, resolved: 0, closed: 0,
  overdue: 0, closed_loop_rate: 0, by_category: [],
})

const loadData = async () => {
  loading.value = true
  try {
    const res = await operationApi.listIssues({
      keyword: keyword.value || undefined,
      category: activeTab.value === 'all' ? undefined : activeTab.value,
      status: statusFilter.value === 'all' ? undefined : statusFilter.value,
      page: pagination.page,
      page_size: pagination.page_size,
    })
    tableData.value = res.items || []
    pagination.total = res.total || 0
  } catch (e) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const res = await operationApi.getStats(activeTab.value === 'all' ? undefined : activeTab.value)
    Object.assign(stats, {
      total: res.total || 0, pending: res.pending || 0, processing: res.processing || 0,
      verify: res.verify || 0, resolved: res.resolved || 0, closed: res.closed || 0,
      overdue: res.overdue || 0, closed_loop_rate: res.closed_loop_rate || 0,
      by_category: res.by_category || [],
    })
  } catch (e) {
    ElMessage.error('加载统计失败')
  }
}

const handleSearch = () => { pagination.page = 1; loadData() }

watch(activeTab, () => { pagination.page = 1; statusFilter.value = 'all'; loadData(); loadStats() })

// ---- 详情抽屉 ----
const detailVisible = ref(false)
const detailRow = ref(null)
const detailLoading = ref(false)
const advanceLoading = ref(false)
const nextStatus = ref('')

const currentIdx = computed(() => STATUS_FLOW.findIndex((s) => s.key === detailRow.value?.status))
const stepClass = (idx) => (idx < currentIdx.value ? 'done' : idx === currentIdx.value ? 'active' : '')

const supervisionRecords = reactive({})
const supervisionList = computed(() => (detailRow.value && supervisionRecords[detailRow.value.id]) || [])

const openDetail = async (row) => {
  detailRow.value = row
  nextStatus.value = row?.status || ''
  detailVisible.value = true
  detailLoading.value = true
  try {
    const res = await operationApi.getIssue(row.id)
    detailRow.value = res
    nextStatus.value = res.status || ''
  } catch (e) {
    ElMessage.error('加载详情失败')
  } finally {
    detailLoading.value = false
  }
}

const refreshDetail = async () => {
  if (!detailRow.value?.id) return
  try {
    const res = await operationApi.getIssue(detailRow.value.id)
    detailRow.value = res
  } catch (e) { /* 保留旧值 */ }
}

const changeStatusFromDetail = async () => {
  if (!detailRow.value || !nextStatus.value || nextStatus.value === detailRow.value.status) return
  advanceLoading.value = true
  try {
    await operationApi.updateIssue(detailRow.value.id, { status: nextStatus.value })
    ElMessage.success('状态已更新')
    await refreshDetail()
    nextStatus.value = detailRow.value?.status || ''
    loadData(); loadStats()
  } catch (e) {
    ElMessage.error('状态更新失败')
  } finally {
    advanceLoading.value = false
  }
}

// ---- 列表快速改状态 ----
const statusLoadingMap = ref({})
const changeStatus = async (row, status) => {
  if (!row || row.status === status) return
  statusLoadingMap.value[row.id] = true
  try {
    await operationApi.updateIssue(row.id, { status })
    ElMessage.success('状态已更新')
    loadData(); loadStats()
    if (detailVisible.value && detailRow.value?.id === row.id) {
      await refreshDetail()
      nextStatus.value = detailRow.value?.status || ''
    }
  } catch (e) {
    ElMessage.error('状态更新失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  } finally {
    delete statusLoadingMap.value[row.id]
  }
}

// ---- 录入 / 编辑 ----
const entryVisible = ref(false)
const isEdit = ref(false)
const entryLoading = ref(false)
const formRef = ref(null)
const form = reactive({
  id: null, issue_no: '', category: 'prod', issue_type: 'other', title: '', handler: [],
  impact_level: 'P2', due: '', situation_desc: '', obsidian_path: '',
})
const entryTypeOptions = computed(() => TYPE_BY_CAT[form.category] || [])
const entryRules = {
  category: [{ required: true, message: '请选择类别', trigger: 'change' }],
  issue_type: [{ required: true, message: '请选择子类', trigger: 'change' }],
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  handler: [{ required: true, type: 'array', min: 1, message: '请至少选择一名责任人', trigger: 'change' }],
  situation_desc: [{ required: true, message: '请输入情况说明', trigger: 'blur' }],
}

const generateIssueNo = (cat) => {
  const prefixMap = { bug: 'BUG', data: 'DATA', prod: 'PROD', task: 'TASK', complaint: 'COMP' }
  const prefix = prefixMap[cat] || 'WO'
  const d = new Date()
  const ds = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`
  return `${prefix}-${ds}-${Math.floor(Math.random() * 900 + 100)}`
}

const onCatChange = () => {
  const opts = TYPE_BY_CAT[form.category] || []
  form.issue_type = opts.length ? opts[0].value : 'other'
}

const openEntry = () => {
  isEdit.value = false
  Object.assign(form, {
    id: null, issue_no: '', category: activeTab.value === 'all' ? 'prod' : activeTab.value,
    issue_type: 'other', title: '', handler: [], impact_level: 'P2', due: '', situation_desc: '', obsidian_path: '',
  })
  onCatChange()
  entryVisible.value = true
}

const openEditFromDetail = () => {
  if (!detailRow.value) return
  isEdit.value = true
  Object.assign(form, {
    id: detailRow.value.id,
    issue_no: detailRow.value.issue_no,
    category: detailRow.value.category,
    issue_type: detailRow.value.issue_type,
    title: detailRow.value.title,
    handler: (detailRow.value.handler || '').split(',').filter(Boolean),
    impact_level: detailRow.value.impact_level || 'P2',
    due: '',
    situation_desc: detailRow.value.situation_desc || '',
    obsidian_path: detailRow.value.obsidian_path || '',
  })
  onCatChange()
  entryVisible.value = true
}

const submitEntry = () => {
  formRef.value.validate(async (valid) => {
    if (!valid) return
    const payload = {
      issue_no: form.issue_no || generateIssueNo(form.category),
      title: form.title.trim(),
      category: form.category,
      issue_type: form.issue_type,
      handler: (form.handler || []).join(','),
      impact_level: form.impact_level,
      situation_desc: form.situation_desc.trim(),
      obsidian_path: form.obsidian_path || null,
    }
    if (isEdit.value && form.id) payload.status = detailRow.value?.status || 'pending'
    entryLoading.value = true
    try {
      if (isEdit.value && form.id) {
        await operationApi.updateIssue(form.id, payload)
        ElMessage.success('更新成功')
      } else {
        payload.status = 'pending'
        payload.discovery_date = new Date().toISOString()
        await operationApi.createIssue(payload)
        ElMessage.success('创建成功')
      }
      entryVisible.value = false
      loadData(); loadStats()
      if (detailVisible.value) refreshDetail()
    } catch (e) {
      ElMessage.error('操作失败：' + (e?.response?.data?.message || e.message || '未知错误'))
    } finally {
      entryLoading.value = false
    }
  })
}

// ---- 关联知识笔记 ----
const notePickerVisible = ref(false)
const notesList = ref([])
const notesLoading = ref(false)
const noteSearch = ref('')
const pickedNote = ref(null)
const linkTarget = ref('entry')

const filteredNotes = computed(() => {
  const kw = noteSearch.value.trim().toLowerCase()
  if (!kw) return notesList.value
  return notesList.value.filter((n) => (n.title || '').toLowerCase().includes(kw))
})

const noteTitle = (path) => notesList.value.find((n) => n.path === path)?.title || path

const openLinkPicker = async (target) => {
  linkTarget.value = target
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

const confirmPickNote = async () => {
  if (!pickedNote.value) return
  const path = pickedNote.value.path
  if (linkTarget.value === 'entry') {
    form.obsidian_path = path
    notePickerVisible.value = false
    return
  }
  // detail：真实关联该工单
  if (!detailRow.value?.id) return
  try {
    await operationApi.updateIssue(detailRow.value.id, { obsidian_path: path })
    detailRow.value.obsidian_path = path
    ElMessage.success('已关联知识条目')
  } catch (e) {
    ElMessage.error('关联失败')
  } finally {
    notePickerVisible.value = false
  }
}

// ---- 邮件督办 ----
const emailVisible = ref(false)
const currentEmailIssue = ref(null)
const emailBody = ref('')
const emailTpl = ref('progress')
const sendingEmail = ref(false)

const emailRecipients = computed(() => (currentEmailIssue.value?.handler || '').split(',').filter(Boolean))

const handlerText = (i) => (i.handler || '').split(',').filter(Boolean).join('、')
const EMAIL_TPL = {
  urgent: (i) => `${handlerText(i)}好：\n工单 ${i.issue_no}（${i.title}）已逾期，请尽快推进处理，有进展随时同步我。`,
  progress: (i) => `${handlerText(i)}好：\n工单 ${i.issue_no}（${i.title}）当前在「${statusBadgeOptions[i.status]?.label || i.status}」，麻烦更新下最新进展。`,
  close: (i) => `${handlerText(i)}好：\n工单 ${i.issue_no}（${i.title}）如已处理完成，请确认闭环，我这边同步关闭。`,
}

const openEmail = (row) => {
  if (!row) return
  currentEmailIssue.value = row
  emailTpl.value = 'progress'
  emailBody.value = EMAIL_TPL.progress(row)
  emailVisible.value = true
}

const useTpl = (key) => {
  emailTpl.value = key
  if (currentEmailIssue.value) emailBody.value = EMAIL_TPL[key](currentEmailIssue.value)
}

const sendEmail = async () => {
  const issue = currentEmailIssue.value
  if (!issue) return
  const body = emailBody.value.trim()
  if (!body) { ElMessage.warning('请输入邮件正文'); return }
  const handlers = emailRecipients.value
  const payload = {
    to: handlers,
    subject: `【工单督办】${issue.issue_no} ${issue.title}`,
    body,
    bodyFormat: 'text',
  }
  let simulated = false
  sendingEmail.value = true
  try {
    const res = await request.post('/plugins/send', payload)
    if (res && res.success === false) simulated = true
  } catch (e) {
    simulated = true
  } finally {
    sendingEmail.value = false
  }
  // 写入该工单督办记录（前端记录，因后端暂无督办记录存储字段）
  const time = formatDateTime(new Date())
  const rec = {
    to: handlers.join('、'),
    time,
    result: simulated ? '已提交（模拟·待联调）' : '已送达（统一邮件中心）',
  }
  if (!supervisionRecords[issue.id]) supervisionRecords[issue.id] = []
  supervisionRecords[issue.id].push(rec)
  emailVisible.value = false
  if (simulated) {
    ElMessage({ message: '督办邮件已提交（模拟）· 待后端 /plugins/send 联调', type: 'warning' })
  } else {
    ElMessage.success('督办邮件已发送')
  }
}

// ---- 路由联动：从总览带 query 跳转 ----
watch(
  () => route.query,
  async (q) => {
    if (q.issue) {
      try {
        const res = await operationApi.getIssue(Number(q.issue))
        openDetail(res)
      } catch (e) { /* ignore */ }
    } else if (q.email) {
      try {
        const res = await operationApi.getIssue(Number(q.email))
        openEmail(res)
      } catch (e) { /* ignore */ }
    }
  },
  { immediate: true }
)

watch(
  () => route.meta.category,
  () => {
    activeTab.value = category.value
    pagination.page = 1
    keyword.value = ''
    statusFilter.value = 'all'
    loadData()
    loadStats()
  }
)

onMounted(() => {
  loadAllCounts()
  loadData()
  loadStats()
})
</script>

<style scoped>
.work-order-view { padding: 20px; }
.page-head { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.page-title { font-size: 20px; font-weight: 600; margin: 0; }

.stats-row { margin-bottom: 18px; }
.stat-item { text-align: center; padding: 10px 0; }
.stat-value { font-size: 26px; font-weight: 700; color: #303133; }
.stat-label { font-size: 13px; color: #606266; margin-top: 6px; }
.status-pending .stat-value { color: #f56c6c; }
.status-processing .stat-value { color: #e6a23c; }
.status-verify .stat-value { color: #409eff; }
.status-resolved .stat-value { color: #67c23a; }
.status-closed .stat-value { color: #909399; }
.status-overdue .stat-value { color: #f56c6c; }
.status-loop .stat-value { color: #409eff; }

.sub-tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }
.sub-tab {
  padding: 8px 16px; border-radius: 9px; font-size: 13px; font-weight: 500;
  color: var(--text-secondary); cursor: pointer; border: 1px solid var(--border);
  transition: all var(--transition-fast); display: inline-flex; align-items: center; gap: 6px;
}
.sub-tab:hover { border-color: var(--accent); color: var(--accent); }
.sub-tab.active { background: var(--accent); border-color: var(--accent); color: #fff; }
.sub-tab .cnt { font-family: var(--font-mono); font-size: 11px; opacity: 0.75; }

.filter-bar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.status-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.st-tag {
  padding: 5px 12px; border-radius: 999px; font-size: 12px; font-weight: 600; cursor: pointer;
  border: 1px solid var(--border); color: var(--text-secondary); background: var(--surface);
  transition: all var(--transition-fast);
}
.st-tag.active { color: #fff; border-color: transparent; }
.st-tag.st-all.active { background: var(--accent); }
.st-tag.st-pending.active { background: var(--warning); }
.st-tag.st-processing.active { background: var(--info); }
.st-tag.st-verify.active { background: var(--accent); }
.st-tag.st-resolved.active { background: var(--success); }
.st-tag.st-closed.active { background: var(--text-muted); }
.st-tag.st-suspended.active { background: var(--text-muted); }

.wo-table { margin-top: 4px; }
.iss-title { font-weight: 600; color: var(--text-primary); cursor: pointer; }
.iss-title:hover { color: var(--accent); }
.handler-tag { margin: 0 4px 4px 0; }
.wo-pager { display: flex; justify-content: flex-end; margin-top: 16px; }

/* 详情抽屉 */
.drawer-body-inner { padding: 4px 4px 8px; }
.detail-stepper { padding: 4px 0 18px; }
.dt-sec { border-top: 1px solid var(--border-subtle); padding: 18px 4px; }
.dt-sec-title { font-size: 13px; font-weight: 700; color: var(--text-secondary); margin-bottom: 14px; }
.dt-desc { font-size: 13.5px; line-height: 1.75; color: var(--text-secondary); background: var(--border-subtle); border-radius: 11px; padding: 14px 16px; }
.dt-link-row { display: flex; align-items: center; gap: 10px; padding: 11px 13px; border: 1px solid var(--border-subtle); border-radius: 9px; margin-bottom: 8px; }
.lk-ico { width: 30px; height: 30px; border-radius: 8px; background: var(--warning-soft); color: var(--warning); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.dt-link-name { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.dt-link-meta { font-size: 11px; color: var(--text-muted); margin-top: 2px; word-break: break-all; }
.email-log { display: flex; flex-direction: column; gap: 8px; }
.email-log-item { display: flex; align-items: flex-start; gap: 10px; padding: 11px 13px; background: var(--info-soft); border-radius: 9px; }
.el-ico { width: 26px; height: 26px; border-radius: 7px; background: var(--info); color: #fff; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 13px; }
.email-log-to { font-size: 12.5px; font-weight: 600; color: var(--text-primary); }
.email-log-time { font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); }
.email-log-result { font-size: 11px; color: var(--success); font-weight: 600; }
.drawer-foot { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }

.note-picker { display: flex; align-items: center; gap: 8px; }

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


/* 邮件督办 */
.email-body { padding: 2px 4px; }
.form-label { font-size: 12.5px; font-weight: 600; color: var(--text-secondary); }
.recp-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.recp-chip { display: inline-flex; align-items: center; gap: 6px; background: var(--accent-soft); color: var(--accent); font-size: 12.5px; font-weight: 500; padding: 5px 11px; border-radius: 8px; }
.recp-chip .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--success); }
.tpl-pick { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
.tpl-btn { font-size: 12px; padding: 6px 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); color: var(--text-secondary); cursor: pointer; transition: all var(--transition-fast); }
.tpl-btn:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }
.tpl-btn.active { background: var(--accent); border-color: var(--accent); color: #fff; }
</style>
