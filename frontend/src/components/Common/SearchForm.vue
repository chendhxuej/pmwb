<template>
  <el-form :model="form" inline class="search-form">
    <slot name="fields" :form="form" />
    <el-form-item>
      <el-button type="primary" @click="handleSearch">查询</el-button>
      <el-button @click="handleReset">重置</el-button>
    </el-form-item>
  </el-form>
</template>

<script setup>
import { reactive } from 'vue'

const props = defineProps({
  modelValue: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['update:modelValue', 'search', 'reset'])

const form = reactive({ ...props.modelValue })

const handleSearch = () => {
  emit('update:modelValue', { ...form })
  emit('search', { ...form })
}

const handleReset = () => {
  Object.keys(form).forEach((key) => {
    form[key] = undefined
  })
  emit('update:modelValue', { ...form })
  emit('reset', { ...form })
}
</script>
