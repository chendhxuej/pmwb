<template>
  <div class="notes-view">
    <div class="page-head">
      <h2 class="page-title">知识沉淀</h2>
      <span class="hint">浏览运营关联的知识笔记，可直接编辑写回 Obsidian，并关联到工单实现 DB+笔记联动管理</span>
    </div>

    <el-row :gutter="16" class="notes-body">
      <!-- 左：笔记列表 -->
      <el-col :span="8">
        <el-card shadow="never" class="list-card">
          <el-input
            v-model="noteSearch"
            placeholder="搜索笔记标题"
            clearable
            style="margin-bottom: 12px"
          />
          <el-scrollbar height="calc(100vh - 220px)">
            <div
              v-for="n in filteredNotes"
              :key="n.path"
              class="note-item"
              :class="{ active: activeNote?.path === n.path }"
              @click="selectNote(n)"
            >
              <div class="note-item-title">{{ n.title }}</div>
              <div class="note-item-folder">{{ n.folder }}</div>
            </div>
            <el-empty v-if="!filteredNotes.length" description="无匹配笔记" />
          </el-scrollbar>
        </el-card>
      </el-col>

      <!-- 右：笔记内容 / 编辑 -->
      <el-col :span="16">
        <el-card shadow="never" class="reader-card" v-loading="noteLoading">
          <template v-if="activeNote">
            <div class="reader-head">
              <div>
                <div class="reader-title">{{ activeNote.title }}</div>
                <div class="reader-path">{{ activeNote.path }}</div>
              </div>
              <div class="reader-actions">
                <el-button
                  v-if="!noteEditing"
                  size="small"
                  @click="openLinkDialog"
                >关联到工单</el-button>
                <el-button v-if="!noteEditing" size="small" @click="startEdit">
                  <el-icon><Edit /></el-icon><span>编辑内容</span>
                </el-button>
                <template v-else>
                  <el-button size="small" type="primary" :loading="noteSaving" @click="saveEdit">保存</el-button>
                  <el-button size="small" :disabled="noteSaving" @click="cancelEdit">取消</el-button>
                </template>
              </div>
            </div>
            <div class="reader-body">
              <template v-if="!noteEditing">
                <MarkdownRender v-if="noteContent" :content="noteContent" />
                <el-empty v-else description="笔记内容为空" />
              </template>
              <el-input
                v-else
                v-model="noteEditContent"
                type="textarea"
                class="edit-area"
                resize="none"
              />
            </div>
          </template>
          <el-empty v-else description="从左侧选择一篇笔记" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 关联到工单弹窗 -->
    <el-dialog v-model="linkDialogVisible" title="关联到工单" width="560px" append-to-body>
      <el-form label-width="80px">
        <el-form-item label="选择工单">
          <el-select
            v-model="linkTarget"
            filterable
            placeholder="搜索工单编号/标题"
            style="width: 100%"
            :loading="linkLoading"
          >
            <el-option
              v-for="wo in linkOptions"
              :key="wo.value"
              :label="wo.label"
              :value="wo.value"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="linkDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!linkTarget" @click="confirmLink">确定关联</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MarkdownRender from '@/components/Common/MarkdownRender.vue'
import { obsidianApi } from '@/api/obsidian'
import { operationApi } from '@/api/operation'

const notes = ref([])
const noteSearch = ref('')
const loadingNotes = ref(false)
const activeNote = ref(null)
const noteContent = ref('')
const noteLoading = ref(false)
const noteEditing = ref(false)
const noteEditContent = ref('')
const noteSaving = ref(false)

const linkDialogVisible = ref(false)
const linkOptions = ref([])
const linkTarget = ref(null)
const linkLoading = ref(false)

const filteredNotes = computed(() => {
  const kw = noteSearch.value.trim().toLowerCase()
  if (!kw) return notes.value
  return notes.value.filter((n) => (n.title || '').toLowerCase().includes(kw))
})

const loadNotes = async () => {
  loadingNotes.value = true
  try {
    const res = await obsidianApi.listNotes()
    notes.value = res || []
  } catch (e) {
    ElMessage.error('加载笔记列表失败')
    notes.value = []
  } finally {
    loadingNotes.value = false
  }
}

const selectNote = (n) => {
  activeNote.value = n
  noteEditing.value = false
  noteContent.value = ''
  loadNoteContent(n.path)
}

const loadNoteContent = async (path) => {
  noteLoading.value = true
  try {
    const res = await obsidianApi.getNoteContent(path)
    noteContent.value = res.content || ''
  } catch (e) {
    noteContent.value = ''
    ElMessage.error('笔记读取失败')
  } finally {
    noteLoading.value = false
  }
}

const startEdit = () => {
  noteEditContent.value = noteContent.value
  noteEditing.value = true
}

const cancelEdit = () => {
  noteEditing.value = false
  noteEditContent.value = ''
}

const saveEdit = async () => {
  if (!activeNote.value) return
  try {
    await ElMessageBox.confirm(
      '保存后将直接覆盖 Obsidian 中的源文件，且不可撤销。确认保存？',
      '保存确认',
      { type: 'warning', confirmButtonText: '确认保存', cancelButtonText: '再想想' }
    )
  } catch {
    return
  }
  noteSaving.value = true
  try {
    await obsidianApi.updateNoteContent(activeNote.value.path, noteEditContent.value)
    noteContent.value = noteEditContent.value
    noteEditing.value = false
    ElMessage.success('已保存，Obsidian 文件已更新')
  } catch (e) {
    ElMessage.error('保存失败：' + (e?.message || '未知错误'))
  } finally {
    noteSaving.value = false
  }
}

const openLinkDialog = async () => {
  linkTarget.value = null
  linkDialogVisible.value = true
  linkLoading.value = true
  try {
    const res = await operationApi.listIssues({ page: 1, page_size: 200 })
    linkOptions.value = (res.items || []).map((it) => ({
      value: it.id,
      label: `${it.issue_no} · ${it.title}`,
    }))
  } catch (e) {
    ElMessage.error('加载工单失败')
    linkOptions.value = []
  } finally {
    linkLoading.value = false
  }
}

const confirmLink = async () => {
  if (!linkTarget.value || !activeNote.value) return
  try {
    await operationApi.updateIssue(linkTarget.value, { obsidian_path: activeNote.value.path })
    ElMessage.success('已关联到工单')
    linkDialogVisible.value = false
  } catch (e) {
    ElMessage.error('关联失败：' + (e?.message || '未知错误'))
  }
}

onMounted(loadNotes)
</script>

<style scoped>
.notes-view {
  padding: 20px;
}

.page-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.hint {
  font-size: 12px;
  color: #909399;
}

.list-card {
  height: calc(100vh - 160px);
}

.note-item {
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  border-left: 3px solid transparent;
  transition: all 0.15s;
}

.note-item:hover {
  background: #f0f7ff;
}

.note-item.active {
  background: #ecf5ff;
  border-left-color: #409eff;
}

.note-item-title {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.note-item-folder {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.reader-card {
  height: calc(100vh - 160px);
}

.reader-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.reader-title {
  font-size: 18px;
  font-weight: 600;
  color: #1f2d3d;
}

.reader-path {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  word-break: break-all;
}

.reader-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.reader-body {
  min-height: 200px;
}

.edit-area {
  width: 100%;
  height: calc(100vh - 320px);
}

.edit-area :deep(textarea) {
  height: 100%;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #303133;
  white-space: pre;
  overflow: auto;
}
</style>
