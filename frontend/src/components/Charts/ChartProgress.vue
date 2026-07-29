<template>
  <div class="chart-progress" :style="{ height }">
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
  height: { type: String, default: '200px' },
})

const chartOption = computed(() => ({
  color: PMWB_COLORS,
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    formatter: (params) => `${params[0].name}<br/>${params[0].value}/${params[0].data.total || 100}`,
  },
  grid: { left: 100, right: 40, top: 10, bottom: 10 },
  xAxis: {
    type: 'value',
    max: 100,
    splitLine: { show: false },
    axisLabel: { show: false },
    axisTick: { show: false },
  },
  yAxis: {
    type: 'category',
    data: props.data.map(d => d.name),
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: '#606266', fontSize: 12 },
  },
  series: [
    {
      type: 'bar',
      data: props.data.map(d => {
        const pct = d.total ? Math.round((d.value / d.total) * 100) : d.value
        return {
          value: pct,
          total: d.total,
          itemStyle: {
            borderRadius: [0, 6, 6, 0],
            color: pct >= 80 ? '#0f9d6b' : pct >= 40 ? '#2f6fed' : '#e02424',
          },
        }
      }),
      barMaxWidth: 16,
      label: {
        show: true,
        position: 'right',
        formatter: (p) => `${p.data.value}%`,
        color: '#606266',
        fontSize: 12,
      },
    },
  ],
}))
</script>
