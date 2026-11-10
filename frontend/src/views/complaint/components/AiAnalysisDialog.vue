<template>
  <el-dialog
    :model-value="modelValue"
    :title="`工单 AI 分析全文 · ${ticket?.ticket_no || ''}`"
    width="72%"
    top="6vh"
    destroy-on-close
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div v-loading="loading" class="ai-full">
      <!-- 头部：单号 + 一键复制全文（下钻场景看完整信息不必再点进详情抽屉） -->
      <div class="ai-full__bar">
        <span class="ai-full__meta">
          {{ ticket?.week || '—' }} ｜ {{ fmtTime(ticket?.created_time) }} ｜ {{ ticket?.city || '—' }}
          ｜ {{ ticket?.status || '—' }}
        </span>
        <el-button size="small" :icon="DocumentCopy" @click="copyAll">复制全文</el-button>
      </div>

      <div class="ai-full__block ai-full__primary">
        <div class="ai-full__h">
          🤖 AI 分析总结（根因全文）
          <el-tag v-if="conf !== null" size="small" :type="conf >= 0.75 ? 'success' : 'warning'">
            置信度 {{ conf.toFixed(2) }}
          </el-tag>
          <el-tag size="small" :type="classifyType">{{ classifyText }}</el-tag>
        </div>
        <pre class="ai-full__pre">{{ d.root_cause || '（根因待分析：下次根因任务自动补齐，或在工单明细页手动重跑）' }}</pre>
      </div>

      <el-descriptions :column="3" border size="small" class="ai-full__desc">
        <el-descriptions-item label="一级性质">{{ d.category_l1 || '—' }}</el-descriptions-item>
        <el-descriptions-item label="二级场景">{{ d.category_l2 || '—' }}</el-descriptions-item>
        <el-descriptions-item label="归类来源">{{ classifyText }}</el-descriptions-item>
        <el-descriptions-item label="故障环节">{{ d.fault_stage || '—' }}</el-descriptions-item>
        <el-descriptions-item label="故障系统">{{ d.fault_system || '—' }}</el-descriptions-item>
        <el-descriptions-item label="缺陷性质">{{ d.fault_type || '—' }}</el-descriptions-item>
        <el-descriptions-item label="责任归属">{{ d.own_party || '—' }}</el-descriptions-item>
        <el-descriptions-item label="处置方式">{{ d.fix_mode || '—' }}</el-descriptions-item>
        <el-descriptions-item label="根因状态">{{ d.rc_status || '—' }}</el-descriptions-item>
        <el-descriptions-item label="根因簇号">{{ d.rootcause_no || '—' }}</el-descriptions-item>
        <el-descriptions-item label="L2 模块问题">{{ moduleNames || '—' }}</el-descriptions-item>
        <el-descriptions-item label="已知/新增">{{ knownText }}</el-descriptions-item>
      </el-descriptions>

      <div class="ai-full__grid">
        <div class="ai-full__block">
          <div class="ai-full__h">AI 归类依据</div>
          <pre class="ai-full__pre ai-full__pre--sub">{{ d.ai_evidence || '（无依据摘录）' }}</pre>
        </div>
        <div class="ai-full__block">
          <div class="ai-full__h">根因判定依据</div>
          <pre class="ai-full__pre ai-full__pre--sub">{{ d.rc_evidence || '（未留存）' }}</pre>
        </div>
      </div>

      <div v-if="d.rc_gap" class="ai-full__block ai-full__warn">
        <div class="ai-full__h">信息缺口（AI 判定受限原因）</div>
        <pre class="ai-full__pre ai-full__pre--sub">{{ d.rc_gap }}</pre>
      </div>

      <div class="ai-full__block">
        <div class="ai-full__h">投诉内容（全文）</div>
        <pre class="ai-full__pre ai-full__pre--scroll">{{ d.content || '（无）' }}</pre>
      </div>
      <div class="ai-full__block">
        <div class="ai-full__h">处理过程 / 往期处置链路（全文）</div>
        <pre class="ai-full__pre ai-full__pre--scroll">{{ d.solution_history || '（无）' }}</pre>
      </div>
    </div>

    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">关闭</el-button>
      <el-button type="primary" :icon="Download" @click="$emit('export-one', d)">导出本单明细</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { DocumentCopy, Download } from '@element-plus/icons-vue'
import { complaintApi } from '@/api/complaint'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 列表行：已含大部分字段，抽屉会再取一次详情兜底全文 */
  ticket: { type: Object, default: null },
})
defineEmits(['update:modelValue', 'export-one'])

const loading = ref(false)
const detail = ref({})
const d = computed(() => ({ ...(props.ticket || {}), ...(detail.value || {}) }))
const conf = computed(() => {
  const v = d.value.ai_confidence
  return v === null || v === undefined ? null : Number(v)
})
const classifyText = computed(() => ({
  ai: 'AI 归类', ai_low: '待人工确认', manual: '人工校正', auto: '待分析',
}[d.value.classify_by] || '待分析'))
const classifyType = computed(() => ({
  ai: 'success', ai_low: 'warning', manual: 'primary',
}[d.value.classify_by] || 'info'))
const knownText = computed(() => {
  const f = d.value.known_flag
  if (f === 1) return `已知问题 ${d.value.known_problem_no || ''}`
  if (f === 0) return '新增问题'
  return '未判定'
})
const moduleNames = computed(() => {
  const tags = d.value.module_problem_tags
  if (!tags) return ''
  return String(tags).split('|')
    .map(t => (t.includes('::') ? t.split('::').slice(1).join('::') : t))
    .join('、')
})

// 列表返回的 content / solution_history 已是全文，但历史行可能只带预览字段；
// 打开时统一取一次详情（getTicket 返回 SELECT * 全文），保证「完整」。
watch(() => [props.modelValue, props.ticket?.id], async ([open, id]) => {
  if (!open || !id) return
  loading.value = true
  try {
    const r = await complaintApi.getTicket(id)
    detail.value = r || {}
  } catch (e) {
    detail.value = {}
  } finally {
    loading.value = false
  }
}, { immediate: true })

function fmtTime(v) {
  return v ? String(v).replace('T', ' ').slice(0, 16) : '—'
}

async function copyAll() {
  const x = d.value
  const text = [
    `工单号：${x.ticket_no || ''}`,
    `归属周：${x.week || ''}｜创建时间：${fmtTime(x.created_time)}｜地市：${x.city || ''}｜状态：${x.status || ''}`,
    `一级性质：${x.category_l1 || '—'}｜二级场景：${x.category_l2 || '—'}｜归类来源：${classifyText.value}`,
    `故障环节：${x.fault_stage || '—'}｜故障系统：${x.fault_system || '—'}｜缺陷性质：${x.fault_type || '—'}`,
    `责任归属：${x.own_party || '—'}｜处置方式：${x.fix_mode || '—'}｜根因簇：${x.rootcause_no || '—'}`,
    `L2 模块问题：${moduleNames.value || '—'}｜已知/新增：${knownText.value}`,
    '',
    '【AI 分析总结（根因全文）】', x.root_cause || '（待分析）',
    '', '【AI 归类依据】', x.ai_evidence || '（无）',
    '', '【根因判定依据】', x.rc_evidence || '（无）',
    ...(x.rc_gap ? ['', '【信息缺口】', x.rc_gap] : []),
    '', '【投诉内容】', x.content || '（无）',
    '', '【处理过程】', x.solution_history || '（无）',
  ].join('\n')
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制工单 AI 分析全文')
  } catch (e) {
    ElMessage.warning('复制失败，请手动选择文本')
  }
}
</script>

<style scoped>
.ai-full { max-height: 76vh; overflow: auto; padding-right: 4px; }
.ai-full__bar {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; margin-bottom: 12px;
}
.ai-full__meta { font-size: 12.5px; color: var(--text-secondary, #6b7a90); }
.ai-full__block {
  margin-top: 12px; padding: 10px 12px;
  background: var(--bg-secondary, #f5f7fa);
  border-left: 3px solid var(--accent, #2563eb); border-radius: 6px;
}
.ai-full__primary { border-left-width: 4px; }
.ai-full__warn { border-left-color: var(--warning, #ea580c); }
.ai-full__h {
  font-size: 13px; font-weight: 600; margin-bottom: 6px;
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.ai-full__desc { margin-top: 12px; }
.ai-full__grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.ai-full__pre {
  margin: 0; white-space: pre-wrap; word-break: break-all;
  font-size: 13px; line-height: 1.75;
  font-family: inherit;
  color: var(--text-primary, #1f2d3d);
}
.ai-full__pre--sub { font-size: 12.5px; color: var(--text-secondary, #6b7a90); }
.ai-full__pre--scroll { max-height: 260px; overflow: auto; font-size: 12.5px; }
@media (max-width: 960px) {
  .ai-full__grid { grid-template-columns: 1fr; }
}
</style>
