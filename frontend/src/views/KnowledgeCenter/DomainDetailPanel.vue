<template>
  <!-- 领域详情主体（可复用）：单列布局，右侧 产品圣经/关联对象/时间线/自动区 四 tab。
       由「领域详情」独立子页与知识中心首页驾驶舱共用，code 变化时自动重载。 -->
  <div class="detail-body" v-loading="loading">
    <div class="detail-right">
      <div class="dtabs" id="dTabs">
        <div class="dtab" :class="{ on: activeTab === 'bible' }" @click="activeTab = 'bible'">产品圣经</div>
        <div class="dtab" :class="{ on: activeTab === 'rel' }" @click="activeTab = 'rel'">关联对象</div>
        <div class="dtab" :class="{ on: activeTab === 'tl' }" @click="activeTab = 'tl'">时间线</div>
        <div class="dtab" :class="{ on: activeTab === 'auto' }" @click="activeTab = 'auto'">自动区状态</div>
      </div>
      <div class="dbody">
        <!-- 产品圣经 tab：直接全文渲染主笔记内容 -->
        <div v-if="activeTab === 'bible'" class="tab-content bible-content">
          <template v-if="isEditing">
            <div class="bible-edit">
              <div class="edit-tip">编辑主笔记全文（Markdown 源码），下方为实时预览</div>
              <textarea v-model="editingContent" class="bible-textarea" spellcheck="false"></textarea>
              <div class="edit-preview">
                <div class="preview-label">实时预览</div>
                <div class="preview-content bible-md" v-html="renderMarkdown(editingContent)"></div>
              </div>
              <div class="edit-actions">
                <el-button @click="cancelEdit">取消</el-button>
                <el-button type="success" :loading="saving" @click="saveAllChanges">保存全部</el-button>
              </div>
            </div>
          </template>
          <template v-else>
            <div v-if="bibleLoading" class="bible-loading">主笔记加载中...</div>
            <div v-else-if="bibleContent" class="bible-full-content bible-md" v-html="renderMarkdown(bibleContent)"></div>
            <el-empty v-else description="该领域暂无主笔记内容，点击顶部「同步主笔记」一键创建" />
          </template>
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
const bibleContent = ref('') // 存储原始完整内容
const bibleLoading = ref(false)
const relations = ref([])
const relFilter = ref('all')
const activeTab = ref('bible')

// 编辑模式状态
const isEditing = ref(false)
const saving = ref(false)
const editingContent = ref('')
const mainNoteItemId = ref(null) // item_id from backend
const syncing = ref(false)

const filteredRelations = computed(() => {
  if (relFilter.value === 'all') return relations.value
  const map = { req: 'requirement', issue: 'operation', meeting: 'meeting' }
  return relations.value.filter(r => r.status === map[relFilter.value])
})

function renderMarkdown(md) {
  if (!md) return ''
  return marked.parse(md)
}

async function loadDetail() {
  loading.value = true
  try {
    const res = await basicDataApi.getDomainRelated(props.code)
    detail.value = res || {}
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
    bibleContent.value = res?.content || ''
    mainNoteItemId.value = res?.item_id || null
  } catch {
    bibleContent.value = ''
  } finally {
    bibleLoading.value = false
  }
}

// 编辑模式管理
function startEdit() {
  isEditing.value = true
  editingContent.value = bibleContent.value
  ElMessage.info('已进入编辑模式')
}

function cancelEdit() {
  isEditing.value = false
  editingContent.value = ''
  ElMessage.info('已取消编辑')
}

async function saveAllChanges() {
  if (!mainNoteItemId.value) {
    ElMessage.error('主笔记 ID 未找到，无法保存')
    return
  }
  saving.value = true
  try {
    await knowledgeApi.updateItemContent(mainNoteItemId.value, editingContent.value)
    ElMessage.success('所有更改已保存')
    isEditing.value = false
    await loadBible()
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
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
  editingContent.value = ''
  activeTab.value = 'bible'
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
  grid-template-columns: 1fr;
  gap: 16px;
  align-items: start;
}
.detail-right { display: flex; flex-direction: column; gap: 14px; }

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

/* ===== 产品圣经：全文展示卡片 ===== */
.bible-loading {
  text-align: center;
  padding: 40px;
  color: #909399;
  font-size: 14px;
}
.bible-full-content {
  padding: 24px 28px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(31, 45, 61, 0.04);
}

/* ===== Markdown 正文排版强化（v-html 内容须用 :deep 命中） ===== */
.bible-md {
  font-size: 13.5px;
  line-height: 1.75;
  color: #1f2d3d;
  word-break: break-word;
}
.bible-md :deep(h1) {
  font-size: 21px;
  font-weight: 700;
  color: #0f172a;
  margin: 4px 0 18px;
  padding-bottom: 10px;
  border-bottom: 2px solid #e8eefb;
  letter-spacing: 0.5px;
}
.bible-md :deep(h2) {
  font-size: 17px;
  font-weight: 700;
  color: #1e3a8a;
  margin: 26px 0 12px;
  padding: 6px 12px;
  background: linear-gradient(90deg, #eff5ff 0%, #ffffff 85%);
  border-left: 4px solid #2f6fed;
  border-radius: 0 6px 6px 0;
}
.bible-md :deep(h2:first-child) { margin-top: 4px; }
.bible-md :deep(h3) {
  font-size: 14.5px;
  font-weight: 600;
  color: #1f2d3d;
  margin: 18px 0 8px;
  padding-left: 10px;
  border-left: 3px solid #93c5fd;
}
.bible-md :deep(h4) {
  font-size: 13.5px;
  font-weight: 600;
  color: #374151;
  margin: 14px 0 6px;
}
.bible-md :deep(p) { margin: 8px 0; }
.bible-md :deep(strong) { color: #0f172a; font-weight: 600; }
.bible-md :deep(a) { color: #2f6fed; text-decoration: none; }
.bible-md :deep(a:hover) { text-decoration: underline; }
.bible-md :deep(ul), .bible-md :deep(ol) { padding-left: 22px; margin: 8px 0; }
.bible-md :deep(li) { margin: 4px 0; }
.bible-md :deep(li)::marker { color: #2f6fed; }
.bible-md :deep(blockquote) {
  margin: 10px 0;
  padding: 8px 14px;
  background: #f8fafc;
  border-left: 3px solid #cbd5e1;
  border-radius: 0 6px 6px 0;
  color: #475569;
}
.bible-md :deep(blockquote p) { margin: 4px 0; }
.bible-md :deep(code) {
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 12px;
  background: #f1f5f9;
  color: #b91c1c;
  padding: 1px 6px;
  border-radius: 4px;
}
.bible-md :deep(pre) {
  background: #0f172a;
  color: #e2e8f0;
  padding: 12px 14px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 10px 0;
}
.bible-md :deep(pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
  font-size: 12px;
}
.bible-md :deep(hr) {
  border: none;
  border-top: 1px dashed #e4e7ed;
  margin: 18px 0;
}
.bible-md :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 12.5px;
  border-radius: 8px;
  overflow: hidden;
}
.bible-md :deep(th) {
  background: #eef4ff;
  color: #1e3a8a;
  font-weight: 600;
  text-align: left;
  padding: 8px 12px;
  border: 1px solid #dbe6f8;
}
.bible-md :deep(td) {
  padding: 7px 12px;
  border: 1px solid #e8eef5;
  color: #374151;
}
.bible-md :deep(tr:nth-child(even) td) { background: #fafcff; }

/* ===== 编辑模式 ===== */
.bible-edit {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.edit-tip {
  font-size: 12px;
  color: #64748b;
  background: #eff6ff;
  border: 1px solid #dbeafe;
  border-radius: 6px;
  padding: 6px 10px;
}
.bible-textarea {
  width: 100%;
  min-height: 260px;
  padding: 12px 14px;
  border: 1px solid #d9d9d9;
  border-radius: 8px;
  font-size: 13px;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  line-height: 1.6;
  resize: vertical;
  transition: border-color 0.2s;
}
.bible-textarea:focus {
  outline: none;
  border-color: #2f6fed;
  box-shadow: 0 0 0 2px rgba(47, 111, 237, 0.1);
}
.edit-preview {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
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
  padding: 14px 16px;
  font-size: 13px;
  line-height: 1.7;
  max-height: 360px;
  overflow-y: auto;
  background: #fff;
}
.edit-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>
