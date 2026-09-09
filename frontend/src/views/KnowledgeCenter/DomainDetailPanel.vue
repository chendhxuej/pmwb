<template>
  <!-- 领域详情主体（可复用）：左侧主笔记结构 + 全景指标，右侧 产品圣经/关联对象/时间线/自动区 四 tab。
       由「领域详情」独立子页与知识中心首页驾驶舱共用，code 变化时自动重载。 -->
  <div class="detail-body" v-loading="loading">
    <!-- 左侧：主笔记结构 + 全景指标 -->
    <div class="detail-left">
      <!-- 主笔记结构卡片 -->
      <div class="dcard">
        <div class="dcard-head">
          <span>主笔记结构（§3.8 三类模板）</span>
          <span v-if="bibleTitle" class="dcard-sub">{{ bibleTitle }}</span>
        </div>
        <div class="bible-list">
          <div
            v-for="sec in bibleSections"
            :key="sec.key"
            class="bible-item"
            :class="{ 'bible-item--active': activeSection === sec.key }"
            @click="scrollToSection(sec.key)"
            title="点击查看对应章节"
          >
            <span class="bible-badge" :class="'kind-' + sec.kind">{{ sec.kind_label }}</span>
            <span class="bible-title">{{ sec.title }}</span>
          </div>
          <el-empty v-if="!bibleSections.length && !bibleLoading" description="暂无主笔记内容" :image-size="60" />
        </div>
      </div>

      <!-- 全景指标卡片 -->
      <div class="dcard">
        <div class="dcard-head"><span>📊 全景指标</span></div>
        <div class="mini-list">
          <div class="mini-item">
            <span>知识条目</span>
            <b>{{ stats.knowledge_count || 0 }}</b>
          </div>
          <div class="mini-item">
            <span>关联需求</span>
            <b>{{ stats.requirement_count || 0 }}</b>
          </div>
          <div class="mini-item">
            <span>关联工单</span>
            <b>{{ stats.issue_count || 0 }}</b>
          </div>
          <div class="mini-item">
            <span>时间线事件</span>
            <b>{{ stats.timeline_count || 0 }}</b>
          </div>
        </div>
        <div class="health-note" v-if="!detail.has_main_note">
          ⚠️ 该领域尚无主笔记，点击「同步主笔记」一键创建。
        </div>
      </div>
    </div>

    <!-- 右侧：tab 切换 + 内容 -->
    <div class="detail-right">
      <div class="dtabs" id="dTabs">
        <div class="dtab" :class="{ on: activeTab === 'bible' }" @click="activeTab = 'bible'">产品圣经</div>
        <div class="dtab" :class="{ on: activeTab === 'rel' }" @click="activeTab = 'rel'">关联对象</div>
        <div class="dtab" :class="{ on: activeTab === 'tl' }" @click="activeTab = 'tl'">时间线</div>
        <div class="dtab" :class="{ on: activeTab === 'auto' }" @click="activeTab = 'auto'">自动区状态</div>
      </div>
      <div class="dbody">
        <!-- 产品圣经 tab -->
        <div v-if="activeTab === 'bible'" class="tab-content bible-content">
          <div v-if="bibleSections.length" class="bible-full">
            <div
              v-for="sec in bibleSections"
              :key="sec.key"
              :id="`section-${sec.key}`"
              class="bible-section"
              :class="{ 'bible-section--active': activeSection === sec.key }"
            >
              <div class="section-header">
                <h2 class="section-title">{{ sec.title }}</h2>
                <span class="section-badge" :class="'kind-' + sec.kind">{{ sec.kind_label }}</span>
                <div class="section-actions" v-if="isEditing">
                  <el-button size="small" @click="startEditSection(sec.key)">编辑</el-button>
                  <el-button size="small" type="success" @click="saveSection(sec.key)" :loading="savingSection === sec.key">保存</el-button>
                </div>
              </div>
              <!-- 编辑模式：textarea -->
              <div v-if="isEditing && editingSection === sec.key" class="section-edit">
                <textarea
                  v-model="editingContent"
                  class="section-textarea"
                  spellcheck="false"
                ></textarea>
                <div class="edit-preview">
                  <div class="preview-label">预览</div>
                  <div class="preview-content" v-html="renderMarkdown(editingContent)"></div>
                </div>
              </div>
              <!-- 只读模式：渲染 markdown -->
              <div v-else class="section-content" v-html="renderMarkdown(sec.markdown)"></div>
            </div>
          </div>
          <el-empty v-else :description="bibleLoading ? '加载中...' : '暂无主笔记内容'" />
        </div>

        <!-- 关联对象 tab -->
        <div v-if="activeTab === 'rel'" class="tab-content">
          <div class="filt">
            <span class="f" :class="{ on: relFilter === 'all' }" @click="relFilter = 'all'">全部</span>
            <span class="f" :class="{ on: relFilter === 'req' }" @click="relFilter = 'req'">需求</span>
            <span class="f" :class="{ on: relFilter === 'issue' }" @click="relFilter = 'issue'">工单</span>
            <span class="f" :class="{ on: relFilter === 'meeting' }" @click="relFilter = 'meeting'">会议</span>
          </div>
          <table class="rel-table">
            <thead>
              <tr>
                <th style="width:80px">类型</th>
                <th>标题</th>
                <th style="width:100px">状态</th>
                <th style="width:80px">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in filteredRelations" :key="item.code">
                <td><span class="ptag">{{ typeLabel(item.status || item.category || '知识') }}</span></td>
                <td>{{ item.title }}</td>
                <td>{{ item.sub_title || '-' }}</td>
                <td><a href="#" @click.prevent="viewItem(item)" class="link-btn">查看</a></td>
              </tr>
              <tr v-if="!filteredRelations.length"><td colspan="4" class="empty-row">暂无关联对象</td></tr>
            </tbody>
          </table>
        </div>

        <!-- 时间线 tab -->
        <div v-if="activeTab === 'tl'" class="tab-content">
          <BusinessTimeline :domain-code="code" :limit="20" />
        </div>

        <!-- 自动区状态 tab -->
        <div v-if="activeTab === 'auto'" class="tab-content">
          <div class="auto-status">
            <div class="auto-item">
              <span class="auto-label">主笔记已建</span>
              <span :class="['auto-val', detail.has_main_note ? 'ok' : 'warn']">{{ detail.has_main_note ? '✅ 是' : '❌ 否' }}</span>
            </div>
            <div class="auto-item">
              <span class="auto-label">结构完整性</span>
              <span :class="['auto-val', detail.structure_ok ? 'ok' : 'warn']">{{ detail.structure_ok ? '✅ 完整' : '⚠️ 残缺' }}</span>
            </div>
            <div class="auto-item">
              <span class="auto-label">最后同步</span>
              <span class="auto-val">{{ detail.updated_at || '未知' }}</span>
            </div>
          </div>
          <div class="note">自动区由系统维护，无需手动操作。</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { basicDataApi } from '@/api/basicData'
import { knowledgeApi } from '@/api/knowledge'
import { productBibleApi } from '@/api/productBible'
import BusinessTimeline from '@/components/Common/BusinessTimeline.vue'
import { openObsidianNote } from '@/utils/obsidian'
import { marked } from 'marked'

const props = defineProps({
  code: { type: String, required: true },
})

const loading = ref(false)
const detail = ref({})
const bibleSections = ref([])
const bibleContent = ref('') // 存储原始完整内容，用于重建
const bibleTitle = ref('')
const bibleLoading = ref(false)
const relations = ref([])
const timelineEvents = ref([])
const relFilter = ref('all')
const activeTab = ref('bible')
const activeSection = ref('1')

// 编辑模式状态
const isEditing = ref(false)
const editingSection = ref(null)
const savingSection = ref(null)
const saving = ref(false)
const editingContent = ref('')
const originalSections = ref([]) // 备份，用于取消时恢复
const mainNoteItemId = ref(null) // item_id from backend
const syncing = ref(false)

const GROUP_META = {
  '商客业务': { color: '#2f6fed', bg: 'rgba(47,111,237,.10)' },
  '系统平台': { color: '#06b6d4', bg: 'rgba(6,182,212,.10)' },
  '公共能力': { color: '#10b981', bg: 'rgba(16,185,129,.10)' },
  '通用': { color: '#8b5cf6', bg: 'rgba(139,92,246,.10)' },
}

const groupStyle = (g) => {
  const m = GROUP_META[g] || GROUP_META.通用
  return { color: m.color, background: m.bg }
}

const stats = computed(() => ({
  knowledge_count: detail.value.knowledge_count || 0,
  requirement_count: detail.value.requirement_count || 0,
  issue_count: detail.value.issue_count || 0,
  timeline_count: timelineEvents.value.length,
}))

const filteredRelations = computed(() => {
  if (relFilter.value === 'all') return relations.value
  const map = { req: 'requirement', issue: 'operation', meeting: 'meeting' }
  return relations.value.filter(r => r.status === map[relFilter.value])
})

function renderMarkdown(md) {
  if (!md) return ''
  return marked.parse(md)
}

function scrollToSection(key) {
  activeSection.value = key
  const el = document.getElementById(`section-${key}`)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

async function loadDetail() {
  loading.value = true
  try {
    const res = await basicDataApi.getDomainRelated(props.code)
    detail.value = res || {}
    // 合并 stats
    relations.value = [
      ...(res.requirements || []).map(r => ({ ...r, status: 'requirement' })),
      ...(res.issues || []).map(r => ({ ...r, status: 'operation' })),
      ...(res.meetings || []).map(r => ({ ...r, status: 'meeting' })),
      ...(res.knowledge_items || []).map(r => ({ ...r, status: 'knowledge' })),
    ]
  } catch (e) {
    ElMessage.error('加载领域详情失败')
  } finally {
    loading.value = false
  }
}

async function loadBible() {
  bibleLoading.value = true
  try {
    const res = await productBibleApi.getMainNote(props.code)
    bibleSections.value = res?.sections || []
    bibleContent.value = res?.content || '' // 保存原始完整内容
    bibleTitle.value = res?.title || ''
    mainNoteItemId.value = res?.item_id || null
    activeSection.value = bibleSections.value.length ? bibleSections.value[0].key : '1'
  } catch {
    bibleSections.value = []
  } finally {
    bibleLoading.value = false
  }
}

// 编辑模式管理
function startEdit() {
  isEditing.value = true
  // 备份当前内容，用于取消恢复
  originalSections.value = JSON.parse(JSON.stringify(bibleSections.value))
  ElMessage.info('已进入编辑模式，点击各章节的「编辑」按钮开始修改')
}

function cancelEdit() {
  isEditing.value = false
  editingSection.value = null
  // 恢复原始内容
  bibleSections.value = JSON.parse(JSON.stringify(originalSections.value))
  ElMessage.info('已取消编辑，内容已恢复')
}

function startEditSection(key) {
  editingSection.value = key
  // 找到对应 section 的原始 markdown 作为初始内容
  const sec = bibleSections.value.find(s => s.key === key)
  editingContent.value = sec?.markdown || ''
}

async function saveSection(key) {
  if (!mainNoteItemId.value) {
    ElMessage.error('主笔记 ID 未找到，无法保存')
    return
  }
  savingSection.value = key
  try {
    // 更新 sections 数组中的 markdown
    const sec = bibleSections.value.find(s => s.key === key)
    if (sec) {
      sec.markdown = editingContent.value
    }
    // 重建完整 content（保持原有 section 顺序）
    const fullContent = buildFullContent(bibleSections.value)
    // 调用 API 保存
    await knowledgeApi.updateItemContent(mainNoteItemId.value, fullContent)
    ElMessage.success(`章节 ${key} 已保存`)
    editingSection.value = null
    // 刷新 sections（重新读取，确保与 Obsidian 一致）
    await loadBible()
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    savingSection.value = null
  }
}

async function saveAllChanges() {
  if (!mainNoteItemId.value) {
    ElMessage.error('主笔记 ID 未找到，无法保存')
    return
  }
  saving.value = true
  try {
    // 重建完整 content
    const fullContent = buildFullContent(bibleSections.value)
    await knowledgeApi.updateItemContent(mainNoteItemId.value, fullContent)
    ElMessage.success('所有更改已保存')
    isEditing.value = false
    editingSection.value = null
    await loadBible()
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

// 根据 sections 重建完整 markdown 内容
function buildFullContent(sections) {
  // 使用保存的原始 content 作为基底，逐段替换
  let result = bibleContent.value
  if (!result) return ''
  for (const sec of sections) {
    const escapedKey = sec.key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    // 匹配 ## key. 标题 ... 直到下一个 ## 或文件末尾
    const regex = new RegExp(`(##\\s+${escapedKey}\\s*[^\n]*\n)(.*?)(?=\n##\\s|$)`, 's')
    const replacement = `$1${sec.markdown}\n`
    result = result.replace(regex, replacement)
  }
  return result
}

async function syncMainNote() {
  // 直接调用同步接口（把需求/用户故事/关联事件回流到主笔记自动区）
  syncing.value = true
  try {
    const res = await knowledgeApi.syncMainNote(props.code)
    const blocks = res?.blocks_written || []
    if (res?.changed) {
      ElMessage.success(`主笔记已同步，写入 ${blocks.length} 个自动区章节`)
    } else {
      ElMessage.info('主笔记无变更（关联数据未发生变化）')
    }
    await loadBible()
  } catch (e) {
    ElMessage.error(e?.message || '同步失败')
  } finally {
    syncing.value = false
  }
}

function openObsidian() {
  if (detail.value.obsidian_path) {
    openObsidianNote(detail.value.obsidian_path)
  }
}

function typeLabel(s) {
  const map = { requirement: '需求', operation: '工单', meeting: '会议', knowledge: '知识' }
  return map[s] || s || '知识'
}

function viewItem(item) {
  // TODO: 根据类型跳转到对应页面
  ElMessage.info(`查看 ${item.title}`)
}

// code 变化（首页切换领域 / 独立子页路由复用）时重载；先退编辑态避免脏写
watch(() => props.code, async (nc, oc) => {
  if (!nc || nc === oc) return
  isEditing.value = false
  editingSection.value = null
  activeTab.value = 'bible'
  activeSection.value = '1'
  await loadDetail()
  await loadBible()
}, { immediate: true })

// 向父组件（领域详情子页 topbar）暴露编辑/同步等能力
defineExpose({
  detail,
  isEditing,
  saving,
  syncing,
  startEdit,
  cancelEdit,
  saveAllChanges,
  syncMainNote,
  openObsidian,
})
</script>

<script>
export default { name: 'DomainDetailPanel' }
</script>

<style scoped>
.detail-body {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 16px;
  align-items: start;
}
.detail-left, .detail-right { display: flex; flex-direction: column; gap: 14px; }

.dcard {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 14px 16px;
}
.dcard-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  font-weight: 700;
  color: #1f2d3d;
  margin-bottom: 12px;
}
.dcard-sub {
  font-size: 12px;
  color: #909399;
  font-weight: 400;
}
.bible-list { display: flex; flex-direction: column; gap: 8px; }
.bible-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  padding: 7px 10px;
  background: #f5f7fa;
  border-radius: 8px;
}
.bible-badge {
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 6px;
  font-weight: 600;
  flex-shrink: 0;
}
.bible-badge.kind-baseline { background: #ecf5ff; color: #409eff; }
.bible-badge.kind-auto { background: #f0f9eb; color: #67c23a; }
.bible-badge.kind-system { background: #f4f4f5; color: #909399; }
.bible-title {
  color: #1f2d3d;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bible-item {
  cursor: pointer;
  transition: background 0.2s, border-left 0.2s;
}
.bible-item:hover {
  background: #e8f0fe;
}
.bible-item--active {
  background: #d4e4ff;
  border-left: 3px solid #2f6fed;
  padding-left: 7px;
}
.mini-list { display: flex; flex-direction: column; gap: 8px; }
.mini-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: #1f2d3d;
}
.mini-item b { font-family: 'JetBrains Mono', monospace; color: #1f2d3d; }
.health-note {
  margin-top: 10px;
  padding: 8px 10px;
  background: #fdf2e8;
  border-radius: 8px;
  font-size: 12px;
  color: #f0a64a;
}

/* 右侧 tab */
.dtabs {
  display: flex;
  gap: 6px;
  border-bottom: 1px solid #e4e7ed;
  margin-bottom: 14px;
}
.dtab {
  padding: 9px 14px;
  cursor: pointer;
  color: #64748b;
  font-size: 13px;
  border-bottom: 2px solid transparent;
}
.dtab.on { color: #2f6fed; border-color: #2f6fed; }
.dbody { min-height: 300px; }
.tab-content { padding: 4px 0; }

/* 关联表格 */
.filt { display: flex; gap: 6px; margin-bottom: 12px; flex-wrap: wrap; }
.f {
  padding: 4px 10px;
  border-radius: 8px;
  background: #f5f7fa;
  font-size: 12px;
  cursor: pointer;
  border: 1px solid transparent;
}
.f.on { border-color: #2f6fed; color: #2f6fed; }
.rel-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.rel-table th {
  text-align: left;
  color: #64748b;
  font-weight: 600;
  font-size: 12px;
  padding: 8px 10px;
  border-bottom: 1px solid #e4e7ed;
}
.rel-table td {
  padding: 9px 10px;
  border-bottom: 1px solid #ebeef5;
}
.ptag {
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 6px;
  background: #ecf5ff;
  color: #409eff;
}
.link-btn {
  font-size: 12px;
  color: #2f6fed;
  text-decoration: none;
}
.empty-row { text-align: center; color: #909399; }

/* 自动区 */
.auto-status { display: flex; flex-direction: column; gap: 10px; }
.auto-item {
  display: flex;
  justify-content: space-between;
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 8px;
}
.auto-label { color: #64748b; font-size: 13px; }
.auto-val { font-size: 13px; font-weight: 600; }
.auto-val.ok { color: #10b981; }
.auto-val.warn { color: #f0a64a; }
.note {
  margin-top: 10px;
  font-size: 12px;
  color: #909399;
  line-height: 1.6;
}

/* markdown body */
.markdown-body {
  font-size: 13px;
  line-height: 1.7;
  color: #1f2d3d;
}
.markdown-body h1, .markdown-body h2, .markdown-body h3 {
  margin: 16px 0 8px;
  color: #1f2d3d;
}
.markdown-body p { margin: 8px 0; }
.markdown-body ul { padding-left: 20px; }

/* 分段渲染样式 */
.bible-content { padding-right: 8px; }
.bible-full { display: flex; flex-direction: column; gap: 16px; }
.bible-section {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 16px;
  transition: box-shadow 0.2s, border-color 0.2s;
}
.bible-section--active {
  border-color: #2f6fed;
  box-shadow: 0 0 0 2px rgba(47, 111, 237, 0.1);
}
.section-title {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2d3d;
  padding-bottom: 8px;
  border-bottom: 1px solid #e4e7ed;
}
.section-content {
  font-size: 13px;
  line-height: 1.7;
  color: #374151;
}
.section-content table {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
}
.section-content th, .section-content td {
  border: 1px solid #e4e7ed;
  padding: 6px 10px;
  text-align: left;
  font-size: 12px;
}
.section-content th {
  background: #f5f7fa;
  font-weight: 600;
}
.section-content ul { padding-left: 18px; }
.section-content li { margin: 4px 0; }

/* 编辑模式样式 */
.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e4e7ed;
}
.section-badge {
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 6px;
  font-weight: 600;
  flex-shrink: 0;
}
.section-badge.kind-baseline { background: #ecf5ff; color: #409eff; }
.section-badge.kind-auto { background: #f0f9eb; color: #67c23a; }
.section-badge.kind-system { background: #f4f4f5; color: #909399; }
.section-actions {
  margin-left: auto;
  display: flex;
  gap: 6px;
}
.section-edit {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.section-textarea {
  width: 100%;
  min-height: 120px;
  padding: 10px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 13px;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  line-height: 1.6;
  resize: vertical;
  transition: border-color 0.2s;
}
.section-textarea:focus {
  outline: none;
  border-color: #2f6fed;
  box-shadow: 0 0 0 2px rgba(47, 111, 237, 0.1);
}
.edit-preview {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  overflow: hidden;
}
.preview-label {
  padding: 6px 12px;
  background: #f5f7fa;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  border-bottom: 1px solid #e4e7ed;
}
.preview-content {
  padding: 12px;
  font-size: 13px;
  line-height: 1.7;
  max-height: 300px;
  overflow-y: auto;
  background: #fff;
}
.preview-content table {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
}
.preview-content th, .preview-content td {
  border: 1px solid #e4e7ed;
  padding: 6px 10px;
  font-size: 12px;
}
.preview-content th {
  background: #f5f7fa;
  font-weight: 600;
}

@media (max-width: 1200px) {
  .detail-body { grid-template-columns: 1fr; }
}
</style>
