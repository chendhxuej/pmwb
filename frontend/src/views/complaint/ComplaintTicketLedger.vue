<template>
  <div class="complaint-tickets">
    <PageHeader title="客诉工单台账" :subtitle="subTitle">
      <template #actions>
        <CategoryDictPopover />
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </template>
    </PageHeader>

    <!-- 筛选区 -->
    <div class="filter-bar">
      <el-select v-model="filters.week" placeholder="全部周次" clearable filterable style="width: 132px" @change="load">
        <el-option v-for="w in weekOptions" :key="w" :label="w" :value="w" />
      </el-select>
      <el-select v-model="filters.l1" placeholder="问题性质" clearable style="width: 150px" @change="load">
        <el-option v-for="x in l1Options" :key="x" :label="x" :value="x" />
      </el-select>
      <el-select v-model="filters.l2" placeholder="问题场景" clearable filterable style="width: 190px" @change="load">
        <el-option v-for="x in l2Options" :key="x" :label="x" :value="x" />
      </el-select>
      <el-select v-model="filters.classify_by" placeholder="分类来源" clearable style="width: 130px" @change="load">
        <el-option label="AI 已归类" value="ai" />
        <el-option label="AI 待人工确认" value="ai_low" />
        <el-option label="人工校正" value="manual" />
        <el-option label="待分析" value="auto" />
      </el-select>
      <el-select v-model="filters.rc_status" placeholder="根因状态" clearable style="width: 124px" @change="load">
        <el-option label="已归纳" value="ai" />
        <el-option label="待人工" value="low" />
        <el-option label="人工确认" value="manual" />
        <el-option label="待分析" value="pending" />
      </el-select>
      <el-select v-model="filters.is_batch" placeholder="批量标记" clearable style="width: 108px" @change="load">
        <el-option label="批量簇内" :value="1" />
        <el-option label="非批量" :value="0" />
      </el-select>
      <el-input
        v-model="filters.keyword"
        placeholder="搜索单号 / 工单内容"
        clearable
        style="width: 220px"
        @keyup.enter="load"
        @clear="load"
      />
      <el-button type="primary" plain :icon="Search" @click="load">查询</el-button>
    </div>

    <el-table ref="pmTbl1" v-loading="loading" :data="rows" size="default" border stripe>
      <el-table-column prop="ticket_no" label="BOMC 流水号" width="150" show-overflow-tooltip />
      <el-table-column prop="created_time" label="创建时间" width="150">
        <template #default="{ row }">{{ (row.created_time || '').replace('T', ' ').slice(0, 16) }}</template>
      </el-table-column>
      <el-table-column prop="city" label="地市" width="76" />
      <el-table-column label="问题分类" min-width="200">
        <template #default="{ row }">
          <el-tag v-if="row.category_l1" size="small" type="info">{{ row.category_l1 }}</el-tag>
          <el-tag v-if="row.category_l2" size="small" style="margin-left: 4px">{{ row.category_l2 }}</el-tag>
          <span v-if="!row.category_l1 && !row.category_l2" class="unclassified">未分类</span>
        </template>
      </el-table-column>
      <el-table-column label="根因分析（真实问题描述）" min-width="280">
        <template #default="{ row }">
          <div v-if="row.root_cause" class="rc-cell">
            <div class="rc-text">{{ row.root_cause }}</div>
            <div class="rc-tags">
              <el-tag size="small" type="info">{{ row.fault_system || '—' }}</el-tag>
              <el-tag size="small" type="info">{{ row.fault_stage || '—' }}</el-tag>
              <el-tag size="small" :type="row.fault_type === '无缺陷' ? 'success' : 'warning'">
                {{ row.fault_type || '—' }}
              </el-tag>
              <el-link
                v-if="row.rootcause_no"
                type="primary"
                :underline="false"
                class="rc-no"
                @click="goRootcause(row)"
              >{{ row.rootcause_no }}</el-link>
            </div>
          </div>
          <div v-else class="unclassified">
            {{ row.rc_status === 'low' ? '根因待人工' : '待根因分析' }}
          </div>
        </template>
      </el-table-column>
      <el-table-column label="批量" width="76" align="center">
        <template #default="{ row }">
          <el-link v-if="row.cluster_key" type="danger" size="small" @click="openCluster(row)">
            {{ row.cluster_key.split('@')[1] || '簇' }}
          </el-link>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="AI 归类" width="118" align="center">
        <template #default="{ row }">
          <el-tag
            :type="{ ai: 'success', ai_low: 'warning', manual: 'primary' }[row.classify_by] || 'info'"
            size="small"
          >
            {{ { ai: 'AI 归类', ai_low: '待确认', manual: '人工校正', auto: '待分析' }[row.classify_by] || row.classify_by }}
          </el-tag>
          <div v-if="row.ai_confidence !== null && row.ai_confidence !== undefined" class="conf-line" :class="row.ai_confidence >= 0.75 ? 'conf-hi' : 'conf-low'">
            {{ row.ai_confidence.toFixed(2) }}
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="handler" label="处理人" width="92" show-overflow-tooltip />
      <el-table-column prop="dispatch_count" label="派单" width="60" align="center" />
      <el-table-column prop="status" label="状态" width="84" />
      <el-table-column prop="content_preview" label="工单内容" min-width="260" show-overflow-tooltip />
      <el-table-column label="操作" width="150" fixed="right" align="center">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="openCorrect(row)">校正分类</el-button>
          <el-button size="small" text type="primary" @click="openRootcause(row)">根因</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager-bar">
      <el-pagination
        v-model:current-page="pager.page"
        v-model:page-size="pager.pageSize"
        :total="pager.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="load"
        @size-change="load"
      />
    </div>

    <!-- 人工校正对话框 -->
    <el-dialog v-model="correctVisible" title="人工校正分类" width="480px">
      <el-alert type="warning" :closable="false" show-icon class="correct-tip">
        校正后该单标记为「人工校正」，AI 重跑归类不会覆盖，且将作为样例回流提升 AI 归类准确率。
      </el-alert>
      <el-form label-width="88px" size="default">
        <el-form-item label="问题性质">
          <el-select v-model="correctForm.l1" filterable style="width: 100%" @change="correctForm.l2 = ''">
            <el-option v-for="x in l1Options" :key="x" :label="x" :value="x" />
          </el-select>
        </el-form-item>
        <el-form-item label="问题场景">
          <el-select v-model="correctForm.l2" filterable clearable style="width: 100%">
            <el-option v-for="x in l2OptionsOf(correctForm.l1)" :key="x" :label="x" :value="x" />
          </el-select>
        </el-form-item>
        <el-form-item label="校正备注">
          <el-input v-model="correctForm.remark" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="correctVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveCorrect">保存</el-button>
      </template>
    </el-dialog>

    <ClusterDrawer v-model="clusterVisible" :cluster="clusterRow" :week="filters.week || metricsWeek" />

    <!-- 根因校正（2026-11-03 根因深化：根因是批量识别与方案制定的基础数据）-->
    <el-dialog v-model="rcVisible" title="人工确认根因" width="660px">
      <el-alert type="warning" :closable="false" show-icon class="correct-tip">
        人工确认后该单标记为「人工确认」，AI 重跑不覆盖，并回流作为根因归并样例。
      </el-alert>
      <el-form label-width="92px">
        <el-form-item label="工单">
          <span>{{ rcForm.ticket_no }}</span>
        </el-form-item>
        <el-form-item label="真实根因">
          <el-input
            v-model="rcForm.root_cause"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            placeholder="写清哪个系统 + 哪个环节 + 具体报错/字段/状态 + 影响什么"
          />
        </el-form-item>
        <el-form-item label="故障环节">
          <el-select v-model="rcForm.fault_stage" clearable style="width: 100%">
            <el-option v-for="x in rcMeta.fault_stages" :key="x" :label="x" :value="x" />
          </el-select>
        </el-form-item>
        <el-form-item label="涉及系统">
          <el-select v-model="rcForm.fault_system" clearable style="width: 100%">
            <el-option v-for="x in rcMeta.fault_systems" :key="x" :label="x" :value="x" />
          </el-select>
        </el-form-item>
        <el-form-item label="缺陷性质">
          <el-select v-model="rcForm.fault_type" clearable style="width: 100%">
            <el-option v-for="x in rcMeta.fault_types" :key="x" :label="x" :value="x" />
          </el-select>
        </el-form-item>
        <el-form-item label="责任归属">
          <el-select v-model="rcForm.own_party" clearable style="width: 100%">
            <el-option v-for="x in rcMeta.own_parties" :key="x" :label="x" :value="x" />
          </el-select>
        </el-form-item>
        <el-form-item label="处置方式">
          <el-select v-model="rcForm.fix_mode" clearable style="width: 100%">
            <el-option v-for="x in rcMeta.fix_modes" :key="x" :label="x" :value="x" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rcVisible = false">取消</el-button>
        <el-button type="primary" :loading="rcSaving" @click="saveRootcause">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import PageHeader from '@/components/Common/PageHeader.vue'
import CategoryDictPopover from './components/CategoryDictPopover.vue'
import ClusterDrawer from './components/ClusterDrawer.vue'
import { complaintApi } from '@/api/complaint'

const router = useRouter()
const loading = ref(false)
const rows = ref([])
const pager = reactive({ page: 1, pageSize: 20, total: 0 })
const filters = reactive({ week: '', l1: '', l2: '', classify_by: '', rc_status: '', is_batch: null, keyword: '' })

const metricsWeek = ref('')
const categories = ref([])
const correctVisible = ref(false)
const saving = ref(false)
const correctForm = reactive({ id: null, l1: '', l2: '', remark: '' })
const clusterVisible = ref(false)
const clusterRow = ref(null)

// 根因校正
const rcVisible = ref(false)
const rcSaving = ref(false)
const rcMeta = ref({ fault_stages: [], fault_systems: [], fault_types: [], own_parties: [], fix_modes: [] })
const rcForm = reactive({
  id: null, ticket_no: '', root_cause: '', fault_stage: '', fault_system: '',
  fault_type: '', own_party: '', fix_mode: '',
})

const subTitle = computed(() =>
  `共 ${pager.total} 条｜口径唯一来源：pmwb_complaint_category 字典表｜人工校正不被自动重跑覆盖`
)

const l1Options = computed(() =>
  categories.value.filter(c => c.level === 1 && c.enabled).map(c => c.name)
)
const l2Options = computed(() =>
  categories.value.filter(c => c.level === 2 && c.enabled).map(c => c.name)
)
function l2OptionsOf(l1) {
  return categories.value.filter(c => c.level === 2 && c.enabled && c.parent_name === l1).map(c => c.name)
}
const weekOptions = computed(() => {
  const s = new Set(rows.value.map(r => r.week).filter(Boolean))
  if (metricsWeek.value) s.add(metricsWeek.value)
  return [...s].sort().reverse()
})

async function load() {
  loading.value = true
  try {
    const params = {
      page: pager.page, page_size: pager.pageSize,
      week: filters.week || undefined,
      l1: filters.l1 || undefined,
      l2: filters.l2 || undefined,
      classify_by: filters.classify_by || undefined,
      rc_status: filters.rc_status || undefined,
      is_batch: filters.is_batch ?? undefined,
      keyword: filters.keyword || undefined,
    }
    const data = await complaintApi.listTickets(params)
    rows.value = data.items || []
    pager.total = data.total || 0
  } catch (e) {
    rows.value = []
  } finally {
    loading.value = false
  }
}

async function loadMeta() {
  try {
    const [cats, metrics, rcmeta] = await Promise.all([
      complaintApi.listCategories(),
      complaintApi.getMetrics().catch(() => ({})),
      complaintApi.rootcauseMeta().catch(() => null),
    ])
    categories.value = cats
    metricsWeek.value = metrics.week || ''
    if (rcmeta && rcmeta.fault_stages) rcMeta.value = rcmeta
  } catch (e) { /* request 已提示 */ }
}

function openRootcause(row) {
  rcForm.id = row.id
  rcForm.ticket_no = row.ticket_no
  rcForm.root_cause = row.root_cause || ''
  rcForm.fault_stage = row.fault_stage || ''
  rcForm.fault_system = row.fault_system || ''
  rcForm.fault_type = row.fault_type || ''
  rcForm.own_party = row.own_party || ''
  rcForm.fix_mode = row.fix_mode || ''
  rcVisible.value = true
}

async function saveRootcause() {
  rcSaving.value = true
  try {
    const res = await complaintApi.correctTicketRootcause(rcForm.id, {
      root_cause: rcForm.root_cause,
      fault_stage: rcForm.fault_stage,
      fault_system: rcForm.fault_system,
      fault_type: rcForm.fault_type,
      own_party: rcForm.own_party,
      fix_mode: rcForm.fix_mode,
      repro: 'unknown',
      evidence: '',
    })
    if (res && res.quality_warnings && res.quality_warnings.length) {
      ElMessage.warning(`已保存，但根因仍偏笼统：${res.quality_warnings.join('；')}`)
    } else {
      ElMessage.success('根因已确认')
    }
    rcVisible.value = false
    load()
  } catch (e) { /* request 已提示 */ } finally {
    rcSaving.value = false
  }
}

function goRootcause(row) {
  router.push({ path: '/complaint-center/rootcause', query: { keyword: row.rootcause_no } })
}

function openCorrect(row) {
  correctForm.id = row.id
  correctForm.l1 = row.category_l1 || ''
  correctForm.l2 = row.category_l2 || ''
  correctForm.remark = row.remark || ''
  correctVisible.value = true
}

async function saveCorrect() {
  saving.value = true
  try {
    await complaintApi.correctCategory(correctForm.id, {
      category_l1: correctForm.l1,
      category_l2: correctForm.l2 || '',
      remark: correctForm.remark || null,
    })
    ElMessage.success('分类已校正（标记为人工）')
    correctVisible.value = false
    load()
  } catch (e) { /* request 已提示 */ } finally {
    saving.value = false
  }
}

function openCluster(row) {
  clusterRow.value = { key: row.cluster_key, l2: row.category_l2, date: (row.cluster_key || '').split('@')[1] }
  clusterVisible.value = true
}

onMounted(async () => {
  await loadMeta()
  load()
})
</script>

<style scoped>
.conf-line {
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}
.conf-hi { color: var(--success); font-weight: 600; }
.conf-low { color: var(--warning); font-weight: 600; }
.rc-cell {
  line-height: 1.5;
}
.rc-text {
  font-size: 13px;
  color: var(--text-primary);
}
.rc-tags {
  display: flex;
  gap: 4px;
  align-items: center;
  margin-top: 3px;
  flex-wrap: wrap;
}
.rc-no {
  font-size: 12px;
  font-weight: 600;
}
</style>
