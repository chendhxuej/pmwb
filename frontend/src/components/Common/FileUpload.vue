<template>
  <el-upload
    :action="action"
    :multiple="multiple"
    :limit="limit"
    :before-upload="beforeUpload"
    :on-success="handleSuccess"
    :on-error="handleError"
  >
    <el-button type="primary">点击上传</el-button>
    <template #tip>
      <div class="el-upload__tip">{{ tip }}</div>
    </template>
  </el-upload>
</template>

<script setup>
import { ElMessage } from 'element-plus'

const props = defineProps({
  action: { type: String, default: '/api/v1/upload' },
  multiple: { type: Boolean, default: false },
  limit: { type: Number, default: 5 },
  maxSize: { type: Number, default: 50 },
  tip: { type: String, default: '' },
  accept: { type: String, default: '' },
})

const emit = defineEmits(['success', 'error'])

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
</script>
