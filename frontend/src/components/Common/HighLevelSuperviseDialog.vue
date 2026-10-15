<template>
  <el-dialog
    :model-value="modelValue"
    :title="dialogTitle"
    width="780px"
    top="5vh"
    append-to-body
    class="hl-supervise"
    @update:model-value="(v) => emit('update:modelValue', v)"
    @open="onOpen"
  >
    <div class="hls">
      <div class="hls-tip">
        <template v-if="ownerName">
          以下为 <b>{{ ownerName }}</b> 名下的高级别在跟工单（P0/P1、超期升格或人工提级），勾选后撰写督办邮件。
        </template>
        <template v-else>
          以下为已勾选的 <b>{{ tasks.length }}</b> 条高级别工单，确认后撰写督办邮件。
        </template>
      </div>

      <div v-loading="loading" class="hls-body">
        <el-table
          v-if="!loading"
          ref="tableRef"
          :data="tasks"
          size="small"
          max-height="380"
          row-key="task_id"
          @selection-change="onSelChange"
        >
          <el-table-column type="selection" width="46" reserve-selection />
          <el-table-column label="来源" width="92">
            <template #default="{ row }">{{ row.source_label }}</template>
          </el-table-column>
          <el-table-column label="级别" width="66">
            <template #default="{ row }">
              <span class="hls-level" :class="`lv-${(row.level_code || 'p3').toLowerCase()}`">
                {{ row.level_code || '—' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="工单" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="hls-title">{{ row.title || '（无标题）' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="86">
            <template #default="{ row }">
              <StatusBadge module="task_center" :value="row.status" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="截止" width="104">
            <template #default="{ row }">{{ row.due_date || '—' }}</template>
          </el-table-column>
          <el-table-column label="" width="52">
            <template #default="{ row }">
              <el-tag v-if="row.is_overdue" size="small" type="danger">超期</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!loading && !tasks.length" description="暂无可督办的高级别工单" :image-size="64" />
      </div>

      <div class="hls-foot">
        <span class="hls-count">已选 {{ selected.length }} / {{ tasks.length }}</span>
        <el-button size="small" link type="primary" @click="toggleAll">
          {{ allChecked ? '取消全选' : '全选' }}
        </el-button>
      </div>
    </div>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button
        type="primary"
        :disabled="!selected.length || composeLoading"
        :loading="composeLoading"
        @click="toCompose"
      >撰写督办邮件</el-button>
    </template>

    <!-- 内层：邮件撰写 / 预览 / 发送（复用通用组件；tasks 透传 variables 保证预览与实发一致） -->
    <MailComposeDialog
      v-model="composeVisible"
      title="高级别工单督办"
      scene="high_level_urge"
      :default-to="defaultTo"
      :default-subject="composeSubject"
      :default-body="composeBody"
      value-key="email"
      :variables="composeVariables"
      :custom-send="sendFn"
      @success="onSent"
    />
  </el-dialog>
</template>

<script setup>
/**
 * 高级别工单 · 批量督办弹窗（2026-10-15）。
 *
 * 两条入口共用本组件：
 *   1) 按责任人：传 ownerName → 拉取其名下全部在跟高级别工单（默认全选）；
 *   2) 按勾选：传 tasks（表格已选行）→ 直接进入勾选确认。
 *
 * 发送走 /high-level/send（scene=high_level_urge），
 * 与列表页共用「结构化 tasks 透传 template_data」机制，保证预览即实发。
 */
import { ref, computed, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import MailComposeDialog from '@/components/Common/MailComposeDialog.vue'
import StatusBadge from '@/components/Common/StatusBadge.vue'
import { getHighLevelTasks, sendHighLevelEmail, requestHighLevelDraft } from '@/api/highLevel.js'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  ownerName: { type: String, default: '' },
  presetTasks: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue', 'sent'])

const loading = ref(false)
const tasks = ref([])
const selected = ref([])
const tableRef = ref(null)
const composeVisible = ref(false)
const composeVariables = ref({})
const composeBody = ref('')
const composeSubject = ref('')
const composeLoading = ref(false)

const dialogTitle = computed(() => (props.ownerName ? '批量督办' : '批量督办（已选工单）'))
const defaultTo = computed(() => {
  if (props.ownerName) return [props.ownerName]
  const names = new Set()
  for (const t of selected.value) {
    for (const n of String(t.owner || '').split(/[,，;；、]+/)) {
      const s = n.trim()
      if (s && s !== '未分配') names.add(s)
    }
  }
  return [...names]
})
const allChecked = computed(
  () => tasks.value.length > 0 && selected.value.length === tasks.value.length
)

function onSelChange(rows) {
  selected.value = rows
}

function toggleAll() {
  if (!tableRef.value) return
  if (allChecked.value) tableRef.value.clearSelection()
  else tableRef.value.toggleAllSelection()
}

async function onOpen() {
  composeVisible.value = false
  selected.value = []
  if (props.presetTasks && props.presetTasks.length) {
    // 按勾选入口：直接用传入的行，不再请求
    tasks.value = [...props.presetTasks]
    await nextTick()
    if (tableRef.value) tableRef.value.toggleAllSelection()
    return
  }
  loading.value = true
  tasks.value = []
  try {
    const res = await getHighLevelTasks({
      owner: props.ownerName,
      page: 1,
      page_size: 500,
    })
    tasks.value = (res && res.items) || []
  } catch (e) {
    ElMessage.error('拉取高级别工单失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  } finally {
    loading.value = false
  }
  // 必须等 loading=false 后表格渲染完成再全选，否则 tableRef 为空
  await nextTick()
  if (tableRef.value) tableRef.value.toggleAllSelection()
}

const DESC_KEYS = ['需求描述', '情况说明', '行动项', '内容', '说明', '备注', '风险说明']
function pickDescription(detail) {
  if (!detail) return ''
  for (const k of DESC_KEYS) {
    if (detail[k]) return String(detail[k]).trim()
  }
  return ''
}

/** 行 → 邮件结构化任务（字段与后端 _build_structured_tasks / render_task_center_section 对齐） */
function structuralize(rows) {
  return rows.map((t, i) => ({
    index: i + 1,
    title: t.title || '（无标题）',
    source_label: t.source_label || t.source,
    source: t.source,
    source_id: t.source_id,
    owner: t.owner || '未分配',
    created_at: t.created_at ? String(t.created_at).slice(0, 10) : '',
    due_date: t.due_date || '',
    status_label: t.status_label || t.status,
    priority: t.priority || t.level_code || '',
    description: pickDescription(t.detail || {}),
    is_overdue: !!t.is_overdue,
    is_due_soon: !!t.is_due_soon,
    source_url: t.source_url || '',
  }))
}

async function toCompose() {
  if (!selected.value.length) return
  composeLoading.value = true
  const structured = structuralize(selected.value)
  composeVariables.value = {
    tasks: structured,
    sendType: 'urge',
    recipient_name: defaultTo.value.join('、'),
  }
  try {
    const res = await requestHighLevelDraft(
      structured, 'urge', '', defaultTo.value.join('、')
    )
    composeBody.value = (res && res.body_md) || ''
    composeSubject.value = (res && res.subject) || ''
  } catch (e) {
    composeBody.value = ''
    composeSubject.value = ''
    console.warn('[HighLevelSupervise] requestHighLevelDraft failed:', e && e.message)
  } finally {
    composeLoading.value = false
  }
  composeVisible.value = true
}

async function sendFn(payload) {
  return sendHighLevelEmail({
    tasks: selected.value.map((t) => ({ source: t.source, source_id: t.source_id })),
    to: (payload.to || []).join(', '),
    cc: (payload.cc || []).length ? (payload.cc || []).join(', ') : null,
    subject: payload.subject,
    body: payload.body,
    send_type: 'urge',
    operator: 'pmwb',
    confirm_send: true,   // 真发唯一入口：页面显式点击
    template_data: payload.variables || null,
  })
}

function onSent() {
  composeVisible.value = false
  emit('update:modelValue', false)
  emit('sent', selected.value.length)
  ElMessage.success(`已发送高级别工单督办邮件（${selected.value.length} 条）`)
}
</script>

<style scoped>
.hl-supervise :deep(.el-dialog__body) {
  padding-top: 12px;
}
.hls-tip {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 12px;
  line-height: 1.6;
}
.hls-tip b {
  color: var(--text-primary);
}
.hls-body {
  min-height: 200px;
}
.hls-title {
  font-size: 13px;
  color: var(--text-primary);
}
.hls-level {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
}
.hls-level.lv-p0 {
  color: var(--danger);
}
.hls-level.lv-p1 {
  color: var(--warning);
}
.hls-level.lv-p2 {
  color: var(--accent);
}
.hls-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
  padding: 0 4px;
}
.hls-count {
  font-size: 12.5px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}
</style>
