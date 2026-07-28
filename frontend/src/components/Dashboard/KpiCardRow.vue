<template>
  <div class="kpi-card-row" :class="[colsClass, { 'has-title': !!title }]">
    <div class="kpi-row-header" v-if="title">
      <span class="kpi-row-title">{{ title }}</span>
      <a class="kpi-row-action" v-if="action" @click="$emit('action')">{{ action }}</a>
    </div>
    <div class="kpi-row-grid">
      <slot />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: { type: String, default: '' },
  action: { type: String, default: '' },
  columns: { type: [Number, String], default: 4 }, // 大屏列数 1-8
})

defineEmits(['action'])

const colsClass = computed(() => `kpi-cols-${Math.min(Math.max(Number(props.columns) || 4, 1), 8)}`)
</script>

<style scoped>
.kpi-card-row {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.kpi-card-row.has-title {
  background: var(--surface);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  padding: 18px 18px 16px;
}

.kpi-row-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.kpi-row-title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-primary);
}

.kpi-row-action {
  font-size: 12px;
  color: var(--accent);
  cursor: pointer;
  font-weight: 500;
  transition: opacity var(--transition-fast);
}
.kpi-row-action:hover {
  opacity: 0.75;
  text-decoration: underline;
}

.kpi-row-grid {
  display: grid;
  gap: 12px;
}

/* 响应式列数：大屏按指定列数，中屏减半，小屏2列 */
.kpi-cols-1 .kpi-row-grid { grid-template-columns: 1fr; }
.kpi-cols-2 .kpi-row-grid { grid-template-columns: repeat(2, 1fr); }
.kpi-cols-3 .kpi-row-grid { grid-template-columns: repeat(3, 1fr); }
.kpi-cols-4 .kpi-row-grid { grid-template-columns: repeat(4, 1fr); }
.kpi-cols-5 .kpi-row-grid { grid-template-columns: repeat(5, 1fr); }
.kpi-cols-6 .kpi-row-grid { grid-template-columns: repeat(6, 1fr); }
.kpi-cols-7 .kpi-row-grid { grid-template-columns: repeat(7, 1fr); }
.kpi-cols-8 .kpi-row-grid { grid-template-columns: repeat(8, 1fr); }

@media (max-width: 1024px) {
  .kpi-cols-5 .kpi-row-grid { grid-template-columns: repeat(3, 1fr); }
  .kpi-cols-6 .kpi-row-grid { grid-template-columns: repeat(3, 1fr); }
  .kpi-cols-7 .kpi-row-grid { grid-template-columns: repeat(4, 1fr); }
  .kpi-cols-8 .kpi-row-grid { grid-template-columns: repeat(4, 1fr); }
}

@media (max-width: 640px) {
  .kpi-row-grid { grid-template-columns: repeat(2, 1fr) !important; }
}
</style>
