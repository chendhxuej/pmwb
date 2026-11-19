<template>
  <div class="pb-version">
    <PageHeader title="版本计划" :subtitle="subtitle">
      <template #actions>
        <el-button @click="openDemo">交互原型 Demo</el-button>
        <el-button :loading="loading" @click="loadAll">刷新</el-button>
        <el-button type="primary" @click="openCreate">登记版本计划</el-button>
      </template>
    </PageHeader>

    <el-alert v-if="meta.dict_degraded" type="warning" show-icon :closable="false" class="pb-alert">
      <template #title>人员中台系统字典暂不可用</template>
      <template #default>可继续登记，系统名将标记为「待自动补校验」；字典恢复后自动复校，无需人工判定。</template>
    </el-alert>

    <!-- 枚举字典单次加载失败：不锁死登记，用内置标签兜底并显式告警（权威仍是 /paiban/meta） -->
    <el-alert v-if="metaError" :type="metaFallback ? 'warning' : 'error'" show-icon :closable="false" class="pb-alert">
      <template #title>
        {{ metaFallback ? '字典接口暂不可用，已用内置标签兜底，不影响登记' : '字典接口暂不可用，选项显示为参考标签' }}
      </template>
      <template #default>
        失败原因：<b>{{ metaErrorMsg }}</b>。待后端恢复会自动切回权威字典，登记/编辑照常可用。
        <el-button link type="primary" @click="retryMeta">重试</el-button>
        <span v-if="metaFallback" class="pb-hint">（内置标签仅用于展示兜底，枚举口径仍以 /paiban/meta 为准，恢复后自动覆盖）</span>
      </template>
    </el-alert>

    <!-- 口径说明：版本计划是唯一基准，派生不落库 -->
    <el-alert type="info" show-icon :closable="false" class="pb-alert">
      <template #title>四环节截止由计划发布日统一倒排</template>
      <template #default>
        方案确认 −15 天 / 开发 −8 天 / 测试 −3 天 / 等待发布 −1 天。
        未单独配置版本计划的系统自动回落「统一默认」，<b>不落副本</b>：默认计划改期，回落工单的截止日与准入时点同步重算。
      </template>
    </el-alert>

    <div class="pm-stat-grid pm-stat-grid--4">
      <div class="pm-stat">
        <div class="pm-stat__top"><span class="pm-stat__label">有效计划</span></div>
        <div class="pm-stat__val is-accent">{{ rows.length }}<span class="pm-stat__unit">条</span></div>
      </div>
      <div class="pm-stat">
        <div class="pm-stat__top"><span class="pm-stat__label">统一默认计划</span></div>
        <div class="pm-stat__val">{{ summary.default_count || 0 }}<span class="pm-stat__unit">条</span></div>
      </div>
      <div class="pm-stat">
        <div class="pm-stat__top"><span class="pm-stat__label">提前准入闸门</span></div>
        <div class="pm-stat__val">{{ summary.crm_gate_count || 0 }}<span class="pm-stat__unit">条</span></div>
      </div>
      <div class="pm-stat">
        <div class="pm-stat__top"><span class="pm-stat__label">待补校验系统名</span></div>
        <div class="pm-stat__val">{{ unverifiedCount }}<span class="pm-stat__unit">条</span></div>
      </div>
    </div>

    <!-- 回落预览：查询期解析，不落副本 -->
    <el-card shadow="never" class="pb-card">
      <template #header><span class="pb-card-title">回落解析预览</span></template>
      <div class="pb-resolve-bar">
        <el-select v-model="resolveSystem" filterable clearable placeholder="选择系统（来自人员中台字典）" style="width: 280px">
          <el-option v-for="s in meta.system_options || []" :key="s" :label="s" :value="s" />
        </el-select>
        <el-button type="primary" plain :disabled="!resolveSystem" @click="doResolve">解析归属版本</el-button>
        <span v-if="resolveResult" class="pb-resolve-out">
          <el-tag :type="resolveTagType" effect="light">{{ resolveResult.source_label }}</el-tag>
          <b>{{ resolveResult.plan?.version_no || '无有效版本计划' }}</b>
          <span v-if="resolveResult.plan">发布日 {{ resolveResult.plan.release_date }} · 准入时点 {{ resolveResult.plan.admit_gate_at || '无闸门' }}</span>
          <span class="pb-hint">{{ resolveResult.hint }}</span>
        </span>
      </div>
    </el-card>

    <!-- 计划列表 -->
    <el-card shadow="never" class="pb-card">
      <template #header>
        <div class="pb-card-head">
          <span class="pb-card-title">版本计划清单</span>
          <div class="pb-filters">
            <el-select v-model="filter.scope_type" clearable placeholder="范围" style="width: 130px" @change="loadList">
              <el-option v-for="o in meta.scope_types || []" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-select v-model="filter.status" clearable placeholder="状态" style="width: 130px" @change="loadList">
              <el-option v-for="o in meta.plan_statuses || []" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-checkbox v-model="filter.future_only" @change="loadList">仅未来计划</el-checkbox>
            <el-checkbox v-model="filter.include_cancelled" @change="loadList">含已取消</el-checkbox>
          </div>
        </div>
      </template>

      <el-alert type="info" :closable="false" show-icon class="pb-alert">
        <template #default>默认只列<b>计划发布日 ≥ 今天</b>的有效计划；历史版本不删除，取消勾选「仅未来计划」即可查看全部。</template>
      </el-alert>

      <el-table :data="rows" v-loading="loading" border stripe size="small" empty-text="暂无版本计划，先登记一条统一默认计划">
        <el-table-column prop="version_no" label="版本标识" min-width="170" show-overflow-tooltip>
          <template #default="{ row }">
            <b>{{ row.version_no }}</b>
            <div class="pb-sub">{{ row.version_type_label }}<span v-if="row.is_crm"> · CRM 特殊准入</span></div>
          </template>
        </el-table-column>
        <el-table-column label="适用范围" min-width="140">
          <template #default="{ row }">
            <el-tag :type="row.scope_type === 'default' ? 'info' : 'primary'" effect="plain" size="small">{{ row.scope_label }}</el-tag>
            <div class="pb-sub">{{ row.system_name || '全部系统' }}<span v-if="!row.system_verified"> · 待自动补校验</span></div>
          </template>
        </el-table-column>
        <el-table-column prop="release_date" label="计划发布日" width="120" />
        <el-table-column label="四环节截止（自动派生）" min-width="290">
          <template #default="{ row }">
            <div class="pb-deadlines">
              <el-tag v-for="s in row.deadlines?.stages || []" :key="s.key" size="small" effect="plain">
                {{ shortStage(s.label) }} {{ s.deadline?.slice(5) }}
              </el-tag>
            </div>
            <div class="pb-sub">冻结 {{ row.deadlines?.freeze_date }} · 准入时点 {{ row.admit_gate_at || '无闸门' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="准入规则" min-width="190">
          <template #default="{ row }">
            <div>{{ row.admit_mode_label }}</div>
            <div class="pb-sub">
              临时合入 <b>{{ row.allow_temp_merge ? '允许' : '禁止（默认自动顺延）' }}</b>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTone(row.status)" size="small" effect="light">{{ row.status_label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link @click="openLogs(row)">变更日志</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 登记 / 编辑 -->
    <el-dialog v-model="dialogVisible" :title="editing ? '编辑版本计划' : '登记版本计划'" width="760px" destroy-on-close>
      <el-form :model="form" label-width="130px" size="default">
        <el-form-item label="适用范围" required>
          <el-radio-group v-model="form.scope_type" :disabled="editing" @change="onScopeChange">
            <el-radio v-for="o in meta.scope_types || []" :key="o.value" :value="o.value">{{ o.label }}</el-radio>
          </el-radio-group>
          <div class="pb-form-hint pb-scope-hint">
            默认「统一默认」= 所有未单独配置的系统共用一份计划，改期自动重算；
            选「指定系统」可为该系统登记<b>个性化版本计划</b>（发布日 / 准入规则独立），未单独配置的系统仍自动回落统一默认。
          </div>
        </el-form-item>
        <el-form-item v-if="form.scope_type === 'system'" label="指定系统" required>
          <el-select v-if="!meta.dict_degraded" v-model="form.system_name" filterable :disabled="editing"
                     placeholder="取自人员中台目标系统字典" style="width: 100%" @change="onSystemChange">
            <el-option v-for="s in meta.system_options || []" :key="s" :label="s" :value="s" />
          </el-select>
          <el-input v-else v-model="form.system_name" :disabled="editing" placeholder="字典暂不可用，登记后待自动补校验" />
        </el-form-item>
        <el-form-item label="版本标识" required>
          <el-input v-model="form.version_no" placeholder="如：订单中心 2026-12 常规版" />
        </el-form-item>
        <el-form-item label="版本类型">
          <el-select v-model="form.version_type" style="width: 100%">
            <el-option v-for="o in meta.version_types || []" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="计划发布日" required>
          <el-date-picker v-model="form.release_date" type="date" value-format="YYYY-MM-DD" placeholder="唯一基准日期" style="width: 100%" />
        </el-form-item>
        <el-form-item label="计划状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option v-for="o in meta.plan_statuses || []" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="准入模式">
          <el-select v-model="form.admit_mode" style="width: 100%" @change="onAdmitModeChange">
            <el-option v-for="o in meta.admit_modes || []" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.admit_mode === 'wait_release_n_days'" label="提前天数">
          <el-input-number v-model="form.admit_lead_days" :min="1" :max="365" />
          <span class="pb-form-hint">判定时点 = 发布日 − N 个自然日；CRM 默认 7 天</span>
        </el-form-item>
        <el-form-item label="允许临时合入">
          <el-switch v-model="form.allow_temp_merge" :active-value="1" :inactive-value="0"
                     :disabled="form.admit_mode === 'wait_release_n_days'" />
          <span class="pb-form-hint">
            {{ form.admit_mode === 'wait_release_n_days'
              ? '闸门模式恒为「否」：未准入默认自动顺延；确需留本版走单据级手工例外放行（pb-3 交付），不开规则后门。'
              : '开放模式可配置；改为「否」后未准入工单默认自动顺延下一版。' }}
          </span>
        </el-form-item>
        <el-form-item label="顺延目标版本">
          <el-select v-model="form.next_version_id" clearable placeholder="留空 = 按发布日自动取下一版" style="width: 100%">
            <el-option v-for="p in otherPlans" :key="p.id" :label="`${p.version_no}（${p.release_date}）`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="窗口说明、割接注意事项" />
        </el-form-item>
        <el-form-item label="操作人">
          <el-input v-model="form.operator" placeholder="写入变更日志" />
        </el-form-item>
      </el-form>

      <!-- 派生预览：公式只在后端，前端只展示 -->
      <el-card shadow="never" class="pb-preview">
        <template #header><span class="pb-card-title">派生预览（不落库）</span></template>
        <div v-if="previewData.deadlines" class="pb-deadlines">
          <el-tag v-for="s in previewData.deadlines.stages" :key="s.key" effect="plain">
            {{ s.label }} {{ s.deadline }}
          </el-tag>
        </div>
        <div class="pb-sub">
          冻结日 {{ previewData.deadlines?.freeze_date || '—' }} ·
          准入时点 {{ previewData.admit_gate_at || '无闸门（开放模式）' }}
        </div>
        <el-alert v-if="form.scope_type === 'system' && form.system_name === meta.crm_system_key"
                  type="warning" :closable="false" show-icon class="pb-preview-alert">
          <template #title>CRM 特殊准入</template>
          <template #default>须提前 {{ form.admit_lead_days || 7 }} 个自然日进入「等待发布」才准入；未准入<b>默认自动顺延</b>，支持单据级手工处理并留痕。</template>
        </el-alert>
      </el-card>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 变更日志 -->
    <el-drawer v-model="logVisible" title="版本计划变更日志" size="620px">
      <el-table :data="logRows" border stripe size="small" empty-text="暂无变更">
        <el-table-column prop="changed_at" label="时间" width="165" />
        <el-table-column prop="field" label="字段" width="120" />
        <el-table-column label="变更" min-width="180">
          <template #default="{ row }">
            <span class="pb-sub">{{ row.old_value || '（空）' }}</span> → <b>{{ row.new_value || '（空）' }}</b>
          </template>
        </el-table-column>
        <el-table-column prop="operator" label="操作人" width="100" />
        <el-table-column prop="affected_count" label="影响在跟数" width="100" />
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup>
/**
 * 版本计划（pb-1 / L1）—— 排版管理 5 页结构中的「版本计划」页。
 * 口径纪律：倒排偏移与准入枚举全部来自 /paiban/meta；派生预览调后端 preview 端点，
 * 前端不复制第二份公式；request.js 已解包，api/paiban.js 返回值直接用。
 */
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/Common/PageHeader.vue'
import {
  getPaibanMeta, listVersionPlans, createVersionPlan, updateVersionPlan,
  getVersionPlan, resolveVersionPlan, previewDeadlines,
} from '@/api/paiban.js'

const meta = ref({ system_options: [], stages: [] })
const metaError = ref(false)
const metaFallback = ref(false)   // 当前字典是否来自兜底（缓存 / 内置快照）
const metaErrorMsg = ref('')
const META_CACHE_KEY = 'pmwb_pb_meta_cache'
// 离线只读兜底：仅用于 el-option 展示，提交值仍是固定契约 value，不参与任何业务判定。
// 权威口径始终以 /paiban/meta（constants/paiban.py）为准，接口恢复后即被覆盖。
const FALLBACK_META = {
  stages: [
    { key: 'plan_confirm', label: '方案确认中', offset_days: -15 },
    { key: 'dev', label: '开发中', offset_days: -8 },
    { key: 'test', label: '测试中', offset_days: -3 },
    { key: 'wait_release', label: '等待发布', offset_days: -1 },
  ],
  freeze_offset_days: -15,
  scope_types: [{ value: 'default', label: '统一默认' }, { value: 'system', label: '指定系统' }],
  version_types: [{ value: 'regular', label: '常规版' }, { value: 'emergency', label: '紧急补丁' }, { value: 'ad_hoc', label: '临时加版' }],
  plan_statuses: [{ value: 'draft', label: '拟定' }, { value: 'confirmed', label: '已确认' }, { value: 'published', label: '已发布' }, { value: 'closed', label: '已收口' }, { value: 'cancelled', label: '已取消' }],
  admit_modes: [{ value: 'open', label: '开放（无提前准入闸门）' }, { value: 'wait_release_n_days', label: '提前 N 天进入等待发布才准入' }],
  default_admit_lead_days: 7, crm_system_key: 'CRM', system_options: [], dict_degraded: true,
}
const rows = ref([])
const summary = ref({})
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const logVisible = ref(false)
const logRows = ref([])
const editing = ref(false)
const editId = ref(null)
const previewData = ref({})
const resolveSystem = ref('')
const resolveResult = ref(null)
const filter = reactive({ scope_type: '', status: '', future_only: true, include_cancelled: false })

const blankForm = () => ({
  version_no: '', scope_type: 'default', system_name: '', version_type: 'regular',
  release_date: '', status: 'draft', admit_mode: 'open', admit_lead_days: 0,
  allow_temp_merge: 1, next_version_id: null, remark: '', operator: '',
})
const form = reactive(blankForm())

const subtitle = computed(() => {
  const offs = (meta.value.stages || []).map(s => `${s.label} ${s.offset_days}d`).join(' / ')
  return offs ? `统一倒排：${offs}；未单独配置的系统回落统一默认计划` : '版本计划是四环节截止与准入判定的唯一基准'
})
const unverifiedCount = computed(() => rows.value.filter(r => !r.system_verified).length)
const otherPlans = computed(() => rows.value.filter(p => p.id !== editId.value))
const resolveTagType = computed(() => (
  resolveResult.value?.source === 'exclusive' ? 'primary'
    : resolveResult.value?.source === 'default' ? 'info'
      : resolveResult.value?.source === 'missing' ? 'danger' : 'info'
))
// 评审原型为静态页（frontend/public/paiban-demo.html，随构建一起产出），不是系统功能页。
// 挂显式入口，避免评审时还要手敲 URL；新标签打开，不打断当前登记流程。
const openDemo = () => window.open('/paiban-demo.html', '_blank', 'noopener')
const shortStage = label => (label || '').replace('方案确认中', '方案').replace('等待发布', '待发布')
const statusTone = s => ({ published: 'success', confirmed: 'primary', closed: 'info', cancelled: 'danger' }[s] || 'warning')

let metaRetryTimer = null
let metaRetryLeft = 0
const errText = e => {
  if (!e) return '未知错误'
  if (typeof e === 'string') return e
  if (e.message) return e.message
  if (e.response?.status) return `HTTP ${e.response.status}`
  if (e.code) return `业务码 ${e.code}`
  return '网络请求失败'
}
function applyMeta(data, fallback) {
  meta.value = data || FALLBACK_META
  metaFallback.value = fallback
}
async function loadMeta(retry = true) {
  try {
    const data = await getPaibanMeta()
    if (!(data?.scope_types || []).length) throw new Error('接口返回的字典为空')
    applyMeta(data, false)
    metaError.value = false
    metaErrorMsg.value = ''
    metaRetryLeft = 0
    try { localStorage.setItem(META_CACHE_KEY, JSON.stringify(data)) } catch (_) { /* 隐私模式忽略 */ }
  } catch (e) {
    metaError.value = true
    metaErrorMsg.value = errText(e)
    // 兜底顺序：上次成功缓存 > 内置只读快照。字典仅影响展示，绝不锁死登记。
    let cached = null
    try { cached = JSON.parse(localStorage.getItem(META_CACHE_KEY) || 'null') } catch (_) { /* ignore */ }
    applyMeta((cached?.scope_types || []).length ? cached : FALLBACK_META, true)
    if (retry && metaRetryLeft < 3) {
      metaRetryLeft += 1
      clearTimeout(metaRetryTimer)
      metaRetryTimer = setTimeout(() => loadMeta(true), 1500 * metaRetryLeft)
    }
  }
}
function retryMeta() {
  metaRetryLeft = 0
  clearTimeout(metaRetryTimer)
  loadMeta(true)
}
async function loadList() {
  loading.value = true
  try {
    const r = await listVersionPlans({
      scope_type: filter.scope_type || undefined,
      status: filter.status || undefined,
      future_only: filter.future_only,
      include_cancelled: filter.include_cancelled,
    })
    rows.value = r.items || []
    summary.value = { default_count: r.default_count, crm_gate_count: r.crm_gate_count }
  } finally {
    loading.value = false
  }
}
async function loadAll() {
  await Promise.all([loadMeta(), loadList()])
}
onMounted(loadAll)

// 派生预览：改动发布日 / 准入模式 / 提前天数即向后端取，禁前端另算一份公式
let previewTimer = null
watch(
  () => [form.release_date, form.admit_mode, form.admit_lead_days],
  () => {
    clearTimeout(previewTimer)
    if (!form.release_date) { previewData.value = {}; return }
    previewTimer = setTimeout(async () => {
      try {
        previewData.value = await previewDeadlines({
          release_date: form.release_date,
          admit_mode: form.admit_mode,
          admit_lead_days: form.admit_lead_days,
        })
      } catch (e) { previewData.value = {} }
    }, 200)
  },
  { immediate: true },
)

function onScopeChange() {
  if (form.scope_type === 'default') form.system_name = ''
}
function onSystemChange(v) {
  if (editing.value) return
  if (v === meta.value.crm_system_key) {
    form.admit_mode = 'wait_release_n_days'
    form.admit_lead_days = meta.value.default_admit_lead_days || 7
    form.allow_temp_merge = 0
    ElMessage.info('已按 CRM 带出：提前 7 自然日准入 / 禁止临时合入 / 未准入默认自动顺延')
  }
}
function onAdmitModeChange(v) {
  if (v === 'wait_release_n_days') {
    if (!form.admit_lead_days) form.admit_lead_days = meta.value.default_admit_lead_days || 7
    form.allow_temp_merge = 0
  } else {
    form.admit_lead_days = 0
  }
}

function openCreate() {
  editing.value = false; editId.value = null
  Object.assign(form, blankForm())
  dialogVisible.value = true
}
function openEdit(row) {
  editing.value = true; editId.value = row.id
  Object.assign(form, {
    version_no: row.version_no, scope_type: row.scope_type, system_name: row.system_name,
    version_type: row.version_type, release_date: row.release_date, status: row.status,
    admit_mode: row.admit_mode, admit_lead_days: row.admit_lead_days,
    allow_temp_merge: row.allow_temp_merge, next_version_id: row.next_version_id,
    remark: row.remark, operator: '',
  })
  dialogVisible.value = true
}
async function save() {
  if (!form.version_no || !form.release_date) { ElMessage.warning('版本标识与计划发布日必填'); return }
  saving.value = true
  try {
    const payload = { ...form }
    if (payload.scope_type === 'default') payload.system_name = null
    if (!payload.next_version_id) payload.next_version_id = null
    if (editing.value) await updateVersionPlan(editId.value, payload)
    else await createVersionPlan(payload)
    ElMessage.success(editing.value ? '已更新，变更已留痕' : '已登记版本计划')
    dialogVisible.value = false
    await loadList()
    if (resolveSystem.value) await doResolve()
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}
async function doResolve() {
  resolveResult.value = await resolveVersionPlan(resolveSystem.value)
}
async function openLogs(row) {
  const detail = await getVersionPlan(row.id)
  logRows.value = detail.change_logs || []
  logVisible.value = true
}
</script>

<style scoped>
.pb-version { padding: 0 4px 24px; }
.pb-alert { margin-bottom: 12px; }
.pb-card { margin-top: 16px; }
.pb-card-title { font-weight: 600; color: var(--text-primary); }
.pb-card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.pb-filters { display: flex; align-items: center; gap: 10px; }
.pb-resolve-bar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.pb-resolve-out { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-secondary); flex-wrap: wrap; }
.pb-hint { color: var(--text-muted); }
.pb-deadlines { display: flex; gap: 6px; flex-wrap: wrap; }
.pb-sub { font-size: 12px; color: var(--text-muted); margin-top: 4px; line-height: 1.5; }
.pb-form-hint { margin-left: 12px; font-size: 12px; color: var(--text-muted); line-height: 1.5; }
.pb-scope-hint { display: block; margin-left: 0; margin-top: 6px; }
.pb-preview { margin-top: 8px; }
.pb-preview-alert { margin-top: 12px; }
</style>
