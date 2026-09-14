<template>
  <el-dialog
    :model-value="modelValue"
    title="导入预览 · 请确认遗留任务分类"
    width="920px"
    @update:model-value="(v) => $emit('update:modelValue', v)"
    @close="onClose"
  >
    <el-alert
      v-if="warnings.length"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 12px"
    >
      <template #title>解析提示（不影响导入，识别不准可后续在工单详情手工修正）</template>
      <div v-for="(w, i) in warnings" :key="i" style="font-size: 12px; line-height: 1.6">{{ w }}</div>
    </el-alert>

    <div class="prev-section">
      <div class="prev-title">分析工单</div>
      <el-descriptions :column="2" size="small" border>
        <el-descriptions-item label="课题名称">{{ fields.topic_name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="运营团队 / 人员">
          {{ [fields.analyst_team, fields.analyst_name].filter(Boolean).join(' / ') || '—' }}
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="prev-section">
      <div class="prev-title">
        <span>遗留任务（共 {{ rows.length }} 条）</span>
        <el-select
          v-model="batchCat"
          placeholder="批量设分类"
          size="small"
          clearable
          style="width: 160px; margin-left: 10px"
          @change="onBatch"
        >
          <el-option v-for="c in WORK_ORDER_CATEGORIES" :key="c.key" :label="c.label" :value="c.key" />
        </el-select>
      </div>
      <el-table :data="rows" size="small" border max-height="320">
        <el-table-column type="index" label="#" width="44" />
        <el-table-column label="任务内容" min-width="220">
          <template #default="{ row }">
            <span class="task-content">{{ row.content }}</span>
          </template>
        </el-table-column>
        <el-table-column label="责任人" width="150">
          <template #default="{ row }">
            <el-tag v-for="h in row.handlers" :key="h" size="small" class="h-tag">{{ h }}</el-tag>
            <span v-if="!row.handlers.length" class="muted">待认领</span>
          </template>
        </el-table-column>
        <el-table-column label="工单类别" width="150">
          <template #default="{ row }">
            <el-select v-model="row.category" size="small" @change="(v) => onCatChange(row, v)">
              <el-option v-for="c in WORK_ORDER_CATEGORIES" :key="c.key" :label="c.label" :value="c.key" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="子类" width="140">
          <template #default="{ row }">
            <el-select v-model="row.issue_type" size="small">
              <el-option
                v-for="t in (TYPE_BY_CAT[row.category] || [])"
                :key="t.value"
                :label="t.label"
                :value="t.value"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="计划完成" width="120">
          <template #default="{ row }">{{ row.due_date || '—' }}</template>
        </el-table-column>
      </el-table>
    </div>

    <template #footer>
      <el-button @click="onClose">取消</el-button>
      <el-button type="primary" @click="$emit('confirm', buildPayload())">确认创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { WORK_ORDER_CATEGORIES, TYPE_BY_CAT } from '@/constants/operation.js'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  preview: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

const rows = ref([])
const warnings = ref([])
const fields = ref({})
const batchCat = ref('')

watch(
  () => props.preview,
  (p) => {
    if (!p) return
    fields.value = p.analysis_fields || {}
    warnings.value = p.warnings || []
    rows.value = (p.legacy_tasks || []).map((t) => ({
      content: t.content,
      handlers: t.handlers || [],
      category: t.suggest_category || 'task',
      issue_type: t.suggest_issue_type || 'temp_task',
      due_date: t.due_date || null,
    }))
  },
  { immediate: true, deep: true }
)

function onCatChange(row, v) {
  const opts = TYPE_BY_CAT[v] || []
  row.issue_type = opts.length ? opts[0].value : 'other'
}

function onBatch(v) {
  if (!v) return
  rows.value.forEach((r) => {
    r.category = v
    onCatChange(r, v)
  })
  batchCat.value = ''
}

function buildPayload() {
  return rows.value.map((r) => ({
    content: r.content,
    handlers: r.handlers,
    category: r.category,
    issue_type: r.issue_type,
    due_date: r.due_date,
  }))
}

function onClose() {
  emit('update:modelValue', false)
  emit('cancel')
}
</script>

<style scoped>
.prev-section {
  margin-bottom: 16px;
}
.prev-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-secondary);
  margin-bottom: 10px;
}
.h-tag {
  margin-right: 4px;
}
.task-content {
  font-size: 13px;
  line-height: 1.5;
}
.muted {
  color: var(--text-muted);
  font-size: 12px;
}
</style>
