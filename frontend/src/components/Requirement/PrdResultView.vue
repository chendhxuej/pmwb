<script setup>
import { computed, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import PrdSourceList from './PrdSourceList.vue'

const props = defineProps({
  result: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  refining: { type: Boolean, default: false },
})
const emit = defineEmits(['finalize', 'refine'])

// 极简 markdown 预览：按行渲染标题/正文，避免引入额外依赖。
// PRD 是纯文本六章结构，此渲染足够可读；下载得到完整原始 .md。
const lines = computed(() => (props.result?.prd_markdown || '').split('\n'))

const statusLabel = computed(() => ({
  generated: 'AI 生成', fallback: '规则降级',
}[props.result?.status] || '已生成'))
const statusTag = computed(() => props.result?.status === 'fallback' ? 'warning' : 'success')

// 待澄清点逐条补充（零迁移：从 PRD 6.1 反解，随 result 切换重置）
const openItems = computed(() => props.result?.open_items || [])
const supplements = reactive({})
const designNotes = reactive({ value: '' })
watch(() => props.result?.trace_id, () => {
  Object.keys(supplements).forEach(k => delete supplements[k])
  designNotes.value = ''
})

function onDownload() {
  emit('finalize', 'download')
}
function onRefine() {
  const pairs = openItems.value
    .map(item => ({ item, answer: (supplements[item] || '').trim() }))
    .filter(x => x.answer)
  const notes = (designNotes.value || '').trim()
  if (!pairs.length && !notes) {
    ElMessage.warning('请至少补充一条待确认项，或填写方案备注')
    return
  }
  emit('refine', { supplements: pairs, design_notes: notes })
}
</script>

<template>
  <div v-if="loading" class="prd-loading">
    <el-skeleton :rows="12" animated />
  </div>
  <div v-else-if="result" class="prd-result">
    <div class="result-bar">
      <span class="pm-tag" :class="statusTag === 'warning' ? 'orange' : 'green'">{{ statusLabel }}</span>
      <span class="pm-tag blue ml-8">{{ result.version || 'v1' }}</span>
      <span v-if="result.parent_trace_id" class="pm-tag gray ml-8">基于 {{ result.parent_trace_id.slice(-6) }}</span>
      <span v-if="result.gen_provider" class="pm-tag gray ml-8">{{ result.gen_provider }} / {{ result.gen_model }}</span>
      <span class="pm-tag gray ml-8">{{ result.trace_id }}</span>
      <div class="bar-right">
        <el-button size="small" :loading="refining" type="warning" plain @click="onRefine">补充并重评</el-button>
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

    <div v-if="openItems.length" class="refine-box">
      <div class="refine-hd">待澄清点补充 · 二次评估<span class="refine-sub">逐条填写后生成新版本，旧版本留痕</span></div>
      <div v-for="(item, i) in openItems" :key="i" class="refine-item">
        <div class="refine-q">{{ item }}</div>
        <el-input
          v-model="supplements[item]"
          type="textarea"
          :rows="2"
          size="small"
          placeholder="补充你的确认结论 / 口径 / 范围（业务语言，不写技术实现）"
        />
      </div>
      <div class="refine-item">
        <div class="refine-q">方案备注（可选）</div>
        <el-input
          v-model="designNotes.value"
          type="textarea"
          :rows="2"
          size="small"
          placeholder="对澄清后需求的细化、设计倾向、验收关注点"
        />
      </div>
      <div class="refine-foot">
        <el-button size="small" type="warning" :loading="refining" @click="onRefine">补充并重评 → 生成 {{ result.version === 'v1' ? 'v2' : '下一版' }}</el-button>
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
.refine-box { margin-top: 14px; border: 1px solid var(--warning); border-radius: 10px; padding: 12px; background: var(--surface); }
.refine-hd { font-weight: 700; font-size: 13px; color: var(--warning); margin-bottom: 10px; }
.refine-sub { font-weight: 400; font-size: 11px; color: var(--text-muted); margin-left: 8px; }
.refine-item { margin-bottom: 9px; }
.refine-q { font-size: 12px; color: var(--text-primary); margin-bottom: 4px; line-height: 1.5; }
.refine-foot { margin-top: 6px; text-align: right; }
@media (max-width: 1100px) { .result-grid { grid-template-columns: 1fr; } }
</style>
