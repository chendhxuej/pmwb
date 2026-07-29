<template>
  <div class="chart-line" :style="{ height }">
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
  smooth: { type: Boolean, default: true },
  area: { type: Boolean, default: true },
  height: { type: String, default: '300px' },
})

const chartOption = computed(() => {
  const hasMultiSeries = props.series.length > 0

  return {
    color: PMWB_COLORS,
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255,255,255,0.9)',
      borderColor: '#e4e7ed',
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
          type: 'line',
          data: s.data,
          smooth: props.smooth,
          areaStyle: props.area ? { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: PMWB_COLORS[i] + '33' }, { offset: 1, color: PMWB_COLORS[i] + '05' }] } } : undefined,
          lineStyle: { width: 2, color: PMWB_COLORS[i] },
          symbol: 'circle',
          symbolSize: 6,
        }))
      : [{
          type: 'line',
          data: props.data.map(d => d.value),
          smooth: props.smooth,
          areaStyle: props.area ? { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#2f6fed33' }, { offset: 1, color: '#2f6fed05' }] } } : undefined,
          lineStyle: { width: 2, color: '#2f6fed' },
          symbol: 'circle',
          symbolSize: 6,
        }],
  }
})
</script>
