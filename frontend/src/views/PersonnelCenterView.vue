<template>
  <div class="pc-view">
    <!-- 顶部栏 -->
    <div class="pc-topbar">
      <div class="pc-titles">
        <h2 class="pc-title">人员中台</h2>
        <div class="pc-crumb">组织 / 身份 / 人员定义管理 · 全站统一数据源</div>
      </div>
      <div class="pc-actions">
        <el-button @click="downloadTemplate">
          <el-icon><Download /></el-icon><span>下载模板</span>
        </el-button>
        <el-button @click="openImport">
          <el-icon><Upload /></el-icon><span>导入</span>
        </el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="pc-tabs" type="border-card">
      <!-- 组织管理 -->
      <el-tab-pane label="组织管理" name="org">
        <div class="pc-tab-body">
          <div class="pc-tab-toolbar">
            <EnlargeInput
              v-model="orgKeyword"
              class="pc-search"
              placeholder="搜索组织名称"
              clearable
              :prefix-icon="Search"
            />
            <el-button type="primary" @click="openOrgCreate">
              <el-icon><Plus /></el-icon><span>新增组织</span>
            </el-button>
          </div>
          <el-table
            v-loading="orgLoading"
            :data="filteredOrgs"
            class="pc-table"
            row-key="id"
            :empty-text="'暂无组织'"
          >
            <el-table-column prop="name" label="组织名称" min-width="160" show-overflow-tooltip />
            <el-table-column prop="sort" label="排序" width="90" />
            <el-table-column prop="staff_count" label="人数" width="90">
              <template #default="{ row }">
                <el-tag size="small" effect="plain" type="info">{{ row.staff_count || 0 }} 人</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="enabled" label="状态" width="90">
              <template #default="{ row }">
                <el-tag v-if="row.enabled" size="small" type="success" effect="light">启用</el-tag>
                <el-tag v-else size="small" type="info" effect="plain">停用</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openOrgEdit(row)">
                  <el-icon><Edit /></el-icon><span>编辑</span>
                </el-button>
                <el-button link type="danger" size="small" @click="removeOrg(row)">
                  <el-icon><Delete /></el-icon><span>删除</span>
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- 身份管理 -->
      <el-tab-pane label="身份管理" name="role">
        <div class="pc-tab-body">
          <div class="pc-tab-toolbar">
            <EnlargeInput
              v-model="roleKeyword"
              class="pc-search"
              placeholder="搜索身份名称"
              clearable
              :prefix-icon="Search"
            />
            <el-button type="primary" @click="openRoleCreate">
              <el-icon><Plus /></el-icon><span>新增身份</span>
            </el-button>
          </div>
          <el-table
            v-loading="roleLoading"
            :data="filteredRoles"
            class="pc-table"
            row-key="id"
            :empty-text="'暂无身份'"
          >
            <el-table-column prop="name" label="身份名称" min-width="180" show-overflow-tooltip />
            <el-table-column prop="sort" label="排序" width="90" />
            <el-table-column prop="enabled" label="状态" width="90">
              <template #default="{ row }">
                <el-tag v-if="row.enabled" size="small" type="success" effect="light">启用</el-tag>
                <el-tag v-else size="small" type="info" effect="plain">停用</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openRoleEdit(row)">
                  <el-icon><Edit /></el-icon><span>编辑</span>
                </el-button>
                <el-button link type="danger" size="small" @click="removeRole(row)">
                  <el-icon><Delete /></el-icon><span>删除</span>
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- 人员管理 -->
      <el-tab-pane label="人员管理" name="staff">
        <div class="pc-tab-body">
          <div class="pc-tab-toolbar">
            <el-select
              v-model="staffOrgFilter"
              placeholder="全部组织"
              clearable
              class="pc-org-filter"
            >
              <el-option
                v-for="o in orgs"
                :key="o.id"
                :label="o.name"
                :value="o.id"
              />
            </el-select>
            <EnlargeInput
              v-model="staffKeyword"
              class="pc-search"
              placeholder="搜索姓名 / 身份 / 邮箱"
              clearable
              :prefix-icon="Search"
              @keyup.enter="loadStaffs"
            />
            <el-button @click="loadStaffs" :icon="Search">查询</el-button>
            <el-button type="primary" @click="openStaffCreate">
              <el-icon><Plus /></el-icon><span>新增人员</span>
            </el-button>
          </div>
          <el-table
            v-loading="staffLoading"
            :data="staffs"
            class="pc-table"
            row-key="id"
            :empty-text="'暂无人员'"
          >
            <el-table-column prop="name" label="姓名" width="120" />
            <el-table-column prop="org_name" label="所属组织" width="150" show-overflow-tooltip />
            <el-table-column prop="role_hint" label="身份" width="130" show-overflow-tooltip>
              <template #default="{ row }">
                <el-tag v-if="row.role_hint" size="small" effect="light" type="primary">{{ row.role_hint }}</el-tag>
                <span v-else class="pc-muted">—</span>
              </template>
            </el-table-column>
            <el-table-column prop="email" label="邮箱" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.email" class="pc-email">{{ row.email }}</span>
                <span v-else class="pc-muted">—</span>
              </template>
            </el-table-column>
            <el-table-column prop="phone" label="电话" width="130" />
            <el-table-column prop="enabled" label="状态" width="90">
              <template #default="{ row }">
                <el-tag v-if="row.enabled" size="small" type="success" effect="light">启用</el-tag>
                <el-tag v-else size="small" type="info" effect="plain">停用</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openStaffEdit(row)">
                  <el-icon><Edit /></el-icon><span>编辑</span>
                </el-button>
                <el-button link type="danger" size="small" @click="removeStaff(row)">
                  <el-icon><Delete /></el-icon><span>删除</span>
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 组织编辑弹窗 -->
    <el-dialog v-model="orgDialogVisible" :title="orgForm.id ? '编辑组织' : '新增组织'" width="420px" append-to-body>
      <el-form :model="orgForm" label-width="72px">
        <el-form-item label="名称" required>
          <EnlargeInput v-model="orgForm.name" placeholder="如：政企业务部" />
        </el-form-item>
        <el-form-item label="排序号">
          <el-input-number v-model="orgForm.sort" :min="0" :step="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="orgForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="orgDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitOrg">保存</el-button>
      </template>
    </el-dialog>

    <!-- 身份编辑弹窗 -->
    <el-dialog v-model="roleDialogVisible" :title="roleForm.id ? '编辑身份' : '新增身份'" width="420px" append-to-body>
      <el-form :model="roleForm" label-width="72px">
        <el-form-item label="名称" required>
          <EnlargeInput v-model="roleForm.name" placeholder="如：产品经理" />
        </el-form-item>
        <el-form-item label="排序号">
          <el-input-number v-model="roleForm.sort" :min="0" :step="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="roleForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitRole">保存</el-button>
      </template>
    </el-dialog>

    <!-- 人员编辑弹窗 -->
    <el-dialog v-model="staffDialogVisible" :title="staffForm.id ? '编辑人员' : '新增人员'" width="480px" append-to-body>
      <el-form :model="staffForm" label-width="72px">
        <el-form-item label="姓名" required>
          <EnlargeInput v-model="staffForm.name" placeholder="姓名" />
        </el-form-item>
        <el-form-item label="所属组织" required>
          <el-select v-model="staffForm.org_id" placeholder="选择组织" style="width: 100%" :disabled="!orgs.length">
            <el-option v-for="o in orgs" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="邮箱">
          <EnlargeInput v-model="staffForm.email" placeholder="可选，用于邮件提醒" />
        </el-form-item>
        <el-form-item label="电话">
          <EnlargeInput v-model="staffForm.phone" placeholder="可选" />
        </el-form-item>
        <el-form-item label="身份" required>
          <el-select
            v-model="staffForm.role_hint"
            placeholder="选择身份"
            filterable
            allow-create
            default-first-option
            clearable
            style="width: 100%"
          >
            <el-option v-for="r in roles" :key="r.id" :label="r.name" :value="r.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序号">
          <el-input-number v-model="staffForm.sort" :min="0" :step="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="staffForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="staffDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitStaff">保存</el-button>
      </template>
    </el-dialog>

    <!-- 文件导入隐藏输入 -->
    <input
      ref="fileInput"
      type="file"
      accept=".xlsx,.xls"
      style="display: none"
      @change="handleImportFile"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Download, Upload, Edit, Delete } from '@element-plus/icons-vue'
import { basicDataApi, refreshStaffOptions } from '@/api/basicData.js'

const activeTab = ref('org')
const fileInput = ref(null)

// ── 组织 ──
const orgs = ref([])
const orgLoading = ref(false)
const orgKeyword = ref('')
const orgDialogVisible = ref(false)
const orgForm = reactive({ id: null, name: '', sort: 0, enabled: true })

const filteredOrgs = computed(() => {
  const kw = orgKeyword.value.trim().toLowerCase()
  if (!kw) return orgs.value
  return orgs.value.filter((o) => (o.name || '').toLowerCase().includes(kw))
})

async function loadOrgs() {
  orgLoading.value = true
  try {
    const data = await basicDataApi.listOrgs()
    orgs.value = Array.isArray(data) ? data : []
  } catch (e) {
    ElMessage.error(e?.message || '组织列表加载失败')
  } finally {
    orgLoading.value = false
  }
}

function openOrgCreate() {
  Object.assign(orgForm, { id: null, name: '', sort: orgs.value.length, enabled: true })
  orgDialogVisible.value = true
}
function openOrgEdit(org) {
  Object.assign(orgForm, { id: org.id, name: org.name, sort: org.sort || 0, enabled: org.enabled })
  orgDialogVisible.value = true
}
async function submitOrg() {
  if (!orgForm.name.trim()) {
    ElMessage.warning('请填写组织名称')
    return
  }
  try {
    const payload = { name: orgForm.name.trim(), sort: orgForm.sort, enabled: orgForm.enabled }
    if (orgForm.id) {
      await basicDataApi.updateOrg(orgForm.id, payload)
      ElMessage.success('组织已更新')
    } else {
      await basicDataApi.createOrg(payload)
      ElMessage.success('组织已创建')
    }
    orgDialogVisible.value = false
    await loadOrgs()
    await refreshStaffOptions()
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  }
}
async function removeOrg(org) {
  try {
    await ElMessageBox.confirm(
      `确认删除组织「${org.name}」？该组织下 ${org.staff_count || 0} 名成员将一并删除。`,
      '删除确认',
      { type: 'warning' },
    )
  } catch { return }
  try {
    await basicDataApi.deleteOrg(org.id)
    ElMessage.success('组织已删除')
    await loadOrgs()
    await refreshStaffOptions()
  } catch (e) {
    ElMessage.error(e?.message || '删除失败')
  }
}

// ── 身份 ──
const roles = ref([])
const roleLoading = ref(false)
const roleKeyword = ref('')
const roleDialogVisible = ref(false)
const roleForm = reactive({ id: null, name: '', sort: 0, enabled: true })

const filteredRoles = computed(() => {
  const kw = roleKeyword.value.trim().toLowerCase()
  if (!kw) return roles.value
  return roles.value.filter((r) => (r.name || '').toLowerCase().includes(kw))
})

async function loadRoles() {
  roleLoading.value = true
  try {
    const data = await basicDataApi.listRoles()
    roles.value = Array.isArray(data) ? data : []
  } catch (e) {
    ElMessage.error(e?.message || '身份列表加载失败')
  } finally {
    roleLoading.value = false
  }
}

function openRoleCreate() {
  Object.assign(roleForm, { id: null, name: '', sort: roles.value.length, enabled: true })
  roleDialogVisible.value = true
}
function openRoleEdit(role) {
  Object.assign(roleForm, { id: role.id, name: role.name, sort: role.sort || 0, enabled: role.enabled })
  roleDialogVisible.value = true
}
async function submitRole() {
  if (!roleForm.name.trim()) {
    ElMessage.warning('请填写身份名称')
    return
  }
  try {
    const payload = { name: roleForm.name.trim(), sort: roleForm.sort, enabled: roleForm.enabled }
    if (roleForm.id) {
      await basicDataApi.updateRole(roleForm.id, payload)
      ElMessage.success('身份已更新')
    } else {
      await basicDataApi.createRole(payload)
      ElMessage.success('身份已创建')
    }
    roleDialogVisible.value = false
    await loadRoles()
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  }
}
async function removeRole(role) {
  try {
    await ElMessageBox.confirm(`确认删除身份「${role.name}」？`, '删除确认', { type: 'warning' })
  } catch { return }
  try {
    await basicDataApi.deleteRole(role.id)
    ElMessage.success('身份已删除')
    await loadRoles()
  } catch (e) {
    ElMessage.error(e?.message || '删除失败')
  }
}

// ── 人员 ──
const staffs = ref([])
const staffLoading = ref(false)
const staffOrgFilter = ref(null)
const staffKeyword = ref('')
const staffDialogVisible = ref(false)
const staffForm = reactive({
  id: null,
  name: '',
  org_id: null,
  email: '',
  phone: '',
  role_hint: '',
  sort: 0,
  enabled: true,
})

async function loadStaffs() {
  staffLoading.value = true
  try {
    const data = await basicDataApi.listStaffs({
      org_id: staffOrgFilter.value || undefined,
      keyword: staffKeyword.value || undefined,
    })
    staffs.value = Array.isArray(data) ? data : []
  } catch (e) {
    ElMessage.error(e?.message || '人员列表加载失败')
  } finally {
    staffLoading.value = false
  }
}

function openStaffCreate() {
  if (!orgs.value.length) {
    ElMessage.warning('请先创建组织')
    activeTab.value = 'org'
    return
  }
  Object.assign(staffForm, {
    id: null,
    name: '',
    org_id: staffOrgFilter.value || orgs.value[0]?.id || null,
    email: '',
    phone: '',
    role_hint: '',
    sort: 0,
    enabled: true,
  })
  staffDialogVisible.value = true
}
function openStaffEdit(row) {
  Object.assign(staffForm, {
    id: row.id,
    name: row.name,
    org_id: row.org_id,
    email: row.email || '',
    phone: row.phone || '',
    role_hint: row.role_hint || '',
    sort: row.sort || 0,
    enabled: row.enabled,
  })
  staffDialogVisible.value = true
}
async function submitStaff() {
  if (!staffForm.name.trim()) { ElMessage.warning('请填写姓名'); return }
  if (!staffForm.role_hint?.trim()) { ElMessage.warning('请选择或填写身份'); return }
  if (!staffForm.org_id) { ElMessage.warning('请选择所属组织'); return }
  try {
    const payload = {
      name: staffForm.name.trim(),
      org_id: staffForm.org_id,
      email: staffForm.email || null,
      phone: staffForm.phone || null,
      role_hint: staffForm.role_hint.trim(),
      sort: staffForm.sort,
      enabled: staffForm.enabled,
    }
    if (staffForm.id) {
      await basicDataApi.updateStaff(staffForm.id, payload)
      ElMessage.success('人员已更新')
    } else {
      await basicDataApi.createStaff(payload)
      ElMessage.success('人员已创建')
    }
    staffDialogVisible.value = false
    await loadStaffs()
    await loadOrgs()
    await refreshStaffOptions()
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  }
}
async function removeStaff(row) {
  try {
    await ElMessageBox.confirm(`确认删除人员「${row.name}」？`, '删除确认', { type: 'warning' })
  } catch { return }
  try {
    await basicDataApi.deleteStaff(row.id)
    ElMessage.success('人员已删除')
    await loadStaffs()
    await loadOrgs()
    await refreshStaffOptions()
  } catch (e) {
    ElMessage.error(e?.message || '删除失败')
  }
}

// ── 导入/导出 ──
async function downloadTemplate() {
  try {
    const blob = await basicDataApi.downloadTemplate()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '团队信息导入模板.xlsx'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success('模板下载成功')
  } catch (e) {
    ElMessage.error(e?.message || '模板下载失败')
  }
}
function openImport() {
  if (fileInput.value) {
    fileInput.value.value = ''
    fileInput.value.click()
  }
}
async function handleImportFile(event) {
  const file = event.target.files?.[0]
  if (!file) return
  try {
    await ElMessageBox.confirm(
      `确认导入文件「${file.name}」？相同组织+姓名的成员将被覆盖更新。`,
      '导入确认',
      { type: 'warning' },
    )
  } catch { return }
  try {
    const result = await basicDataApi.importFromExcel(file)
    ElMessage.success(
      `导入完成：新增 ${result.created_orgs || 0} 个组织、${result.created_staffs || 0} 名成员，更新 ${result.updated_orgs || 0} 个组织、${result.updated_staffs || 0} 名成员`,
    )
    if (result.errors?.length) {
      ElMessage.warning(`导入存在 ${result.errors.length} 行异常：${result.errors.slice(0, 3).join('；')}`)
    }
    await loadOrgs()
    await loadRoles()
    await loadStaffs()
    await refreshStaffOptions()
  } catch (e) {
    ElMessage.error(e?.message || '导入失败')
  }
}

// ── 切换 tab 时按需加载 ──
watch(activeTab, (tab) => {
  if (tab === 'org') loadOrgs()
  if (tab === 'role') loadRoles()
  if (tab === 'staff') {
    loadOrgs()
    loadRoles()
    loadStaffs()
  }
})

onMounted(() => {
  loadOrgs()
})
</script>

<style scoped>
.pc-view {
  padding: 0 4px 24px;
}
.pc-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.pc-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1f2d3d;
}
.pc-crumb {
  margin-top: 4px;
  font-size: 13px;
  color: #8a94a6;
}
.pc-tabs :deep(.el-tabs__content) {
  padding: 0;
}
.pc-tab-body {
  padding: 16px;
  background: #fff;
  min-height: 420px;
}
.pc-tab-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.pc-search {
  width: 240px;
}
.pc-org-filter {
  width: 200px;
}
.pc-table {
  width: 100%;
}
.pc-email {
  color: #2f6fed;
  font-size: 13px;
}
.pc-muted {
  color: #c0c4cc;
}
</style>
