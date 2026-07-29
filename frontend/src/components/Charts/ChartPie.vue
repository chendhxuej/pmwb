<template>
  <div class="chart-pie" :style="{ height }">
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
  donut: { type: Boolean, default: true },
  height: { type: String, default: '300px' },
  centerText: { type: String, default: '' },
  centerSubText: { type: String, default: '' },
})

const chartOption = computed(() => ({
  color: PMWB_COLORS,
  tooltip: {
    trigger: 'item',
    formatter: '{b}: {c} ({d}%)',
    backgroundColor: 'rgba(255,255,255,0.9)',
    borderColor: '#e4e7ed',
  },
  legend: {
    orient: 'vertical',
    right: 10,
    top: 'center',
    textStyle: { color: '#606266', fontSize: 12 },
  },
  series: [
    {
      type: 'pie',
      radius: props.donut ? ['45%', '70%'] : '70%',
      center: ['40%', '50%'],
      data: props.data,
      label: { show: false },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold' },
        itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.15)' },
      },
      itemStyle: {
        borderRadius: 4,
        borderColor: '#fff',
        borderWidth: 2,
      },
    },
  ],
  graphic: props.centerText
    ? [
        {
          type: 'text',
          left: '27%',
          top: '45%',
          style: {
            text: props.centerText,
            textAlign: 'center',
            fill: '#303133',
            fontSize: 22,
            fontWeight: 700,
          },
        },
        ...(props.centerSubText
          ? [
              {
                type: 'text',
                left: '27%',
                top: '55%',
                style: {
                  text: props.centerSubText,
                  textAlign: 'center',
                  fill: '#909399',
                  fontSize: 12,
                },
              },
            ]
          : []),
      ]
    : undefined,
}))
</script>
