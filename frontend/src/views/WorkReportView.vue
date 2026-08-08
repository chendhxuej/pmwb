<template>
  <div class="work-report-page">
    <div class="page-header">
      <div class="page-title">AI总结</div>
      <div class="page-actions">
        <el-button type="primary" :icon="EditPen" @click="openGenerate">生成报告</el-button>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <el-table :data="list" v-loading="loading" border stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="report_type_label" label="类型" width="90" />
      <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
      <el-table-column label="统计区间" width="200">
        <template #default="{ row }">
          {{ row.date_start || '-' }} ~ {{ row.date_end || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)">{{ row.status_label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">查看</el-button>
          <el-button link type="danger" @click="doDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 生成报告弹窗 -->
    <el-dialog v-model="generateVisible" title="生成AI总结" width="460px">
      <el-form label-width="90px">
        <el-form-item label="报告类型">
          <el-select v-model="genForm.report_type" style="width: 100%">
            <el-option label="日报" value="daily" />
            <el-option label="周报" value="weekly" />
            <el-option label="月报" value="monthly" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="起始日期">
          <el-date-picker v-model="genForm.date_start" type="date" value-format="YYYY-MM-DD" placeholder="缺省自动推算" style="width: 100%" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="genForm.date_end" type="date" value-format="YYYY-MM-DD" placeholder="缺省为今天" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="generateVisible = false">取消</el-button>
        <el-button type="primary" :loading="genLoading" @click="doGenerate">生成</el-button>
      </template>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" :size="720" :title="current.title || '报告详情'">
      <template #header>
        <div class="detail-header">
          <span class="detail-title">{{ current.title || '报告详情' }}</span>
          <el-tag :type="statusTagType(current.status)">{{ current.status_label }}</el-tag>
          <el-tag v-if="current.obsidian_path" type="success" class="path-tag">
            <el-icon><FolderChecked /></el-icon>
            <span class="path-text" :title="current.obsidian_path">{{ current.obsidian_path }}</span>
            <el-icon class="copy-icon" @click="copyPath"><CopyDocument /></el-icon>
          </el-tag>
        </div>
      </template>

      <div class="detail-body">
        <MarkdownRender v-if="!editing" :content="current.content || ''" />
        <el-input v-else type="textarea" v-model="editContent" :rows="26" placeholder="可手工编辑报告内容" />
      </div>

      <template #footer>
        <div class="detail-footer">
          <el-button v-if="!editing" type="primary" :icon="Edit" @click="startEdit">编辑</el-button>
          <template v-else>
            <el-button :icon="Check" type="success" @click="saveEdit">保存</el-button>
            <el-button @click="editing = false">取消</el-button>
          </template>
          <el-button v-if="current.status === 'draft'" type="warning" :icon="Stamp" :loading="finalizeLoading" @click="doFinalize">定稿</el-button>
          <el-button type="primary" :icon="Message" @click="openEmail">邮件发送</el-button>
          <el-button type="danger" :icon="Delete" @click="doDelete(current)">删除</el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 邮件发送弹窗 -->
    <el-dialog v-model="emailVisible" title="邮件发送" width="620px">
      <el-form label-width="70px">
        <el-form-item label="收件人">
          <StaffSelect v-model="emailForm.to" multiple value-key="email" placeholder="选择人员自动带出邮箱，支持手输" />
        </el-form-item>
        <el-form-item label="抄送">
          <StaffSelect v-model="emailForm.cc" multiple value-key="email" placeholder="抄送人员" />
        </el-form-item>
        <el-form-item label="主题">
          <el-input v-model="emailForm.subject" placeholder="邮件主题" />
        </el-form-item>
        <el-form-item label="正文">
          <div class="email-body-bar">
            <el-button size="small" @click="emailEditing = !emailEditing">
              {{ emailEditing ? '预览' : '编辑' }}
            </el-button>
          </div>
          <el-input v-if="emailEditing" type="textarea" v-model="emailForm.body" :rows="16" placeholder="邮件正文（支持 Markdown）" />
          <MarkdownRender v-else :content="emailForm.body || ''" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="emailVisible = false">取消</el-button>
        <el-button type="primary" :loading="sendLoading" @click="doSend">发送</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { EditPen, Edit, Check, Message, Delete, Stamp, FolderChecked, CopyDocument, Refresh } from '@element-plus/icons-vue'
import MarkdownRender from '@/components/Common/MarkdownRender.vue'
import StaffSelect from '@/components/Common/StaffSelect.vue'
import {
  listWorkReports, getWorkReport, generateWorkReport,
  updateWorkReport, deleteWorkReport, finalizeWorkReport, sendWorkReport,
} from '@/api/workReport'

const list = ref([])
const loading = ref(false)
const generateVisible = ref(false)
const genLoading = ref(false)
const genForm = reactive({ report_type: 'daily', date_start: '', date_end: '' })

const detailVisible = ref(false)
const current = ref({})
const editing = ref(false)
const editContent = ref('')
const finalizeLoading = ref(false)

const emailVisible = ref(false)
const sendLoading = ref(false)
const emailEditing = ref(true)
const emailForm = reactive({ to: [], cc: [], subject: '', body: '' })

function statusTagType(status) {
  if (status === 'sent') return 'success'
  if (status === 'finalized') return 'warning'
  return 'info'
}

async function load() {
  loading.value = true
  try {
    list.value = await listWorkReports()
  } catch (e) {
    ElMessage.error('加载报告列表失败')
  } finally {
    loading.value = false
  }
}

function openGenerate() {
  genForm.report_type = 'daily'
  genForm.date_start = ''
  genForm.date_end = ''
  generateVisible.value = true
}

async function doGenerate() {
  genLoading.value = true
  try {
    const r = await generateWorkReport({ ...genForm })
    ElMessage.success('已生成')
    generateVisible.value = false
    await load()
    openDetail(r)
  } catch (e) {
    ElMessage.error('生成失败')
  } finally {
    genLoading.value = false
  }
}

async function openDetail(row) {
  try {
    const r = await getWorkReport(row.id)
    current.value = r
    editing.value = false
    editContent.value = r.content || ''
    detailVisible.value = true
  } catch (e) {
    ElMessage.error('打开详情失败')
  }
}

function startEdit() {
  editContent.value = current.value.content || ''
  editing.value = true
}

async function saveEdit() {
  try {
    const r = await updateWorkReport(current.value.id, { content: editContent.value })
    current.value = r
    editing.value = false
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

async function doFinalize() {
  try {
    await ElMessageBox.confirm('定稿后将自动归档到 Obsidian 知识库，且不可再次编辑/定稿。确认定稿？', '定稿确认', { type: 'warning' })
  } catch {
    return
  }
  finalizeLoading.value = true
  try {
    const r = await finalizeWorkReport(current.value.id)
    current.value = r
    ElMessage.success('已定稿并归档')
    await load()
  } catch (e) {
    ElMessage.error('定稿失败')
  } finally {
    finalizeLoading.value = false
  }
}

async function doDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除报告「${row.title || row.id}」？此操作不可恢复。`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteWorkReport(row.id)
    ElMessage.success('已删除')
    if (detailVisible.value && current.value.id === row.id) detailVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

function openEmail() {
  emailForm.to = (current.value.recipient || '').split(',').map(s => s.trim()).filter(Boolean)
  emailForm.cc = (current.value.cc || '').split(',').map(s => s.trim()).filter(Boolean)
  emailForm.subject = current.value.title || ''
  emailForm.body = current.value.content || ''
  emailEditing.value = true
  emailVisible.value = true
}

async function doSend() {
  if (!emailForm.to.length) {
    ElMessage.warning('请至少选择一个收件人')
    return
  }
  sendLoading.value = true
  try {
    const r = await sendWorkReport(current.value.id, { ...emailForm })
    current.value = r
    ElMessage.success('邮件已发送')
    emailVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error('发送失败：' + (e?.message || '未知错误'))
  } finally {
    sendLoading.value = false
  }
}

async function copyPath() {
  try {
    await navigator.clipboard.writeText(current.value.obsidian_path || '')
    ElMessage.success('已复制归档路径')
  } catch {
    ElMessage.info(current.value.obsidian_path || '')
  }
}

onMounted(load)
</script>

<style scoped>
.work-report-page { padding: 16px; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.page-title { font-size: 20px; font-weight: 600; }
.detail-header { display: flex; align-items: center; gap: 10px; }
.detail-title { font-size: 16px; font-weight: 600; }
.path-tag { display: inline-flex; align-items: center; gap: 4px; max-width: 360px; }
.path-text { max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.copy-icon { cursor: pointer; }
.detail-body { padding: 4px 8px; }
.detail-footer { display: flex; gap: 8px; flex-wrap: wrap; }
.email-body-bar { margin-bottom: 6px; text-align: right; }
</style>
