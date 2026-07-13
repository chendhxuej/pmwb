<template>
  <el-tag :type="type" size="small">
    {{ label }}
  </el-tag>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  value: { type: String, default: '' },
  options: { type: Object, default: () => ({}) },
})

const label = computed(() => props.options[props.value]?.label || props.value)
const type = computed(() => props.options[props.value]?.type || '')
</script>
