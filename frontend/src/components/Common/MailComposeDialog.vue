<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="980px"
    top="4vh"
    append-to-body
    class="mail-compose-dialog"
    @update:model-value="(v) => emit('update:modelValue', v)"
  >
    <div class="compose">
      <!-- 左：编辑区 -->
      <div class="compose-edit">
        <div class="compose-row">
          <span class="compose-label">收件人</span>
          <StaffSelect v-model="to" multiple placeholder="选择 / 输入收件人（姓名或邮箱）" />
        </div>
        <div class="compose-row">
          <span class="compose-label">抄送</span>
          <StaffSelect v-model="cc" multiple placeholder="选择 / 输入抄送（可空）" />
        </div>
        <div class="compose-row">
          <span class="compose-label">主题</span>
          <el-input v-model="subject" placeholder="邮件主题" />
        </div>
        <div class="compose-row compose-body">
          <span class="compose-label">
            正文
            <em class="compose-hint">支持 Markdown，右侧实时预览</em>
          </span>
          <el-input
            v-model="body"
            type="textarea"
            :rows="15"
            placeholder="支持 Markdown：# 标题、**加粗**、- 列表、| 表格 | 等"
            @input="onBodyInput"
          />
        </div>
      </div>

      <!-- 右：预览区 -->
      <div class="compose-preview">
        <div class="compose-preview-title">邮件预览</div>
        <div class="compose-preview-body" v-html="previewHtml"></div>
      </div>
    </div>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="sending" @click="onSend">发送</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import StaffSelect from '@/components/Common/StaffSelect.vue'
import { previewEmail } from '@/api/mailDispatch.js'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '撰写邮件' },
  defaultTo: { type: Array, default: () => [] },
  defaultCc: { type: Array, default: () => [] },
  defaultSubject: { type: String, default: '' },
  defaultBody: { type: String, default: '' },
  scene: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'send'])

const to = ref([])
const cc = ref([])
const subject = ref('')
const body = ref('')
const previewHtml = ref('')
const sending = ref(false)

let timer = null
let lastBody = ''

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      to.value = [...(props.defaultTo || [])]
      cc.value = [...(props.defaultCc || [])]
      subject.value = props.defaultSubject || ''
      body.value = props.defaultBody || ''
      lastBody = body.value
      refreshPreview()
    }
  },
)

function onBodyInput() {
  if (timer) clearTimeout(timer)
  timer = setTimeout(refreshPreview, 250)
}

async function refreshPreview() {
  if (body.value === lastBody) return
  lastBody = body.value
  try {
    const data = await previewEmail({ body: body.value, body_format: 'html', add_signature: true })
    previewHtml.value = data?.html || ''
  } catch {
    previewHtml.value = ''
  }
}

onBeforeUnmount(() => {
  if (timer) clearTimeout(timer)
})

function onSend() {
  if (!to.value.length) {
    ElMessage.warning('请选择收件人')
    return
  }
  if (!body.value.trim()) {
    ElMessage.warning('请输入邮件正文')
    return
  }
  emit('send', {
    to: to.value,
    cc: cc.value,
    subject: subject.value,
    body: body.value,
    scene: props.scene,
  })
}

defineExpose({ sending })
</script>

<style scoped>
.compose {
  display: flex;
  gap: 16px;
  align-items: stretch;
}
.compose-edit {
  flex: 1 1 50%;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}
.compose-preview {
  flex: 1 1 50%;
  display: flex;
  flex-direction: column;
  min-width: 0;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}
.compose-preview-title {
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 600;
  color: #606266;
  background: #f5f7fa;
  border-bottom: 1px solid #ebeef5;
}
.compose-preview-body {
  flex: 1;
  padding: 14px 16px;
  overflow: auto;
  max-height: 60vh;
}
.compose-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.compose-label {
  flex-shrink: 0;
  width: 48px;
  font-size: 13px;
  color: #606266;
  padding-top: 7px;
  text-align: right;
}
.compose-body {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.compose-body :deep(.el-textarea),
.compose-body :deep(.el-textarea__inner) {
  flex: 1;
}
.compose-hint {
  display: block;
  font-style: normal;
  font-size: 11px;
  color: #909399;
  font-weight: 400;
  width: 100%;
  text-align: left;
  margin-top: 2px;
}
:deep(.el-dialog__body) {
  padding-top: 12px;
}
</style>
