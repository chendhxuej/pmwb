<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getPrdMeta, analyzePrd, getPrdStatus, finalizePrd } from '@/api/prdAnalysis.js'
import PrdResultView from './PrdResultView.vue'
import PrdKnowledgeSync from './PrdKnowledgeSync.vue'
import { downloadWithAuth } from '@/utils/download.js'

const props = defineProps({
  reqId: { type: String, default: '' },
  reqName: { type: String, default: '' },
  clarification: { type: String, default: '' },
})
const emit = defineEmits(['update:clarification'])

// 与用户故事生成完全独立：本地 state，不触碰父组件的 selectedStrategy / stories / genMeta。
const mode = ref('qa')
const profile = ref('concise')
const selectedSystems = ref(['CRM'])
const selectedDirs = ref([])   // 业务子目录筛选（同步面板勾选）
const answers = ref({})
const meta = ref({ dimensions: [], systems: [], knowledge_status: 'none', llm_available: false })
const metaLoading = ref(false)
const generating = ref(false)
const step = ref(-1)          // -1 未生成；0-4 五步进度
const result = ref(null)
const traceId = ref('')

const STEP_LABELS = ['解析原始需求', '推荐并确认系统', '装载本地知识', '十维拷问 / 快速自决', '生成并交付 PRD.md']
const stepLabel = computed(() => step.value >= 0 ? STEP_LABELS[step.value] : '')

const knowledgeLabel = computed(() => ({
  git: `Git 知识源已装载 ${meta.value.knowledge_files || 0} 篇`,
  none: '未 clone 知识库 · 降级无知识分析',
}[meta.value.knowledge_status] || '未知'))

async function loadMeta() {
  metaLoading.value = true
  try {
    const res = await getPrdMeta()
    meta.value = res || meta.value
    if (!selectedSystems.value.length && meta.value.systems?.length) {
      selectedSystems.value = [meta.value.systems[0]]
    }
    // 重开页面恢复最近分析状态（不自动拉取正文，避免与用户故事生成混淆）
    if (props.reqId) {
      const s = await getPrdStatus(props.reqId)
      if (s?.trace_id) traceId.value = s.trace_id
    }
  } catch (e) {
    console.warn('[PRD] meta 加载失败', e)
  } finally {
    metaLoading.value = false
  }
}

function toggleSystem(sys) {
  const arr = selectedSystems.value
  selectedSystems.value = arr.includes(sys) ? arr.filter(x => x !== sys) : [...arr, sys]
}

function setAnswer(key, val) {
  answers.value = { ...answers.value, [key]: val }
}

function answerCount() {
  return Object.values(answers.value).filter(v => v && v !== '__skip__').length
}

async function generate() {
  if (!props.clarification?.trim()) {
    ElMessage.warning('请先在左侧「澄清后需求内容」填写需求，作为分析输入')
    return
  }
  if (!selectedSystems.value.length) {
    ElMessage.warning('请至少选择一个涉及系统')
    return
  }
  generating.value = true
  result.value = null
  step.value = 0
  const timer = setInterval(() => {
    if (step.value < 4) step.value++
  }, 900)

  try {
    const data = await analyzePrd(props.reqId, {
      raw_requirement: props.clarification,
      systems: selectedSystems.value,
      mode: mode.value,
      profile: profile.value,
      answers: answers.value,
      req_name: props.reqName,
      selected_dirs: selectedDirs.value,
    })
    result.value = data
    traceId.value = data.trace_id
    if (data.status === 'fallback') {
      ElMessage({ type: 'warning', message: 'AI 降级为规则模板（非 AI 分析），详见结果区提示', duration: 8000 })
    } else {
      ElMessage.success(`PRD 生成完成：${data.sources?.length || 0} 条引用、${data.conflicts?.length || 0} 条冲突`)
    }
  } catch (e) {
    console.error('[PRD] 分析失败', e)
    ElMessage.error(typeof e === 'string' ? e : (e?.message || '需求分析失败'))
  } finally {
    clearInterval(timer)
    step.value = -1
    generating.value = false
  }
}

async function onAction(action) {
  if (!traceId.value) return
  if (action === 'download') {
    downloadWithAuth(`/api/v1/prd/download/${encodeURIComponent(traceId.value)}`, `PRD-${props.reqId}.md`)
    return
  }
  try {
    await finalizePrd(traceId.value)
    ElMessage.success('已确认落库')
  } catch (e) {
    ElMessage.error(e?.message || '确认落库失败')
  }
}

onMounted(loadMeta)
watch(() => props.reqId, (v) => { if (v) { result.value = null; loadMeta() } })
</script>

<template>
  <div class="prd-panel">
    <div class="prd-hd">
      <span class="prd-icon">✦</span>
      <span class="prd-title">AI 需求分析（PRD）</span>
      <span class="pm-tag blue">skill 移植</span>
      <span class="prd-hd-right">
        <span class="pm-tag gray">{{ knowledgeLabel }}</span>
        <span v-if="meta.llm_available" class="pm-tag green">大模型已连接</span>
        <span v-else class="pm-tag orange">大模型未连接</span>
      </span>
    </div>

    <div class="prd-body">
      <!-- 知识源同步（与用户故事生成无关，独立面板） -->
      <PrdKnowledgeSync @synced="loadMeta" @update:selectedDirs="selectedDirs = $event" />

      <!-- 配置区 -->
      <div class="prd-config">
        <div class="cfg-item">
          <div class="cfg-label">分析模式</div>
          <el-radio-group v-model="mode" size="small">
            <el-radio-button value="qa">问答拷问（十维）</el-radio-button>
            <el-radio-button value="fast">快速模式（不提问·记假设）</el-radio-button>
          </el-radio-group>
        </div>
        <div class="cfg-item">
          <div class="cfg-label">涉及系统（1–5 个）</div>
          <div class="sys-chips">
            <span
              v-for="s in (meta.systems || [])" :key="s"
              class="sys-chip" :class="{ on: selectedSystems.includes(s) }"
              @click="toggleSystem(s)"
            >{{ s }}</span>
          </div>
        </div>
        <div class="cfg-item">
          <div class="cfg-label">模板</div>
          <el-select v-model="profile" size="small" style="width: 150px">
            <el-option label="精简版 concise" value="concise" />
            <el-option label="深度版 deep" value="deep" />
          </el-select>
        </div>
        <div class="cfg-item cfg-action">
          <el-button
            type="primary" :loading="generating" :disabled="!clarification?.trim()"
            @click="generate"
          >{{ generating ? '正在分析…' : '生成 PRD（六章 + 冲突 + 引用）' }}</el-button>
        </div>
      </div>

      <!-- 十维问卷（qa 模式，一次性展示，非逐轮） -->
      <div v-if="mode === 'qa'" class="prd-questions">
        <div class="q-hd">
          <span>十维拷问 · 一次性问卷</span>
          <span class="pm-tag gray ml-8">已答 {{ answerCount() }} / {{ meta.dimensions.length || 10 }} · 跳过项记入待确认</span>
        </div>
        <div class="q-grid">
          <div v-for="d in (meta.dimensions || [])" :key="d.key" class="q-item">
            <div class="q-name">{{ d.name }}</div>
            <div class="q-hint">{{ d.hint }}</div>
            <el-input
              :model-value="answers[d.key] && answers[d.key] !== '__skip__' ? answers[d.key] : ''"
              size="small" placeholder="填写业务答案（可留空，由 AI 自决并记假设）"
              @update:model-value="setAnswer(d.key, $event)"
            />
            <el-button link size="small" class="q-skip" @click="setAnswer(d.key, '__skip__')">跳过</el-button>
          </div>
        </div>
        <div class="q-note">提示：全部问题均为业务语言（客户/订单/流程/规则/验收）；字段、接口、表结构等技术问题不做提问。</div>
      </div>

      <!-- 五步进度 -->
      <div v-if="generating" class="prd-progress">
        <div class="step-line">
          <span v-for="(l, i) in STEP_LABELS" :key="i" class="step-node" :class="{ active: i === step, done: i < step }">{{ i + 1 }} {{ l }}</span>
        </div>
        <el-progress :percentage="Math.round((step + 1) / 5 * 100)" :show-text="false" />
        <div class="step-cur">当前：{{ stepLabel }}</div>
      </div>

      <!-- 结果 -->
      <PrdResultView :result="result" :loading="false" @finalize="onAction" />
    </div>
  </div>
</template>

<style scoped>
.prd-panel { border: 1px solid var(--violet, #7c3aed); border-radius: 12px; margin-bottom: 16px; overflow: hidden; background: var(--surface); }
.prd-hd { display: flex; align-items: center; gap: 8px; padding: 10px 14px; border-bottom: 1px solid var(--border-subtle); font-weight: 700; font-size: 13px; }
.prd-icon { width: 20px; height: 20px; border-radius: 6px; background: var(--violet, #7c3aed); color: #fff; display: grid; place-items: center; font-size: 11px; }
.prd-title { font-weight: 700; }
.prd-hd-right { margin-left: auto; display: flex; gap: 6px; align-items: center; font-weight: 400; }
.prd-body { padding: 14px; }
.prd-config { display: flex; gap: 18px; align-items: flex-end; flex-wrap: wrap; margin-bottom: 14px; }
.cfg-label { font-size: 11.5px; color: var(--text-secondary); font-weight: 600; margin-bottom: 5px; }
.cfg-action { margin-left: auto; }
.sys-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.sys-chip { border: 1px solid var(--border); border-radius: 7px; padding: 5px 10px; font-size: 11.5px; cursor: pointer; color: var(--text-secondary); background: var(--surface); }
.sys-chip.on { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); font-weight: 600; }
.prd-questions { border: 1px solid var(--border-subtle); border-radius: 10px; padding: 12px; margin-bottom: 14px; background: var(--bg-app); }
.q-hd { display: flex; align-items: center; font-weight: 600; font-size: 12.5px; margin-bottom: 10px; }
.q-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.q-item { border: 1px solid var(--border); border-radius: 8px; padding: 9px 10px; background: var(--surface); }
.q-name { font-weight: 600; font-size: 12px; margin-bottom: 2px; }
.q-hint { color: var(--text-muted); font-size: 10.5px; margin-bottom: 6px; line-height: 1.5; }
.q-skip { margin-top: 4px; }
.q-note { color: var(--text-muted); font-size: 10.5px; margin-top: 10px; line-height: 1.6; }
.prd-progress { border: 1px solid var(--border-subtle); border-radius: 10px; padding: 12px; margin-bottom: 14px; }
.step-line { display: flex; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; }
.step-node { font-size: 10.5px; color: var(--text-muted); padding: 3px 6px; border-radius: 5px; background: var(--bg-app); }
.step-node.active { background: var(--accent-soft); color: var(--accent); font-weight: 700; }
.step-node.done { background: var(--success-soft, #ecfdf3); color: var(--success, #0f9d6b); }
.step-cur { font-size: 11px; color: var(--text-secondary); margin-top: 6px; }
.ml-8 { margin-left: 8px; }
@media (max-width: 1100px) { .q-grid { grid-template-columns: 1fr; } }
</style>
