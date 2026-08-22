<template>
  <div
    ref="pasteZoneRef"
    class="paste-upload-zone"
    tabindex="0"
    :class="{ 'is-pasting': isPasting }"
  >
    <el-upload
      ref="uploadRef"
      :action="action"
      :multiple="multiple"
      :limit="limit"
      :before-upload="beforeUpload"
      :on-success="handleSuccess"
      :on-error="handleError"
      :accept="accept"
    >
      <el-button type="primary" :loading="isPasting">点击上传</el-button>
      <template #tip>
        <div class="el-upload__tip">{{ finalTip }}</div>
      </template>
    </el-upload>
  </div>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { usePasteUpload } from '@/composables/usePasteUpload.js'

const props = defineProps({
  action: { type: String, default: '/api/v1/upload' },
  multiple: { type: Boolean, default: false },
  limit: { type: Number, default: 5 },
  maxSize: { type: Number, default: 50 },
  tip: { type: String, default: '' },
  accept: { type: String, default: '' },
})

const emit = defineEmits(['success', 'error'])

const uploadRef = ref(null)
const pasteZoneRef = ref(null)

const finalTip = computed(() => {
  const pasteHint = '支持点击上传或 Ctrl+V 粘贴文件/截图'
  return props.tip ? `${props.tip}，${pasteHint}` : pasteHint
})

const beforeUpload = (file) => {
  const sizeMB = file.size / 1024 / 1024
  if (sizeMB > props.maxSize) {
    ElMessage.error(`文件大小不能超过 ${props.maxSize}MB`)
    return false
  }
  return true
}

const handleSuccess = (response, file) => {
  ElMessage.success(`${file.name} 上传成功`)
  emit('success', response, file)
}

const handleError = (error, file) => {
  ElMessage.error(`${file.name} 上传失败`)
  emit('error', error, file)
}

const { isPasting } = usePasteUpload({
  targetRef: pasteZoneRef,
  accept: props.accept,
  onFiles: async (files) => {
    const validFiles = files.filter((file) => beforeUpload(file) !== false)
    if (!validFiles.length) return
    validFiles.forEach((file) => uploadRef.value?.handleStart(file))
    await nextTick()
    uploadRef.value?.submit()
  },
})
</script>

<style scoped>
.paste-upload-zone {
  outline: none;
  border-radius: 4px;
  transition: background-color 0.2s;
}
.paste-upload-zone:focus-visible {
  background-color: var(--el-fill-color-light);
}
.paste-upload-zone.is-pasting {
  opacity: 0.7;
  pointer-events: none;
}
</style>
