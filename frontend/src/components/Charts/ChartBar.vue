<template>
  <div class="chart-bar" ref="chartRef" :style="{ height }">
    <v-chart :option="chartOption" autoresize />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import './chart-setup'
import { PMWB_COLORS } from './chart-setup'

const props = defineProps({
  data: { type: Array, default: () => [] },
  xData: { type: Array, default: () => [] },
  series: { type: Array, default: () => [] },
  stacked: { type: Boolean, default: false },
  height: { type: String, default: '300px' },
  // ↓ 2026-10-16 新增，默认值 = 改造前行为（不影响既有调用方）
  showLabel: { type: Boolean, default: false },
  unit: { type: String, default: '' },
})

const chartOption = computed(() => {
  const hasMultiSeries = props.series.length > 0

  return {
    color: PMWB_COLORS,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(255,255,255,0.9)',
      borderColor: '#e4e7ed',
      // unit 为空时保持 undefined（= 原行为）
      valueFormatter: props.unit ? (v) => `${v}${props.unit}` : undefined,
    },
    legend: hasMultiSeries ? { data: props.series.map(s => s.name), bottom: 0 } : undefined,
    grid: { left: 40, right: 20, top: 20, bottom: hasMultiSeries ? 40 : 30 },
    xAxis: {
      type: 'category',
      data: hasMultiSeries ? props.xData : props.data.map(d => d.name),
      axisLine: { lineStyle: { color: '#e4e7ed' } },
      axisLabel: { color: '#909399', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f0f2f5', type: 'dashed' } },
      axisLabel: { color: '#909399', fontSize: 11 },
    },
    series: hasMultiSeries
      ? props.series.map((s, i) => ({
          name: s.name,
          type: 'bar',
          data: s.data,
          stack: props.stacked ? 'total' : undefined,
          barMaxWidth: 32,
          itemStyle: { borderRadius: [3, 3, 0, 0] },
        }))
      : [{
          type: 'bar',
          data: props.data.map(d => d.value),
          barMaxWidth: 32,
          // showLabel 为 false 时 label = undefined（= 原行为）
          label: props.showLabel ? {
            show: true,
            position: 'top',
            color: '#64748b',
            fontSize: 11,
            formatter: (p) => (p.value === null || p.value === undefined ? '' : `${p.value}${props.unit}`),
          } : undefined,
          itemStyle: {
            borderRadius: [3, 3, 0, 0],
            color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#2f6fed' }, { offset: 1, color: '#6b9aff' }] },
          },
        }],
  }
})
</script>
