<template>
  <!-- 只读来源（派生数据，如需求催办）→ 仅展示徽标 -->
  <StatusBadge v-if="!writable" :module="domain" :value="current" />

  <!-- 可写来源 → 原生全量状态就地切换 -->
  <div v-else class="status-transition">
    <el-select
      v-model="pending"
      size="small"
      class="st-select"
      :loading="submitting"
      :disabled="submitting || !options.length"
      @change="onSelect"
    >
      <el-option
        v-for="o in options"
        :key="o.value"
        :label="o.label"
        :value="o.value"
        :disabled="o.disabled"
      >
        <span class="st-opt">
          <StatusBadge :module="domain" :value="o.value" size="small" />
          <!-- 注意：注册表下发的字段是 snake_case 的 is_terminal，写成 isTerminal 会永远为假 -->
          <span v-if="o.is_terminal" class="st-opt-tag">终态</span>
        </span>
      </el-option>
    </el-select>
    <el-tooltip v-if="lockedHint" :content="lockedHint" placement="top">
      <el-icon class="st-lock"><Lock /></el-icon>
    </el-tooltip>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Lock } from '@element-plus/icons-vue'
import StatusBadge from './StatusBadge.vue'
import { updateTaskStatus } from '@/api/taskCenter.js'
import { domainStatuses, isDomainWritable, resolveDomain, resolveStatusValue } from '@/constants/statusConfig.js'

const props = defineProps({
  source: { type: String, required: true },
  sourceId: { type: [String, Number], default: '' },
  // 当前**原生态**状态值（任务中心 row.raw_status）
  current: { type: String, default: '' },
})
const emit = defineEmits(['updated'])

const submitting = ref(false)

// 状态域（后端注册表 key）；任务中心按来源渲染各自的原生全量状态
const domain = computed(() => resolveDomain(props.source, String(props.sourceId || '')))
const statuses = computed(() => domainStatuses(domain.value))
const writable = computed(() => isDomainWritable(domain.value) && statuses.value.length > 0)

// 当前选中值始终用**规范值**（消化自由串历史脏值），否则 el-select 匹配不到选项会显示空白
const pending = ref('')
watch(
  () => [props.current, domain.value, statuses.value],
  () => {
    const v = resolveStatusValue(domain.value, props.current)
    pending.value = statuses.value.some((s) => s.value === v) ? v : props.current
  },
  { immediate: true }
)

const currentDef = computed(
  // 先做别名容错：自由串状态列（会议行动项）可能存的是中文历史值
  () => statuses.value.find((s) => s.value === resolveStatusValue(domain.value, props.current)) || null
)
// 可选目标：优先注册表声明的 allowed_next；未声明且非终态时放开为「其余全部状态」
const options = computed(() => {
  const cur = currentDef.value
  if (!cur) return statuses.value.map((s) => ({ ...s, disabled: false }))
  let targets = Array.isArray(cur.allowed_next) ? cur.allowed_next : []
  if (!targets.length && !cur.is_terminal) {
    targets = statuses.value.filter((s) => s.value !== cur.value).map((s) => s.value)
  }
  const list = [cur, ...targets.map((v) => statuses.value.find((s) => s.value === v)).filter(Boolean)]
  return list.map((s) => ({ ...s, disabled: false }))
})

const lockedHint = computed(() => {
  const cur = currentDef.value
  if (!cur || !cur.is_terminal) return ''
  const back = (cur.allowed_next || []).map(
    (v) => statuses.value.find((s) => s.value === v)?.label || v
  )
  return back.length
    ? `终态「${cur.label}」不可逆，仅可回退到：${back.join('、')}`
    : `终态「${cur.label}」不可变更`
})

// 回滚到「当前值」（走规范值，与 pending 初始化同口径）
function resetPending() {
  const v = resolveStatusValue(domain.value, props.current)
  pending.value = statuses.value.some((s) => s.value === v) ? v : props.current
}

async function onSelect(target) {
  if (target === props.current) return
  const def = statuses.value.find((s) => s.value === target)
  if (def?.is_terminal) {
    try {
      await ElMessageBox.confirm(
        `确认将状态变更为终态「${def.label}」？该操作通常不可逆（如需修改需先回退）。`,
        '确认变更状态',
        { type: 'warning', confirmButtonText: '确认变更', cancelButtonText: '取消' }
      )
    } catch (e) {
      resetPending() // 取消 → 回滚选择
      return
    }
  }
  submitting.value = true
  try {
    const item = await updateTaskStatus(props.source, String(props.sourceId), target)
    ElMessage.success(`状态已更新为「${def?.label || target}」`)
    emit('updated', item)
  } catch (e) {
    // request.js 拦截器已弹出后端真实错误文案
    console.warn('[StatusTransitionSelect] 改状态失败:', e && (e.message || e))
    resetPending() // 失败 → 回滚选择
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.status-transition {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.st-select {
  width: 122px;
}
.st-opt {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.st-opt-tag {
  font-size: 11px;
  color: var(--text-tertiary, #909399);
}
.st-lock {
  color: var(--text-tertiary, #909399);
  cursor: help;
}
</style>
