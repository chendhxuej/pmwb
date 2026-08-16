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
          <StaffSelect v-model="to" multiple :value-key="valueKey" placeholder="选择 / 输入收件人（姓名或邮箱）" />
        </div>
        <div class="compose-row">
          <span class="compose-label">抄送</span>
          <StaffSelect v-model="cc" multiple :value-key="valueKey" placeholder="选择 / 输入抄送（可空）" />
        </div>
        <div class="compose-row">
          <span class="compose-label">主题</span>
          <el-input v-model="subject" placeholder="邮件主题" />
        </div>
        <div v-if="editableBody" class="compose-row compose-body">
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
import { ref, watch, computed, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import StaffSelect from '@/components/Common/StaffSelect.vue'
import { previewEmail, sendEmail } from '@/api/mailDispatch.js'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '撰写邮件' },
  defaultTo: { type: Array, default: () => [] },
  defaultCc: { type: Array, default: () => [] },
  defaultSubject: { type: String, default: '' },
  defaultBody: { type: String, default: '' },
  // 邮件治理场景标识；传入 scene 即启用 scene 模式，否则为 raw 模式
  scene: { type: String, default: '' },
  // scene 模式下渲染/发送使用的变量
  variables: { type: Object, default: () => ({}) },
  // raw 模式下是否允许编辑正文；scene 模式若 false 则正文只读由后端模板渲染
  editableBody: { type: Boolean, default: true },
  // raw 模式下的正文格式（html 表示 Markdown 渲染后 HTML，text 表示纯文本）
  bodyFormat: { type: String, default: 'html' },
  // 是否注入统一签名
  addSignature: { type: Boolean, default: true },
  // 发送成功后是否自动关闭弹窗
  closeOnSuccess: { type: Boolean, default: true },
  // 自定义发送函数；默认走统一发送端点 /mail-dispatch/send
  // 函数签名：async (payload) => result，其中 payload 已包含 to/cc/subject/scene/variables/body 等
  customSend: { type: Function, default: null },
  // StaffSelect 取值键：'value' 返回姓名，'email' 返回邮箱（无邮箱回退姓名）
  valueKey: { type: String, default: 'value' },
})

const emit = defineEmits(['update:modelValue', 'send', 'success', 'error'])

const to = ref([])
const cc = ref([])
const subject = ref('')
const body = ref('')
const previewHtml = ref('')
const sending = ref(false)

let timer = null
let lastBody = ''

const isRawMode = computed(() => !props.scene)

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      to.value = [...(props.defaultTo || [])]
      cc.value = [...(props.defaultCc || [])]
      subject.value = props.defaultSubject || ''
      body.value = props.defaultBody || ''
      refreshPreview(true)
    }
  },
)

watch(
  () => [props.scene, props.variables, props.editableBody],
  () => {
    if (props.modelValue) {
      refreshPreview(true)
    }
  },
  { deep: true },
)

function onBodyInput() {
  if (timer) clearTimeout(timer)
  timer = setTimeout(refreshPreview, 250)
}

async function refreshPreview(force = false) {
  if (!force && body.value === lastBody) return
  lastBody = body.value
  try {
    const payload = buildPreviewPayload()
    const data = await previewEmail(payload)
    previewHtml.value = data?.html || data?.rendered_body || ''
  } catch (e) {
    console.warn('[MailComposeDialog] 邮件预览失败：', e)
    previewHtml.value = `<div style="color:#909399;padding:20px;text-align:center;">预览加载失败：${e?.message || '请检查后端邮件服务'}</div>`
  }
}

function buildPreviewPayload() {
  if (isRawMode.value) {
    return {
      body: body.value,
      body_format: props.bodyFormat,
      add_signature: props.addSignature,
    }
  }
  const variables = { ...props.variables }
  if (props.editableBody) {
    // 可编辑正文时，把当前编辑内容作为正文变量透给后端；
    // 若父组件已在 variables 里传了 body/content，会被当前编辑内容覆盖，保证预览=实发
    variables.body = body.value
  }
  return {
    scene: props.scene,
    subject: subject.value,
    variables,
    add_signature: props.addSignature,
  }
}

function buildSendPayload() {
  const payload = isRawMode.value
    ? { body: body.value, body_format: props.bodyFormat }
    : { scene: props.scene, variables: { ...props.variables } }
  if (props.editableBody && !isRawMode.value) {
    payload.variables.body = body.value
  }
  return {
    ...payload,
    to: to.value,
    cc: cc.value || [],
    subject: subject.value,
  }
}

function normalizeRecipients(list) {
  if (!Array.isArray(list)) return []
  return list
    .map((item) => {
      if (typeof item === 'string') return item.trim()
      if (item && typeof item === 'object') return (item.email || item.value || item.label || '').trim()
      return ''
    })
    .filter(Boolean)
}

async function onSend() {
  const toList = normalizeRecipients(to.value)
  if (!toList.length) {
    ElMessage.warning('请选择收件人')
    return
  }
  if (props.editableBody && !body.value.trim()) {
    ElMessage.warning('请输入邮件正文')
    return
  }
  sending.value = true
  try {
    const payload = buildSendPayload()
    payload.to = toList
    payload.cc = normalizeRecipients(cc.value)
    emit('send', payload)
    let res
    if (typeof props.customSend === 'function') {
      res = await props.customSend(payload)
    } else {
      res = await sendEmail(payload)
    }
    if (res?.success) {
      ElMessage.success('邮件发送成功')
      emit('success', res)
      if (props.closeOnSuccess) {
        emit('update:modelValue', false)
      }
    } else {
      const msg = res?.message || '邮件发送失败'
      ElMessage.error(msg)
      emit('error', new Error(msg))
    }
  } catch (e) {
    console.error('[MailComposeDialog] 邮件发送失败：', e)
    ElMessage.error('邮件发送失败：' + (e?.message || '未知错误'))
    emit('error', e)
  } finally {
    sending.value = false
  }
}

onBeforeUnmount(() => {
  if (timer) clearTimeout(timer)
})

defineExpose({ sending, refreshPreview })
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
