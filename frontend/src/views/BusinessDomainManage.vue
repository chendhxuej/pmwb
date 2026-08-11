<template>
  <div class="bdm-page">
    <div class="bdm-header">
      <h2>业务领域管理</h2>
      <div class="bdm-actions">
        <el-button type="primary" @click="openCreate">＋ 新增领域</el-button>
        <el-button @click="loadData">刷新</el-button>
      </div>
    </div>

    <!-- 商客业务 -->
    <el-card v-for="group in domainTree" :key="group.domain_code" class="bdm-group-card">
      <template #header>
        <div class="bdm-group-header">
          <span class="bdm-group-name">{{ group.domain_name }}</span>
          <span class="bdm-group-code">{{ group.domain_code }}</span>
          <el-tag size="small" type="info">{{ group.children.length }} 个子类</el-tag>
          <el-button size="small" type="primary" plain @click="openCreateChild(group)">＋ 新增子类</el-button>
        </div>
      </template>
      <el-table :data="group.children" stripe size="small">
        <el-table-column prop="domain_code" label="编码" width="180" />
        <el-table-column prop="domain_name" label="名称" width="140" />
        <el-table-column prop="description" label="描述" show-overflow-tooltip />
        <el-table-column prop="vault_path" label="Vault 路径" show-overflow-tooltip />
        <el-table-column prop="enabled" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
              {{ row.enabled ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" align="center">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm
              title="确定停用该业务领域？"
              confirm-button-text="确定"
              @confirm="handleDelete(row.domain_code)"
            >
              <template #reference>
                <el-button size="small" text type="danger">停用</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 弹窗：新增/编辑 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑业务领域' : '新增业务领域'"
      width="560px"
      @closed="resetForm"
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="业务编码" required>
          <EnlargeInput v-model="form.domain_code" :disabled="isEdit" placeholder="如 ywt-broadband" />
        </el-form-item>
        <el-form-item label="中文名称" required>
          <EnlargeInput v-model="form.domain_name" placeholder="如一网通宽带" />
        </el-form-item>
        <el-form-item label="所属大类" required>
          <el-select v-model="form.domain_group" style="width:100%">
            <el-option v-for="g in allGroups" :key="g" :label="g" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item label="父领域">
          <el-select v-model="form.parent_domain_code" clearable placeholder="空=一级大类" style="width:100%">
            <el-option v-for="d in parentOptions" :key="d.domain_code" :label="d.domain_name" :value="d.domain_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <EnlargeInput v-model="form.description" type="textarea" :rows="2" placeholder="业务领域的简要说明" />
        </el-form-item>
        <el-form-item label="Vault 路径">
          <EnlargeInput v-model="form.vault_path" placeholder="Obsidian vault 内目录路径" />
        </el-form-item>
        <el-form-item label="分类关键词">
          <EnlargeInput v-model="form.match_keywords" placeholder="逗号分隔，如 一网通,集客一网通（用于把扁平笔记归入该细分业务）" />
        </el-form-item>
        <el-form-item label="排序号">
          <el-input-number v-model="form.sort_order" :min="0" :max="999" controls-position="right" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">
          {{ isEdit ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { basicDataApi } from '@/api/basicData.js'

// ── 数据 ──
const domainTree = ref([])
const allFlat = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const saving = ref(false)

const blankForm = () => ({
  domain_code: '',
  domain_name: '',
  domain_group: '商客业务',
  parent_domain_code: '',
  description: '',
  vault_path: '',
  match_keywords: '',
  sort_order: 0,
  enabled: true,
})
const form = reactive(blankForm())

const allGroups = ['商客业务', '政企业务', '系统平台', '通用']

// 父领域选项：仅一级大类（parent_domain_code 为空）
const parentOptions = computed(() => allFlat.value.filter(d => !d.parent_domain_code))

// ── 数据加载 ──
const loadData = async () => {
  try {
    const [tree, flat] = await Promise.all([
      basicDataApi.getBusinessDomains({ tree: true }),
      basicDataApi.getBusinessDomains({ all: true }),
    ])
    domainTree.value = tree
    allFlat.value = flat
  } catch {
    ElMessage.error('加载业务领域失败')
  }
}

// ── 新增 ──
const openCreate = () => {
  isEdit.value = false
  Object.assign(form, blankForm())
  dialogVisible.value = true
}

const openCreateChild = (group) => {
  isEdit.value = false
  Object.assign(form, {
    ...blankForm(),
    domain_group: group.domain_group,
    parent_domain_code: group.domain_code,
  })
  dialogVisible.value = true
}

// ── 编辑 ──
const openEdit = (row) => {
  isEdit.value = true
  Object.assign(form, {
    domain_code: row.domain_code,
    domain_name: row.domain_name,
    domain_group: row.domain_group,
    parent_domain_code: row.parent_domain_code || '',
    description: row.description || '',
    vault_path: row.vault_path || '',
    match_keywords: row.match_keywords || '',
    sort_order: row.sort_order || 0,
    enabled: row.enabled,
  })
  dialogVisible.value = true
}

// ── 保存 ──
const handleSave = async () => {
  if (!form.domain_code || !form.domain_name) {
    ElMessage.warning('编码和名称为必填')
    return
  }
  saving.value = true
  try {
    const payload = {
      domain_name: form.domain_name,
      domain_group: form.domain_group,
      parent_domain_code: form.parent_domain_code || null,
      description: form.description || null,
      vault_path: form.vault_path || null,
      match_keywords: form.match_keywords || null,
      sort_order: form.sort_order,
      enabled: form.enabled,
    }
    if (isEdit.value) {
      await basicDataApi.updateBusinessDomain(form.domain_code, payload)
      ElMessage.success('已更新')
    } else {
      await basicDataApi.createBusinessDomain({ ...payload, domain_code: form.domain_code })
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await loadData()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || err?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

// ── 删除（软删除） ──
const handleDelete = async (code) => {
  try {
    await basicDataApi.deleteBusinessDomain(code)
    ElMessage.success('已停用')
    await loadData()
  } catch {
    ElMessage.error('停用失败')
  }
}

// ── 重置 ──
const resetForm = () => {
  Object.assign(form, blankForm())
}

onMounted(loadData)
</script>

<style scoped>
.bdm-page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 24px;
}

.bdm-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.bdm-header h2 {
  margin: 0;
  font-size: 20px;
}

.bdm-group-card {
  margin-bottom: 20px;
}

.bdm-group-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bdm-group-name {
  font-size: 16px;
  font-weight: 600;
}

.bdm-group-code {
  font-size: 12px;
  color: #909399;
  font-family: monospace;
}
</style>
