<template>
  <el-drawer
    v-model="visible"
    title="团队信息管理"
    direction="rtl"
    size="72%"
    :close-on-click-modal="false"
    append-to-body
    destroy-on-close
    @opened="onOpened"
  >
    <div class="admin-drawer">
      <!-- 工具栏 -->
      <div class="admin-toolbar">
        <div class="admin-toolbar-left">
          <el-button @click="downloadTemplate" size="small">
            <el-icon><Download /></el-icon><span>下载模板</span>
          </el-button>
          <el-button @click="openImport" size="small">
            <el-icon><Upload /></el-icon><span>导入</span>
          </el-button>
        </div>
        <div class="admin-toolbar-right">
          <el-button type="primary" @click="openOrgCreate" size="small">
            <el-icon><Plus /></el-icon><span>新增团队</span>
          </el-button>
        </div>
      </div>

      <div class="admin-body">
        <!-- 左：团队列表 -->
        <div class="admin-org-card">
          <div class="admin-panel-head">
            <span class="admin-panel-title">团队</span>
            <span class="admin-panel-count">{{ orgs.length }}</span>
          </div>
          <div class="admin-org-list" v-loading="orgLoading">
            <div
              v-for="org in orgs"
              :key="org.id"
              class="admin-org-item"
              :class="{ active: selectedOrgId === org.id }"
              @click="selectOrg(org)"
            >
              <div class="admin-org-main">
                <span class="admin-org-name">{{ org.name }}</span>
                <el-tag v-if="!org.enabled" size="small" type="info" effect="plain">停用</el-tag>
              </div>
              <div class="admin-org-meta">
                <span class="admin-org-count">{{ org.staff_count || 0 }} 人</span>
                <span class="admin-org-ops">
                  <el-button link type="primary" size="small" @click.stop="openOrgEdit(org)">编辑</el-button>
                  <el-button link type="danger" size="small" @click.stop="removeOrg(org)">删除</el-button>
                </span>
              </div>
            </div>
            <el-empty v-if="!orgLoading && !orgs.length" description="暂无团队" :image-size="60">
              <template #description>
                <div class="admin-empty-hint">
                  <p>暂无团队</p>
                  <p>点击上方「新增团队」或「导入」开始</p>
                </div>
              </template>
            </el-empty>
          </div>
        </div>

        <!-- 右：成员列表 -->
        <div class="admin-staff-card">
          <div class="admin-panel-head">
            <span class="admin-panel-title">
              成员<template v-if="selectedOrg"> · {{ selectedOrg.name }}</template>
            </span>
            <div class="admin-staff-tools">
              <el-input
                v-model="keyword"
                class="admin-search"
                placeholder="搜索姓名/身份/邮箱"
                clearable
                size="small"
                @input="loadStaffs"
                @clear="loadStaffs"
              >
                <template #prefix><el-icon><Search /></el-icon></template>
              </el-input>
              <el-button type="primary" :disabled="!selectedOrgId" @click="openStaffCreate" size="small">
                <el-icon><Plus /></el-icon><span>新增成员</span>
              </el-button>
            </div>
          </div>

          <el-table
            v-loading="staffLoading"
            :data="staffs"
            class="admin-staff-table"
            row-key="id"
            size="small"
            :empty-text="selectedOrgId ? '暂无成员' : '请先在左侧选择一个团队'"
          >
            <el-table-column prop="name" label="姓名" width="100" />
            <el-table-column prop="role_hint" label="身份" width="120" show-overflow-tooltip>
              <template #default="{ row }">
                <el-tag v-if="row.role_hint" size="small" effect="light" type="primary">{{ row.role_hint }}</el-tag>
                <span v-else class="admin-muted">—</span>
              </template>
            </el-table-column>
            <el-table-column prop="email" label="邮箱" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.email" class="admin-email">{{ row.email }}</span>
                <span v-else class="admin-muted">—</span>
              </template>
            </el-table-column>
            <el-table-column prop="phone" label="电话" width="120">
              <template #default="{ row }">
                <span v-if="row.phone">{{ row.phone }}</span>
                <span v-else class="admin-muted">—</span>
              </template>
            </el-table-column>
            <el-table-column prop="enabled" label="状态" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.enabled" size="small" type="success" effect="light">启用</el-tag>
                <el-tag v-else size="small" type="info" effect="plain">停用</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openStaffEdit(row)">编辑</el-button>
                <el-button link type="danger" size="small" @click="removeStaff(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </div>

    <!-- 团队编辑弹窗 -->
    <el-dialog v-model="orgDialogVisible" :title="orgForm.id ? '编辑团队' : '新增团队'" width="400px" append-to-body>
      <el-form :model="orgForm" label-width="72px">
        <el-form-item label="名称" required>
          <el-input v-model="orgForm.name" placeholder="如：政企业务部" />
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

    <!-- 成员编辑弹窗 -->
    <el-dialog v-model="staffDialogVisible" :title="staffForm.id ? '编辑成员' : '新增成员'" width="440px" append-to-body>
      <el-form :model="staffForm" label-width="72px">
        <el-form-item label="姓名" required>
          <el-input v-model="staffForm.name" placeholder="姓名" />
        </el-form-item>
        <el-form-item label="所属团队" required>
          <el-select v-model="staffForm.org_id" placeholder="选择团队" style="width: 100%" :disabled="!orgs.length">
            <el-option v-for="o in orgs" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="staffForm.email" placeholder="可选，用于邮件提醒" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="staffForm.phone" placeholder="可选" />
        </el-form-item>
        <el-form-item label="身份" required>
          <el-select
            v-model="staffForm.role_hint"
            placeholder="选择或输入身份"
            filterable
            allow-create
            default-first-option
            clearable
            style="width: 100%"
          >
            <el-option v-for="r in IDENTITY_OPTIONS" :key="r" :label="r" :value="r" />
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
  </el-drawer>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Download, Upload } from '@element-plus/icons-vue'
import { basicDataApi, refreshStaffOptions } from '@/api/basicData.js'
import { useStaffAdmin } from '@/composables/useStaffAdmin.js'

const { visible, activeOrgId } = useStaffAdmin()

// ── 数据 ──
const orgs = ref([])
const orgLoading = ref(false)
const selectedOrgId = ref(null)
const staffs = ref([])
const staffLoading = ref(false)
const keyword = ref('')
const fileInput = ref(null)

// ── 团队弹窗 ──
const orgDialogVisible = ref(false)
const orgForm = reactive({ id: null, name: '', sort: 0, enabled: true })

// ── 成员弹窗 ──
const staffDialogVisible = ref(false)
const IDENTITY_OPTIONS = [
  '产品经理', '业务维护', '系统维护', '项目经理',
  '开发负责人', '测试负责人', '业务对接人', '运营负责人',
  '数据分析', '综合管理',
]
const staffForm = reactive({
  id: null, name: '', org_id: null, email: '', phone: '',
  role_hint: '', sort: 0, enabled: true,
})

const selectedOrg = computed(() => orgs.value.find((o) => o.id === selectedOrgId.value) || null)

// ── 抽屉打开时加载数据 ──
function onOpened() {
  loadOrgs()
}

// ── 加载团队 ──
async function loadOrgs() {
  orgLoading.value = true
  try {
    const data = await basicDataApi.listOrgs()
    orgs.value = Array.isArray(data) ? data : []
    // 如果有指定团队或已有选中，保持；否则默认选第一个
    if (activeOrgId.value) {
      selectedOrgId.value = activeOrgId.value
      activeOrgId.value = null
    } else if (!selectedOrgId.value && orgs.value.length) {
      selectedOrgId.value = orgs.value[0].id
    }
    if (selectedOrgId.value) {
      loadStaffs()
    }
  } catch (e) {
    ElMessage.error(e?.message || '团队列表加载失败')
  } finally {
    orgLoading.value = false
  }
}

function selectOrg(org) {
  selectedOrgId.value = org.id
  loadStaffs()
}

async function loadStaffs() {
  if (!selectedOrgId.value) {
    staffs.value = []
    return
  }
  staffLoading.value = true
  try {
    const data = await basicDataApi.listStaffs({
      org_id: selectedOrgId.value,
      keyword: keyword.value || undefined,
    })
    staffs.value = Array.isArray(data) ? data : []
  } catch (e) {
    ElMessage.error(e?.message || '成员列表加载失败')
  } finally {
    staffLoading.value = false
  }
}

// ── 团队 CRUD ──
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
    ElMessage.warning('请填写团队名称')
    return
  }
  try {
    if (orgForm.id) {
      await basicDataApi.updateOrg(orgForm.id, { name: orgForm.name, sort: orgForm.sort, enabled: orgForm.enabled })
      ElMessage.success('团队已更新')
    } else {
      await basicDataApi.createOrg({ name: orgForm.name, sort: orgForm.sort, enabled: orgForm.enabled })
      ElMessage.success('团队已创建')
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
      `确认删除团队「${org.name}」？该团队下 ${org.staff_count || 0} 名成员将一并删除。`,
      '删除确认',
      { type: 'warning' },
    )
  } catch { return }
  try {
    await basicDataApi.deleteOrg(org.id)
    ElMessage.success('团队已删除')
    if (selectedOrgId.value === org.id) selectedOrgId.value = null
    await loadOrgs()
    await refreshStaffOptions()
  } catch (e) {
    ElMessage.error(e?.message || '删除失败')
  }
}

// ── 成员 CRUD ──
function openStaffCreate() {
  Object.assign(staffForm, {
    id: null, name: '', org_id: selectedOrgId.value,
    email: '', phone: '', role_hint: '业务维护',
    sort: staffs.value.length, enabled: true,
  })
  staffDialogVisible.value = true
}
function openStaffEdit(row) {
  Object.assign(staffForm, {
    id: row.id, name: row.name, org_id: row.org_id,
    email: row.email || '', phone: row.phone || '',
    role_hint: row.role_hint || '', sort: row.sort || 0, enabled: row.enabled,
  })
  staffDialogVisible.value = true
}
async function submitStaff() {
  if (!staffForm.name.trim()) { ElMessage.warning('请填写姓名'); return }
  if (!staffForm.role_hint?.trim()) { ElMessage.warning('请选择或填写身份'); return }
  if (!staffForm.org_id) { ElMessage.warning('请选择所属团队'); return }
  try {
    const payload = {
      name: staffForm.name,
      org_id: staffForm.org_id,
      email: staffForm.email || null,
      phone: staffForm.phone || null,
      role_hint: staffForm.role_hint.trim(),
      sort: staffForm.sort,
      enabled: staffForm.enabled,
    }
    if (staffForm.id) {
      await basicDataApi.updateStaff(staffForm.id, payload)
      ElMessage.success('成员已更新')
    } else {
      await basicDataApi.createStaff(payload)
      ElMessage.success('成员已创建')
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
    await ElMessageBox.confirm(`确认删除成员「${row.name}」？`, '删除确认', { type: 'warning' })
  } catch { return }
  try {
    await basicDataApi.deleteStaff(row.id)
    ElMessage.success('成员已删除')
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
      `确认导入文件「${file.name}」？相同团队+姓名的成员将被覆盖更新。`,
      '导入确认',
      { type: 'warning' },
    )
  } catch { return }
  try {
    const result = await basicDataApi.importFromExcel(file)
    ElMessage.success(
      `导入完成：新增 ${result.created_orgs || 0} 个团队、${result.created_staffs || 0} 名成员，更新 ${result.updated_orgs || 0} 个团队、${result.updated_staffs || 0} 名成员`,
    )
    if (result.errors?.length) {
      ElMessage.warning(`导入存在 ${result.errors.length} 行异常：${result.errors.slice(0, 3).join('；')}`)
    }
    await loadOrgs()
    await loadStaffs()
    await refreshStaffOptions()
  } catch (e) {
    ElMessage.error(e?.message || '导入失败')
  }
}
</script>

<style scoped>
.admin-drawer {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0 4px;
}
.admin-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 0 12px;
  border-bottom: 1px solid #f0f0f0;
  margin-bottom: 12px;
}
.admin-toolbar-left,
.admin-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.admin-body {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 12px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.admin-org-card,
.admin-staff-card {
  background: #fff;
  border: 1px solid #eef0f4;
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.admin-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid #f2f4f8;
  flex-shrink: 0;
}
.admin-panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2d3d;
}
.admin-panel-count {
  font-size: 12px;
  color: #8a94a6;
  background: #f2f4f8;
  border-radius: 10px;
  padding: 1px 8px;
}
.admin-staff-tools {
  display: flex;
  align-items: center;
  gap: 8px;
}
.admin-search {
  width: 180px;
}
.admin-org-list {
  padding: 6px;
  overflow-y: auto;
  flex: 1;
}
.admin-org-item {
  padding: 10px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
  border: 1px solid transparent;
}
.admin-org-item:hover {
  background: #f6f8fc;
}
.admin-org-item.active {
  background: #eaf1ff;
  border-color: #cfe0ff;
}
.admin-org-main {
  display: flex;
  align-items: center;
  gap: 6px;
}
.admin-org-name {
  font-size: 13px;
  font-weight: 600;
  color: #1f2d3d;
}
.admin-org-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 3px;
}
.admin-org-count {
  font-size: 12px;
  color: #8a94a6;
}
.admin-org-ops {
  display: flex;
  align-items: center;
  gap: 2px;
}
.admin-empty-hint {
  text-align: center;
}
.admin-empty-hint p {
  margin: 0;
  color: #8a94a6;
  font-size: 13px;
}
.admin-staff-table {
  padding: 4px 8px 8px;
  flex: 1;
  overflow-y: auto;
}
.admin-email {
  color: #2f6fed;
  font-size: 13px;
}
.admin-muted {
  color: #c0c4cc;
}
@media (max-width: 800px) {
  .admin-body {
    grid-template-columns: 1fr;
  }
}
</style>
