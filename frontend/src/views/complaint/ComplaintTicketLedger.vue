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
      <el-select v-model="filters.classify_by" placeholder="分类来源" clearable style="width: 118px" @change="load">
        <el-option label="自动分类" value="auto" />
        <el-option label="人工校正" value="manual" />
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

    <el-table v-loading="loading" :data="rows" size="default" border stripe>
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
      <el-table-column label="批量" width="76" align="center">
        <template #default="{ row }">
          <el-link v-if="row.cluster_key" type="danger" size="small" @click="openCluster(row)">
            {{ row.cluster_key.split('@')[1] || '簇' }}
          </el-link>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="分类来源" width="86" align="center">
        <template #default="{ row }">
          <el-tag :type="row.classify_by === 'manual' ? 'warning' : 'info'" size="small">
            {{ row.classify_by === 'manual' ? '人工' : '自动' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="handler" label="处理人" width="92" show-overflow-tooltip />
      <el-table-column prop="dispatch_count" label="派单" width="60" align="center" />
      <el-table-column prop="status" label="状态" width="84" />
      <el-table-column prop="content_preview" label="工单内容" min-width="260" show-overflow-tooltip />
      <el-table-column label="操作" width="92" fixed="right" align="center">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="openCorrect(row)">校正分类</el-button>
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
        校正后该单标记为「人工」，字典重跑分类不会覆盖。
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
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import PageHeader from '@/components/Common/PageHeader.vue'
import CategoryDictPopover from './components/CategoryDictPopover.vue'
import ClusterDrawer from './components/ClusterDrawer.vue'
import { complaintApi } from '@/api/complaint'

const loading = ref(false)
const rows = ref([])
const pager = reactive({ page: 1, pageSize: 20, total: 0 })
const filters = reactive({ week: '', l1: '', l2: '', classify_by: '', is_batch: null, keyword: '' })

const metricsWeek = ref('')
const categories = ref([])
const correctVisible = ref(false)
const saving = ref(false)
const correctForm = reactive({ id: null, l1: '', l2: '', remark: '' })
const clusterVisible = ref(false)
const clusterRow = ref(null)

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
    const [cats, metrics] = await Promise.all([
      complaintApi.listCategories(),
      complaintApi.getMetrics().catch(() => ({})),
    ])
    categories.value = cats
    metricsWeek.value = metrics.week || ''
  } catch (e) { /* request 已提示 */ }
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
