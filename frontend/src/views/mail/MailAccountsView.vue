<template>
  <div class="accounts-view">
    <div class="toolbar">
      <el-button type="primary" @click="onCreate">新建账号</el-button>
    </div>
    <el-table :data="list" v-loading="loading" stripe border>
      <el-table-column label="发件人名称" prop="senderName" min-width="140" />
      <el-table-column label="邮箱地址" prop="email" min-width="200" />
      <el-table-column label="SMTP 服务器" prop="smtpHost" min-width="160" />
      <el-table-column label="端口" prop="smtpPort" width="70" />
      <el-table-column label="默认" width="60" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.isDefault" type="success" size="small">默认</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
            {{ row.status === 'active' ? '正常' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="onEdit(row)">编辑</el-button>
          <el-button link type="primary" size="small" @click="onTest(row)">测试</el-button>
          <el-button link type="primary" size="small" @click="onSetDefault(row)" v-if="!row.isDefault">设为默认</el-button>
          <el-button link type="danger" size="small" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="formVisible" :title="isEdit ? '编辑账号' : '新建账号'" width="540px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="发件人名称">
          <EnlargeInput v-model="form.senderName" />
        </el-form-item>
        <el-form-item label="邮箱地址">
          <EnlargeInput v-model="form.email" />
        </el-form-item>
        <el-form-item label="SMTP 服务器">
          <EnlargeInput v-model="form.smtpHost" />
        </el-form-item>
        <el-form-item label="端口">
          <el-input-number v-model="form.smtpPort" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="是否默认">
          <el-switch v-model="form.isDefault" />
        </el-form-item>
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
import { getAccounts, createAccount, updateAccount, deleteAccount, testAccount, setDefaultAccount } from '@/api/mailCenter.js'
import { ElMessage, ElMessageBox } from 'element-plus'

const list = ref([])
const loading = ref(false)
const formVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const form = ref({ senderName: '', email: '', smtpHost: '', smtpPort: 25, isDefault: false })

async function fetchData() {
  loading.value = true
  try {
    const resp = await getAccounts()
    list.value = resp.data?.data || resp.data || []
  } finally {
    loading.value = false
  }
}

function onCreate() {
  isEdit.value = false
  editId.value = null
  form.value = { senderName: '', email: '', smtpHost: '', smtpPort: 25, isDefault: false }
  formVisible.value = true
}

function onEdit(row) {
  isEdit.value = true
  editId.value = row.id
  form.value = { ...row }
  formVisible.value = true
}

async function onSave() {
  try {
    if (isEdit.value && editId.value) {
      await updateAccount(editId.value, form.value)
      ElMessage.success('已更新')
    } else {
      await createAccount(form.value)
      ElMessage.success('已创建')
    }
    formVisible.value = false
    fetchData()
  } catch (err) {
    ElMessage.error(err.message || '保存失败')
  }
}

function onTest(row) {
  ElMessage.info('测试连接中...')
  testAccount(row.id).then(() => ElMessage.success('连接成功')).catch(e => ElMessage.error(e.message || '连接失败'))
}

async function onSetDefault(row) {
  try {
    await setDefaultAccount(row.id)
    ElMessage.success('已设为默认')
    fetchData()
  } catch (err) {
    ElMessage.error(err.message || '操作失败')
  }
}

function onDelete(row) {
  ElMessageBox.confirm(`确定删除账号 ${row.email} ？`, '确认').then(async () => {
    await deleteAccount(row.id)
    ElMessage.success('已删除')
    fetchData()
  }).catch(() => {})
}

onMounted(fetchData)
</script>
<style scoped>
.toolbar { margin-bottom: 12px; }
</style>
