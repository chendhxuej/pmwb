<template>
  <el-select
    :model-value="modelValue"
    placeholder="选择业务领域"
    clearable
    filterable
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
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { basicDataApi } from '@/api/basicData.js'
import { bus, EVT_DOMAINS_CHANGED } from '@/utils/bus'

const props = defineProps({
  modelValue: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'change'])

const domainTree = ref([])

const loadDomains = async () => {
  try {
    domainTree.value = await basicDataApi.getBusinessDomains({ tree: true })
  } catch {
    // 静默失败，选择器显示为空
  }
}

const onSelect = (val) => {
  emit('update:modelValue', val)
  emit('change', val)
}

onMounted(loadDomains)
// 领域增删改后全局通知刷新（kc-5：跨模块联动）
bus.on(EVT_DOMAINS_CHANGED, loadDomains)
onBeforeUnmount(() => bus.off(EVT_DOMAINS_CHANGED, loadDomains))
</script>
