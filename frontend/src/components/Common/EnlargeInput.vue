<template>
  <div class="enlarge-input-wrap" :class="{ 'is-textarea': isTextarea }">
    <ElInput
      v-bind="passAttrs"
      :model-value="model"
      @update:model-value="(v) => (model = v)"
    >
      <template v-for="(_, name) in $slots" :key="name" #[name]="slotData">
        <slot :name="name" v-bind="slotData" />
      </template>
    </ElInput>
    <button class="enlarge-trigger" type="button" title="放大编辑" @click="onEnlarge">
      <FullScreen />
    </button>
  </div>
</template>

<script setup>
import { useAttrs, computed } from 'vue'
import { ElInput } from 'element-plus'
import { FullScreen } from '@element-plus/icons-vue'
import { useEnlargeInput } from '@/composables/useEnlargeInput'

// 双向绑定：直接复用父级的 v-model（不递归，内部渲染的是 import 来的原始 ElInput）
const model = defineModel()

const attrs = useAttrs()
const isTextarea = computed(() => attrs.type === 'textarea')

// 透传给原始 ElInput 的属性；移除 update:modelValue 避免与下方手动绑定重复触发
const passAttrs = computed(() => {
  const { 'onUpdate:modelValue': _omit, ...rest } = attrs
  return rest
})

function onEnlarge() {
  useEnlargeInput().open({
    value: model.value,
    type: attrs.type,
    rows: attrs.rows,
    onSave: (v) => {
      model.value = v
    },
  })
}
</script>

<style scoped>
.enlarge-input-wrap {
  position: relative;
  width: 100%;
}
.enlarge-trigger {
  position: absolute;
  top: 50%;
  right: 6px;
  transform: translateY(-50%);
  z-index: 2;
  display: none;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: var(--accent-soft);
  color: var(--accent);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}
.enlarge-input-wrap:hover .enlarge-trigger {
  display: inline-flex;
}
.enlarge-trigger:hover {
  background: var(--accent);
  color: #fff;
}
/* 多行文本：按钮置于右上角，避免垂直居中遮挡 */
.enlarge-input-wrap.is-textarea .enlarge-trigger {
  top: 6px;
  transform: none;
}
</style>
