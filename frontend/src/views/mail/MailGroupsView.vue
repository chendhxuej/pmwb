<template>
  <div class="groups-view">
    <div class="toolbar">
      <el-button type="primary" @click="onCreate">新建分组</el-button>
    </div>
    <el-table :data="list" v-loading="loading" stripe border>
      <el-table-column label="分组名称" prop="name" min-width="200" />
      <el-table-column label="描述" prop="description" min-width="300" show-overflow-tooltip />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="onEdit(row)">编辑</el-button>
          <el-button link type="danger" size="small" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="formVisible" :title="isEdit ? '编辑分组' : '新建分组'" width="460px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称"><EnlargeInput v-model="form.name" /></el-form-item>
        <el-form-item label="描述"><EnlargeInput v-model="form.description" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getContactGroups, createContactGroup, updateContactGroup, deleteContactGroup } from '@/api/mailCenter.js'
import { ElMessage, ElMessageBox } from 'element-plus'

const list = ref([])
const loading = ref(false)
const formVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const form = ref({ name: '', description: '' })

async function fetchData() {
  loading.value = true
  try {
    const resp = await getContactGroups()
    list.value = resp.data?.data || resp.data || []
  } finally { loading.value = false }
}

function onCreate() {
  isEdit.value = false; editId.value = null
  form.value = { name: '', description: '' }; formVisible.value = true
}

function onEdit(row) {
  isEdit.value = true; editId.value = row.id
  form.value = { name: row.name, description: row.description }; formVisible.value = true
}

async function onSave() {
  try {
    if (isEdit.value && editId.value) {
      await updateContactGroup(editId.value, form.value)
      ElMessage.success('已更新')
    } else {
      await createContactGroup(form.value)
      ElMessage.success('已创建')
    }
    formVisible.value = false; fetchData()
  } catch (err) { ElMessage.error(err.message || '保存失败') }
}

function onDelete(row) {
  ElMessageBox.confirm(`确定删除分组 ${row.name} ？`, '确认').then(async () => {
    await deleteContactGroup(row.id); ElMessage.success('已删除'); fetchData()
  }).catch(() => {})
}

onMounted(fetchData)
</script>
<style scoped>
.toolbar { margin-bottom: 12px; }
</style>
