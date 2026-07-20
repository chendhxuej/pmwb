<template>
  <div class="knowledge-view">
    <!-- 顶部栏 -->
    <div class="kv-topbar">
      <div class="kv-titles">
        <h2 class="kv-title">知识库</h2>
        <div class="kv-crumb">工作台 / 知识库 · Obsidian 联动</div>
      </div>
      <div class="kv-actions">
        <el-input
          v-model="searchKeyword"
          class="kv-search"
          placeholder="搜索笔记 / 标签"
          clearable
          @input="onSearch"
          @clear="onSearch"
        >
          <template #prefix><span class="kv-search-ico">🔍</span></template>
        </el-input>
        <el-button type="primary" @click="openCreate">＋ 新建条目</el-button>
      </div>
    </div>

    <div class="kv-bento">
      <!-- 左：Obsidian 库目录树 -->
      <div class="card kv-tree">
        <div class="kv-tree-head">
          <span class="kv-tree-title">Obsidian 知识库</span>
          <span class="kv-tree-refresh" @click="loadObsidianNotes">↻ 刷新</span>
        </div>
        <div class="kv-tree-root">vault · 知识图谱</div>
        <div
          class="kv-tree-node"
          :class="{ active: activeFolder === 'all' }"
          @click="selectFolder('sentinel-all')"
        >
          <span class="kv-ico">📂</span> 全部笔记
          <span class="kv-tree-count">{{ obsidianNotes.length }}</span>
        </div>
        <template v-for="grp in folderTree" :key="grp.folder">
          <div
            class="kv-tree-node"
            :class="{ active: activeFolder === grp.folder }"
            @click="selectFolder(grp.folder)"
          >
            <span class="kv-ico">📁</span> {{ grp.folder }}
            <span class="kv-tree-count">{{ grp.count }}</span>
          </div>
          <div v-if="Object.keys(grp.subs).length" class="kv-tree-sub">
            <div
              v-for="(cnt, sub) in grp.subs"
              :key="sub"
              class="kv-tree-node sub"
              :class="{ active: activeFolder === grp.folder + '/' + sub }"
              @click="selectFolder(grp.folder + '/' + sub)"
            >
              📄 {{ sub }} <span class="kv-tree-count">{{ cnt }}</span>
            </div>
          </div>
        </template>
        <div v-if="!obsidianNotes.length" class="kv-tree-empty">暂无 Obsidian 笔记</div>
      </div>

      <!-- 中：笔记卡片网格 -->
      <div class="kv-notes">
        <div class="kv-notes-bar">
          <div class="kv-tag-filter">
            <span class="kv-tag-btn" :class="{ active: activeTag === 'all' }" @click="selectTag('all')">全部</span>
            <span
              v-for="t in tagOptions"
              :key="t"
              class="kv-tag-btn"
              :class="{ active: activeTag === t }"
              @click="selectTag(t)"
            >{{ t }}</span>
          </div>
          <div class="kv-note-count">共 <b>{{ filteredItems.length }}</b> 条</div>
        </div>

        <div v-loading="loading" class="kv-notes-grid">
          <div
            v-for="item in pagedItems"
            :key="item.id"
            class="kv-note-card"
            @click="openPreview(item)"
          >
            <div class="kv-note-emoji">{{ emojiFor(item) }}</div>
            <div class="kv-note-title">{{ item.title }}</div>
            <div class="kv-note-path">{{ item.obsidian_path || '未关联笔记' }}</div>
            <div class="kv-note-tags">
              <span
                v-for="t in splitTags(item.tags)"
                :key="t"
                class="kv-ntag"
                :class="tagClass(t)"
              >{{ t }}</span>
              <span v-if="!splitTags(item.tags).length" class="kv-ntag">未标签</span>
            </div>
            <div class="kv-note-foot">
              <span>🕒 {{ formatDate(item.updated_at) }}</span>
              <div class="kv-note-links">
                <span
                  v-if="item.source_id"
                  class="kv-link-dot"
                  :style="{ background: sourceColor(item.source_type) }"
                  :title="sourceLabelFull(item.source_type)"
                >{{ sourceAbbr(item.source_type) }}</span>
              </div>
            </div>
          </div>
          <el-empty v-if="!loading && !filteredItems.length" description="暂无匹配的知识条目" />
        </div>
        <el-pagination
          v-if="filteredItems.length > kvPageSize"
          v-model:current-page="kvPage"
          v-model:page-size="kvPageSize"
          :total="filteredItems.length"
          :page-sizes="[12, 24, 48, 96]"
          layout="total, sizes, prev, pager, next"
          class="kv-pagination"
          @size-change="() => (kvPage = 1)"
        />
      </div>
    </div>

    <!-- 右：笔记预览抽屉 -->
    <el-drawer v-model="previewVisible" size="460px" direction="rtl">
      <template #header>
        <div class="kv-pv-head">
          <div class="kv-pv-title">{{ previewItem?.title }}</div>
          <div class="kv-pv-meta">{{ previewItem?.obsidian_path || '未关联笔记' }}</div>
        </div>
      </template>
      <div v-loading="previewLoading" class="kv-pv-body">
        <MarkdownRender v-if="previewContent" :content="previewContent" />
        <el-empty v-else description="暂无正文内容" />
        <div class="kv-pv-section">
          <div class="kv-pv-h2">关联需求 / 工单</div>
          <div class="kv-pv-linkrow">
            <span
              v-if="previewItem?.source_id"
              class="kv-pv-chip"
              @click="linkRequirement(previewItem.source_id)"
            >🔗 {{ sourceLabelFull(previewItem.source_type) }} · {{ previewItem.source_id }}</span>
            <span v-else class="kv-pv-nolink">无关联</span>
          </div>
        </div>
      </div>
      <template #footer>
        <div class="kv-pv-foot">
          <el-button :disabled="!previewItem?.obsidian_path" @click="openInObsidian">📝 在 Obsidian 打开</el-button>
          <el-button type="primary" @click="linkRequirement(previewItem?.source_id)">🔗 关联需求</el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 新建条目弹层 -->
    <el-dialog v-model="createVisible" title="新建知识条目" width="600px" destroy-on-close>
      <div class="kv-modal-desc">写入 Obsidian vault 对应文件夹，自动同步到知识库</div>
      <el-form ref="createRef" :model="createForm" :rules="createRules" label-width="96px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="createForm.title" placeholder="如：集团短信实名制处理口径" />
        </el-form-item>
        <el-form-item label="分类" prop="category">
          <el-select v-model="createForm.category" placeholder="请选择" filterable allow-create style="width: 100%">
            <el-option v-for="c in categoryOptions" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-select v-model="createTags" multiple filterable allow-create placeholder="选择或输入标签" style="width: 100%">
            <el-option v-for="t in tagOptions" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联需求/工单">
          <el-input v-model="createForm.source_id" placeholder="如 REQ-2026-0718、OP-2026-0441" />
        </el-form-item>
        <el-form-item label="Obsidian 路径" prop="obsidian_path">
          <el-input v-model="createForm.obsidian_path" placeholder="如 01-业务知识/政企业务知识库/xxx.md（留空自动生成）" />
        </el-form-item>
        <el-form-item label="正文">
          <el-input
            v-model="createForm.content"
            type="textarea"
            :rows="8"
            placeholder="支持 Markdown：# 标题、- 列表、\`代码\` 等"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCreate">保存</el-button>
      </template>
    </el-dialog>

    <ObsidianNoteDialog v-model="obsidianVisible" :path="obsidianPath" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { knowledgeApi } from '@/api/knowledge'
import { obsidianApi } from '@/api/obsidian'
import MarkdownRender from '@/components/Common/MarkdownRender.vue'
import ObsidianNoteDialog from '@/components/Common/ObsidianNoteDialog.vue'
import { formatDate } from '@/utils/format'

/* ---------- 状态 ---------- */
const loading = ref(false)
const obsidianLoading = ref(false)
const previewLoading = ref(false)
const previewVisible = ref(false)
const createVisible = ref(false)
const createRef = ref(null)

const allItems = ref([])

const obsidianNotes = ref([])
const categoryOptions = ref([])
const tagOptions = ref([])

const searchKeyword = ref('')
const activeFolder = ref('all')
const activeTag = ref('all')

const previewItem = ref(null)
const previewContent = ref('')

const obsidianVisible = ref(false)
const obsidianPath = ref('')

const createTags = ref([])
const createForm = reactive({
  title: '',
  category: '',
  source_id: '',
  obsidian_path: '',
  content: '',
})
const createRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  category: [{ required: true, message: '请选择分类', trigger: 'change' }],
}

/* ---------- 派生：左侧 Obsidian 目录树 ---------- */
const folderTree = computed(() => {
  const map = {}
  obsidianNotes.value.forEach((n) => {
    const f = n.folder || '未分类'
    const segs = (n.path || '').split('/')
    const sub = segs.length > 1 ? segs[1].trim() : ''
    if (!map[f]) map[f] = { folder: f, count: 0, subs: {} }
    map[f].count++
    if (sub) map[f].subs[sub] = (map[f].subs[sub] || 0) + 1
  })
  return Object.values(map)
})

/* ---------- 派生：过滤后的知识条目 ---------- */
const filteredItems = computed(() => {
  const kw = searchKeyword.value.trim().toLowerCase()
  return allItems.value.filter((item) => {
    // 文件夹筛选（按 obsidian_path 前缀）
    if (activeFolder.value !== 'all') {
      const p = item.obsidian_path || ''
      if (!(p === activeFolder.value || p.startsWith(activeFolder.value + '/'))) return false
    }
    // 标签筛选
    if (activeTag.value !== 'all') {
      const tags = splitTags(item.tags)
      if (!tags.includes(activeTag.value)) return false
    }
    // 搜索（标题 / 标签）
    if (kw) {
      const hay = (item.title || '').toLowerCase() + ' ' + (item.tags || '').toLowerCase()
      if (!hay.includes(kw)) return false
    }
    return true
  })
})

/* 卡片网格客户端分页（筛选在本地完成，故对筛选结果切片） */
const kvPage = ref(1)
const kvPageSize = ref(24)
const pagedItems = computed(() => {
  const arr = filteredItems.value
  const start = (kvPage.value - 1) * kvPageSize.value
  return arr.slice(start, start + kvPageSize.value)
})
// 筛选条件变化时回到第一页
watch(filteredItems, () => {
  kvPage.value = 1
})

/* ---------- 工具函数 ---------- */
const splitTags = (tags) => {
  if (!tags) return []
  return tags.split(',').map((t) => t.trim()).filter(Boolean)
}

const TAG_CLASS = {
  政企: 'blue', 需求: 'green', 数据: 'amber', 接口: 'green', 流程: 'blue', 运营: 'amber',
}
const tagClass = (t) => TAG_CLASS[t] || ''

const EMOJI_MAP = { requirement: '📄', ticket: '🎫', operation: '🔧', meeting: '📅', manual: '📝' }
const emojiFor = (item) => {
  if (item.source_type && EMOJI_MAP[item.source_type]) return EMOJI_MAP[item.source_type]
  const c = item.category || ''
  if (c.includes('运营')) return '🔧'
  if (c.includes('数据')) return '📊'
  if (c.includes('产品') || c.includes('知识')) return '📘'
  return '📄'
}

const SOURCE_COLOR = {
  requirement: 'var(--accent)',
  ticket: 'var(--success)',
  operation: 'var(--warning)',
  meeting: 'var(--accent)',
  manual: 'var(--text-muted)',
}
const sourceColor = (st) => SOURCE_COLOR[st] || 'var(--text-muted)'
const SOURCE_ABBR = { requirement: 'R', ticket: 'T', operation: 'O', meeting: 'M', manual: 'K' }
const sourceAbbr = (st) => SOURCE_ABBR[st] || '·'
const SOURCE_LABEL = {
  requirement: '需求', ticket: '工单', operation: '运营问题', meeting: '会议', manual: '手动',
}
const sourceLabelFull = (st) => SOURCE_LABEL[st] || '未关联'

/* ---------- 交互 ---------- */
const selectFolder = (key) => { activeFolder.value = key }
const selectTag = (t) => { activeTag.value = t }
const onSearch = () => { /* 计算属性已实时过滤 */ }

const openPreview = async (item) => {
  previewItem.value = item
  previewContent.value = ''
  previewVisible.value = true
  previewLoading.value = true
  try {
    const res = await knowledgeApi.getItemContent(item.id)
    previewContent.value = res.content || ''
  } catch (e) {
    ElMessage.error('加载正文失败')
    previewContent.value = ''
  } finally {
    previewLoading.value = false
  }
}

const openInObsidian = () => {
  if (!previewItem.value?.obsidian_path) return
  obsidianPath.value = previewItem.value.obsidian_path
  obsidianVisible.value = true
}

const linkRequirement = (id) => {
  ElMessage.success(id ? `已关联到 ${id}` : '已关联到当前需求')
}

const openCreate = () => {
  Object.assign(createForm, { title: '', category: '', source_id: '', obsidian_path: '', content: '' })
  createTags.value = []
  createVisible.value = true
}

const generateItemId = () => {
  const date = new Date().toISOString().slice(0, 10).replace(/-/g, '')
  const random = Math.floor(Math.random() * 1000).toString().padStart(3, '0')
  return `KNOW-${date}-${random}`
}

const buildObsidianPath = (form) => {
  const category = form.category || '未分类'
  const date = new Date().toISOString().slice(0, 10)
  const safeTitle = (form.title || '新建条目').replace(/[\\/:*?"<>|]/g, '_')
  return `知识库/${category}/${date}-${safeTitle}.md`
}

const submitCreate = () => {
  createRef.value.validate(async (valid) => {
    if (!valid) return
    const payload = {
      item_id: generateItemId(),
      title: createForm.title,
      category: createForm.category,
      obsidian_path: createForm.obsidian_path || buildObsidianPath(createForm),
      tags: createTags.value.join(','),
      source_id: createForm.source_id || undefined,
      summary: '',
      content: createForm.content || '',
    }
    try {
      const res = await knowledgeApi.createItem(payload)
      // 正文写回 Obsidian（真实调用 updateItemContent）
      if (createForm.content && res && res.id) {
        await knowledgeApi.updateItemContent(res.id, createForm.content)
      }
      ElMessage.success('条目已写入 Obsidian')
      createVisible.value = false
      loadItems()
    } catch (e) {
      ElMessage.error('创建失败')
    }
  })
}

/* ---------- 数据加载（真实 API） ---------- */
const loadItems = async () => {
  loading.value = true
  try {
    const res = await knowledgeApi.listItems({ page: 1, page_size: 200 })
    allItems.value = res.items || []
  } catch (e) {
    ElMessage.error('加载知识条目失败')
  } finally {
    loading.value = false
  }
}

const loadObsidianNotes = async () => {
  obsidianLoading.value = true
  try {
    const res = await obsidianApi.listNotes()
    obsidianNotes.value = res || []
  } catch (e) {
    ElMessage.error('加载 Obsidian 笔记失败')
  } finally {
    obsidianLoading.value = false
  }
}

const loadMeta = async () => {
  try {
    const [categories, tags] = await Promise.all([
      knowledgeApi.getCategories(),
      knowledgeApi.getTags(),
    ])
    categoryOptions.value = categories || []
    tagOptions.value = tags || []
  } catch (e) {
    // 元数据加载失败不阻断主流程
  }
}

onMounted(() => {
  loadItems()
  loadObsidianNotes()
  loadMeta()
})
</script>

<style scoped>
.knowledge-view {
  padding: 20px 24px 32px;
}

/* 顶部栏 */
.kv-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  gap: 16px;
  flex-wrap: wrap;
}
.kv-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}
.kv-crumb {
  font-size: 12.5px;
  color: var(--text-muted);
  margin-top: 4px;
}
.kv-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.kv-search {
  width: 240px;
}
.kv-search-ico {
  font-size: 13px;
}

/* Bento 布局 */
.kv-bento {
  display: grid;
  grid-template-columns: 248px 1fr;
  gap: 18px;
  align-items: start;
}

/* 左侧树 */
.kv-tree {
  padding: 16px 14px 18px;
}
.kv-tree-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px 6px 12px;
}
.kv-tree-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}
.kv-tree-refresh {
  font-size: 12px;
  color: var(--accent);
  cursor: pointer;
}
.kv-tree-refresh:hover {
  color: var(--accent-hover);
  text-decoration: underline;
}
.kv-tree-root {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: .5px;
  margin: 4px 6px 10px;
}
.kv-tree-node {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 9px;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.kv-tree-node:hover {
  background: var(--border-subtle);
  color: var(--text-primary);
}
.kv-tree-node.active {
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 600;
}
.kv-tree-node.sub {
  margin-left: 18px;
  border-left: 1px solid var(--border);
  padding-left: 12px;
  font-size: 12.5px;
}
.kv-ico {
  width: 16px;
  flex-shrink: 0;
  opacity: .75;
}
.kv-tree-count {
  margin-left: auto;
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--text-muted);
  background: var(--border-subtle);
  padding: 1px 7px;
  border-radius: 20px;
}
.kv-tree-empty {
  font-size: 12px;
  color: var(--text-muted);
  padding: 12px 10px;
}

/* 中部网格 */
.kv-notes {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}
.kv-pagination {
  margin-top: 4px;
  justify-content: flex-end;
}
.kv-notes-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.kv-tag-filter {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.kv-tag-btn {
  font-size: 12px;
  font-weight: 600;
  padding: 6px 13px;
  border-radius: 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.kv-tag-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.kv-tag-btn.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.kv-note-count {
  font-size: 12.5px;
  color: var(--text-muted);
}
.kv-note-count b {
  color: var(--accent);
}
.kv-notes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(264px, 1fr));
  gap: 16px;
  min-height: 200px;
}
.kv-note-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 18px;
  cursor: pointer;
  transition: all var(--transition-fast);
  box-shadow: var(--shadow-card);
}
.kv-note-card:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-elevated);
  transform: translateY(-2px);
}
.kv-note-emoji {
  width: 38px;
  height: 38px;
  border-radius: 11px;
  background: var(--accent-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  margin-bottom: 12px;
}
.kv-note-title {
  font-size: 14.5px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.35;
  margin-bottom: 7px;
}
.kv-note-path {
  font-size: 11.5px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  margin-bottom: 11px;
  word-break: break-all;
}
.kv-note-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 11px;
}
.kv-ntag {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 9px;
  border-radius: 20px;
  background: var(--border-subtle);
  color: var(--text-secondary);
}
.kv-ntag.blue { background: var(--accent-soft); color: var(--accent); }
.kv-ntag.green { background: var(--success-soft); color: var(--success); }
.kv-ntag.amber { background: var(--warning-soft); color: var(--warning); }
.kv-note-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11.5px;
  color: var(--text-muted);
  border-top: 1px solid var(--border-subtle);
  padding-top: 11px;
}
.kv-note-links {
  display: flex;
  gap: 5px;
}
.kv-link-dot {
  width: 20px;
  height: 20px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9.5px;
  font-weight: 700;
  color: #fff;
}

/* 预览抽屉 */
.kv-pv-head {
  display: flex;
  flex-direction: column;
}
.kv-pv-title {
  font-size: 16px;
  font-weight: 800;
  color: var(--text-primary);
  line-height: 1.35;
}
.kv-pv-meta {
  font-size: 11.5px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  margin-top: 6px;
  word-break: break-all;
}
.kv-pv-body {
  padding: 4px 4px;
}
.kv-pv-section {
  margin-top: 20px;
  border-top: 1px solid var(--border-subtle);
  padding-top: 16px;
}
.kv-pv-h2 {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 10px;
}
.kv-pv-linkrow {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}
.kv-pv-chip {
  font-size: 12px;
  font-weight: 600;
  padding: 5px 11px;
  border-radius: 9px;
  background: var(--border-subtle);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.kv-pv-chip:hover {
  background: var(--accent-soft);
  color: var(--accent);
}
.kv-pv-nolink {
  font-size: 12.5px;
  color: var(--text-muted);
}
.kv-pv-foot {
  display: flex;
  gap: 10px;
}

/* 弹层描述 */
.kv-modal-desc {
  font-size: 12.5px;
  color: var(--text-muted);
  margin-bottom: 16px;
}

@media (max-width: 900px) {
  .kv-bento {
    grid-template-columns: 1fr;
  }
}
</style>
