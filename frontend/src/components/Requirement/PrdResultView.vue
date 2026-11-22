<script setup>
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import PrdSourceList from './PrdSourceList.vue'

const props = defineProps({
  result: { type: Object, default: null },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['finalize'])

// 极简 markdown 预览：按行渲染标题/正文，避免引入额外依赖。
// PRD 是纯文本六章结构，此渲染足够可读；下载得到完整原始 .md。
const lines = computed(() => (props.result?.prd_markdown || '').split('\n'))

const statusLabel = computed(() => ({
  generated: 'AI 生成', fallback: '规则降级',
}[props.result?.status] || '已生成'))
const statusTag = computed(() => props.result?.status === 'fallback' ? 'warning' : 'success')

function onDownload() {
  emit('finalize', 'download')
}
</script>

<template>
  <div v-if="loading" class="prd-loading">
    <el-skeleton :rows="12" animated />
  </div>
  <div v-else-if="result" class="prd-result">
    <div class="result-bar">
      <span class="pm-tag" :class="statusTag === 'warning' ? 'orange' : 'green'">{{ statusLabel }}</span>
      <span v-if="result.gen_provider" class="pm-tag gray ml-8">{{ result.gen_provider }} / {{ result.gen_model }}</span>
      <span class="pm-tag gray ml-8">{{ result.trace_id }}</span>
      <div class="bar-right">
        <el-button size="small" @click="onDownload">下载 PRD.md</el-button>
        <el-button size="small" type="primary" plain @click="emit('finalize', 'finalize')">确认落库</el-button>
      </div>
    </div>

    <div v-if="result.notice" class="result-notice">
      <el-alert type="warning" :closable="false" show-icon :title="result.gen_fallback_reason || result.notice" />
    </div>

    <div class="result-grid">
      <div class="result-col">
        <div class="col-hd">PRD 六章预览</div>
        <div class="md-preview">
          <template v-for="(line, i) in lines" :key="i">
            <div v-if="line.startsWith('# ') || line.startsWith('## ')" class="md-h2">{{ line.replace(/^#+\s*/, '') }}</div>
            <div v-else-if="line.startsWith('### ')" class="md-h3">{{ line.replace(/^###\s*/, '') }}</div>
            <div v-else-if="line.startsWith('> ')" class="md-quote">{{ line.slice(2) }}</div>
            <div v-else-if="line.startsWith('- ')" class="md-li">{{ line.slice(2) }}</div>
            <div v-else-if="line.trim()" class="md-p">{{ line }}</div>
            <div v-else class="md-gap"></div>
          </template>
        </div>
      </div>
      <div class="result-col">
        <div class="col-hd">冲突 · 引用 · 假设</div>
        <PrdSourceList
          :sources="result.sources || []"
          :conflicts="result.conflicts || []"
          :assumptions="result.assumptions || []"
          :open-items="result.open_items || []"
        />
      </div>
    </div>
  </div>
  <el-empty v-else description="尚无需求分析结果，点击上方「生成 PRD」开始" :image-size="70" />
</template>

<style scoped>
.prd-result { font-size: 12px; }
.result-bar { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.bar-right { margin-left: auto; display: flex; gap: 7px; }
.ml-8 { margin-left: 8px; }
.result-notice { margin-bottom: 10px; }
.result-grid { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr); gap: 14px; }
.result-col { min-width: 0; border: 1px solid var(--border); border-radius: 10px; padding: 12px; background: var(--surface); }
.col-hd { font-weight: 700; font-size: 12.5px; margin-bottom: 10px; padding-bottom: 6px; border-bottom: 1px solid var(--border-subtle); }
.md-preview { max-height: 560px; overflow: auto; line-height: 1.7; padding-right: 6px; }
.md-h2 { font-weight: 700; font-size: 13px; margin: 12px 0 5px; padding-left: 7px; border-left: 3px solid var(--accent); }
.md-h3 { font-weight: 600; font-size: 12px; margin: 9px 0 4px; color: var(--text-secondary); }
.md-quote { color: var(--warning); background: var(--bg-app); border-radius: 5px; padding: 5px 8px; margin: 5px 0; font-size: 11px; }
.md-li { padding-left: 16px; position: relative; margin: 3px 0; }
.md-li::before { content: '•'; position: absolute; left: 4px; color: var(--accent); }
.md-p { margin: 4px 0; white-space: pre-wrap; word-break: break-word; }
.md-gap { height: 6px; }
@media (max-width: 1100px) { .result-grid { grid-template-columns: 1fr; } }
</style>
