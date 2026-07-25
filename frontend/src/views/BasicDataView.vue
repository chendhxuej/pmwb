<template>
  <div class="bd-view">
    <!-- 顶部栏 -->
    <div class="bd-topbar">
      <div class="bd-titles">
        <h2 class="bd-title">基础数据</h2>
        <div class="bd-crumb">组织与人员主数据 · 全站选人统一来源</div>
      </div>
      <div class="bd-actions">
        <el-button type="primary" @click="openOrgCreate">
          <el-icon><Plus /></el-icon><span>新增组织</span>
        </el-button>
      </div>
    </div>

    <div class="bd-body">
      <!-- 左：组织列表 -->
      <div class="bd-org-card">
        <div class="bd-panel-head">
        <span class="bd-panel-title">组织 / 团队</span>
        <span class="bd-panel-count">{{ orgs.length }}</span>
        <span class="bd-panel-hint">（左侧点选组织，右侧维护成员）</span>
        </div>
        <div class="bd-org-list" v-loading="orgLoading">
          <div
            v-for="org in orgs"
            :key="org.id"
            class="bd-org-item"
            :class="{ active: selectedOrgId === org.id }"
            @click="selectOrg(org)"
          >
            <div class="bd-org-main">
              <span class="bd-org-name">{{ org.name }}</span>
              <el-tag v-if="!org.enabled" size="small" type="info" effect="plain">已停用</el-tag>
            </div>
            <div class="bd-org-meta">
              <span class="bd-org-count">{{ org.staff_count || 0 }} 人</span>
              <span class="bd-org-ops">
                <el-button link type="primary" size="small" @click.stop="openOrgEdit(org)">编辑</el-button>
                <el-button link type="danger" size="small" @click.stop="removeOrg(org)">删除</el-button>
              </span>
            </div>
          </div>
          <el-empty v-if="!orgLoading && !orgs.length" description="暂无组织" :image-size="80" />
        </div>
      </div>

      <!-- 右：人员列表 -->
      <div class="bd-staff-card">
        <div class="bd-panel-head">
          <span class="bd-panel-title">
            人员
            <template v-if="selectedOrg">· {{ selectedOrg.name }}</template>
          </span>
          <div class="bd-staff-tools">
            <el-input
              v-model="keyword"
              class="bd-search"
              placeholder="搜索姓名 / 身份 / 邮箱"
              clearable
              @input="loadStaffs"
              @clear="loadStaffs"
            >
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-button type="primary" :disabled="!selectedOrgId" @click="openStaffCreate">
              <el-icon><Plus /></el-icon><span>新增人员</span>
            </el-button>
          </div>
        </div>

        <el-table
          v-loading="staffLoading"
          :data="staffs"
          class="bd-staff-table"
          row-key="id"
          empty-text="请先在左侧选择组织"
        >
          <el-table-column prop="name" label="姓名" width="120" />
          <el-table-column prop="role_hint" label="身份" width="130" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tag v-if="row.role_hint" size="small" effect="light" type="primary">{{ row.role_hint }}</el-tag>
              <span v-else class="bd-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column prop="email" label="邮箱" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.email" class="bd-email">{{ row.email }}</span>
              <span v-else class="bd-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column prop="phone" label="电话" width="130">
            <template #default="{ row }">
              <span v-if="row.phone">{{ row.phone }}</span>
              <span v-else class="bd-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column prop="enabled" label="状态" width="90">
            <template #default="{ row }">
              <el-tag v-if="row.enabled" size="small" type="success" effect="light">启用</el-tag>
              <el-tag v-else size="small" type="info" effect="plain">停用</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="130" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openStaffEdit(row)">编辑</el-button>
              <el-button link type="danger" size="small" @click="removeStaff(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 组织编辑弹窗 -->
    <el-dialog v-model="orgDialogVisible" :title="orgForm.id ? '编辑组织' : '新增组织'" width="420px" append-to-body>
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

    <!-- 人员编辑弹窗 -->
    <el-dialog v-model="staffDialogVisible" :title="staffForm.id ? '编辑人员' : '新增人员'" width="460px" append-to-body>
      <el-form :model="staffForm" label-width="72px">
        <el-form-item label="姓名" required>
          <el-input v-model="staffForm.name" placeholder="姓名" />
        </el-form-item>
        <el-form-item label="所属组织" required>
          <el-select v-model="staffForm.org_id" placeholder="选择组织" style="width: 100%" :disabled="!orgs.length">
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
            <el-option v-for="r in identityOptions" :key="r" :label="r" :value="r" />
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
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { basicDataApi, refreshStaffOptions } from '@/api/basicData.js'

const orgs = ref([])
const orgLoading = ref(false)
const selectedOrgId = ref(null)

const staffs = ref([])
const staffLoading = ref(false)
const keyword = ref('')

// ── 组织弹窗 ──
const orgDialogVisible = ref(false)
const orgForm = reactive({ id: null, name: '', sort: 0, enabled: true })

// ── 人员弹窗 ──
const staffDialogVisible = ref(false)
const IDENTITY_OPTIONS = [
  '产品经理',
  '业务维护',
  '系统维护',
  '项目经理',
  '开发负责人',
  '测试负责人',
  '业务对接人',
  '运营负责人',
  '数据分析',
  '综合管理',
]

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

const selectedOrg = computed(() => orgs.value.find((o) => o.id === selectedOrgId.value) || null)

async function loadOrgs() {
  orgLoading.value = true
  try {
    const data = await basicDataApi.listOrgs()
    orgs.value = Array.isArray(data) ? data : []
    if (!selectedOrgId.value && orgs.value.length) {
      selectOrg(orgs.value[0])
    }
  } catch (e) {
    ElMessage.error(e?.message || '组织列表加载失败')
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
    ElMessage.error(e?.message || '人员列表加载失败')
  } finally {
    staffLoading.value = false
  }
}

// ── 组织 CRUD ──
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
    if (orgForm.id) {
      await basicDataApi.updateOrg(orgForm.id, { name: orgForm.name, sort: orgForm.sort, enabled: orgForm.enabled })
      ElMessage.success('组织已更新')
    } else {
      await basicDataApi.createOrg({ name: orgForm.name, sort: orgForm.sort, enabled: orgForm.enabled })
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
      `确认删除组织「${org.name}」？该组织下 ${org.staff_count || 0} 名人员将一并删除。`,
      '删除确认',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await basicDataApi.deleteOrg(org.id)
    ElMessage.success('组织已删除')
    if (selectedOrgId.value === org.id) selectedOrgId.value = null
    await loadOrgs()
    await refreshStaffOptions()
  } catch (e) {
    ElMessage.error(e?.message || '删除失败')
  }
}

// ── 人员 CRUD ──
function openStaffCreate() {
  Object.assign(staffForm, {
    id: null,
    name: '',
    org_id: selectedOrgId.value,
    email: '',
    phone: '',
    role_hint: '业务维护',
    sort: staffs.value.length,
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
  if (!staffForm.name.trim()) {
    ElMessage.warning('请填写姓名')
    return
  }
  if (!staffForm.role_hint || !staffForm.role_hint.trim()) {
    ElMessage.warning('请选择或填写身份')
    return
  }
  if (!staffForm.org_id) {
    ElMessage.warning('请选择所属组织')
    return
  }
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
  } catch {
    return
  }
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

onMounted(() => {
  loadOrgs()
})
</script>

<style scoped>
.bd-view {
  padding: 0 4px 24px;
}
.bd-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.bd-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1f2d3d;
}
.bd-crumb {
  margin-top: 4px;
  font-size: 13px;
  color: #8a94a6;
}
.bd-body {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 16px;
  align-items: start;
}
.bd-org-card,
.bd-staff-card {
  background: #fff;
  border: 1px solid #eef0f4;
  border-radius: 14px;
  box-shadow: 0 2px 12px rgba(31, 45, 61, 0.04);
  min-height: 420px;
  display: flex;
  flex-direction: column;
}
.bd-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #f2f4f8;
}
.bd-panel-title {
  font-size: 15px;
  font-weight: 600;
  color: #1f2d3d;
}
.bd-panel-count {
  font-size: 12px;
  color: #8a94a6;
  background: #f2f4f8;
  border-radius: 10px;
  padding: 1px 9px;
}
.bd-panel-hint {
  font-size: 12px;
  color: #8a94a6;
  margin-left: 8px;
  font-weight: normal;
}
.bd-staff-tools {
  display: flex;
  align-items: center;
  gap: 8px;
}
.bd-search {
  width: 200px;
}
.bd-org-list {
  padding: 8px;
  overflow-y: auto;
  flex: 1;
}
.bd-org-item {
  padding: 11px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s;
  border: 1px solid transparent;
}
.bd-org-item:hover {
  background: #f6f8fc;
}
.bd-org-item.active {
  background: #eaf1ff;
  border-color: #cfe0ff;
}
.bd-org-main {
  display: flex;
  align-items: center;
  gap: 8px;
}
.bd-org-name {
  font-size: 14px;
  font-weight: 600;
  color: #1f2d3d;
}
.bd-org-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 4px;
}
.bd-org-count {
  font-size: 12px;
  color: #8a94a6;
}
.bd-org-ops {
  opacity: 0;
  transition: opacity 0.15s;
}
.bd-org-item:hover .bd-org-ops {
  opacity: 1;
}
.bd-staff-table {
  padding: 4px 8px 12px;
}
.bd-email {
  color: #2f6fed;
  font-size: 13px;
}
.bd-muted {
  color: #c0c4cc;
}
@media (max-width: 900px) {
  .bd-body {
    grid-template-columns: 1fr;
  }
}
</style>
