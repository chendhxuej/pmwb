<template>
  <el-drawer
    :model-value="modelValue"
    :title="drawerTitle"
    size="68%"
    destroy-on-close
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div class="drill-bar">
      <el-tag
        v-for="(v, k) in activeFilters"
        :key="k"
        closable
        size="small"
        type="info"
        @close="removeFilter(k)"
      >{{ filterLabels[k] }}：{{ v }}</el-tag>
      <el-button size="small" text type="primary" @click="openLedger">进入工单台账 →</el-button>
    </div>

    <el-table v-loading="loading" :data="rows" size="small" @row-click="showDetail">
      <el-table-column prop="ticket_no" label="工单号" width="150">
        <template #default="{ row }"><span class="mono">{{ row.ticket_no }}</span></template>
      </el-table-column>
      <el-table-column prop="created_time" label="创建时间" width="150">
        <template #default="{ row }">{{ fmtTime(row.created_time) }}</template>
      </el-table-column>
      <el-table-column prop="city" label="地市" width="80" />
      <el-table-column prop="category_l1" label="一级" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="l1TagType(row.category_l1)">{{ row.category_l1 || '待分析' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="category_l2" label="二级场景" min-width="140" show-overflow-tooltip />
      <el-table-column prop="ai_confidence" label="AI置信" width="80" align="center">
        <template #default="{ row }">
          <span v-if="row.ai_confidence !== null && row.ai_confidence !== undefined"
                :class="row.ai_confidence >= 0.75 ? 'conf-hi' : 'conf-low'">
            {{ row.ai_confidence.toFixed(2) }}
          </span>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="86" />
      <el-table-column prop="content" label="投诉内容" min-width="220" show-overflow-tooltip />
    </el-table>

    <div class="drill-pager">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        small
        @current-change="load"
      />
    </div>

    <!-- 工单详情（嵌套抽屉） -->
    <el-drawer
      v-model="detailVisible"
      :title="`工单详情 ${detail?.ticket_no || ''}`"
      size="46%"
      append-to-body
    >
      <template v-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="工单号">{{ detail.ticket_no }}</el-descriptions-item>
          <el-descriptions-item label="归属周">{{ detail.week || '—' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ fmtTime(detail.created_time) }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ detail.status || '—' }}</el-descriptions-item>
          <el-descriptions-item label="地市">{{ detail.city || '—' }}</el-descriptions-item>
          <el-descriptions-item label="渠道">{{ detail.channel || '—' }}</el-descriptions-item>
          <el-descriptions-item label="申告类别">{{ detail.appeal_category || '—' }}</el-descriptions-item>
          <el-descriptions-item label="工单属性">{{ detail.biz_attr || '—' }}</el-descriptions-item>
          <el-descriptions-item label="处理人">{{ detail.handler || '—' }}</el-descriptions-item>
          <el-descriptions-item label="处理单位">{{ detail.handle_unit || '—' }}</el-descriptions-item>
          <el-descriptions-item label="一级定性">
            <el-tag size="small" :type="l1TagType(detail.category_l1)">{{ detail.category_l1 || '待分析' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="二级场景">{{ detail.category_l2 || '—' }}</el-descriptions-item>
        </el-descriptions>

        <!-- AI 分析块：始终展示归类来源，历史单无置信度时如实说明（不静默省略） -->
        <div class="ai-block">
          <div class="ai-title">
            🤖 大模型分析
            <span
              v-if="detail.ai_confidence !== null && detail.ai_confidence !== undefined"
              class="conf"
              :class="detail.ai_confidence >= 0.75 ? 'conf-hi' : 'conf-low'"
            >
              置信度 {{ detail.ai_confidence.toFixed(2) }}
            </span>
            <el-tag size="small" :type="classifyTagType(detail.classify_by)">
              {{ classifyText(detail.classify_by) }}
            </el-tag>
          </div>
          <div class="ai-evidence">
            {{ detail.ai_evidence
              || (detail.classify_by === 'manual' ? '（人工校正，AI 判断依据未留存）'
                : detail.classify_by === 'auto' || !detail.classify_by ? '（待 AI 分析：下次归类任务自动补齐，也可在工单明细页手动重跑）'
                : '（无依据摘录）') }}
          </div>
        </div>

        <div class="sec"><h4>投诉内容</h4><pre class="pre">{{ detail.content || '（无）' }}</pre></div>
        <div class="sec"><h4>处理过程（往期处置链路）</h4><pre class="pre">{{ detail.solution_history || '（无）' }}</pre></div>
      </template>
    </el-drawer>
  </el-drawer>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { complaintApi } from '@/api/complaint'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '投诉工单下钻' },
  /** 下钻过滤条件：{week, l1, l2, is_batch, is_recur, unclosed, retention, problem_no, handler, city, classify_by} */
  filters: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['update:modelValue'])

const router = useRouter()
const loading = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const detail = ref(null)
const detailVisible = ref(false)

const filterLabels = {
  week: '周', l1: '一级', l2: '场景', is_batch: '批量簇', is_recur: '复发',
  unclosed: '未结单', retention: '超期', problem_no: '问题', handler: '处理人',
  city: '地市', classify_by: '归类来源',
}

const activeFilters = computed(() => {
  const out = {}
  for (const [k, v] of Object.entries(props.filters || {})) {
    if (v !== undefined && v !== null && v !== '') out[k] = v
  }
  return out
})

const drawerTitle = computed(() => `${props.title}（共 ${total.value} 单）`)

async function load() {
  loading.value = true
  try {
    const res = await complaintApi.listTickets({ page: page.value, page_size: pageSize, ...activeFilters.value })
    rows.value = res?.items || []
    total.value = res?.total || 0
  } catch (e) {
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

watch(() => [props.modelValue, props.filters], () => {
  if (props.modelValue) {
    page.value = 1
    load()
  }
}, { deep: true, immediate: true })

function removeFilter(key) {
  const next = { ...props.filters }
  delete next[key]
  emit('update:filters', next)
}

function showDetail(row) {
  // 列表已带全部字段，直接用；content 预览截断过，取全量详情兜底
  if ((row.content || '').length >= 300 || !row.solution_history) {
    complaintApi.getTicket(row.id).then(d => { detail.value = d || row }).catch(() => { detail.value = row })
  } else {
    detail.value = row
  }
  detailVisible.value = true
}

function openLedger() {
  emit('update:modelValue', false)
  router.push({ path: '/operation/complaint-center/tickets', query: { ...activeFilters.value } })
}

function fmtTime(v) {
  if (!v) return '—'
  return String(v).replace('T', ' ').slice(0, 16)
}

function l1TagType(l1) {
  return { '系统问题': 'danger', '流程优化': 'warning', '数据问题': 'info', '投诉咨询': 'success' }[l1] || 'info'
}

// 归类来源展示（AI 归类 / 待人工确认 / 人工校正 / 待分析）
function classifyText(by) {
  return { ai: 'AI 归类', ai_low: '待人工确认', manual: '人工校正' }[by] || '待分析'
}

function classifyTagType(by) {
  return { ai: 'success', ai_low: 'warning', manual: 'primary' }[by] || 'info'
}
</script>

<style scoped>
.drill-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-bottom: 10px;
}
.mono {
  font-family: var(--font-mono, monospace);
  font-size: 12px;
}
.conf-hi { color: var(--success, #16a34a); font-weight: 600; }
.conf-low { color: var(--warning, #ea580c); font-weight: 600; }
.drill-pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}
.ai-block {
  margin-top: 12px;
  padding: 10px 12px;
  background: var(--bg-secondary, #f5f7fa);
  border-left: 3px solid var(--accent, #2563eb);
  border-radius: 6px;
}
.ai-title {
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.conf { font-size: 12px; }
.ai-evidence {
  margin-top: 6px;
  font-size: 12.5px;
  color: var(--text-secondary, #6b7a90);
  line-height: 1.6;
}
.sec { margin-top: 14px; }
.sec h4 {
  font-size: 13px;
  margin: 0 0 6px;
  color: var(--text-primary, #1f2d3d);
}
.pre {
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12.5px;
  line-height: 1.7;
  background: var(--bg-secondary, #f5f7fa);
  padding: 10px 12px;
  border-radius: 6px;
  margin: 0;
  max-height: 320px;
  overflow: auto;
}
:deep(.el-table__row) { cursor: pointer; }
</style>
