<template>
  <el-select
    :model-value="modelValue"
    placeholder="选择业务领域"
    clearable
    filterable
    :loading="loading"
    :disabled="disabled"
    style="width: 100%"
    @update:model-value="onSelect"
  >
    <el-option-group
      v-for="group in domainTree"
      :key="group.domain_code"
      :label="`${group.domain_name}（${group.children?.length || 0}个子类）`"
    >
      <el-option
        v-for="child in group.children"
        :key="child.domain_code"
        :value="child.domain_code"
        :label="child.domain_name"
      />
    </el-option-group>
  </el-select>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { loadBusinessDomains, subscribeBusinessDomains } from '@/api/basicData.js'

const props = defineProps({
  modelValue: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'change'])

const domainTree = ref([])
const loading = ref(false)

const DOMAIN_PARAMS = { tree: true }
const DOMAIN_KEY = JSON.stringify(DOMAIN_PARAMS)

const loadDomains = async (force = false) => {
  loading.value = true
  try {
    domainTree.value = await loadBusinessDomains(DOMAIN_PARAMS, force)
  } catch {
    // 静默失败，选择器显示为空
  } finally {
    loading.value = false
  }
}

const onSelect = (val) => {
  emit('update:modelValue', val)
  emit('change', val)
}

let unsub = null
onMounted(() => {
  loadDomains()
  unsub = subscribeBusinessDomains((key, data) => {
    if (key === DOMAIN_KEY) {
      domainTree.value = data
    }
  })
})

onUnmounted(() => {
  if (unsub) unsub()
})
</script>
