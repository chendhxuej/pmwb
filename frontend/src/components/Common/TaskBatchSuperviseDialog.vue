<template>
  <el-dialog
    :model-value="modelValue"
    title="批量督办"
    width="760px"
    top="5vh"
    append-to-body
    class="task-batch-supervise"
    @update:model-value="(v) => emit('update:modelValue', v)"
    @open="onOpen"
  >
    <div class="tbs">
      <div class="tbs-tip">
        以下为 <b>{{ ownerName }}</b> 的全部未完结任务（pending + 进行中），勾选需督办的任务后撰写催办邮件。
      </div>

      <div v-loading="loading" class="tbs-body">
        <el-table
          v-if="!loading"
          ref="tableRef"
          :data="tasks"
          size="small"
          max-height="380"
          @selection-change="onSelChange"
        >
          <el-table-column type="selection" width="46" />
          <el-table-column label="来源" width="92">
            <template #default="{ row }">{{ row.source_label }}</template>
          </el-table-column>
          <el-table-column label="任务" min-width="210" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="tbs-title">{{ row.title || '（无标题）' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="86">
            <template #default="{ row }">
              <el-tag size="small" :type="statusType(row.status)">{{ row.status_label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="截止" width="108">
            <template #default="{ row }">{{ row.due_date || '—' }}</template>
          </el-table-column>
          <el-table-column label="" width="58">
            <template #default="{ row }">
              <el-tag v-if="row.is_overdue" size="small" type="danger">超期</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!loading && !tasks.length" description="该人员暂无未完结任务" :image-size="64" />
      </div>

      <div class="tbs-foot">
        <span class="tbs-count">已选 {{ selectedTasks.length }} / {{ tasks.length }}</span>
        <el-button size="small" link type="primary" @click="toggleAll">{{ allChecked ? '取消全选' : '全选' }}</el-button>
      </div>
    </div>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button
        type="primary"
        :disabled="!selectedTasks.length || composeLoading"
        :loading="composeLoading"
        @click="toCompose"
      >撰写催办邮件</el-button>
    </template>

    <!-- 内层：邮件撰写 / 预览 / 发送（复用通用组件，tasks 透传 variables 保证预览与实发一致） -->
    <MailComposeDialog
      v-model="composeVisible"
      title="撰写催办邮件"
      scene="task_center_urge"
      :default-to="[ownerName]"
      :default-body="composeBody"
      value-key="email"
      :variables="composeVariables"
      :custom-send="batchSendFn"
      @success="onSent"
    />
  </el-dialog>
</template>

<script setup>
/**
 * 任务中心 · 批量督办弹窗（2026-09-19 新增）。
 *
 * 入口：任务总览页责任人卡片「督办」按钮 → 按责任人拉取其全部未完结任务
 *      → 复选框默认全选、支持个性化勾选 → 复用 MailComposeDialog 撰写/预览/发送。
 *
 * 与 TaskCenterView 既有的 openTaskEmail 共用同一套「结构化 tasks 透传 variables」机制：
 * 预览与实发都携带 tasks，保证所见即所发；发送走 /task-center/send（逐任务落 email_records）。
 */
import { ref, computed, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import MailComposeDialog from '@/components/Common/MailComposeDialog.vue'
import { getTasks, sendTaskEmail, requestTaskCenterDraft } from '@/api/taskCenter.js'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  ownerName: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])

const loading = ref(false)
const tasks = ref([])
const selectedTasks = ref([])
const tableRef = ref(null)
const composeVisible = ref(false)
const composeVariables = ref({})
const composeBody = ref('') // 左侧 Markdown 编辑区默认值（后端按场景装配的草稿）
const composeLoading = ref(false)

const allChecked = computed(
  () => tasks.value.length > 0 && selectedTasks.value.length === tasks.value.length
)

function statusType(status) {
  if (status === 'in_progress') return 'primary'
  if (status === 'done') return 'success'
  if (status === 'blocked') return 'info'
  return 'warning'
}

function onSelChange(rows) {
  selectedTasks.value = rows
}

function toggleAll() {
  if (!tableRef.value) return
  if (allChecked.value) {
    tableRef.value.clearSelection()
  } else {
    tableRef.value.toggleAllSelection()
  }
}

// 打开时按责任人拉取全部未完结任务（include_done=false → pending + in_progress）
async function onOpen() {
  if (!props.ownerName) return
  loading.value = true
  tasks.value = []
  selectedTasks.value = []
  try {
    const res = await getTasks({
      owners: props.ownerName,
      include_done: false,
      page: 1,
      page_size: 500,
    })
    tasks.value = (res && res.items) || []
  } catch (e) {
    ElMessage.error('拉取在途任务失败：' + (e?.response?.data?.message || e.message || '未知错误'))
  } finally {
    loading.value = false
  }
  // 必须等 loading=false 后 el-table(v-if=!loading) 渲染完成再全选，否则 tableRef 为空
  await nextTick()
  if (tableRef.value) tableRef.value.toggleAllSelection()
}

// 进入撰写：把选中的任务结构化后透传 variables（预览/实发共用），
// 并拉取后端按场景装配的 Markdown 草稿填充左侧编辑框（保证可手工调整 + 发送时正文非空）
async function toCompose() {
  if (!selectedTasks.value.length) return
  composeLoading.value = true
  const structured = selectedTasks.value.map((t, i) => ({
    index: i + 1,
    title: t.title || '（无标题）',
    source_label: t.source_label || t.source,
    source: t.source,
    source_id: t.source_id,
    owner: t.owner || '未分配',
    due_date: t.due_date || '',
    status_label: t.status_label || t.status,
    priority: t.priority || '',
    description: pickDescription(t.detail || {}),
    is_overdue: !!t.is_overdue,
    is_due_soon: !!t.is_due_soon,
    source_url: t.source_url || '',
  }))
  composeVariables.value = {
    tasks: structured,
    sendType: 'urge',
    recipient_name: props.ownerName,
  }
  // 拉取 Markdown 草稿（与 TaskCenterView 单任务催办同链路）
  try {
    const res = await requestTaskCenterDraft(structured, 'urge', '')
    composeBody.value = (res && res.body_md) || ''
  } catch (e) {
    composeBody.value = ''
    console.warn('[TaskBatchSupervise] requestTaskCenterDraft failed:', e && e.message)
  } finally {
    composeLoading.value = false
  }
  composeVisible.value = true
}

const DESC_KEYS = ['需求描述', '情况说明', '行动项', '内容', '说明', '备注', '风险说明']
function pickDescription(detail) {
  if (!detail) return ''
  for (const k of DESC_KEYS) {
    if (detail[k]) return String(detail[k]).trim()
  }
  return ''
}

async function batchSendFn(payload) {
  return sendTaskEmail({
    tasks: selectedTasks.value.map((t) => ({ source: t.source, source_id: t.source_id })),
    to: (payload.to || []).join(', '),
    cc: (payload.cc || []).length ? (payload.cc || []).join(', ') : null,
    subject: payload.subject,
    body: payload.body,
    send_type: 'urge',
    operator: 'pmwb',
    confirm_send: true,
    template_data: payload.variables || null,
  })
}

function onSent() {
  composeVisible.value = false
  emit('update:modelValue', false)
  ElMessage.success(`已向 ${props.ownerName} 发送催办邮件（${selectedTasks.value.length} 项任务）`)
}
</script>

<style scoped>
.task-batch-supervise :deep(.el-dialog__body) {
  padding-top: 12px;
}
.tbs-tip {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 12px;
  line-height: 1.6;
}
.tbs-tip b {
  color: var(--text-primary);
}
.tbs-body {
  min-height: 200px;
}
.tbs-title {
  font-size: 13px;
  color: var(--text-primary);
}
.tbs-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
  padding: 0 4px;
}
.tbs-count {
  font-size: 12.5px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}
</style>
