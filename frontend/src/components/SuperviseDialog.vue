<template>
  <el-dialog
    :model-value="modelValue"
    title="邮件督办"
    width="70%"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    destroy-on-close
    append-to-body
    @update:model-value="(v) => emit('update:modelValue', v)"
    @before-close="handleBeforeClose"
  >
    <!-- 工单摘要 -->
    <div v-if="ticketBrief" class="supervise-brief">
      <div class="supervise-brief-title">{{ ticketBrief }}</div>
      <div class="supervise-brief-sub">正文将自动携带该工单的完整信息</div>
    </div>

    <el-form :model="form" label-width="80px">
      <el-form-item label="督办类型">
        <el-radio-group v-model="form.scene">
          <el-radio label="sync">同步通知</el-radio>
          <el-radio label="urge">催办</el-radio>
        </el-radio-group>
        <div class="supervise-hint">{{ sceneHint }}</div>
      </el-form-item>

      <el-form-item label="收件人">
        <StaffSelect v-model="form.recipients" multiple value-key="value" placeholder="选择收件人（可多选）" />
        <div class="supervise-hint">默认取工单负责人/处理人，可按需增删</div>
      </el-form-item>

      <el-form-item label="留言">
        <el-input
          v-model="form.extra_msg"
          type="textarea"
          :rows="3"
          placeholder="补充说明（可选），将随正文一并发送"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button :loading="loadingPreview" :disabled="!canSend" @click="previewMail">
        预览
      </el-button>
      <el-button type="primary" :loading="loading" :disabled="!canSend" @click="confirmSend">
        发送督办
      </el-button>
    </template>
  </el-dialog>

  <!-- 邮件预览弹窗：iframe 隔离渲染，自动带出工单附件清单 -->
  <el-dialog v-model="previewVisible" title="邮件预览（含工单附件）" width="74%" append-to-body destroy-on-close>
    <iframe v-if="previewHtml" :srcdoc="previewHtml" class="supervise-preview-frame" />
    <div v-else class="supervise-preview-empty">暂无预览内容</div>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import StaffSelect from './Common/StaffSelect.vue'
import { superviseTicket } from '../api/supervise'
import { previewEmail } from '../api/mailDispatch'
import { useDrawerDraft } from '../composables/useDrawerDraft'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 工单类型：work_order / operation / dev_ticket / requirement */
  ticketType: { type: String, default: 'operation' },
  /** 工单 id */
  ticketId: { type: [Number, String], default: null },
  /** 工单摘要（标题/编号），展示在弹窗顶部 */
  ticketBrief: { type: String, default: '' },
  /** 默认收件人（姓名数组），来自工单负责人/处理人 */
  defaultRecipients: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue', 'success'])

const form = reactive({
  scene: 'urge',
  recipients: [],
  extra_msg: '',
})

const loading = ref(false)

// 邮件预览：调后端 /mail-dispatch/preview，自动带出工单附件清单（预览 = 正式）
const loadingPreview = ref(false)
const previewVisible = ref(false)
const previewHtml = ref('')
async function previewMail() {
  if (props.ticketId == null) return
  loadingPreview.value = true
  try {
    const res = await previewEmail({
      scene: form.scene === 'sync' ? 'supervise_sync' : 'supervise_urge',
      attachmentIssueId: props.ticketId,
      variables: {},
    })
    previewHtml.value = res?.html || ''
    previewVisible.value = true
  } catch (e) {
    ElMessage.error(e?.message || '预览失败，请稍后重试')
  } finally {
    loadingPreview.value = false
  }
}

const sceneHint = computed(() =>
  form.scene === 'sync' ? '信息同步：将工单进展同步通知给相关人员' : '催办：提醒相关人员跟进工单',
)

const canSend = computed(
  () => form.recipients.length > 0 && props.ticketId !== null && props.ticketId !== undefined && props.ticketId !== '',
)

/** 草稿：按 工单类型+id 维度隔离，避免不同工单串台 */
const { clearDraft, restoreDraft, resetBaseline, handleBeforeClose } = useDrawerDraft(
  'supervise-dialog',
  form,
  {
    enabled: true,
    keySuffix: () => `${props.ticketType}:${props.ticketId ?? ''}`,
  },
)

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    // 打开时以默认收件人为基线，再尝试恢复草稿
    form.recipients = [...(props.defaultRecipients || [])]
    form.scene = 'urge'
    form.extra_msg = ''
    resetBaseline()
    restoreDraft()
  },
)

async function confirmSend() {
  if (!canSend.value) {
    ElMessage.warning('请至少选择一名收件人')
    return
  }
  loading.value = true
  try {
    await superviseTicket({
      scene: form.scene,
      ticket_type: props.ticketType,
      ticket_id: props.ticketId,
      recipients: form.recipients,
      extra_msg: form.extra_msg?.trim() || undefined,
    })
    ElMessage.success('督办邮件已发送')
    clearDraft()
    emit('success')
    emit('update:modelValue', false)
  } catch (e) {
    ElMessage.error(e?.message || '督办发送失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

function handleCancel() {
  handleBeforeClose(() => emit('update:modelValue', false))
}
</script>

<style scoped>
.supervise-brief {
  background: var(--el-fill-color-light, #f5f7fa);
  border-radius: 6px;
  padding: 10px 14px;
  margin-bottom: 16px;
}
.supervise-brief-title {
  font-weight: 600;
  font-size: 14px;
  color: var(--el-text-color-primary, #303133);
}
.supervise-brief-sub {
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
  margin-top: 4px;
}
.supervise-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
  line-height: 1.5;
  margin-top: 4px;
}
.supervise-preview-frame {
  width: 100%;
  height: 70vh;
  border: 1px solid var(--el-border-color, #e5e6eb);
  border-radius: 6px;
  background: #fff;
}
.supervise-preview-empty {
  padding: 24px;
  text-align: center;
  color: var(--el-text-color-secondary, #909399);
}
</style>
