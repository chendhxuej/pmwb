<template>
  <span
    class="pm-status-badge"
    :class="[`tone-${tone}`, sizeClass, { 'is-sensitive': sensitive }]"
    :style="badgeStyle"
  >
    <span class="pm-status-dot"></span>
    <span class="pm-status-text">{{ label }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { getStatusMeta, getToneVars } from '@/constants/statusConfig.js'

const props = defineProps({
  // 模式 A（推荐）：中心化 —— 传 module + value，统一语义色
  module: { type: String, default: '' },
  value: { type: [String, Number], default: '' },
  // 模式 B：兼容旧用法 —— 传 options({value:{label,type}}) + value
  options: { type: Object, default: null },
  // 模式 C：兼容旧用法 —— 直接传 label + el-tag type
  label: { type: String, default: '' },
  type: { type: String, default: '' },
  // 敏感字段（逾期 / 超期 / 风险）脉冲高亮
  sensitive: { type: Boolean, default: false },
  size: { type: String, default: 'default' }, // default | small
})

// 旧 el-tag 的 type 值 -> 统一语义色调（兜底兼容，不推荐新代码使用）
const LEGACY_TYPE_TONE = {
  danger: 'danger',
  warning: 'warning',
  primary: 'primary',
  success: 'success',
  info: 'info',
  '': 'info',
}

const resolved = computed(() => {
  if (props.module) {
    return getStatusMeta(props.module, props.value == null ? '' : String(props.value))
  }
  if (props.options && props.value != null && props.options[props.value]) {
    const o = props.options[props.value]
    return {
      label: o.label != null ? o.label : String(props.value),
      tone: LEGACY_TYPE_TONE[o.type] || 'info',
      sensitive: false,
    }
  }
  if (props.label) {
    return { label: props.label, tone: LEGACY_TYPE_TONE[props.type] || 'info', sensitive: false }
  }
  return { label: props.value == null ? '-' : String(props.value), tone: 'info', sensitive: false }
})

const tone = computed(() => resolved.value.tone)
const label = computed(() => resolved.value.label)
const sensitive = computed(() => props.sensitive || resolved.value.sensitive)
const sizeClass = computed(() => (props.size === 'small' ? 'size-small' : ''))
const toneVars = computed(() => getToneVars(tone.value))
const badgeStyle = computed(() => ({
  color: toneVars.value.color,
  background: toneVars.value.bg,
  borderColor: toneVars.value.border,
  '--pulse-bg': toneVars.value.bg,
}))
</script>

<style scoped>
.pm-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border-radius: 12px;
  border: 1px solid transparent;
  font-size: 12px;
  line-height: 18px;
  font-weight: 600;
  white-space: nowrap;
  transition: box-shadow 0.2s ease, transform 0.15s ease, background 0.2s ease;
}
.pm-status-badge.size-small {
  padding: 1px 8px;
  font-size: 11px;
  gap: 4px;
}
.pm-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  flex: 0 0 auto;
}
/* 敏感字段（逾期 / 超期 / 风险）：脉冲高亮，明显区别于普通状态 */
.pm-status-badge.is-sensitive {
  animation: pm-status-pulse 1.5s ease-in-out infinite;
}
@keyframes pm-status-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 transparent;
    transform: translateZ(0);
  }
  50% {
    box-shadow: 0 0 0 4px var(--pulse-bg, #fef0f0);
  }
}
</style>
