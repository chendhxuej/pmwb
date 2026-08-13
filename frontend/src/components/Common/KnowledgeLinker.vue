<template>
  <div class="knowledge-linker">
    <div class="kl-header">
      <span class="kl-title">
        <el-icon><Link /></el-icon>
        关联业务知识
        <el-tag v-if="links.length" size="small" type="success">{{ links.length }}</el-tag>
      </span>
      <el-button size="small" type="primary" link @click="openPicker">+ 关联</el-button>
    </div>

    <div v-if="loading" class="kl-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
    </div>
    <div v-else-if="links.length === 0" class="kl-empty">尚未关联业务知识笔记</div>
    <div v-else class="kl-list">
      <div v-for="lk in links" :key="lk.link_id" class="kl-item">
        <span class="kl-name" :title="lk.title" @click="openNote(lk)">{{ lk.title }}</span>
        <div class="kl-ops">
          <el-button size="small" link type="primary" @click="openNote(lk)">查看</el-button>
          <el-button size="small" link type="danger" @click="removeLink(lk)">取消</el-button>
        </div>
      </div>
    </div>

    <!-- 关联选择弹窗 -->
    <el-dialog v-model="pickerVisible" title="关联业务知识笔记" width="820px" append-to-body @open="onPickerOpen">
      <div class="kl-filters">
        <div class="kl-filter-item" style="flex: 1 1 220px">
          <label class="kl-fl">业务领域</label>
          <BusinessDomainSelect v-model="filterDomain" @change="onFilterChange" />
        </div>
        <div class="kl-filter-item" style="flex: 0 0 150px">
          <label class="kl-fl">标签</label>
          <el-select v-model="filterTag" placeholder="全部标签" clearable filterable style="width: 100%" @change="onFilterChange">
            <el-option v-for="t in tagOptions" :key="t" :label="t" :value="t" />
          </el-select>
        </div>
        <div class="kl-filter-item" style="flex: 1 1 200px">
          <label class="kl-fl">关键词</label>
          <EnlargeInput v-model="kw" placeholder="搜索标题 / 关键词" clearable />
        </div>
      </div>
      <el-table
        ref="tableRef"
        :data="candidates"
        height="340"
        class="kl-table"
        v-loading="loadingCandidates"
        @selection-change="onSelect"
        :row-class-name="rowCls"
      >
        <el-table-column type="selection" width="46" :selectable="rowSelectable" />
        <el-table-column prop="title" label="笔记标题" min-width="200" show-overflow-tooltip />
        <el-table-column label="领域" width="130" show-overflow-tooltip>
          <template #default="{ row }">{{ domainName(row.domain_code) }}</template>
        </el-table-column>
        <el-table-column label="类型" width="110" show-overflow-tooltip>
          <template #default="{ row }">{{ typeLabel(row.category) }}</template>
        </el-table-column>
        <el-table-column prop="summary" label="摘要" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.summary">{{ row.summary }}</span>
            <span v-else class="kl-muted">—</span>
          </template>
        </el-table-column>
      </el-table>
      <div class="kl-pager">
        <span class="kl-total">共 {{ total }} 条</span>
        <el-pagination
          layout="prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          small
          @current-change="onPageChange"
        />
      </div>
      <template #footer>
        <el-button @click="pickerVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!selected.length" @click="confirmLink">
          关联选中（{{ selected.length }}）
        </el-button>
      </template>
    </el-dialog>

    <!-- 笔记内容预览 -->
    <el-dialog v-model="contentVisible" :title="activeNote?.title || '笔记内容'" width="760px" append-to-body>
      <pre class="kl-content">{{ activeContent || '（空）' }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { knowledgeApi } from '@/api/knowledge.js'
import { basicDataApi } from '@/api/basicData.js'
import BusinessDomainSelect from '@/components/Common/BusinessDomainSelect.vue'
import EnlargeInput from '@/components/Common/EnlargeInput.vue'

const props = defineProps({
  sourceType: { type: String, required: true }, // requirement / ticket / operation / meeting
  sourceId: { type: [String, Number], required: true },
  domainCode: { type: String, default: '' },
})

// 知识大类（category）友好中文；其余中文值原样显示
const TYPE_LABEL = { meeting: '会议', product: '产品', requirement: '需求' }

const links = ref([])
const loading = ref(false)
const pickerVisible = ref(false)
const kw = ref('')
const candidates = ref([])
const selected = ref([])
const selectedMap = ref(new Map())
const tableRef = ref(null)
const contentVisible = ref(false)
const activeNote = ref(null)
const activeContent = ref('')

// 筛选与分页
const filterDomain = ref('')
const filterTag = ref('')
const tagOptions = ref([])
const domainMap = ref({})
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const linkedSet = ref(new Set())
const loadingCandidates = ref(false)

const fetchLinks = async () => {
  if (!props.sourceId) {
    links.value = []
    return
  }
  loading.value = true
  try {
    const data = await knowledgeApi.getLinks(props.sourceType, String(props.sourceId))
    links.value = data || []
    linkedSet.value = new Set(links.value.map((l) => l.knowledge_item_id))
  } catch {
    links.value = []
  } finally {
    loading.value = false
  }
}

const domainName = (code) => domainMap.value[code] || code || '—'
const typeLabel = (c) => TYPE_LABEL[c] || c || '—'

const loadDomains = async () => {
  try {
    const tree = await basicDataApi.getBusinessDomains({ tree: true })
    const m = {}
    for (const g of tree || []) {
      m[g.domain_code] = g.domain_name
      for (const ch of g.children || []) m[ch.domain_code] = ch.domain_name
    }
    domainMap.value = m
  } catch {
    // 静默失败
  }
}

const loadTags = async () => {
  try {
    tagOptions.value = (await knowledgeApi.getTags()) || []
  } catch {
    tagOptions.value = []
  }
}

let kwTimer = null
watch(kw, () => {
  clearTimeout(kwTimer)
  kwTimer = setTimeout(() => {
    page.value = 1
    searchNotes()
  }, 300)
})

const onFilterChange = () => {
  page.value = 1
  searchNotes()
}
const onPageChange = (p) => {
  page.value = p
  searchNotes()
}

const searchNotes = async () => {
  loadingCandidates.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (kw.value) params.keyword = kw.value
    if (filterDomain.value) params.domain_code = filterDomain.value
    if (filterTag.value) params.tag = filterTag.value
    const data = await knowledgeApi.listItems(params)
    candidates.value = data?.items || []
    total.value = data?.total || 0
  } catch {
    candidates.value = []
  } finally {
    loadingCandidates.value = false
  }
}

const onPickerOpen = async () => {
  selectedMap.value.clear()
  selected.value = []
  kw.value = ''
  filterDomain.value = props.domainCode || ''
  filterTag.value = ''
  page.value = 1
  await Promise.all([loadDomains(), loadTags()])
  await searchNotes()
}

const openPicker = () => {
  pickerVisible.value = true
}

const rowSelectable = (row) => !linkedSet.value.has(row.id)
const rowCls = ({ row }) => (linkedSet.value.has(row.id) ? 'kl-row-linked' : '')

const onSelect = (rows) => {
  // 合并当前页选中，支持跨页累积
  for (const c of candidates.value) selectedMap.value.delete(c.id)
  for (const r of rows) selectedMap.value.set(r.id, r)
  selected.value = [...selectedMap.value.values()]
}

const confirmLink = async () => {
  const toLink = selected.value.filter((i) => !linkedSet.value.has(i.id))
  if (!toLink.length) return
  try {
    for (const item of toLink) {
      await knowledgeApi.createLink({
        source_type: props.sourceType,
        source_id: String(props.sourceId),
        knowledge_item_id: item.id,
        domain_code: props.domainCode || item.domain_code || null,
      })
    }
    ElMessage.success(`已关联 ${toLink.length} 条知识笔记`)
    pickerVisible.value = false
    await fetchLinks()
  } catch (e) {
    ElMessage.error('关联失败：' + (e.message || '未知错误'))
  }
}

const removeLink = async (lk) => {
  try {
    await knowledgeApi.deleteLink(lk.link_id)
    ElMessage.success('已取消关联')
    await fetchLinks()
  } catch {
    ElMessage.error('取消关联失败')
  }
}

const openNote = async (lk) => {
  activeNote.value = lk
  activeContent.value = ''
  contentVisible.value = true
  try {
    const data = await knowledgeApi.getItemContent(lk.knowledge_item_id)
    activeContent.value = data?.content || ''
  } catch {
    activeContent.value = '（内容读取失败）'
  }
}

watch(() => props.sourceId, fetchLinks, { immediate: true })
onMounted(fetchLinks)
</script>

<style scoped>
.knowledge-linker {
  border: 1px solid var(--border-subtle, #e4e7ed);
  border-radius: 8px;
  padding: 12px;
  margin-top: 12px;
  background: var(--bg-secondary, #fafafa);
}
.kl-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #303133);
}
.kl-title {
  display: flex;
  align-items: center;
  gap: 6px;
}
.kl-loading,
.kl-empty {
  text-align: center;
  padding: 16px 0;
  font-size: 12.5px;
  color: var(--text-secondary, #909399);
}
.kl-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 260px;
  overflow-y: auto;
}
.kl-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  border-radius: 6px;
  background: #fff;
  font-size: 12.5px;
}
.kl-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
  color: var(--text-primary, #303133);
}
.kl-name:hover {
  color: var(--el-color-primary, #409eff);
}
.kl-ops {
  display: flex;
  gap: 4px;
}
.kl-filters {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.kl-filter-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.kl-fl {
  font-size: 12px;
  color: var(--text-secondary, #909399);
}
.kl-table {
  margin-top: 4px;
}
.kl-row-linked {
  opacity: 0.55;
}
.kl-muted {
  color: var(--text-secondary, #909399);
}
.kl-pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
}
.kl-total {
  font-size: 12.5px;
  color: var(--text-secondary, #909399);
}
.kl-content {
  max-height: 60vh;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.6;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
</style>
