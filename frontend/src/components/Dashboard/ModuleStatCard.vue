<template>
  <div class="module-stat-card" :class="[colorThemeClass, sizeClass]">
    <div class="msc-header">
      <div class="msc-header-left">
        <div class="msc-icon" v-if="icon" v-html="icon"></div>
        <span class="msc-title">{{ title }}</span>
      </div>
      <a class="msc-action" v-if="action" @click="$emit('action')">{{ action }}</a>
    </div>
    <div class="msc-body" :style="bodyStyle">
      <slot />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: { type: String, default: '' },
  icon: { type: String, default: '' },
  action: { type: String, default: '' },
  color: { type: String, default: 'blue' },
  size: { type: String, default: 'normal' }, // normal | large | full
  scrollable: { type: Boolean, default: false },
})

defineEmits(['action'])

const colorThemeClass = computed(() => `msc-${props.color}`)

const sizeClass = computed(() => `msc-${props.size}`)

const bodyStyle = computed(() => {
  if (props.scrollable) return { overflow: 'auto', maxHeight: '280px' }
  return {}
})
</script>

<style scoped>
.module-stat-card {
  display: flex;
  flex-direction: column;
  border-radius: var(--radius-sm);
  background: var(--surface);
  border: 1px solid var(--border);
  overflow: hidden;
  transition: all 0.2s ease;
}
.module-stat-card:hover {
  box-shadow: 0 4px 16px -4px rgba(0, 0, 0, 0.06);
}

.msc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px 0;
}

.msc-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.msc-icon {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  font-size: 14px;
}
.msc-blue .msc-icon { background: var(--accent-soft); color: var(--accent); }
.msc-green .msc-icon { background: var(--success-soft); color: var(--success); }
.msc-amber .msc-icon { background: var(--warning-soft); color: var(--warning); }
.msc-red .msc-icon { background: var(--danger-soft); color: var(--danger); }
.msc-purple .msc-icon { background: #f0e6ff; color: #7c3aed; }
.msc-teal .msc-icon { background: #e6fffa; color: #0d9488; }

.msc-title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-primary);
}

.msc-action {
  font-size: 12px;
  color: var(--accent);
  cursor: pointer;
  font-weight: 500;
  opacity: 0;
  transition: opacity var(--transition-fast);
}
.module-stat-card:hover .msc-action {
  opacity: 1;
}
.msc-action:hover {
  text-decoration: underline;
}

.msc-body {
  flex: 1;
  padding: 10px 0 6px;
  min-height: 40px;
}

.msc-large .msc-body { min-height: 80px; }
.msc-full .msc-body { min-height: 120px; }
</style>
