<template>
  <div class="product-bible">
    <div class="pb-header">
      <div class="pb-title-row">
        <h2 class="page-title">知识标准化管理</h2>
        <el-radio-group v-model="activeKey" @change="loadBible" size="default">
          <el-radio-button v-for="b in catalog" :key="b.key" :value="b.key">
            {{ b.name }}
          </el-radio-button>
        </el-radio-group>
      </div>

      <el-card v-if="meta.title" class="meta-card" shadow="never">
        <div class="meta-item">
          <span class="meta-label">业务线</span><span class="meta-value">{{ meta.name }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">主笔记</span><span class="meta-value">{{ meta.title }}</span>
        </div>
        <div class="meta-item" v-if="meta.updated_at">
          <span class="meta-label">更新日期</span><span class="meta-value">{{ meta.updated_at }}</span>
        </div>
      </el-card>
    </div>

    <div class="pb-body" v-loading="loading">
      <!-- 左侧目录：标准章节 -->
      <aside class="pb-toc" v-if="sections.length">
        <div class="toc-title">标准知识结构</div>
        <ul class="toc-list">
          <li
            v-for="sec in sections"
            :key="sec.key"
            class="toc-item"
            :class="['kind-' + sec.kind, { active: activeToc === sec.key }]"
            @click="scrollTo('sec-' + sec.key)"
          >
            <span class="toc-dot" :class="'dot-' + sec.kind"></span>
            <span class="toc-text">{{ sec.title }}</span>
          </li>
        </ul>
      </aside>

      <!-- 右侧：标准结构卡片 -->
      <main class="pb-content">
        <el-empty v-if="!loading && !sections.length" description="该业务暂无主笔记，请先同步" />
        <section
          v-for="sec in sections"
          :key="sec.key"
          :id="'sec-' + sec.key"
          class="std-section"
        >
          <div class="std-head">
            <div class="std-title">
              <span class="std-badge" :class="'badge-' + sec.kind">{{ sec.kind_label }}</span>
              <span class="std-name">{{ sec.title }}</span>
            </div>
            <div class="std-actions">
              <template v-if="sec.editable && editingKey !== sec.key">
                <el-button size="small" @click="startEdit(sec)">
                  <el-icon><Edit /></el-icon><span>编辑</span>
                </el-button>
              </template>
              <template v-else-if="sec.editable && editingKey === sec.key">
                <el-button size="small" type="primary" :loading="saving" @click="saveEdit(sec)">
                  <el-icon><Check /></el-icon><span>保存</span>
                </el-button>
                <el-button size="small" :disabled="saving" @click="cancelEdit">取消</el-button>
              </template>
              <el-tag v-else size="small" type="info" effect="plain">系统维护</el-tag>
            </div>
          </div>

          <div class="std-body" v-if="editingKey !== sec.key">
            <MarkdownRender v-if="sec.markdown && sec.markdown !== '_暂无数据_'" :content="sec.markdown" />
            <div v-else class="std-empty">（暂无内容，可在 Obsidian 主笔记或上方「编辑」补充）</div>
          </div>

          <div class="std-edit" v-else>
            <div class="edit-hint">
              直接编辑本章节 Markdown 源码，保存后写回 Obsidian 主笔记对应章节（系统自动区不受影响）。
            </div>
            <EnlargeInput
              v-model="editContent"
              type="textarea"
              class="edit-area"
              :autosize="false"
              resize="none"
            />
          </div>
        </section>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { productBibleApi } from '@/api/productBible'
import MarkdownRender from '@/components/Common/MarkdownRender.vue'
import EnlargeInput from '@/components/Common/EnlargeInput.vue'

const route = useRoute()

const catalog = ref([])
const activeKey = ref('')
const loading = ref(false)
const sections = ref([])
const activeToc = ref('')

// 编辑
const editingKey = ref('')
const editContent = ref('')
const saving = ref(false)

const meta = reactive({
  name: '',
  title: '',
  updated_at: '',
})

const loadCatalog = async () => {
  try {
    const res = await productBibleApi.getCatalog()
    catalog.value = res || []
    if (!catalog.value.length) return
    const pref = route.query.domain
    const matched =
      pref && catalog.value.find((c) => c.key === pref) ? pref : catalog.value[0].key
    if (activeKey.value !== matched) {
      activeKey.value = matched
      await loadBible(matched)
    }
  } catch (e) {
    ElMessage.error('加载业务目录失败')
  }
}

const loadBible = async (key) => {
  if (!key) return
  loading.value = true
  editingKey.value = ''
  editContent.value = ''
  activeToc.value = ''
  try {
    const res = await productBibleApi.getMainNote(key)
    meta.name = res.name
    meta.title = res.title
    meta.updated_at = res.updated_at
    sections.value = res.sections || []
    if (sections.value.length) activeToc.value = sections.value[0].key
    await nextTick()
    activeToc.value = sections.value.length ? sections.value[0].key : ''
  } catch (e) {
    ElMessage.error('加载知识标准化管理内容失败')
    sections.value = []
  } finally {
    loading.value = false
  }
}

// ---- 编辑基线章节 ----
const startEdit = (sec) => {
  editContent.value = sec.markdown || ''
  editingKey.value = sec.key
}

const cancelEdit = () => {
  editingKey.value = ''
  editContent.value = ''
}

const saveEdit = async (sec) => {
  try {
    await ElMessageBox.confirm(
      '保存后将直接覆盖 Obsidian 主笔记中该章节，且不可撤销。确认保存？',
      '保存确认',
      { type: 'warning', confirmButtonText: '确认保存', cancelButtonText: '再想想' }
    )
  } catch {
    return
  }
  saving.value = true
  try {
    await productBibleApi.updateMainNoteSection(activeKey.value, sec.key, editContent.value)
    sec.markdown = editContent.value
    editingKey.value = ''
    editContent.value = ''
    ElMessage.success('已保存，Obsidian 主笔记已更新')
  } catch (e) {
    ElMessage.error('保存失败：' + (e?.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

const scrollTo = (id) => {
  const el = document.getElementById(id)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  const key = id.replace('sec-', '')
  if (key) activeToc.value = key
}

onMounted(loadCatalog)
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
  width: 260px;
  flex: 0 0 260px;
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
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  font-size: 13px;
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

.toc-item.active {
  background: #ecf5ff;
  color: #409eff;
  font-weight: 600;
}

.toc-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: 0 0 8px;
}
.dot-baseline { background: #409eff; }
.dot-auto { background: #67c23a; }
.dot-system { background: #c0c4cc; }

.pb-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.std-section {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 16px 20px;
  scroll-margin-top: 16px;
}

.std-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.std-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.std-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.std-badge {
  font-size: 12px;
  padding: 1px 8px;
  border-radius: 999px;
  font-weight: 600;
}
.badge-baseline { background: #ecf5ff; color: #409eff; }
.badge-auto { background: #f0f9eb; color: #67c23a; }
.badge-system { background: #f4f4f5; color: #909399; }

.std-body {
  font-size: 14px;
  color: #303133;
  line-height: 1.7;
}

.std-empty {
  color: #c0c4cc;
  font-size: 13px;
  padding: 6px 0;
}

.std-actions .el-button span {
  margin-left: 4px;
}

.edit-hint {
  font-size: 13px;
  color: #909399;
  background: #f4f8ff;
  border: 1px solid #d9ecff;
  border-radius: 6px;
  padding: 10px 14px;
  margin-bottom: 12px;
  line-height: 1.6;
}

.edit-area {
  width: 100%;
}

.edit-area :deep(textarea) {
  height: 50vh;
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
