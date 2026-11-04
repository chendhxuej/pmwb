<template>
  <div class="chart-line" ref="chartRef" :style="{ height }">
    <v-chart :option="chartOption" autoresize @click="(p) => emit('itemClick', p)" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import './chart-setup'
import { PMWB_COLORS } from './chart-setup'

const emit = defineEmits(['itemClick'])

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
      ? props.series.map((s, i) => {
          // 系列级样式可覆盖：dash=虚线 / width=线宽 / area=是否铺面积 / color=指定色
          // 多线对比时基准线（上周、上月）应关面积、走虚线，避免面积层叠糊成一片。
          const color = s.color || PMWB_COLORS[i]
          const width = s.width || 2
          const withArea = s.area === undefined ? props.area : !!s.area
          return {
            name: s.name,
            type: 'line',
            data: s.data,
            smooth: props.smooth,
            areaStyle: withArea ? { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: color + '33' }, { offset: 1, color: color + '05' }] } } : undefined,
            lineStyle: { width, color, type: s.dash ? 'dashed' : 'solid' },
            symbol: 'circle',
            symbolSize: s.dash ? 4 : 6,
            z: s.dash ? 1 : 3,
          }
        })
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
