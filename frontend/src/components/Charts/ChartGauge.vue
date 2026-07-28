<template>
  <div class="chart-gauge" ref="chartRef" :style="{ height }">
    <v-chart :option="chartOption" autoresize />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import './chart-setup'

const props = defineProps({
  value: { type: Number, default: 0 },
  min: { type: Number, default: 0 },
  max: { type: Number, default: 100 },
  unit: { type: String, default: '%' },
  height: { type: String, default: '300px' },
})

const chartOption = computed(() => {
  const percentage = ((props.value - props.min) / (props.max - props.min)) * 100
  const thumbColor = percentage >= 80 ? '#0f9d6b' : percentage >= 40 ? '#2f6fed' : '#e02424'

  return {
    series: [
      {
        type: 'gauge',
        center: ['50%', '55%'],
        radius: '80%',
        startAngle: 220,
        endAngle: -40,
        min: props.min,
        max: props.max,
        splitNumber: 5,
        progress: {
          show: true,
          width: 12,
          itemStyle: { color: thumbColor },
        },
        axisLine: {
          lineStyle: {
            width: 12,
            color: [[1, '#f0f2f5']],
          },
        },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        detail: {
          valueAnimation: true,
          formatter: `{value}${props.unit}`,
          fontSize: 28,
          fontWeight: 700,
          color: '#303133',
          offsetCenter: [0, '40%'],
        },
        data: [{ value: props.value, name: '' }],
      },
    ],
  }
})
</script>
