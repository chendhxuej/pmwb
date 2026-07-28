<template>
  <div class="kpi-card" :class="[colorClass, { 'has-unit': !!unit }]">
    <!-- 装饰光晕 -->
    <div class="kpi-glow" v-if="colorClass"></div>

    <!-- 图标 -->
    <div class="kpi-icon" v-if="icon" v-html="icon"></div>

    <!-- 顶部标签 -->
    <div class="kpi-label">{{ title }}</div>

    <!-- 中间大数字 + 单位 -->
    <div class="kpi-value-row">
      <span class="kpi-value" :style="{ fontSize: calcFontSize }">
        {{ displayValue }}
      </span>
      <span class="kpi-unit" v-if="unit">{{ unit }}</span>
    </div>

    <!-- 底部趋势 -->
    <div class="kpi-trend" v-if="trend !== undefined && trend !== null" :class="trendTypeClass">
      <span class="kpi-trend-arrow" v-html="trendArrow"></span>
      <span class="kpi-trend-text">{{ trendText }}</span>
    </div>

    <!-- 可选微型进度条 -->
    <div class="kpi-progress" v-if="progress !== undefined">
      <div class="kpi-progress-track">
        <div class="kpi-progress-fill" :style="{ width: progressPct + '%' }" :class="colorClass"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: { type: String, default: '' },
  value: { type: [Number, String], default: 0 },
  unit: { type: String, default: '' },
  trend: { type: [Number, String], default: null },
  trendType: { type: String, default: 'neutral' },  // up | down | neutral
  trendLabel: { type: String, default: '' },
  icon: { type: String, default: '' },
  color: { type: String, default: 'blue' },           // blue | green | amber | red | purple | teal
  progress: { type: Number, default: undefined },
})

const colorClass = computed(() => `kpi-${props.color}`)

const displayValue = computed(() => {
  const v = props.value
  if (typeof v === 'number') {
    if (v >= 10000) return (v / 10000).toFixed(1).replace(/\.0$/, '') + '万'
    return v.toLocaleString()
  }
  return v
})

const calcFontSize = computed(() => {
  const raw = String(props.value)
  const len = raw.length
  if (len <= 3) return '34px'
  if (len <= 5) return '28px'
  if (len <= 7) return '24px'
  return '20px'
})

const trendTypeClass = computed(() => `kpi-trend--${props.trendType}`)

const trendArrow = computed(() => {
  const t = Number(props.trend)
  if (t > 0) return '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M7 14l5-5 5 5z"/></svg>'
  if (t < 0) return '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M7 10l5 5 5-5z"/></svg>'
  return '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M5 12h14"/></svg>'
})

const trendText = computed(() => {
  const t = Number(props.trend)
  const prefix = t > 0 ? '+' : ''
  const pct = Math.abs(t).toFixed(1)
  return props.trendLabel || `${prefix}${pct}%`
})
</script>

<style scoped>
.kpi-card {
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 20px 20px 18px;
  border-radius: var(--radius-sm);
  background: var(--surface);
  border: 1px solid var(--border);
  transition: all 0.25s ease;
  min-height: 120px;
}
.kpi-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 28px -8px rgba(0, 0, 0, 0.12);
  border-color: var(--border-hover);
}

/* 光晕装饰 */
.kpi-glow {
  position: absolute;
  top: -40%;
  right: -30%;
  width: 160px;
  height: 160px;
  border-radius: 50%;
  opacity: 0.08;
  pointer-events: none;
}
.kpi-blue .kpi-glow { background: radial-gradient(circle, #2f6fed 0%, transparent 70%); }
.kpi-green .kpi-glow { background: radial-gradient(circle, #22c55e 0%, transparent 70%); }
.kpi-amber .kpi-glow { background: radial-gradient(circle, #d98a1f 0%, transparent 70%); }
.kpi-red .kpi-glow { background: radial-gradient(circle, #dc2626 0%, transparent 70%); }
.kpi-purple .kpi-glow { background: radial-gradient(circle, #7c3aed 0%, transparent 70%); }
.kpi-teal .kpi-glow { background: radial-gradient(circle, #0d9488 0%, transparent 70%); }

/* 图标 */
.kpi-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  margin-bottom: 4px;
}
.kpi-blue .kpi-icon { background: var(--accent-soft); color: var(--accent); }
.kpi-green .kpi-icon { background: var(--success-soft); color: var(--success); }
.kpi-amber .kpi-icon { background: var(--warning-soft); color: var(--warning); }
.kpi-red .kpi-icon { background: var(--danger-soft); color: var(--danger); }
.kpi-purple .kpi-icon { background: #f0e6ff; color: #7c3aed; }
.kpi-teal .kpi-icon { background: #e6fffa; color: #0d9488; }

.kpi-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  letter-spacing: 0.02em;
}

.kpi-value-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-top: auto;
}

.kpi-value {
  font-weight: 800;
  font-family: var(--font-mono);
  line-height: 1.15;
  letter-spacing: -1px;
  transition: font-size 0.2s;
}
.kpi-blue .kpi-value { color: var(--accent); }
.kpi-green .kpi-value { color: var(--success); }
.kpi-amber .kpi-value { color: var(--warning); }
.kpi-red .kpi-value { color: var(--danger); }
.kpi-purple .kpi-value { color: #7c3aed; }
.kpi-teal .kpi-value { color: #0d9488; }

.kpi-unit {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.kpi-trend {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 12px;
  font-weight: 600;
  margin-top: 2px;
  padding: 2px 8px;
  border-radius: 6px;
  align-self: flex-start;
}

.kpi-trend--up {
  color: var(--success);
  background: var(--success-soft);
}
.kpi-trend--down {
  color: var(--danger);
  background: var(--danger-soft);
}
.kpi-trend--neutral {
  color: var(--text-muted);
  background: var(--bg-app);
}

.kpi-trend-arrow {
  display: inline-flex;
  align-items: center;
}

.kpi-trend-text {
  font-variant-numeric: tabular-nums;
}

/* 微型进度条 */
.kpi-progress {
  margin-top: 8px;
}
.kpi-progress-track {
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  overflow: hidden;
}
.kpi-progress-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.4s ease;
}
.kpi-blue .kpi-progress-fill { background: var(--accent); }
.kpi-green .kpi-progress-fill { background: var(--success); }
.kpi-amber .kpi-progress-fill { background: var(--warning); }
.kpi-red .kpi-progress-fill { background: var(--danger); }
.kpi-purple .kpi-progress-fill { background: #7c3aed; }
.kpi-teal .kpi-progress-fill { background: #0d9488; }
</style>
