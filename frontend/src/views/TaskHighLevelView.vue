<template>
  <div class="task-high-level">
    <PageHeader title="高级别工单" :subtitle="subtitle">
      <template #actions>
        <el-button type="primary" :loading="syncing" @click="doSync">
          <el-icon><Refresh /></el-icon>
          <span>同步</span>
        </el-button>
        <el-button :loading="loading" @click="loadAll">刷新</el-button>
      </template>
    </PageHeader>

    <!-- 采集失败告警：失败来源本轮不参与「源消失」判定，需明确提示，避免误读为工单消失 -->
    <el-alert
      v-if="failedSources.length"
      type="warning"
      show-icon
      :closable="false"
      class="hl-alert"
      :title="`${failedSources.length} 个来源本轮采集失败，未参与判定`"
      :description="`失败来源：${failedSources.map((s) => sourceLabel(s)).join('、')}。这些来源的工单跟踪态本轮未更新，不代表工单已消失。`"
    />

    <!-- 统计卡（在跟池口径：open / tracking / escalated） -->
    <div class="hl-stats">
      <el-card shadow="hover" class="hl-stat">
        <div class="hl-stat-value">{{ stats.total || 0 }}</div>
        <div class="hl-stat-label">在跟高级别</div>
      </el-card>
      <el-card shadow="hover" class="hl-stat stat-danger">
        <div class="hl-stat-value">{{ stats.overdue || 0 }}</div>
        <div class="hl-stat-label">已超期</div>
      </el-card>
      <el-card shadow="hover" class="hl-stat stat-warning">
        <div class="hl-stat-value">{{ stats.escalated || 0 }}</div>
        <div class="hl-stat-label">已升级</div>
      </el-card>
      <el-card shadow="hover" class="hl-stat">
        <div class="hl-stat-value">{{ stats.unassigned || 0 }}</div>
        <div class="hl-stat-label">未分配责任人</div>
      </el-card>
    </div>

    <!-- 按责任人一键督办（高级别对象天然集中在少数责任人手里，先给快捷入口） -->
    <div v-if="ownerChips.length" class="hl-owner-bar">
      <span class="hl-owner-bar-label">按责任人督办</span>
      <div class="hl-owner-chips">
        <el-check-tag
          v-for="o in ownerChips"
          :key="o.name"
          :checked="filters.owner === o.name"
          size="small"
          @change="toggleOwnerFilter(o.name)"
        >
          {{ o.name }} · {{ o.count }}
        </el-check-tag>
      </div>
      <el-button
        v-if="filters.owner"
        type="warning"
        size="small"
        class="hl-supervise-owner"
        @click="openOwnerSupervise(filters.owner)"
      >
        督办 {{ filters.owner }} 的全部高级别工单
      </el-button>
    </div>

    <!-- 筛选栏 -->
    <div class="hl-filter-bar">
      <el-select v-model="filters.source" placeholder="来源" clearable style="width: 130px" @change="onFilterChange">
        <el-option label="全部来源" value="" />
        <el-option v-for="s in sourceOptions" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
      <el-select v-model="filters.level" placeholder="级别" clearable style="width: 110px" @change="onFilterChange">
        <el-option label="全部级别" value="" />
        <el-option label="P0 致命" value="P0" />
        <el-option label="P1 严重" value="P1" />
        <el-option label="P2 一般(超期升格)" value="P2" />
      </el-select>
      <el-select v-model="filters.track" placeholder="跟踪态" clearable style="width: 130px" @change="onFilterChange">
        <el-option label="全部跟踪态" value="" />
        <el-option v-for="s in trackOptions" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
      <StaffSelect
        v-model="filters.ownerList"
        :multiple="true"
        placeholder="选择责任人"
        collapse-tags
        style="width: 220px"
        @change="onFilterChange"
      />
      <el-checkbox v-model="filters.onlyOverdue" label="只看超期" @change="onFilterChange" />
      <el-checkbox v-model="filters.includeClosed" label="含已闭环/已移除" @change="onFilterChange" />
      <el-input
        v-model="filters.keyword"
        placeholder="搜索标题 / 责任人 / 详情"
        clearable
        style="width: 220px"
        @keyup.enter="onFilterChange"
        @clear="onFilterChange"
      />
      <div class="hl-filter-spacer" />
      <el-button
        type="warning"
        :disabled="!selectedRows.length"
        @click="openBatchSupervise"
      >批量督办（{{ selectedRows.length }}）</el-button>
    </div>

    <!-- 主表 -->
    <el-table
      v-loading="loading"
      :data="items"
      size="small"
      border
      stripe
      row-key="task_id"
      class="hl-table"
      @selection-change="(rows) => (selectedRows = rows)"
      @row-dblclick="openDetail"
    >
      <el-table-column type="selection" width="42" reserve-selection />
      <el-table-column label="来源" width="96">
        <template #default="{ row }">{{ row.source_label }}</template>
      </el-table-column>
      <el-table-column label="级别" width="60" align="center">
        <template #default="{ row }">
          <span class="hl-level" :class="`lv-${(row.level_code || 'p3').toLowerCase()}`">
            {{ row.level_code || '—' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="工单" min-width="280" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="hl-title" :class="{ 'is-gone': row.source_gone }">{{ row.title || '（无标题）' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="责任人" width="150" show-overflow-tooltip>
        <template #default="{ row }">{{ row.owner_display || '未分配' }}</template>
      </el-table-column>
      <el-table-column label="源状态" width="96">
        <template #default="{ row }">
          <StatusBadge module="task_center" :value="row.status" size="small" />
        </template>
      </el-table-column>
      <el-table-column label="截止" width="106">
        <template #default="{ row }">
          <span :class="{ 'is-overdue': row.is_overdue }">{{ row.due_date || '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="跟踪态" width="104">
        <template #default="{ row }">
          <StatusBadge module="high_level_track" :value="row.track_status" size="small" />
        </template>
      </el-table-column>
      <el-table-column label="督办" width="62" align="center">
        <template #default="{ row }">
          <span class="hl-urge-count">{{ row.urge_count || 0 }}</span>
        </template>
      </el-table-column>
      <el-table-column label="判定依据" min-width="170" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="hl-reason">{{ reasonText(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="96" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="暂无高级别工单（可点击右上角「同步」重新采集）" :image-size="72" />
      </template>
    </el-table>

    <div class="hl-pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        background
        @current-change="loadTasks"
        @size-change="onSizeChange"
      />
    </div>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" title="工单详情" size="620px" :destroy-on-close="true">
      <div v-if="current" class="hl-detail">
        <div class="hl-detail-title">{{ current.title || '（无标题）' }}</div>

        <div class="hl-detail-sec">
          <div class="hl-detail-sec-title">工单信息</div>
          <div class="hl-kv"><span>来源</span><b>{{ current.source_label }}</b></div>
          <div class="hl-kv"><span>负责人</span><b>{{ current.owner_display || '未分配' }}</b></div>
          <div class="hl-kv"><span>源状态</span><b>{{ current.status_label }}</b></div>
          <div class="hl-kv"><span>级别</span><b>{{ current.priority_label || '—' }}</b></div>
          <div class="hl-kv"><span>创建</span><b>{{ fmtDate(current.created_at) }}</b></div>
          <div class="hl-kv"><span>截止</span><b>{{ fmtDate(current.due_date) }}</b></div>
          <div class="hl-kv"><span>判定依据</span><b>{{ reasonText(current) }}</b></div>
          <div v-for="(v, k) in current.detail || {}" :key="k" class="hl-kv">
            <span>{{ k }}</span><b>{{ v || '—' }}</b>
          </div>
        </div>

        <div class="hl-detail-sec">
          <div class="hl-detail-sec-title">汇聚跟踪</div>
          <div class="hl-kv"><span>首次纳入</span><b>{{ fmtDateTime(current.first_seen_at) }}</b></div>
          <div class="hl-kv"><span>最近命中</span><b>{{ fmtDateTime(current.last_seen_at) }}</b></div>
          <div class="hl-kv"><span>累计督办</span><b>{{ current.urge_count }} 次</b></div>
          <div class="hl-kv"><span>最近督办</span><b>{{ fmtDateTime(current.last_urged_at) }}</b></div>
          <div class="hl-kv">
            <span>跟踪态</span>
            <b><StatusBadge module="high_level_track" :value="current.track_status" size="small" /></b>
          </div>
          <div class="hl-kv">
            <span>人工覆盖</span>
            <b>{{ overrideLabel(current.manual_override) }}</b>
          </div>
          <div class="hl-track-actions">
            <el-select v-model="trackTarget" size="small" placeholder="流转到…" style="width: 150px">
              <el-option
                v-for="s in nextTrackOptions"
                :key="s.value"
                :label="s.label"
                :value="s.value"
              />
            </el-select>
            <el-button size="small" type="primary" :disabled="!trackTarget" @click="saveTrack">
              保存跟踪态
            </el-button>
            <el-button size="small" :disabled="!!current.manual_override" @click="setOverride('lock')">
              锁定
            </el-button>
            <el-button size="small" type="warning" @click="setOverride('escalate')">提级</el-button>
            <el-button size="small" type="danger" plain @click="setOverride('dismiss')">移出</el-button>
            <el-button v-if="current.manual_override" size="small" link @click="setOverride('')">
              清除覆盖
            </el-button>
          </div>
        </div>

        <div class="hl-detail-sec">
          <div class="hl-detail-sec-title">督办记录</div>
          <EmailSuperviseLog ref-type="high_level" :ref-id="`${current.source}:${current.source_id}`" />
        </div>

        <div class="hl-detail-foot">
          <el-button v-if="current.source_url" type="primary" plain @click="gotoSource">前往源模块</el-button>
          <el-button type="warning" @click="openSingleSupervise">督办此工单</el-button>
        </div>
      </div>
    </el-drawer>

    <!-- 批量督办弹窗（两条入口共用：按责任人 / 按勾选行） -->
    <HighLevelSuperviseDialog
      v-model="superviseVisible"
      :owner-name="superviseOwner"
      :preset-tasks="supervisePreset"
      @sent="onSupervised"
    />
  </div>
</template>

<script setup>
/**
 * 高级别工单（任务中心子模块，2026-10-15）。
 *
 * 能力：自动汇总各类工单中的高级别对象（P0/P1、P2 超期升格、母项继承、人工提级）
 *      + 汇聚跟踪（本地跟踪态流转 / 锁定 / 提级 / 移出）
 *      + 批量邮件督办（按责任人 / 按勾选）。
 *
 * 数据来源：GET /high-level/tasks|stats（列表实时回读源，跟踪表只供跟踪态），
 *          POST /high-level/sync（幂等同步池），PATCH /high-level/track/...（人工跟踪态）。
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import PageHeader from '@/components/Common/PageHeader.vue'
import StatusBadge from '@/components/Common/StatusBadge.vue'
import StaffSelect from '@/components/Common/StaffSelect.vue'
import EmailSuperviseLog from '@/components/Common/EmailSuperviseLog.vue'
import HighLevelSuperviseDialog from '@/components/Common/HighLevelSuperviseDialog.vue'
import {
  getHighLevelTasks,
  getHighLevelStats,
  syncHighLevel,
  updateHighLevelTrack,
} from '@/api/highLevel.js'
import { domainStatuses, allowedNext } from '@/constants/statusConfig.js'

const route = useRoute()
const router = useRouter()

const TRACK_DOMAIN = 'high_level_track'

// 来源中文名（与后端 schemas/task_center.SOURCE_LABELS 对齐）
const SOURCE_LABELS = {
  todo: '个人待办',
  operation_issue: '运营问题',
  research_issue: '一线调研',
  dev_ticket: '开发工单',
  meeting_action: '会议行动项',
  key_work: '重点工作',
  active_optimization: '主动优化',
}

const OVERRIDE_LABELS = { lock: '已锁定', escalate: '已提级', dismiss: '已移出' }

const loading = ref(false)
const syncing = ref(false)
const items = ref([])
const total = ref(0)
const summary = ref({})
const stats = ref({})
const failedSources = ref([])
const selectedRows = ref([])
const page = ref(1)
const pageSize = ref(20)

const filters = ref({
  source: '',
  level: '',
  track: '',
  ownerList: [],
  owner: '',
  onlyOverdue: false,
  includeClosed: false,
  keyword: '',
})

const detailVisible = ref(false)
const current = ref(null)
const trackTarget = ref('')

const superviseVisible = ref(false)
const superviseOwner = ref('')
const supervisePreset = ref([])

const subtitle = computed(
  () => '自动汇总 P0/P1、超期升格与人工提级的高级别工单，支持汇聚跟踪与批量邮件督办'
)

const sourceOptions = computed(() =>
  Object.entries(SOURCE_LABELS).map(([value, label]) => ({ value, label }))
)
const trackOptions = computed(() => domainStatuses(TRACK_DOMAIN) || [])
const nextTrackOptions = computed(() => {
  const cur = current.value?.track_status
  const allowed = allowedNext(TRACK_DOMAIN, cur) || []
  const all = domainStatuses(TRACK_DOMAIN) || []
  return all.filter((s) => s.value !== cur && (!allowed.length || allowed.includes(s.value)))
})

/** 责任人分布：单一数据源 = stats.by_handler（在跟池全量口径，禁止拿当前分页自己算） */
const ownerChips = computed(() => {
  const list = (stats.value && stats.value.by_handler) || []
  return list.map((h) => ({ name: h.name, count: h.count }))
})

function sourceLabel(s) {
  return SOURCE_LABELS[s] || s
}
function fmtDate(d) {
  return d ? String(d).slice(0, 10) : '—'
}
function fmtDateTime(d) {
  if (!d) return '—'
  return String(d).replace('T', ' ').slice(0, 16)
}
function overrideLabel(v) {
  return v ? OVERRIDE_LABELS[v] || v : '无'
}
/** 判定依据 → 中文可读（R1 级别直判 / R2 超期升格 / R3 母项继承 / R4 人工覆盖） */
function reasonText(row) {
  const r = row.judge_reason || ''
  if (!r) return '—'
  if (r.startsWith('R1:')) return `级别直判 ${r.slice(3)}`
  if (r.startsWith('R2:')) {
    const parts = r.split(':')
    return `超期升格（${parts[2] || ''}，已超期 ${(parts[3] || '').replace('d', ' 天')}）`
  }
  if (r.startsWith('R3:')) return `继承母项 ${r.replace('R3:inherit:', '')}`
  if (r === 'R4:lock') return '人工锁定'
  if (r === 'R4:escalate') return '人工提级'
  if (r === 'R4:dismiss') return '人工移出'
  return r
}

// ── 数据加载 ────────────────────────────────────────────────
function buildParams() {
  const owner = filters.value.owner || (filters.value.ownerList || []).join(',')
  return {
    source: filters.value.source || undefined,
    level: filters.value.level || undefined,
    track_status: filters.value.track || undefined,
    owner: owner || undefined,
    keyword: filters.value.keyword || undefined,
    only_overdue: filters.value.onlyOverdue || undefined,
    include_closed: filters.value.includeClosed || undefined,
    page: page.value,
    page_size: pageSize.value,
  }
}

async function loadTasks() {
  loading.value = true
  try {
    const res = await getHighLevelTasks(buildParams())
    items.value = (res && res.items) || []
    total.value = (res && res.total) || 0
    summary.value = (res && res.summary) || {}
  } catch (e) {
    ElMessage.error('加载高级别工单失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    stats.value = (await getHighLevelStats()) || {}
  } catch (e) {
    console.warn('[TaskHighLevel] loadStats failed:', e && e.message)
  }
}

async function loadAll() {
  await Promise.all([loadTasks(), loadStats()])
}

async function doSync() {
  syncing.value = true
  try {
    const res = await syncHighLevel()
    failedSources.value = (res && res.failed_sources) || []
    ElMessage.success(
      `同步完成：采集 ${res.scanned} 条，命中高级别 ${res.high} 条` +
      `（新增 ${res.added} / 刷新 ${res.updated} / 闭环 ${res.resolved} / 移除 ${res.removed}）`
    )
    await loadAll()
  } catch (e) {
    ElMessage.error('同步失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  } finally {
    syncing.value = false
  }
}

// ── 筛选与深链 ──────────────────────────────────────────────
function onFilterChange() {
  page.value = 1
  syncQuery()
  loadTasks()
}

function onSizeChange() {
  page.value = 1
  loadTasks()
}

function toggleOwnerFilter(name) {
  filters.value.owner = filters.value.owner === name ? '' : name
  filters.value.ownerList = filters.value.owner ? [] : filters.value.ownerList
  onFilterChange()
}

function syncQuery() {
  const q = {}
  if (filters.value.source) q.source = filters.value.source
  if (filters.value.level) q.level = filters.value.level
  if (filters.value.track) q.track = filters.value.track
  if (filters.value.owner) q.owner = filters.value.owner
  if (filters.value.onlyOverdue) q.overdue = '1'
  if (filters.value.keyword) q.keyword = filters.value.keyword
  router.replace({ path: route.path, query: q })
}

function applyRouteFilters() {
  const q = route.query || {}
  filters.value.source = q.source || ''
  filters.value.level = q.level || ''
  filters.value.track = q.track || ''
  filters.value.owner = q.owner || ''
  filters.value.ownerList = q.owner ? [] : []
  filters.value.onlyOverdue = q.overdue === '1'
  filters.value.keyword = q.keyword || ''
}

watch(
  () => route.query,
  (q, old) => {
    // 仅在外部深链变化时响应（自身 syncQuery 写入时 query 相同，不会抖动）
    if (JSON.stringify(q) === JSON.stringify(old)) return
    applyRouteFilters()
    page.value = 1
    loadTasks()
  }
)

// ── 详情与跟踪态 ────────────────────────────────────────────
function openDetail(row) {
  current.value = row
  trackTarget.value = ''
  detailVisible.value = true
}

async function refreshDetail() {
  if (!current.value) return
  const key = current.value.task_id
  await loadAll()
  const fresh = items.value.find((it) => it.task_id === key)
  if (fresh) current.value = fresh
}

async function saveTrack() {
  if (!current.value || !trackTarget.value) return
  try {
    await updateHighLevelTrack(current.value.source, current.value.source_id, {
      track_status: trackTarget.value,
      operator: 'pmwb',
    })
    ElMessage.success('跟踪态已更新')
    trackTarget.value = ''
    await refreshDetail()
  } catch (e) {
    ElMessage.error('更新失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  }
}

async function setOverride(ov) {
  if (!current.value) return
  const label = ov ? OVERRIDE_LABELS[ov] : '清除人工覆盖'
  try {
    await ElMessageBox.confirm(
      ov === 'dismiss'
        ? `确认将「${current.value.title}」移出高级别跟踪池？移出后自动规则不再将其纳入。`
        : `确认对「${current.value.title}」执行「${label}」？`,
      '确认操作',
      { type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await updateHighLevelTrack(current.value.source, current.value.source_id, {
      manual_override: ov,
      operator: 'pmwb',
    })
    ElMessage.success(`${label}成功`)
    await refreshDetail()
  } catch (e) {
    ElMessage.error('操作失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  }
}

function gotoSource() {
  if (current.value?.source_url) router.push(current.value.source_url)
}

// ── 督办 ────────────────────────────────────────────────────
function openOwnerSupervise(name) {
  superviseOwner.value = name
  supervisePreset.value = []
  superviseVisible.value = true
}

function openBatchSupervise() {
  if (!selectedRows.value.length) return
  superviseOwner.value = ''
  supervisePreset.value = [...selectedRows.value]
  superviseVisible.value = true
}

function openSingleSupervise() {
  if (!current.value) return
  superviseOwner.value = ''
  supervisePreset.value = [current.value]
  superviseVisible.value = true
}

async function onSupervised() {
  await refreshDetail()
}

onMounted(async () => {
  applyRouteFilters()
  // 进入页面自动同步一次（显式写操作，幂等），保证池子新鲜
  await doSync()
})
</script>

<style scoped>
.task-high-level {
  padding: 0 0 24px;
}
.hl-alert {
  margin-bottom: 14px;
}
.hl-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}
.hl-stat {
  border: 1px solid var(--border);
}
.hl-stat :deep(.el-card__body) {
  padding: 14px 16px;
}
.hl-stat-value {
  font-family: var(--font-display);
  font-size: 26px;
  font-weight: 650;
  line-height: 1.15;
  color: var(--text-primary);
}
.hl-stat-label {
  margin-top: 2px;
  font-size: 12.5px;
  color: var(--text-secondary);
}
.hl-stat.stat-danger .hl-stat-value {
  color: var(--danger);
}
.hl-stat.stat-warning .hl-stat-value {
  color: var(--warning);
}

.hl-owner-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 10px 12px;
  margin-bottom: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.hl-owner-bar-label {
  font-size: 12.5px;
  color: var(--text-secondary);
  white-space: nowrap;
}
.hl-owner-chips {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  flex: 1;
}
.hl-supervise-owner {
  white-space: nowrap;
}

.hl-filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.hl-filter-spacer {
  flex: 1;
}

.hl-table :deep(.el-table__cell) {
  font-size: 13px;
}
.hl-title {
  color: var(--text-primary);
}
.hl-title.is-gone {
  color: var(--text-muted);
  text-decoration: line-through;
}
.hl-level {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
}
.hl-level.lv-p0 {
  color: var(--danger);
}
.hl-level.lv-p1 {
  color: var(--warning);
}
.hl-level.lv-p2 {
  color: var(--accent);
}
.is-overdue {
  color: var(--danger);
  font-weight: 600;
}
.hl-urge-count {
  font-family: var(--font-mono);
  color: var(--text-secondary);
}
.hl-reason {
  font-size: 12px;
  color: var(--text-muted);
}

.hl-pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}

.hl-detail-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.5;
  margin-bottom: 16px;
}
.hl-detail-sec {
  margin-bottom: 22px;
}
.hl-detail-sec-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  padding-left: 8px;
  border-left: 3px solid var(--accent);
  margin-bottom: 10px;
}
.hl-kv {
  display: flex;
  gap: 10px;
  font-size: 13px;
  line-height: 2;
}
.hl-kv > span {
  width: 92px;
  flex: none;
  color: var(--text-secondary);
}
.hl-kv > b {
  color: var(--text-primary);
  font-weight: 500;
  word-break: break-word;
}
.hl-track-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.hl-detail-foot {
  display: flex;
  gap: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--border-subtle);
}

@media (max-width: 1100px) {
  .hl-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
