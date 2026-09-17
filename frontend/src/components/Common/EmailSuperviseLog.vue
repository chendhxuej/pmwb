<template>
  <div class="email-supervise-log">
    <div v-if="loading" class="esl-empty">加载中…</div>
    <div v-else-if="error" class="esl-empty esl-error">{{ error }}</div>
    <template v-else>
      <div v-for="(e, i) in list" :key="e.id || i" class="esl-item">
        <div class="esl-head">
          <span class="esl-time">{{ fmtTime(e.created_at) }}</span>
          <StatusBadge :label="statusLabel(e.send_status)" :type="statusType(e.send_status)" size="small" />
          <span class="esl-type">{{ typeLabel(e) }}</span>
        </div>
        <div class="esl-subject">{{ e.subject || '(无主题)' }}</div>
        <div class="esl-to">收件：{{ e.recipient_name || e.recipient || '—' }}</div>
        <div v-if="expanded[i]" class="esl-body" v-html="e.content"></div>
        <el-button link type="primary" size="small" class="esl-toggle" @click="expanded[i] = !expanded[i]">
          {{ expanded[i] ? '收起正文' : '查看正文' }}
        </el-button>
      </div>
      <div v-if="!list.length" class="esl-empty">暂无督办邮件</div>
    </template>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import request from '@/api/request'
import StatusBadge from '@/components/Common/StatusBadge.vue'

const props = defineProps({
  refType: { type: String, required: true },
  refId: { type: String, default: '' },
  limit: { type: Number, default: 50 },
})

const list = ref([])
const loading = ref(false)
const error = ref('')
const expanded = ref({})

const TYPE_LABELS = {
  supervise_urge: '督办催办',
  supervise_sync: '督办同步',
  action_supervise: '行动项督办',
  research_urge: '调研催办',
  research_sync: '调研同步',
  requirement_reminder: '需求催办',
  task_reminder: '任务提醒',
  task_center_notify: '任务通知',
  task_center_urge: '任务催办',
  meeting_notice: '会议通知',
  meeting_minutes: '会议纪要',
  action_dispatch: '行动项派发',
  work_report: '周报',
  keywork_feedback: '重点工作反馈',
  active_optimization_urge: '主动优化催办',
  active_optimization_sync: '主动优化同步',
  plugin: '插件',
}

const STATUS_TYPE = { success: 'success', pending: 'warning', failed: 'danger', dry_run: 'info' }
const STATUS_LABEL = { success: '已发送', pending: '发送中', failed: '失败', dry_run: '草稿(未发)' }

function statusType(s) {
  return STATUS_TYPE[s] || 'info'
}
function statusLabel(s) {
  return STATUS_LABEL[s] || s || '未知'
}
function typeLabel(e) {
  return TYPE_LABELS[e.email_type] || e.source || e.email_type || ''
}
function fmtTime(t) {
  if (!t) return ''
  return String(t).replace('T', ' ').slice(0, 19)
}

async function load() {
  if (!props.refId) {
    list.value = []
    return
  }
  loading.value = true
  error.value = ''
  try {
    const data = await request.get('/mail-dispatch/records', {
      params: { ref_type: props.refType, ref_id: props.refId, limit: props.limit },
    })
    list.value = Array.isArray(data) ? data : []
  } catch (e) {
    error.value = '加载督办记录失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => [props.refType, props.refId], load)

defineExpose({ reload: load })
</script>

<style scoped>
.email-supervise-log {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.esl-item {
  border: 1px solid var(--border-color, #e5e6eb);
  border-radius: 6px;
  padding: 8px 10px;
  background: var(--bg-elevated, #fff);
}
.esl-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.esl-time {
  font-size: 12px;
  color: var(--text-secondary, #64748b);
}
.esl-type {
  font-size: 12px;
  color: var(--text-secondary, #64748b);
}
.esl-subject {
  margin-top: 4px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #1d2129);
}
.esl-to {
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-secondary, #64748b);
}
.esl-body {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed var(--border-color, #e5e6eb);
  font-size: 13px;
  line-height: 1.6;
  max-height: 320px;
  overflow: auto;
}
.esl-toggle {
  margin-top: 2px;
  padding-left: 0;
}
.esl-empty {
  font-size: 12px;
  color: var(--text-secondary, #64748b);
  padding: 4px 0;
}
.esl-error {
  color: var(--danger, #d9544d);
}
</style>
