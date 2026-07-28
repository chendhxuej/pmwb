<template>
  <div class="templates-view">
    <div class="toolbar">
      <el-button type="primary" @click="onCreate">新建模板</el-button>
    </div>
    <el-table :data="list" v-loading="loading" stripe border>
      <el-table-column label="模板名称" prop="name" min-width="160" />
      <el-table-column label="主题" prop="subject" min-width="200" show-overflow-tooltip />
      <el-table-column label="变量" prop="variables" width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.variables?.length">{{ row.variables.join(', ') }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="onEdit(row)">编辑</el-button>
          <el-button link type="primary" size="small" @click="onPreview(row)">预览</el-button>
          <el-button link type="danger" size="small" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="formVisible" :title="isEdit ? '编辑模板' : '新建模板'" width="640px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="主题"><el-input v-model="form.subject" /></el-form-item>
        <el-form-item label="内容"><el-input v-model="form.body" type="textarea" :rows="8" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" @click="onSave">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="previewVisible" title="模板预览" width="640px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="名称">{{ previewRow?.name }}</el-descriptions-item>
        <el-descriptions-item label="主题">{{ previewRow?.subject }}</el-descriptions-item>
        <el-descriptions-item label="内容">
          <pre class="preview-body">{{ previewRow?.body }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getTemplates, createTemplate, updateTemplate, deleteTemplate } from '@/api/mailCenter.js'
import { ElMessage, ElMessageBox } from 'element-plus'

const list = ref([])
const loading = ref(false)
const formVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const form = ref({ name: '', subject: '', body: '' })
const previewVisible = ref(false)
const previewRow = ref(null)

async function fetchData() {
  loading.value = true
  try {
    const resp = await getTemplates()
    list.value = resp.data?.data || resp.data || []
  } finally { loading.value = false }
}

function onCreate() {
  isEdit.value = false; editId.value = null
  form.value = { name: '', subject: '', body: '' }; formVisible.value = true
}

function onEdit(row) {
  isEdit.value = true; editId.value = row.id
  form.value = { name: row.name, subject: row.subject, body: row.body }; formVisible.value = true
}

function onPreview(row) {
  previewRow.value = row; previewVisible.value = true
}

async function onSave() {
  try {
    if (isEdit.value && editId.value) {
      await updateTemplate(editId.value, form.value)
      ElMessage.success('已更新')
    } else {
      await createTemplate(form.value)
      ElMessage.success('已创建')
    }
    formVisible.value = false; fetchData()
  } catch (err) { ElMessage.error(err.message || '保存失败') }
}

function onDelete(row) {
  ElMessageBox.confirm(`确定删除模板 ${row.name} ？`, '确认').then(async () => {
    await deleteTemplate(row.id); ElMessage.success('已删除'); fetchData()
  }).catch(() => {})
}

onMounted(fetchData)
</script>
<style scoped>
.toolbar { margin-bottom: 12px; }
.preview-body {
  max-height: 360px; overflow-y: auto; background: var(--el-fill-color, #f0f2f5);
  padding: 12px; border-radius: 4px; white-space: pre-wrap; word-break: break-all; font-size: 13px; line-height: 1.7;
}
</style>
