<template>
  <el-dialog
    :model-value="modelValue"
    title="上传客诉工单周报数据"
    width="560px"
    @update:model-value="$emit('update:modelValue', $event)"
    @closed="reset"
  >
    <el-alert type="info" :closable="false" show-icon class="tip">
      上传小信工单导出 xlsx：系统自动按自然周归档留底 → BOMC 流水号去重入库 →
      按字典分类 → 重算批量簇/复发标记。
    </el-alert>

    <el-upload
      ref="uploadRef"
      drag
      :auto-upload="false"
      :limit="1"
      accept=".xlsx"
      :on-change="onFileChange"
      :on-remove="() => (file = null)"
    >
      <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
      <div class="el-upload__text">拖拽文件到此处，或<em>点击选择</em></div>
      <template #tip>
        <div class="el-upload__tip">仅支持 .xlsx（小信「全部明细」导出格式）</div>
      </template>
    </el-upload>

    <el-checkbox v-model="withReport" class="report-check">导入完成后直接生成客诉周报</el-checkbox>

    <div v-if="result" class="result-box">
      <template v-if="result.ingest">
        <div class="result-line">
          解析 <b>{{ result.ingest.parsed }}</b> 行 / 新增
          <b class="ok">{{ result.ingest.inserted }}</b> 条（重复跳过 {{ result.ingest.skipped_duplicate }}），
          归属周：{{ (result.ingest.weeks || []).join('、') || '—' }}
        </div>
        <div class="result-line">批量簇 {{ result.ingest.clusters }} 个｜复发标记 {{ result.ingest.recur }} 条</div>
      </template>
      <div v-if="result.report && result.report.week" class="result-line ok">
        周报已生成：{{ result.report.week }}（{{ result.report.pdf_generated ? 'HTML+PDF' : '仅 HTML' }}）
      </div>
      <div v-if="result.report && result.report.error" class="result-line err">
        周报生成失败：{{ result.report.error }}
      </div>
    </div>

    <template #footer>
      <el-button v-if="result && result.report && result.report.week" type="primary" @click="openReport">
        打开周报
      </el-button>
      <el-button @click="$emit('update:modelValue', false)">关闭</el-button>
      <el-button type="primary" :loading="uploading" :disabled="!file" @click="doImport">
        开始导入
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { complaintApi } from '@/api/complaint'

defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue', 'imported'])

const uploadRef = ref(null)
const file = ref(null)
const withReport = ref(true)
const uploading = ref(false)
const result = ref(null)

function onFileChange(f) {
  file.value = f.raw || null
}

function reset() {
  file.value = null
  result.value = null
  uploadRef.value?.clearFiles()
}

async function doImport() {
  if (!file.value) return
  uploading.value = true
  try {
    result.value = await complaintApi.importWeekly(file.value, withReport.value)
    ElMessage.success(`导入完成：新增 ${result.value.ingest?.inserted ?? 0} 条`)
    emit('imported', result.value)
  } catch (e) {
    // request.js 已弹错误提示
  } finally {
    uploading.value = false
  }
}

function openReport() {
  const w = result.value?.report?.week
  if (w) window.open(complaintApi.reportDownloadUrl(w, 'html'), '_blank')
}
</script>

<style scoped>
.tip {
  margin-bottom: 14px;
}
.report-check {
  margin-top: 10px;
}
.result-box {
  margin-top: 12px;
  padding: 10px 14px;
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  font-size: 12.5px;
  line-height: 1.9;
}
.result-line.ok {
  color: var(--success);
}
.result-line.err {
  color: var(--danger);
}
</style>
