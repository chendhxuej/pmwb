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
    <el-dialog v-model="pickerVisible" title="关联业务知识笔记" width="680px" append-to-body>
      <el-input
        v-model="kw"
        placeholder="按标题/关键字搜索（留空显示当前领域笔记）"
        clearable
        @input="searchNotes"
      />
      <el-table
        ref="tableRef"
        :data="candidates"
        height="320"
        class="kl-table"
        @selection-change="onSelect"
      >
        <el-table-column type="selection" width="46" />
        <el-table-column prop="title" label="笔记标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="domain_code" label="领域" width="120" show-overflow-tooltip />
        <el-table-column prop="sub_category" label="类型" width="120" show-overflow-tooltip />
      </el-table>
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

const props = defineProps({
  sourceType: { type: String, required: true }, // requirement / ticket / operation / meeting
  sourceId: { type: [String, Number], required: true },
  domainCode: { type: String, default: '' },
})

const links = ref([])
const loading = ref(false)
const pickerVisible = ref(false)
const kw = ref('')
const candidates = ref([])
const selected = ref([])
const tableRef = ref(null)
const contentVisible = ref(false)
const activeNote = ref(null)
const activeContent = ref('')

const fetchLinks = async () => {
  if (!props.sourceId) {
    links.value = []
    return
  }
  loading.value = true
  try {
    const data = await knowledgeApi.getLinks(props.sourceType, String(props.sourceId))
    links.value = data || []
  } catch {
    links.value = []
  } finally {
    loading.value = false
  }
}

const searchNotes = async () => {
  try {
    const params = { page_size: 100 }
    if (kw.value) params.keyword = kw.value
    else if (props.domainCode) params.domain_code = props.domainCode
    const data = await knowledgeApi.listItems(params)
    const items = data?.items || []
    // 过滤掉已关联的
    const linkedIds = new Set(links.value.map((l) => l.knowledge_item_id))
    candidates.value = items.filter((i) => !linkedIds.has(i.id))
  } catch {
    candidates.value = []
  }
}

const openPicker = async () => {
  selected.value = []
  kw.value = ''
  await searchNotes()
  pickerVisible.value = true
}

const onSelect = (rows) => {
  selected.value = rows
}

const confirmLink = async () => {
  if (!selected.value.length) return
  try {
    for (const item of selected.value) {
      await knowledgeApi.createLink({
        source_type: props.sourceType,
        source_id: String(props.sourceId),
        knowledge_item_id: item.id,
        domain_code: props.domainCode || item.domain_code || null,
      })
    }
    ElMessage.success(`已关联 ${selected.value.length} 条知识笔记`)
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
.kl-table {
  margin-top: 10px;
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
