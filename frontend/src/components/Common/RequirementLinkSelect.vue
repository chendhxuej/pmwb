<template>
  <div class="rls" :class="{ 'is-disabled': disabled }" @click="openDialog">
    <div class="rls-trigger">
      <template v-if="displayed.length">
        <el-tag
          v-for="opt in displayed"
          :key="opt.value"
          size="small"
          closable
          :disable-transitions="true"
          :title="opt.value"
          @close.stop="remove(opt.value)"
        >
          {{ opt.label }}
        </el-tag>
        <span v-if="collapsedCount" class="rls-more">+{{ collapsedCount }}</span>
      </template>
      <span v-else class="rls-placeholder">{{ placeholder }}</span>
    </div>
    <el-icon v-if="selected.length && !disabled" class="rls-clear" @click.stop="clearAll">
      <CircleClose />
    </el-icon>
  </div>

  <el-dialog
    v-model="visible"
    title="选择关联需求"
    width="860px"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
  >
    <div class="rls-picker">
      <!-- 搜索 -->
      <div class="rls-picker-header">
        <el-input
          v-model="query"
          class="rls-picker-search"
          placeholder="输入需求文号 / 名称搜索"
          clearable
          @keyup.enter="doSearch"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button :loading="loading" @click="doSearch">搜索</el-button>
      </div>

      <!-- 已选 -->
      <div class="rls-picker-selected">
        <span class="rls-picker-label">已选 {{ selected.length }} 个</span>
        <div class="rls-picker-tags">
          <el-tag
            v-for="opt in selectedOptions"
            :key="opt.value"
            size="small"
            closable
            :disable-transitions="true"
            @close="remove(opt.value)"
          >
            {{ opt.label }}
          </el-tag>
          <span v-if="!selected.length" class="rls-picker-none">未选择</span>
        </div>
        <el-button v-if="selected.length" link type="primary" size="small" @click="clearAll">清空</el-button>
      </div>

      <!-- 候选列表 -->
      <div class="rls-picker-list">
        <div
          v-for="item in options"
          :key="item.req_id"
          class="rls-picker-option"
          :class="{ active: selected.includes(item.req_id) }"
          @click="toggle(item)"
        >
          <span class="rls-picker-check" aria-hidden="true"></span>
          <span class="rls-picker-code font-mono">{{ item.req_id }}</span>
          <span class="rls-picker-name">{{ item.req_name || '未命名需求' }}</span>
          <span v-if="item.system_name" class="rls-picker-sys">{{ item.system_name }}</span>
        </div>
        <el-empty v-if="!options.length && !loading" description="没有匹配的需求" :image-size="80" />
      </div>
    </div>

    <template #footer>
      <span class="rls-picker-hint">最多可选 {{ max }} 个</span>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="confirm">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, CircleClose } from '@element-plus/icons-vue'
import { getRequirements, getRequirement } from '@/api/requirement.js'

/**
 * 关联需求文号多选选择器（一对多）。
 *
 * 交互范式沿用 components/Common/StaffSelect.vue：只读 trigger（标签 + 折叠）
 * + el-dialog（搜索 / 已选区 / 候选列表）。
 *
 * 数据来源：需求宇宙（GET /requirements 列表接口），与建单时的远端搜索同源。
 */
const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  /** 父组件已掌握的文号→名称映射（来自列表接口的 req_links，避免逐条回查） */
  linkNames: { type: Object, default: () => ({}) },
  placeholder: { type: String, default: '点击选择关联需求' },
  disabled: { type: Boolean, default: false },
  max: { type: Number, default: 50 },
  maxVisible: { type: Number, default: 3 },
})
const emit = defineEmits(['update:modelValue'])

const selected = ref([])
const nameMap = ref({})
const visible = ref(false)
const query = ref('')
const options = ref([])
const loading = ref(false)

// 父组件传入的映射直接合并，避免逐条回查需求详情
watch(
  () => props.linkNames,
  (m) => {
    if (m && typeof m === 'object') Object.assign(nameMap.value, m)
  },
  { immediate: true, deep: true },
)

watch(
  () => props.modelValue,
  (v) => {
    selected.value = Array.isArray(v) ? [...v] : []
  },
  { immediate: true },
)

const labelOf = (rid) => {
  const nm = nameMap.value[rid]
  return nm ? `${nm}（${rid}）` : rid
}
const selectedOptions = computed(() => selected.value.map((rid) => ({ value: rid, label: labelOf(rid) })))
const displayed = computed(() => selectedOptions.value.slice(0, props.maxVisible))
const collapsedCount = computed(() => Math.max(0, selected.value.length - props.maxVisible))

/** 补回缺失的名称（仅在打开弹窗时按需回查，通常由 linkNames 覆盖） */
async function ensureNames() {
  const missing = selected.value.filter((rid) => !nameMap.value[rid])
  if (!missing.length) return
  await Promise.all(
    missing.slice(0, 10).map(async (rid) => {
      try {
        const res = await getRequirement(rid)
        if (res && res.req_name) nameMap.value[rid] = res.req_name
      } catch (e) {
        /* 忽略：仅影响展示，不影响关联本身 */
      }
    }),
  )
}

async function doSearch() {
  loading.value = true
  try {
    const res = await getRequirements({ keyword: query.value || undefined, page: 1, page_size: 50 })
    options.value = res?.items || []
    // 顺带补全名称缓存
    for (const it of options.value) {
      if (it.req_id && it.req_name) nameMap.value[it.req_id] = it.req_name
    }
  } catch (e) {
    options.value = []
  } finally {
    loading.value = false
  }
}

function openDialog() {
  if (props.disabled) return
  visible.value = true
  ensureNames()
  if (!options.value.length) doSearch()
}

function toggle(item) {
  const rid = item.req_id
  if (!rid) return
  if (selected.value.includes(rid)) {
    selected.value = selected.value.filter((x) => x !== rid)
    return
  }
  if (selected.value.length >= props.max) {
    ElMessage.warning(`最多关联 ${props.max} 个需求文号`)
    return
  }
  if (item.req_name) nameMap.value[rid] = item.req_name
  selected.value = [...selected.value, rid]
}

function remove(rid) {
  selected.value = selected.value.filter((x) => x !== rid)
  syncIfTrigger()
}
function clearAll() {
  selected.value = []
  syncIfTrigger()
}
/** 触发器上的删除/清空需即时同步 modelValue；弹窗内保持事务性（点「确定」才生效） */
function syncIfTrigger() {
  if (!visible.value) emit('update:modelValue', [...selected.value])
}
function confirm() {
  emit('update:modelValue', [...selected.value])
  visible.value = false
}
</script>

<style scoped>
.rls {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  padding: 3px 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  cursor: pointer;
  transition: border-color var(--transition-fast);
}
.rls:hover {
  border-color: var(--accent);
}
.rls.is-disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
.rls-trigger {
  display: flex;
  flex: 1;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px;
  min-width: 0;
}
.rls-placeholder {
  color: var(--text-muted);
  font-size: 13px;
}
.rls-more {
  color: var(--text-secondary);
  font-size: 12px;
}
.rls-clear {
  color: var(--text-muted);
  cursor: pointer;
}
.rls-clear:hover {
  color: var(--danger);
}

.rls-picker-header {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.rls-picker-search {
  flex: 1;
}
.rls-picker-selected {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 10px;
  margin-bottom: 10px;
  border: 1px dashed var(--border-subtle);
  border-radius: var(--radius-sm);
  background: var(--bg-app);
}
.rls-picker-label {
  flex-shrink: 0;
  color: var(--text-secondary);
  font-size: 12.5px;
  line-height: 24px;
}
.rls-picker-tags {
  display: flex;
  flex: 1;
  flex-wrap: wrap;
  gap: 5px;
}
.rls-picker-none {
  color: var(--text-muted);
  font-size: 12.5px;
  line-height: 24px;
}
.rls-picker-list {
  max-height: 380px;
  overflow-y: auto;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
}
.rls-picker-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  border-bottom: 1px solid var(--border-subtle);
  font-size: 13px;
}
.rls-picker-option:last-child {
  border-bottom: none;
}
.rls-picker-option:hover {
  background: var(--bg-app);
}
.rls-picker-option.active {
  background: color-mix(in srgb, var(--accent) 10%, transparent);
}
.rls-picker-check {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  border: 1px solid var(--border);
  border-radius: 3px;
}
.rls-picker-option.active .rls-picker-check {
  background: var(--accent);
  border-color: var(--accent);
}
.rls-picker-code {
  flex-shrink: 0;
  color: var(--text-secondary);
  font-size: 12.5px;
}
.rls-picker-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary);
}
.rls-picker-sys {
  flex-shrink: 0;
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--bg-app);
  color: var(--text-muted);
  font-size: 12px;
}
.rls-picker-hint {
  float: left;
  color: var(--text-muted);
  font-size: 12px;
  line-height: 32px;
}
</style>
