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
            <el-input
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
          <el-table ref="pmTbl1"
            v-loading="orgLoading"
            :data="filteredOrgs"
            class="pc-table"
            row-key="id"
            :empty-text="'暂无组织'"
          >
            <el-table-column prop="name" label="组织名称" min-width="170">
              <template #default="{ row }">
                <div class="pc-org-cell">
                  <span class="pc-org-title">{{ row.name }}</span>
                  <el-button link type="primary" size="small" class="pc-org-maplink" @click="openOrgMapping(row)">
                    <el-icon><Connection /></el-icon><span>配置映射管理</span>
                  </el-button>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="org_type" label="组织类型" width="92" align="center">
              <template #default="{ row }">
                <el-tag size="small" effect="plain" :type="orgTypeTone(row.org_type)">
                  {{ orgTypeLabel(row.org_type) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="目标系统名" width="140" show-overflow-tooltip>
              <template #default="{ row }">
                <el-tag v-if="row.target_system_name" size="small" type="success" effect="light">
                  {{ row.target_system_name }}
                </el-tag>
                <span v-else class="pc-muted" :title="`未配置，映射到自身：${row.name}`">自身</span>
              </template>
            </el-table-column>
            <el-table-column label="系统别名" min-width="150">
              <template #default="{ row }">
                <div v-if="orgAliasList(row).length" class="pc-alias-wrap">
                  <el-tag v-for="a in orgAliasList(row)" :key="a" size="small" type="info" effect="plain">{{ a }}</el-tag>
                </div>
                <span v-else class="pc-muted">—</span>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="描述" min-width="140" show-overflow-tooltip />
            <el-table-column prop="source_trace" label="数据来源" width="100" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.source_trace" size="small" type="info" effect="plain">{{ row.source_trace }}</el-tag>
                <span v-else class="pc-muted">—</span>
              </template>
            </el-table-column>
            <el-table-column prop="staff_count" label="人数" width="80" align="right">
              <template #default="{ row }">
                <span class="pc-badge">{{ row.staff_count || 0 }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="enabled" label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.enabled" size="small" type="success" effect="light">启用</el-tag>
                <el-tag v-else size="small" type="info" effect="plain">停用</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="165">
              <template #default="{ row }">
                <span class="pc-time">{{ _fmtTime(row.created_at) }}</span>
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
            <el-input
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
          <el-table ref="pmTbl2"
            v-loading="roleLoading"
            :data="filteredRoles"
            class="pc-table"
            row-key="id"
            :empty-text="'暂无身份'"
          >
            <el-table-column prop="name" label="身份名称" min-width="160" show-overflow-tooltip />
            <el-table-column prop="enabled" label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.enabled" size="small" type="success" effect="light">启用</el-tag>
                <el-tag v-else size="small" type="info" effect="plain">停用</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="165">
              <template #default="{ row }">
                <span class="pc-time">{{ _fmtTime(row.created_at) }}</span>
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
            <el-input
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
          <el-table ref="pmTbl3"
            v-loading="staffLoading"
            :data="staffs"
            class="pc-table"
            row-key="id"
            :empty-text="'暂无人员'"
          >
            <el-table-column prop="name" label="姓名" width="100" align="center" />
            <el-table-column prop="org_name" label="所属组织" min-width="140" show-overflow-tooltip />
            <el-table-column prop="role_hint" label="身份" min-width="130" show-overflow-tooltip>
              <template #default="{ row }">
                <el-tag v-if="row.role_hint" size="small" effect="light" type="primary">{{ row.role_hint }}</el-tag>
                <span v-else class="pc-muted">—</span>
              </template>
            </el-table-column>
            <el-table-column prop="email" label="邮箱" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.email" class="pc-email">{{ row.email }}</span>
                <span v-else class="pc-muted">—</span>
              </template>
            </el-table-column>
            <el-table-column prop="phone" label="电话" width="130" show-overflow-tooltip />
            <el-table-column prop="source_trace" label="来源" width="90" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.source_trace" size="small" type="info" effect="plain">{{ row.source_trace }}</el-tag>
                <span v-else class="pc-muted">—</span>
              </template>
            </el-table-column>
            <el-table-column prop="enabled" label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.enabled" size="small" type="success" effect="light">启用</el-tag>
                <el-tag v-else size="small" type="info" effect="plain">停用</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="165">
              <template #default="{ row }">
                <span class="pc-time">{{ _fmtTime(row.created_at) }}</span>
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
    <el-dialog v-model="orgDialogVisible" :title="orgForm.id ? '编辑组织' : '新增组织'" width="560px" append-to-body>
      <el-form :model="orgForm" label-width="88px">
        <el-form-item label="名称" required>
          <el-input v-model="orgForm.name" placeholder="如：政企业务部" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="orgForm.description" type="textarea" :rows="2" placeholder="选填，组织用途说明" />
        </el-form-item>
        <el-divider content-position="left" class="pc-divider">
          <span class="pc-divider-text">配置映射管理（工单识别用）</span>
        </el-divider>
        <el-form-item label="组织类型">
          <el-select v-model="orgForm.org_type" style="width: 100%">
            <el-option v-for="t in orgTypeOptions" :key="t" :label="orgTypeLabel(t)" :value="t" />
          </el-select>
          <div class="pc-hint">
            system=按系统名识别厂家；department/branch=普通组织，不参与工单归一
          </div>
        </el-form-item>
        <el-form-item label="目标系统名">
          <div style="display: flex; gap: 8px; width: 100%">
            <el-select
              v-model="orgForm.target_system_name"
              placeholder="不配置＝映射到自身名称"
              filterable
              clearable
              style="flex: 1"
            >
              <el-option v-for="s in targetSystemOptions" :key="s" :label="s" :value="s" />
            </el-select>
            <el-button @click="createPlatform">新增</el-button>
          </div>
          <div class="pc-hint">
            多个组织填同一个系统名＝多对一归一（如 政企工作台/电子协议 → 订单中心）；
            候选里没有的新平台点「新增」创建为系统组织
          </div>
        </el-form-item>
        <el-form-item label="系统别名">
          <el-input
            v-model="orgForm.aliases"
            type="textarea"
            :rows="2"
            placeholder="半角逗号分隔，如：电子协议系统,电子协议"
          />
          <div class="pc-hint">
            工单标题里可能出现的写法；精确比对，不按子串模糊匹配
          </div>
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
          <el-input v-model="roleForm.name" placeholder="如：产品经理" />
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
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Download, Upload, Edit, Delete, Connection } from '@element-plus/icons-vue'
import { basicDataApi, refreshStaffOptions } from '@/api/basicData.js'

const route = useRoute()
const activeTab = ref('org')
const fileInput = ref(null)

// ── 映射配置候选项 ────────────────────────────────────────────
// org_type 取值域的唯一真相源在人员中台 GET /basic-data/org-type-options；
// 目标系统名候选集走主后端 GET /meta/target-system-options（含历史表 distinct，
// 历史表在 yxtyg_db，中台读不到）。两处失败都静默降级，不阻塞页面。
const orgTypeOptions = ref(['system', 'department', 'branch'])
const targetSystemOptions = ref([])

const ORG_TYPE_LABELS = { system: '系统', department: '部门', branch: '分公司' }
const ORG_TYPE_TONES = { system: 'primary', department: 'info', branch: 'warning' }

function orgTypeLabel(type) {
  return ORG_TYPE_LABELS[type] || ORG_TYPE_LABELS.department
}
function orgTypeTone(type) {
  return ORG_TYPE_TONES[type] || 'info'
}
function orgAliasList(org) {
  return String(org?.aliases || '')
    .split(/[,，]/)
    .map((s) => s.trim())
    .filter(Boolean)
}

async function loadMappingOptions() {
  try {
    const types = await basicDataApi.getOrgTypeOptions()
    if (Array.isArray(types) && types.length) orgTypeOptions.value = types
  } catch {
    /* 中台不可达：沿用内置兜底取值，不阻塞页面 */
  }
  try {
    const systems = await basicDataApi.getTargetSystemOptions()
    if (Array.isArray(systems)) targetSystemOptions.value = systems
  } catch {
    /* 同上：下拉为空时仍可清空/不配置 */
  }
}

// ── 通用工具 ──
function _fmtTime(ts) {
  if (!ts) return '—'
  try {
    const d = new Date(ts)
    if (isNaN(d.getTime())) return String(ts).slice(0, 16)
    const pad = (n) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  } catch {
    return String(ts).slice(0, 16)
  }
}

// ── 组织 ──
const orgs = ref([])
const orgLoading = ref(false)
const orgKeyword = ref('')
const orgDialogVisible = ref(false)
const orgForm = reactive({
  id: null,
  name: '',
  description: '',
  sort: 0,
  enabled: true,
  org_type: 'department',
  target_system_name: '',
  aliases: '',
})

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
  Object.assign(orgForm, {
    id: null,
    name: '',
    description: '',
    sort: orgs.value.length,
    enabled: true,
    org_type: 'department',
    target_system_name: '',
    aliases: '',
  })
  orgDialogVisible.value = true
}
function openOrgEdit(org) {
  Object.assign(orgForm, {
    id: org.id,
    name: org.name,
    description: org.description || '',
    sort: org.sort || 0,
    enabled: org.enabled,
    org_type: org.org_type || 'department',
    target_system_name: org.target_system_name || '',
    aliases: org.aliases || '',
  })
  orgDialogVisible.value = true
}
// 「配置映射管理」入口（组织名称后面的链接）：映射三字段与编辑表单同源，
// 不另起一套弹窗，避免两处维护同一份数据。
function openOrgMapping(org) {
  openOrgEdit(org)
}

// 新增目标系统平台：候选集里没有的新平台，以「系统」类组织创建进人员中台，
// 创建后自动进目标系统名候选（中台实时；主后端 meta 有 60s TTL，本地乐观追加兜底）。
/** 从 axios 错误里取可读文案（后端既有 {code,message} 也有 FastAPI 的 {detail}） */
function errText(e) {
  const d = e?.response?.data || e || {}
  if (typeof d.message === 'string' && d.message) return d.message
  if (typeof d.detail === 'string' && d.detail) return d.detail
  if (Array.isArray(d.detail)) {
    return d.detail.map((x) => (x && x.msg) || '').filter(Boolean).join('；')
  }
  return e?.message || ''
}

/** 把新平台补齐进候选并选中（8000 侧 meta 有 60s TTL，必须本地补一次） */
async function selectNewPlatform(name) {
  await loadOrgs()
  await loadMappingOptions()
  if (!targetSystemOptions.value.includes(name)) {
    targetSystemOptions.value = [...targetSystemOptions.value, name].sort()
  }
  orgForm.target_system_name = name
}

async function createPlatform() {
  let name = ''
  try {
    const ret = await ElMessageBox.prompt(
      '新平台将作为「系统」类组织创建（org_type=system），创建后可为其配置别名、成员，并自动出现在目标系统名候选中。',
      '新增目标系统平台',
      {
        confirmButtonText: '创建',
        cancelButtonText: '取消',
        inputPlaceholder: '如：商客专区运营平台',
        inputValidator: (v) => (v && v.trim() ? true : '请输入平台名称'),
      }
    )
    name = (ret.value || '').trim()
  } catch {
    return // 取消
  }
  if (targetSystemOptions.value.includes(name)) {
    orgForm.target_system_name = name
    ElMessage.info(`「${name}」已在候选集中，已为你选中`)
    return
  }
  try {
    await basicDataApi.createOrg({
      name,
      description: null,
      sort: 0,
      enabled: true,
      org_type: 'system',
      target_system_name: null,
      aliases: null,
    })
    // 顺序很重要：先刷新（拿到的可能是 8000 侧 60s 内的旧列表），
    // 再把新平台补齐进候选，最后才回填选中值 —— 否则刷新会把乐观项覆盖掉，
    // el-select 找不到对应 option，输入框显示为空（2026-10-19 实测踩到）。
    await selectNewPlatform(name)
    ElMessage.success(`平台「${name}」已创建为系统组织，并已选中`)
  } catch (e) {
    const msg = errText(e)
    // 重名且已有那条不是系统平台 → 提供「一键转为系统平台」。
    // 典型来源：2026-10-19 之前代理层丢字段，创建时 org_type 被丢弃落成了 department。
    const exist = orgs.value.find((o) => (o.name || '').trim() === name)
    if (/已存在同名组织|组织名称重复/.test(msg) && exist) {
      const curType = exist.org_type || 'department'
      if (curType === 'system') {
        await selectNewPlatform(name)
        ElMessage.info(`「${name}」已是系统平台，已为你选中`)
        return
      }
      try {
        await ElMessageBox.confirm(
          `已存在同名组织「${name}」（当前类型：${ORG_TYPE_LABELS[curType] || curType}）。` +
            '是否把它转为「系统平台」？转换后会出现在目标系统名候选中，可按系统维度配置别名与厂家。',
          '转为系统平台',
          { confirmButtonText: '转为系统平台', cancelButtonText: '取消', type: 'warning' }
        )
      } catch {
        return
      }
      try {
        await basicDataApi.updateOrg(exist.id, { org_type: 'system' })
        await selectNewPlatform(name)
        ElMessage.success(`「${name}」已转为系统平台，并已选中`)
      } catch (e2) {
        ElMessage.error(errText(e2) || '转为系统平台失败')
      }
      return
    }
    ElMessage.error(msg || '创建失败')
  }
}

async function submitOrg() {
  if (!orgForm.name.trim()) {
    ElMessage.warning('请填写组织名称')
    return
  }
  try {
    const payload = {
      name: orgForm.name.trim(),
      description: orgForm.description || null,
      sort: orgForm.sort,
      enabled: orgForm.enabled,
      // 映射三字段：空值＝不配置（target 为空则映射到自身 name）
      org_type: orgForm.org_type || 'department',
      target_system_name: orgForm.target_system_name || null,
      aliases: orgForm.aliases || null,
    }
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
  // 深链定位：/basic-data?tab=org|role|staff（需求页「系统别名映射」跳到这里）
  const tab = String(route?.query?.tab || '').trim()
  if (['org', 'role', 'staff'].includes(tab)) activeTab.value = tab
  loadOrgs()
  loadMappingOptions()
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
.pc-badge {
  display: inline-block;
  min-width: 22px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}
.pc-time {
  font-variant-numeric: tabular-nums;
  color: #6b7280;
  font-size: 12px;
}
/* 组织名称单元格：名称 + 「配置映射管理」入口 */
.pc-org-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.pc-org-title {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pc-org-maplink {
  flex: 0 0 auto;
  padding: 0;
  height: auto;
  font-size: 12px;
}
.pc-alias-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.pc-divider {
  margin: 4px 0 18px;
}
.pc-divider-text {
  font-size: 12px;
  color: #6b7280;
}
.pc-hint {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: #8a94a6;
}
</style>
