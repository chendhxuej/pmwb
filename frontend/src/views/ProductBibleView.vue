<template>
  <div class="product-bible">
    <div class="pb-header">
      <div class="pb-title-row">
        <h2 class="page-title">产品圣经</h2>
        <el-radio-group v-model="activeKey" @change="loadBible" size="default">
          <el-radio-button v-for="b in catalog" :key="b.key" :value="b.key">
            {{ b.name }}
          </el-radio-button>
        </el-radio-group>
        <div class="pb-actions">
          <template v-if="!editing && format !== 'docx'">
            <el-button size="small" @click="startEdit">
              <el-icon><Edit /></el-icon><span>编辑内容</span>
            </el-button>
          </template>
          <template v-else>
            <el-button size="small" type="primary" :loading="saving" @click="saveEdit">
              <el-icon><Check /></el-icon><span>保存</span>
            </el-button>
            <el-button size="small" :disabled="saving" @click="cancelEdit">取消</el-button>
          </template>
        </div>
      </div>

      <el-card v-if="meta.title && !editing" class="meta-card" shadow="never">
        <div class="meta-item">
          <span class="meta-label">业务线</span><span class="meta-value">{{ meta.name }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">文档</span><span class="meta-value">{{ meta.title }}</span>
        </div>
        <div class="meta-item" v-if="meta.updated_at">
          <span class="meta-label">更新日期</span><span class="meta-value">{{ meta.updated_at }}</span>
        </div>
      </el-card>
    </div>

    <div class="pb-body" v-loading="loading">
      <aside class="pb-toc" v-if="!editing">
        <div class="toc-search">
          <el-icon class="toc-search-icon"><Search /></el-icon>
          <input
            v-model="searchKw"
            class="toc-search-input"
            type="text"
            placeholder="关键字查询…"
            @input="onSearchInput"
            @keyup.enter="onSearchNext"
          />
          <template v-if="searchKw">
            <span class="toc-search-count">
              {{ matchCount ? matchIndex + '/' + matchCount : '0' }}
            </span>
            <el-icon class="toc-search-nav" title="上一个" @click="onSearchPrev"><ArrowUp /></el-icon>
            <el-icon class="toc-search-nav" title="下一个" @click="onSearchNext"><ArrowDown /></el-icon>
            <el-icon class="toc-search-nav" title="清除" @click="onSearchClear"><Close /></el-icon>
          </template>
        </div>
        <div class="toc-title">目录</div>
        <ul class="toc-list">
          <li v-for="node in tocTree" :key="node.id" class="toc-group">
            <div
              class="toc-item toc-level-2"
              :class="{ active: activeToc === node.id }"
              @click="scrollTo(node.id)"
            >
              <span class="toc-caret" @click.stop="toggle(node.id)">
                {{ expandedMap[node.id] ? '▾' : '▸' }}
              </span>
              <span class="toc-text">{{ node.text }}</span>
            </div>
            <ul v-show="expandedMap[node.id]" class="toc-children">
              <li
                v-for="child in node.children"
                :key="child.id"
                class="toc-item toc-level-3"
                :class="{ active: activeToc === child.id }"
                @click="scrollTo(child.id)"
              >
                {{ child.text }}
              </li>
            </ul>
          </li>
        </ul>
      </aside>

      <main class="pb-content">
        <template v-if="!editing">
          <MarkdownRender ref="mdRef" :content="markdown" @toc="onToc" />
        </template>
        <template v-else>
          <div class="edit-hint">
            直接编辑下方 Markdown 源码，保存后写回 Obsidian 文件，页面立即生效。
            <b>mermaid</b> 代码块、表格请保持原始格式，避免损坏。
          </div>
          <el-input
            v-model="editContent"
            type="textarea"
            class="edit-area"
            :autosize="false"
            resize="none"
          />
        </template>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { productBibleApi } from '@/api/productBible'
import MarkdownRender from '@/components/Common/MarkdownRender.vue'

const catalog = ref([])
const activeKey = ref('')
const loading = ref(false)
const markdown = ref('')
const toc = ref([])
const activeToc = ref('')

// 搜索
const mdRef = ref(null)
const searchKw = ref('')
const matchCount = ref(0)
const matchIndex = ref(0)

// 编辑
const editing = ref(false)
const editContent = ref('')
const saving = ref(false)

// 目录树折叠状态（key=H2 id）
const expandedMap = reactive({})

const meta = reactive({
  name: '',
  title: '',
  updated_at: '',
})
const format = ref('markdown')

const tocTree = computed(() => {
  const tree = []
  let current = null
  toc.value.forEach((t) => {
    if (t.level === 2) {
      current = { id: t.id, text: t.text, children: [] }
      tree.push(current)
    } else if (t.level === 3 && current) {
      current.children.push({ id: t.id, text: t.text })
    }
  })
  return tree
})

let observer = null

const loadCatalog = async () => {
  try {
    const res = await productBibleApi.getCatalog()
    catalog.value = res || []
    if (!activeKey.value && catalog.value.length) {
      activeKey.value = catalog.value[0].key
      await loadBible(activeKey.value)
    }
  } catch (e) {
    ElMessage.error('加载业务目录失败')
  }
}

const loadBible = async (key) => {
  if (!key) return
  loading.value = true
  // 切换业务时重置搜索与编辑态
  onSearchClear()
  editing.value = false
  try {
    const res = await productBibleApi.getBible(key)
    meta.name = res.name
    meta.title = res.title
    meta.updated_at = res.updated_at
    format.value = res.format || 'markdown'
    markdown.value = res.markdown
  } catch (e) {
    ElMessage.error('加载产品圣经内容失败')
    markdown.value = ''
  } finally {
    loading.value = false
  }
}

const onToc = async (list) => {
  toc.value = list || []
  const map = {}
  list.forEach((t) => {
    if (t.level === 2) map[t.id] = true
  })
  Object.assign(expandedMap, map)
  activeToc.value = toc.value.length ? toc.value[0].id : ''
  await nextTick()
  setupSpy()
}

const scrollTo = (id) => {
  const el = document.getElementById(id)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const toggle = (id) => {
  expandedMap[id] = !expandedMap[id]
}

// ---- 搜索 ----
const onSearchInput = () => {
  if (!mdRef.value) return
  const c = mdRef.value.search(searchKw.value.trim())
  matchCount.value = c
  matchIndex.value = c > 0 ? 1 : 0
}

const onSearchNext = () => {
  if (!mdRef.value || matchCount.value === 0) return
  const i = mdRef.value.next()
  matchIndex.value = (i >= 0 ? i : 0) + 1
}

const onSearchPrev = () => {
  if (!mdRef.value || matchCount.value === 0) return
  const i = mdRef.value.prev()
  matchIndex.value = (i >= 0 ? i : 0) + 1
}

const onSearchClear = () => {
  searchKw.value = ''
  matchCount.value = 0
  matchIndex.value = 0
  if (mdRef.value) mdRef.value.clear()
}

// ---- 编辑 ----
const startEdit = () => {
  if (format.value === 'docx') return
  editContent.value = markdown.value
  editing.value = true
  onSearchClear()
}

const cancelEdit = () => {
  editing.value = false
  editContent.value = ''
}

const saveEdit = async () => {
  try {
    await ElMessageBox.confirm(
      '保存后将直接覆盖 Obsidian 中的源文件，且不可撤销。确认保存？',
      '保存确认',
      { type: 'warning', confirmButtonText: '确认保存', cancelButtonText: '再想想' }
    )
  } catch {
    return
  }
  saving.value = true
  try {
    await productBibleApi.updateBible(activeKey.value, editContent.value)
    markdown.value = editContent.value
    editing.value = false
    ElMessage.success('已保存，Obsidian 文件已更新')
  } catch (e) {
    ElMessage.error('保存失败：' + (e?.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

const setupSpy = () => {
  if (observer) observer.disconnect()
  observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) activeToc.value = e.target.id
      })
    },
    { rootMargin: '-80px 0px -65% 0px', threshold: 0 }
  )
  toc.value.forEach((t) => {
    const el = document.getElementById(t.id)
    if (el) observer.observe(el)
  })
}

onMounted(loadCatalog)
onBeforeUnmount(() => {
  if (observer) observer.disconnect()
})
</script>

<style scoped>
.product-bible {
  padding: 20px 24px;
  height: 100%;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1f2d3d;
}

.pb-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 14px;
}

.meta-card {
  margin-bottom: 16px;
  background: #f8fafc;
}

.meta-card :deep(.el-card__body) {
  display: flex;
  gap: 32px;
  padding: 14px 18px;
  flex-wrap: wrap;
}

.meta-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 14px;
}

.meta-label {
  color: #909399;
  font-size: 13px;
}

.meta-value {
  color: #303133;
  font-weight: 600;
}

.pb-body {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}

.pb-toc {
  width: 240px;
  flex: 0 0 240px;
  position: sticky;
  top: 16px;
  max-height: calc(100vh - 140px);
  overflow-y: auto;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 14px 10px;
}

.toc-title {
  font-size: 13px;
  font-weight: 600;
  color: #909399;
  padding: 0 8px 10px;
  border-bottom: 1px solid #f0f2f5;
  margin-bottom: 8px;
}

.toc-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.toc-item {
  padding: 6px 8px;
  font-size: 13.5px;
  color: #606266;
  cursor: pointer;
  border-radius: 6px;
  line-height: 1.5;
  transition: all 0.15s;
}

.toc-item:hover {
  background: #f0f7ff;
  color: #409eff;
}

.toc-level-3 {
  padding-left: 22px;
  font-size: 13px;
}

.toc-item.active {
  background: #ecf5ff;
  color: #409eff;
  font-weight: 600;
}

.pb-content {
  flex: 1;
  min-width: 0;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 28px 32px;
  min-height: 60vh;
}

.pb-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.pb-actions .el-button span {
  margin-left: 4px;
}

/* TOC 搜索 */
.toc-search {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 8px 10px;
  border-bottom: 1px solid #f0f2f5;
  margin-bottom: 8px;
}

.toc-search-icon {
  color: #c0c4cc;
  font-size: 15px;
}

.toc-search-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  font-size: 13px;
  color: #303133;
  background: transparent;
}

.toc-search-count {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}

.toc-search-nav {
  cursor: pointer;
  color: #909399;
  font-size: 14px;
  transition: color 0.15s;
}

.toc-search-nav:hover {
  color: #409eff;
}

/* 目录树折叠 */
.toc-caret {
  display: inline-block;
  width: 16px;
  color: #909399;
  font-size: 12px;
  cursor: pointer;
  user-select: none;
}

.toc-children {
  list-style: none;
  margin: 0;
  padding: 0;
}

/* 编辑区 */
.edit-hint {
  font-size: 13px;
  color: #909399;
  background: #f4f8ff;
  border: 1px solid #d9ecff;
  border-radius: 6px;
  padding: 10px 14px;
  margin-bottom: 14px;
  line-height: 1.6;
}

.edit-area {
  width: 100%;
}

.edit-area :deep(textarea) {
  height: 68vh;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #303133;
  white-space: pre;
  overflow: auto;
}

@media (max-width: 900px) {
  .pb-toc {
    display: none;
  }
}
</style>
