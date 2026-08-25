<template>
  <div class="bdm-page">
    <div class="bdm-header">
      <div class="bdm-header-left">
        <h2>业务领域管理</h2>
        <span class="bdm-header-sub">管理业务大类与细分领域，变更后全站选择器自动同步</span>
      </div>
      <div class="bdm-actions">
        <el-input
          v-model="searchText"
          placeholder="搜索编码/名称/关键词"
          clearable
          :prefix-icon="Search"
          style="width: 240px"
        />
        <el-checkbox v-model="showDisabled" label="显示停用" />
        <el-button type="primary" @click="openCreate">＋ 新增领域</el-button>
        <el-button @click="openCreateRoot">＋ 新增大类</el-button>
        <el-button :icon="Refresh" @click="loadData">刷新</el-button>
      </div>
    </div>

    <!-- 大类卡片 -->
    <div v-loading="loading">
      <el-card v-for="group in filteredGroups" :key="group.domain_code" class="bdm-group-card">
        <template #header>
          <div class="bdm-group-header">
            <span class="bdm-group-name">{{ group.domain_name }}</span>
            <span class="bdm-group-code">{{ group.domain_code }}</span>
            <el-tag size="small" type="info">{{ group.children.length }} 个子类</el-tag>
            <span v-if="group.enabled === false" class="bdm-group-off">已停用</span>
            <div class="bdm-group-header-spacer" />
            <el-button size="small" text type="primary" @click="openEdit(group, true)">编辑大类</el-button>
            <el-button size="small" type="primary" plain @click="openCreateChild(group)">＋ 新增子类</el-button>
          </div>
        </template>
        <el-table :data="group.children" stripe size="small" :row-class-name="rowClass">
          <el-table-column prop="domain_code" label="编码" width="170" show-overflow-tooltip />
          <el-table-column prop="domain_name" label="名称" width="130" />
          <el-table-column label="关联数" width="200" align="center">
            <template #default="{ row }">
              <div class="bdm-counts">
                <span title="知识">知 {{ row.knowledge_count ?? 0 }}</span>
                <span title="需求">需 {{ row.req_count ?? 0 }}</span>
                <span title="工单">工 {{ row.issue_count ?? 0 }}</span>
                <span title="会议">会 {{ row.meeting_count ?? 0 }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" show-overflow-tooltip min-width="160" />
          <el-table-column prop="match_keywords" label="分类关键词" show-overflow-tooltip min-width="120">
            <template #default="{ row }">
              <span v-if="row.match_keywords" class="bdm-kw">{{ row.match_keywords }}</span>
              <span v-else class="bdm-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column prop="vault_path" label="Vault 路径" show-overflow-tooltip min-width="140">
            <template #default="{ row }">
              <span v-if="row.vault_path" class="bdm-kw">{{ row.vault_path }}</span>
              <span v-else class="bdm-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="70" align="center">
            <template #default="{ row }">
              <el-switch
                :model-value="row.enabled"
                size="small"
                @change="(val) => handleToggle(row, val)"
              />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140" align="center" fixed="right">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button
                v-if="row.enabled"
                size="small"
                text
                type="danger"
                @click="handleDisable(row.domain_code)"
              >停用</el-button>
              <el-button
                v-else
                size="small"
                text
                type="success"
                @click="handleEnable(row.domain_code)"
              >启用</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-empty v-if="!loading && !filteredGroups.length" description="暂无业务领域，点击「新增大类」创建" />
    </div>
    <!-- 弹窗：新增/编辑 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="580px"
      :close-on-click-modal="false"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px">
        <el-form-item label="业务编码" prop="domain_code">
          <el-input
            v-model="form.domain_code"
            :disabled="isEdit"
            placeholder="如 ywt-broadband / public-capability（唯一，创建后不可改）"
          />
        </el-form-item>
        <el-form-item label="中文名称" prop="domain_name">
          <el-input v-model="form.domain_name" placeholder="如一网通宽带" />
        </el-form-item>
        <el-form-item label="业务大类" prop="domain_group">
          <el-select v-model="form.domain_group" filterable allow-create style="width:100%" placeholder="选择或输入新大类名">
            <el-option v-for="g in allGroups" :key="g" :label="g" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="!isRootMode" label="父领域" prop="parent_domain_code">
          <el-select
            v-model="form.parent_domain_code"
            clearable
            filterable
            style="width:100%"
            placeholder="空=作为一级大类（不推荐，选具体大类更规范）"
          >
            <el-option
              v-for="d in parentOptions"
              :key="d.domain_code"
              :label="`${d.domain_name}（${d.domain_code}）`"
              :value="d.domain_code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="业务领域的简要说明" />
        </el-form-item>
        <el-form-item label="Vault 路径">
          <el-input v-model="form.vault_path" placeholder="Obsidian vault 内目录路径（知识笔记归档目录）" />
        </el-form-item>
        <el-form-item label="分类关键词">
          <el-input
            v-model="form.match_keywords"
            placeholder="逗号分隔，如 一网通,集客一网通（vault 同步时按关键词归入该领域）"
          />
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
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh } from '@element-plus/icons-vue'
import { basicDataApi, refreshBusinessDomains } from '@/api/basicData.js'

// ── 数据 ──
const domainTree = ref([])
const allFlat = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const isRootMode = ref(false)
const saving = ref(false)
const searchText = ref('')
const showDisabled = ref(false)
const formRef = ref(null)

const blankForm = () => ({
  domain_code: '',
  domain_name: '',
  domain_group: '',
  parent_domain_code: '',
  description: '',
  vault_path: '',
  match_keywords: '',
  sort_order: 0,
  enabled: true,
})
const form = reactive(blankForm())

const formRules = {
  domain_code: [
    { required: true, message: '业务编码必填', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_-]+$/, message: '仅支持英文/数字/中划线/下划线', trigger: 'blur' },
  ],
  domain_name: [{ required: true, message: '中文名称必填', trigger: 'blur' }],
  domain_group: [{ required: true, message: '业务大类必填', trigger: 'change' }],
}

// 大类下拉选项：从 DB 根节点动态取（不再硬编码），支持 allow-create 新建大类
const allGroups = computed(() =>
  [...new Set(allFlat.value.filter((d) => !d.parent_domain_code).map((d) => d.domain_group))].filter(Boolean)
)

// 父领域选项：仅一级大类（parent_domain_code 为空），排除自己（编辑时）
const parentOptions = computed(() =>
  allFlat.value.filter(
    (d) => !d.parent_domain_code && d.domain_code !== form.domain_code
  )
)

// 搜索 + 停用过滤（大类名命中时展示全部子类）
const filteredGroups = computed(() => {
  const kw = searchText.value.trim().toLowerCase()
  return domainTree.value
    .map((group) => {
      const groupMatch = !kw || `${group.domain_code} ${group.domain_name}`.toLowerCase().includes(kw)
      const children = group.children.filter((c) => {
        if (!showDisabled.value && !c.enabled) return false
        if (groupMatch) return true
        if (!kw) return true
        const hay = `${c.domain_code} ${c.domain_name} ${c.description || ''} ${c.match_keywords || ''}`.toLowerCase()
        return hay.includes(kw)
      })
      return { ...group, children, _groupMatch: groupMatch }
    })
    .filter((g) => {
      if (!showDisabled.value && g.enabled === false) return false
      if (!kw) return true
      if (g.children.length > 0) return true
      if (g._groupMatch) return true
      return false
    })
})

const dialogTitle = computed(() => {
  if (isEdit.value) return isRootMode.value ? '编辑业务大类' : '编辑业务领域'
  return isRootMode.value ? '新增业务大类' : '新增业务领域'
})

const rowClass = ({ row }) => (row.enabled ? '' : 'bdm-row-off')

// ── 数据加载 ──
// 树形接口已在后端把"无父但有 domain_group"的孤儿领域归入对应大类，
// 管理页直接使用；同时做二次兜底，防止历史脏数据或新增大类未归类时展示异常。
const loadData = async () => {
  loading.value = true
  try {
    const [tree, flat] = await Promise.all([
      basicDataApi.getBusinessDomains({ tree: true, all: true }),
      basicDataApi.getBusinessDomains({ all: true }),
    ])
    allFlat.value = flat

    // 正式大类根节点（有子节点挂载，或 domain_code 以 -group 结尾的规范根）
    const realRoots = new Map()
    for (const node of tree) {
      realRoots.set(node.domain_code, node)
    }
    // 孤儿根：本身没有子节点、且不是任何节点的 parent 的根 → 归入 domain_group 对应大类
    const parentCodes = new Set(flat.map((d) => d.parent_domain_code).filter(Boolean))
    const merged = new Map()
    for (const node of tree) {
      const isRealRoot =
        (node.children && node.children.length > 0) || parentCodes.has(node.domain_code)
      if (isRealRoot) {
        merged.set(node.domain_code, node)
      } else {
        // 孤儿领域 → 挂到 domain_group 匹配的大类下
        const target =
          [...merged.values()].find((g) => g.domain_group === node.domain_group) ||
          [...merged.values()].find((g) => g.domain_name === node.domain_group)
        if (target) {
          target.children.push({ ...node, _orphan: true })
        } else {
          merged.set(node.domain_code, { ...node, children: [] })
        }
      }
    }
    domainTree.value = [...merged.values()].sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
  } catch {
    ElMessage.error('加载业务领域失败')
  } finally {
    loading.value = false
  }
}

// ── 新增 ──
const openCreate = () => {
  isEdit.value = false
  isRootMode.value = false
  Object.assign(form, blankForm(), { domain_group: allGroups.value[0] || '' })
  dialogVisible.value = true
}

const openCreateRoot = () => {
  isEdit.value = false
  isRootMode.value = true
  Object.assign(form, blankForm(), { domain_group: '' })
  dialogVisible.value = true
}

const openCreateChild = (group) => {
  isEdit.value = false
  isRootMode.value = false
  Object.assign(form, {
    ...blankForm(),
    domain_group: group.domain_group,
    parent_domain_code: group.domain_code,
    sort_order: (group.children.at(-1)?.sort_order || group.sort_order || 0) + 1,
  })
  dialogVisible.value = true
}

// ── 编辑 ──
// isRoot=true 表示编辑大类本身（一级节点）
const openEdit = (row, isRoot = false) => {
  isEdit.value = true
  isRootMode.value = isRoot
  Object.assign(form, {
    domain_code: row.domain_code,
    domain_name: row.domain_name,
    domain_group: row.domain_group,
    parent_domain_code: isRoot ? '' : row.parent_domain_code || '',
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
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  saving.value = true
  try {
    const payload = {
      domain_name: form.domain_name,
      domain_group: form.domain_group,
      parent_domain_code: isRootMode.value ? null : form.parent_domain_code || null,
      description: form.description || null,
      vault_path: form.vault_path || null,
      match_keywords: form.match_keywords || null,
      sort_order: form.sort_order,
      enabled: form.enabled,
    }
    if (isEdit.value) {
      await basicDataApi.updateBusinessDomain(form.domain_code, payload)
      ElMessage.success('已更新，全站选择器已同步刷新')
    } else {
      await basicDataApi.createBusinessDomain({ ...payload, domain_code: form.domain_code })
      ElMessage.success('已创建，全站选择器已同步刷新')
    }
    dialogVisible.value = false
    await loadData()
    refreshBusinessDomains().catch(() => {})
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || err?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

// ── 快速启停 ──
const handleToggle = async (row, val) => {
  try {
    await basicDataApi.updateBusinessDomain(row.domain_code, { enabled: val })
    row.enabled = val
    ElMessage.success(val ? `已启用「${row.domain_name}」` : `已停用「${row.domain_name}」`)
    refreshBusinessDomains().catch(() => {})
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '操作失败')
  }
}

const handleDisable = async (code) => {
  try {
    await ElMessageBox.confirm(
      '停用后该业务领域将不再出现在全站下拉选择中（已有数据不受影响，可随时重新启用）。',
      '确定停用？',
      { confirmButtonText: '停用', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await basicDataApi.deleteBusinessDomain(code)
    ElMessage.success('已停用，全站选择器已同步刷新')
    await loadData()
    refreshBusinessDomains().catch(() => {})
  } catch {
    ElMessage.error('停用失败')
  }
}

const handleEnable = async (code) => {
  try {
    await basicDataApi.updateBusinessDomain(code, { enabled: true })
    ElMessage.success('已启用，全站选择器已同步刷新')
    await loadData()
    refreshBusinessDomains().catch(() => {})
  } catch {
    ElMessage.error('启用失败')
  }
}

// ── 重置 ──
const resetForm = () => {
  Object.assign(form, blankForm())
  formRef.value?.clearValidate()
}

onMounted(loadData)
</script>

<style scoped>
.bdm-page {
  max-width: 1280px;
  margin: 0 auto;
  padding: 20px 24px;
}

.bdm-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 18px;
}

.bdm-header-left h2 {
  margin: 0;
  font-size: 20px;
}

.bdm-header-sub {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-left: 10px;
}

.bdm-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.bdm-group-card {
  margin-bottom: 18px;
}

.bdm-group-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bdm-group-header-spacer {
  flex: 1;
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

.bdm-group-off {
  font-size: 12px;
  color: #f56c6c;
}

.bdm-counts {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: var(--el-text-color-regular);
}

.bdm-counts span {
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--el-fill-color-light);
}

.bdm-kw {
  font-size: 12px;
  font-family: monospace;
}

.bdm-muted {
  color: var(--el-text-color-placeholder);
}

:deep(.bdm-row-off) {
  opacity: 0.5;
}
</style>
