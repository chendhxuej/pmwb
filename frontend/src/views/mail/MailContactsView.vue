<template>
  <div class="contacts-view">
    <div class="toolbar">
      <el-button type="primary" @click="onCreate">新建联系人</el-button>
      <el-button :loading="syncing" @click="onSyncFromMaster">
        <el-icon><Refresh /></el-icon> 同步人员中台
      </el-button>
    </div>
    <el-table :data="list" v-loading="loading" stripe border>
      <el-table-column label="姓名" prop="name" min-width="120" />
      <el-table-column label="邮箱" prop="email" min-width="200" />
      <el-table-column label="手机" prop="phone" width="140" />
      <el-table-column label="分组" prop="groupName" width="120" />
      <el-table-column label="备注" prop="remark" min-width="160" show-overflow-tooltip />
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="onEdit(row)">编辑</el-button>
          <el-button link type="danger" size="small" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="formVisible" :title="isEdit ? '编辑联系人' : '新建联系人'" width="520px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="姓名"><EnlargeInput v-model="form.name" /></el-form-item>
        <el-form-item label="邮箱"><EnlargeInput v-model="form.email" /></el-form-item>
        <el-form-item label="手机"><EnlargeInput v-model="form.phone" /></el-form-item>
        <el-form-item label="分组">
          <el-select v-model="form.groupId" placeholder="请选择" clearable style="width:100%">
            <el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><EnlargeInput v-model="form.remark" type="textarea" :rows="2" /></el-form-item>
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
import { getContacts, createContact, updateContact, deleteContact, getContactGroups, syncContactsFromMaster } from '@/api/mailCenter.js'
import { ElMessage, ElMessageBox } from 'element-plus'

const list = ref([])
const loading = ref(false)
const syncing = ref(false)
const groups = ref([])
const formVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const form = ref({ name: '', email: '', phone: '', groupId: null, remark: '' })

async function fetchData() {
  loading.value = true
  try {
    const [contactsResp, groupsResp] = await Promise.all([getContacts(), getContactGroups()])
    list.value = contactsResp.data?.data || contactsResp.data || []
    groups.value = groupsResp.data?.data || groupsResp.data || []
  } finally {
    loading.value = false
  }
}

async function onSyncFromMaster() {
  try {
    await ElMessageBox.confirm(
      '将从人员中台(8001)拉取全员邮箱，按姓名匹配邮件中心通讯录：邮箱不一致则更新，缺失则新建。是否继续？',
      '同步人员中台通讯录',
      { confirmButtonText: '开始同步', cancelButtonText: '取消', type: 'info' }
    )
  } catch {
    return
  }
  syncing.value = true
  try {
    const resp = await syncContactsFromMaster()
    const d = resp.data?.data || resp.data || {}
    await fetchData()
    ElMessage.success(
      `同步完成：新建 ${d.created || 0} 人，更新 ${d.updated || 0} 人，跳过 ${d.skipped || 0} 人`
      + (d.errors && d.errors.length ? `（${d.errors.length} 条异常）` : '')
    )
  } catch (err) {
    ElMessage.error(err.message || '同步失败')
  } finally {
    syncing.value = false
  }
}

function onCreate() {
  isEdit.value = false; editId.value = null
  form.value = { name: '', email: '', phone: '', groupId: null, remark: '' }
  formVisible.value = true
}

function onEdit(row) {
  isEdit.value = true; editId.value = row.id
  form.value = { name: row.name, email: row.email, phone: row.phone, groupId: row.groupId, remark: row.remark }
  formVisible.value = true
}

async function onSave() {
  try {
    if (isEdit.value && editId.value) {
      await updateContact(editId.value, form.value)
      ElMessage.success('已更新')
    } else {
      await createContact(form.value)
      ElMessage.success('已创建')
    }
    formVisible.value = false; fetchData()
  } catch (err) { ElMessage.error(err.message || '保存失败') }
}

function onDelete(row) {
  ElMessageBox.confirm(`确定删除 ${row.name} ？`, '确认').then(async () => {
    await deleteContact(row.id); ElMessage.success('已删除'); fetchData()
  }).catch(() => {})
}

onMounted(fetchData)
</script>
<style scoped>
.toolbar { margin-bottom: 12px; }
</style>
